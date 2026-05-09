"""
Chain Anchor Service — Phase 5
Blockchain-Enabled Digital Twin Framework

Bridges the off-chain SQLite hash chain (`services/audit_bridge.py`) to the
on-chain `AuditAnchor` Solidity contract.

Two modes:

  1) `dry_run` (default): computes anchor batches, payload Merkle root, and
     terminal chain hash, but does NOT post to a blockchain. Useful when no
     web3 endpoint is configured (CI, classroom demo, local development).

  2) `live`: requires `web3` and a JSON-RPC endpoint plus contract address /
     signing key from env. Calls `commitAnchor` on the deployed contract.

Configuration (environment variables):
    AUDIT_ANCHOR_RPC_URL        # e.g. http://127.0.0.1:8545
    AUDIT_ANCHOR_CONTRACT       # 0x... deployed address
    AUDIT_ANCHOR_PRIVATE_KEY    # hex private key of an authorized writer
    AUDIT_ANCHOR_CHAIN_ID       # int, e.g. 31337 for hardhat local

State:
    The service tracks the highest already-anchored ledger block_id in
    `blockchain/anchor_state.json` so that subsequent runs continue from
    where the previous batch left off (anchors must be contiguous per the
    contract).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from services.audit_bridge import AuditBridge

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_PATH = os.path.join(REPO_ROOT, "blockchain", "anchor_state.json")
DEPLOYED_PATH = os.path.join(REPO_ROOT, "blockchain", "deployed.json")


# ─── Merkle root over payload hashes ─────────────────────────────────────────
def merkle_root(hashes: List[str]) -> str:
    """SHA-256 binary Merkle root over a list of hex digests. Pads odd levels."""
    if not hashes:
        return "0x" + "0" * 64
    layer = [bytes.fromhex(h) for h in hashes]
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        layer = [
            hashlib.sha256(layer[i] + layer[i + 1]).digest()
            for i in range(0, len(layer), 2)
        ]
    return "0x" + layer[0].hex()


# ─── State (high-water mark of anchored ledger) ──────────────────────────────
def _load_state() -> Dict:
    if os.path.isfile(STATE_PATH):
        with open(STATE_PATH, "r") as fh:
            return json.load(fh)
    return {"last_anchored_block_id": 0, "last_chain_hash": None, "anchors": []}


def _save_state(state: Dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as fh:
        json.dump(state, fh, indent=2)


# ─── Batching ────────────────────────────────────────────────────────────────
@dataclass
class AnchorBatch:
    from_block_id: int
    to_block_id: int
    chain_hash: str       # hex string with leading 0x
    payload_root: str     # hex string with leading 0x
    payload_count: int


def build_pending_batch(bridge: AuditBridge, max_blocks: int = 1024) -> Optional[AnchorBatch]:
    """
    Walk the off-chain ledger from the last anchored block_id+1 up to the tip
    (capped by max_blocks) and return one AnchorBatch describing the range.
    Returns None if nothing new to anchor.
    """
    state = _load_state()
    last_anchored = int(state.get("last_anchored_block_id", 0))

    with bridge._connect() as conn:  # noqa: SLF001 — same package
        rows = conn.execute(
            """
            SELECT block_id, chain_hash, payload_hash
            FROM audit_chain
            WHERE block_id > ?
            ORDER BY block_id ASC
            LIMIT ?
            """,
            (last_anchored, max_blocks),
        ).fetchall()

    if not rows:
        return None

    from_id = int(rows[0]["block_id"])
    to_id = int(rows[-1]["block_id"])
    terminal_hash = "0x" + rows[-1]["chain_hash"]
    proot = merkle_root([r["payload_hash"] for r in rows])
    return AnchorBatch(
        from_block_id=from_id,
        to_block_id=to_id,
        chain_hash=terminal_hash,
        payload_root=proot,
        payload_count=len(rows),
    )


# ─── Live posting (web3 optional) ────────────────────────────────────────────
def _load_deployment() -> Optional[Dict]:
    if os.path.isfile(DEPLOYED_PATH):
        with open(DEPLOYED_PATH, "r") as fh:
            return json.load(fh)
    return None


def post_anchor_onchain(batch: AnchorBatch) -> Dict:
    """
    Post the anchor to the AuditAnchor contract.

    Requires `web3` package and a configured JSON-RPC endpoint + key.
    Raises RuntimeError on misconfiguration.
    """
    try:
        from web3 import Web3
        from web3.middleware import geth_poa_middleware  # noqa: F401 (kept for future PoA chains)
    except ImportError as exc:
        raise RuntimeError(
            "web3 is required for live anchor posting. "
            "Install with: pip install 'web3>=6.15'"
        ) from exc

    rpc = os.environ.get("AUDIT_ANCHOR_RPC_URL")
    pk = os.environ.get("AUDIT_ANCHOR_PRIVATE_KEY")
    chain_id = int(os.environ.get("AUDIT_ANCHOR_CHAIN_ID", "31337"))
    contract_addr = os.environ.get("AUDIT_ANCHOR_CONTRACT")
    if not contract_addr:
        deployment = _load_deployment()
        if deployment:
            contract_addr = deployment["address"]
    if not (rpc and pk and contract_addr):
        raise RuntimeError(
            "Live mode needs AUDIT_ANCHOR_RPC_URL, AUDIT_ANCHOR_PRIVATE_KEY, "
            "and either AUDIT_ANCHOR_CONTRACT or blockchain/deployed.json"
        )

    abi = [
        {
            "inputs": [
                {"name": "fromBlockId", "type": "uint256"},
                {"name": "toBlockId", "type": "uint256"},
                {"name": "chainHash", "type": "bytes32"},
                {"name": "payloadRoot", "type": "bytes32"},
            ],
            "name": "commitAnchor",
            "outputs": [{"name": "anchorId", "type": "uint256"}],
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]
    w3 = Web3(Web3.HTTPProvider(rpc))
    acct = w3.eth.account.from_key(pk)
    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_addr), abi=abi)
    nonce = w3.eth.get_transaction_count(acct.address)
    tx = contract.functions.commitAnchor(
        batch.from_block_id,
        batch.to_block_id,
        bytes.fromhex(batch.chain_hash[2:]),
        bytes.fromhex(batch.payload_root[2:]),
    ).build_transaction({
        "from": acct.address,
        "nonce": nonce,
        "chainId": chain_id,
        "gas": 250_000,
        "gasPrice": w3.to_wei("2", "gwei"),
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    return {
        "tx_hash": tx_hash.hex(),
        "block_number": receipt.blockNumber,
        "status": int(receipt.status),
        "gas_used": int(receipt.gasUsed),
    }


# ─── Public driver ───────────────────────────────────────────────────────────
def anchor_now(mode: str = "dry_run", max_blocks: int = 1024) -> Dict:
    """
    Build the next pending batch and (in `live` mode) post it on-chain.

    Returns a dict suitable for logging back into the off-chain ledger as a
    `MODEL_INFER`-class audit event.
    """
    if mode not in ("dry_run", "live"):
        raise ValueError("mode must be 'dry_run' or 'live'")

    bridge = AuditBridge()
    batch = build_pending_batch(bridge, max_blocks=max_blocks)
    if batch is None:
        return {"status": "noop", "message": "no new ledger blocks to anchor"}

    result: Dict = {
        "status": "prepared" if mode == "dry_run" else "submitted",
        "mode": mode,
        "from_block_id": batch.from_block_id,
        "to_block_id": batch.to_block_id,
        "payload_count": batch.payload_count,
        "chain_hash": batch.chain_hash,
        "payload_root": batch.payload_root,
    }

    if mode == "live":
        receipt = post_anchor_onchain(batch)
        result["receipt"] = receipt

    # Update state + persistent log so we never re-anchor the same range.
    state = _load_state()
    state["last_anchored_block_id"] = batch.to_block_id
    state["last_chain_hash"] = batch.chain_hash
    state.setdefault("anchors", []).append({
        "from_block_id": batch.from_block_id,
        "to_block_id": batch.to_block_id,
        "chain_hash": batch.chain_hash,
        "payload_root": batch.payload_root,
        "mode": mode,
        "receipt": result.get("receipt"),
    })
    _save_state(state)
    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────
def _cli() -> None:
    import argparse
    p = argparse.ArgumentParser(description="Anchor off-chain audit ledger to on-chain contract")
    p.add_argument("--mode", choices=["dry_run", "live"], default="dry_run")
    p.add_argument("--max-blocks", type=int, default=1024)
    args = p.parse_args()
    out = anchor_now(mode=args.mode, max_blocks=args.max_blocks)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    _cli()
