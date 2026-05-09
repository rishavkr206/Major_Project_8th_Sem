// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/**
 * @title AuditAnchor
 * @notice On-chain commitment store for off-chain ICU audit chains.
 *
 * Phase 5 of the Blockchain-Enabled Digital Twin Framework.
 *
 * The off-chain ledger (`services/audit_bridge.py`) is a SHA-256 hash chain.
 * Periodically, the latest `chain_hash` of the off-chain ledger is committed
 * here as an "anchor". Anyone can later verify that an off-chain audit
 * trail is authentic by recomputing its terminal hash and proving it
 * matches a stored anchor.
 *
 * Design choices:
 *   - Anchors are append-only; existing anchors can never be mutated or
 *     deleted, even by the owner.
 *   - Only addresses on the writer allowlist may submit anchors. The owner
 *     can rotate writers (e.g. swap out a compromised gateway key) but
 *     cannot rewrite history.
 *   - We store: anchor index, off-chain block id range, payload root,
 *     submitter, and block timestamp. This is the minimum needed to bind
 *     an off-chain trail to wall-clock blockchain time.
 *
 * Gas posture: each anchor is one SSTORE-heavy struct + one event.
 * Designed to be batched (e.g. one anchor per N off-chain events).
 */
contract AuditAnchor {
    struct Anchor {
        uint256 indexInLedger;     // off-chain ledger highest block_id covered
        uint256 fromBlockId;       // off-chain ledger first block_id covered
        bytes32 chainHash;         // terminal SHA-256 of covered range
        bytes32 payloadRoot;       // optional Merkle root of payload hashes
        uint64  committedAt;       // block.timestamp at submission
        address submitter;         // the writer that posted this anchor
    }

    address public owner;
    mapping(address => bool) public writers;

    Anchor[] private _anchors;

    event WriterAdded(address indexed who);
    event WriterRemoved(address indexed who);
    event OwnershipTransferred(address indexed previous, address indexed next);
    event AnchorCommitted(
        uint256 indexed anchorId,
        uint256 indexed fromBlockId,
        uint256 indexed toBlockId,
        bytes32 chainHash,
        bytes32 payloadRoot,
        address submitter
    );

    modifier onlyOwner() {
        require(msg.sender == owner, "AuditAnchor: not owner");
        _;
    }

    modifier onlyWriter() {
        require(writers[msg.sender], "AuditAnchor: not writer");
        _;
    }

    constructor() {
        owner = msg.sender;
        writers[msg.sender] = true;
        emit OwnershipTransferred(address(0), msg.sender);
        emit WriterAdded(msg.sender);
    }

    // ─── Admin ──────────────────────────────────────────────────────────────
    function transferOwnership(address next) external onlyOwner {
        require(next != address(0), "AuditAnchor: zero owner");
        emit OwnershipTransferred(owner, next);
        owner = next;
    }

    function addWriter(address who) external onlyOwner {
        require(who != address(0), "AuditAnchor: zero writer");
        require(!writers[who], "AuditAnchor: already writer");
        writers[who] = true;
        emit WriterAdded(who);
    }

    function removeWriter(address who) external onlyOwner {
        require(writers[who], "AuditAnchor: not a writer");
        writers[who] = false;
        emit WriterRemoved(who);
    }

    // ─── Anchor commit ──────────────────────────────────────────────────────
    /**
     * @notice Commit an anchor for off-chain ledger range [fromBlockId, toBlockId].
     * @param fromBlockId  first off-chain block id covered (inclusive)
     * @param toBlockId    last off-chain block id covered (inclusive)
     * @param chainHash    terminal SHA-256 of the off-chain hash chain at toBlockId
     * @param payloadRoot  Merkle root over payload hashes in this range (or 0x0)
     * @return anchorId the new anchor's index
     */
    function commitAnchor(
        uint256 fromBlockId,
        uint256 toBlockId,
        bytes32 chainHash,
        bytes32 payloadRoot
    ) external onlyWriter returns (uint256 anchorId) {
        require(toBlockId >= fromBlockId, "AuditAnchor: bad range");
        require(chainHash != bytes32(0), "AuditAnchor: empty chainHash");
        if (_anchors.length > 0) {
            require(
                fromBlockId == _anchors[_anchors.length - 1].indexInLedger + 1,
                "AuditAnchor: non-contiguous fromBlockId"
            );
        }

        anchorId = _anchors.length;
        _anchors.push(Anchor({
            indexInLedger: toBlockId,
            fromBlockId:   fromBlockId,
            chainHash:     chainHash,
            payloadRoot:   payloadRoot,
            committedAt:   uint64(block.timestamp),
            submitter:     msg.sender
        }));

        emit AnchorCommitted(anchorId, fromBlockId, toBlockId, chainHash, payloadRoot, msg.sender);
    }

    // ─── Reads ──────────────────────────────────────────────────────────────
    function anchorCount() external view returns (uint256) {
        return _anchors.length;
    }

    function getAnchor(uint256 anchorId) external view returns (Anchor memory) {
        require(anchorId < _anchors.length, "AuditAnchor: out of range");
        return _anchors[anchorId];
    }

    function latestAnchor() external view returns (Anchor memory) {
        require(_anchors.length > 0, "AuditAnchor: no anchors");
        return _anchors[_anchors.length - 1];
    }

    /**
     * @notice Verify that a candidate `chainHash` matches the anchor stored
     *         for a particular off-chain block range.
     */
    function verify(uint256 anchorId, bytes32 chainHash) external view returns (bool) {
        if (anchorId >= _anchors.length) return false;
        return _anchors[anchorId].chainHash == chainHash;
    }
}
