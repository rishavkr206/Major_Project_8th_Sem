"""
Tests for the Phase 5 chain anchor service.

We do NOT exercise web3 / live posting here (no chain available in CI).
We test:
  - the merkle_root helper has the expected algebraic shape
  - build_pending_batch returns None on an empty ledger and a valid batch
    after we append off-chain events
  - dry-run anchor_now() advances the high-water mark and is idempotent
  - live mode raises a clear error when env vars are missing
"""

import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import services.chain_anchor as chain_anchor
from services.audit_bridge import AuditBridge


class MerkleRootTests(unittest.TestCase):

    def test_empty_returns_zero_root(self):
        r = chain_anchor.merkle_root([])
        self.assertEqual(r, "0x" + "0" * 64)

    def test_single_leaf_root_is_that_leaf(self):
        h = "ab" * 32
        r = chain_anchor.merkle_root([h])
        # Single-leaf root should equal the leaf itself (no hashing applied).
        self.assertEqual(r, "0x" + h)

    def test_two_leaves_root_changes_with_order(self):
        h1 = "11" * 32
        h2 = "22" * 32
        a = chain_anchor.merkle_root([h1, h2])
        b = chain_anchor.merkle_root([h2, h1])
        self.assertNotEqual(a, b)


class _IsolatedAnchorEnv(unittest.TestCase):
    """Base class that gives each test its own ledger + state file."""

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="audit_anchor_test_")
        self.ledger_path = os.path.join(self.tmp, "audit_ledger.db")
        self.state_path = os.path.join(self.tmp, "anchor_state.json")
        # Patch module-level constants so we don't touch the real repo files.
        self._state_patch = mock.patch.object(chain_anchor, "STATE_PATH", self.state_path)
        self._state_patch.start()
        # Patch AuditBridge so that anchor_now() uses our isolated ledger too.
        self._bridge_patch = mock.patch.object(
            chain_anchor, "AuditBridge", lambda: AuditBridge(ledger_path=self.ledger_path)
        )
        self._bridge_patch.start()
        self.bridge = AuditBridge(ledger_path=self.ledger_path)

    def tearDown(self) -> None:
        self._bridge_patch.stop()
        self._state_patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


class BuildPendingBatchTests(_IsolatedAnchorEnv):

    def test_empty_ledger_returns_none(self):
        self.assertIsNone(chain_anchor.build_pending_batch(self.bridge))

    def test_batch_after_appending(self):
        for i in range(5):
            self.bridge.log_event("RECOMMENDATION", str(900_000 + i),
                                  {"i": i, "PEEP": 8})
        batch = chain_anchor.build_pending_batch(self.bridge)
        self.assertIsNotNone(batch)
        self.assertEqual(batch.from_block_id, 1)
        self.assertEqual(batch.to_block_id, 5)
        self.assertEqual(batch.payload_count, 5)
        self.assertTrue(batch.chain_hash.startswith("0x"))
        self.assertTrue(batch.payload_root.startswith("0x"))


class AnchorNowDryRunTests(_IsolatedAnchorEnv):

    def test_dry_run_advances_high_water_mark(self):
        for i in range(3):
            self.bridge.log_event("TWIN_SIM", "777", {"step": i})
        out = chain_anchor.anchor_now(mode="dry_run")
        self.assertEqual(out["status"], "prepared")
        self.assertEqual(out["from_block_id"], 1)
        self.assertEqual(out["to_block_id"], 3)
        self.assertEqual(out["payload_count"], 3)

        # State file persisted with the new high-water mark.
        with open(self.state_path) as fh:
            st = json.load(fh)
        self.assertEqual(st["last_anchored_block_id"], 3)

        # A second call with no new events should be a no-op.
        out2 = chain_anchor.anchor_now(mode="dry_run")
        self.assertEqual(out2["status"], "noop")

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            chain_anchor.anchor_now(mode="bogus")


class LiveModeMissingConfigTests(_IsolatedAnchorEnv):

    def test_live_mode_raises_without_env(self):
        self.bridge.log_event("RECOMMENDATION", "1", {"x": 1})
        # Strip any anchor env that might be set in the host environment.
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ("AUDIT_ANCHOR_RPC_URL", "AUDIT_ANCHOR_PRIVATE_KEY", "AUDIT_ANCHOR_CONTRACT"):
                os.environ.pop(k, None)
            # Also force deployed.json to be absent.
            with mock.patch.object(chain_anchor, "DEPLOYED_PATH",
                                   os.path.join(self.tmp, "missing.json")):
                with self.assertRaises(RuntimeError):
                    chain_anchor.anchor_now(mode="live")


if __name__ == "__main__":
    unittest.main()
