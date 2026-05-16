"""
Blockchain Audit Bridge
Blockchain-Enabled Digital Twin Framework

Implements a tamper-evident, append-only hash chain ledger using SQLite.
Each record is cryptographically linked to its predecessor, simulating
a permissioned blockchain:

  Block_N = {block_id, prev_hash, timestamp, stay_id, event_type,
              actor, payload_hash, chain_hash}

  chain_hash = SHA256(prev_hash || payload_hash || timestamp)
"""

import sqlite3
import hashlib
import json
import time
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

LEDGER_PATH = os.path.join(os.path.dirname(__file__), '..', 'blockchain', 'audit_ledger.db')

GENESIS_HASH = '0' * 64  # Genesis block prev hash

EVENT_TYPES = {
    'RECOMMENDATION',   # System generated ventilator recommendation
    'ACCEPT',           # Clinician accepted recommendation
    'OVERRIDE',         # Clinician overrode recommendation
    'REJECT',           # Clinician rejected recommendation
    'ALERT',            # System hypoxia alert
    'TWIN_SIM',         # Digital twin simulation run
    'MODEL_INFER',      # LSTM inference executed
}


class AuditBridge:
    """
    Tamper-evident blockchain audit ledger.
    Thread-safe for concurrent FastAPI requests.
    """

    def __init__(self, ledger_path: str = LEDGER_PATH):
        self.ledger_path = ledger_path
        os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.ledger_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_chain (
                    block_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                    prev_hash    TEXT    NOT NULL,
                    chain_hash   TEXT    NOT NULL UNIQUE,
                    timestamp    TEXT    NOT NULL,
                    stay_id      TEXT,
                    event_type   TEXT    NOT NULL,
                    actor        TEXT    DEFAULT 'SYSTEM',
                    payload_json TEXT    NOT NULL,
                    payload_hash TEXT    NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stay ON audit_chain(stay_id);")
            conn.commit()

    # ─── Hashing ────────────────────────────────────────────────────────────
    @staticmethod
    def _sha256(data: str) -> str:
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def _get_last_hash(self, conn) -> str:
        row = conn.execute(
            "SELECT chain_hash FROM audit_chain ORDER BY block_id DESC LIMIT 1"
        ).fetchone()
        return row['chain_hash'] if row else GENESIS_HASH

    # ─── Append ─────────────────────────────────────────────────────────────
    def log_event(
        self,
        event_type: str,
        stay_id: Optional[str],
        payload: Dict,
        actor: str = 'SYSTEM',
    ) -> Dict:
        """
        Append an immutable audit event to the chain.
        Returns the created block record.
        """
        assert event_type in EVENT_TYPES, f"Unknown event type: {event_type}"

        ts           = datetime.now(timezone.utc).isoformat()
        payload_str  = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = self._sha256(payload_str)

        with self._connect() as conn:
            prev_hash  = self._get_last_hash(conn)
            chain_hash = self._sha256(prev_hash + payload_hash + ts)

            conn.execute("""
                INSERT INTO audit_chain
                    (prev_hash, chain_hash, timestamp, stay_id, event_type, actor, payload_json, payload_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (prev_hash, chain_hash, ts, str(stay_id) if stay_id else None,
                  event_type, actor, payload_str, payload_hash))
            conn.commit()

            block_id = conn.execute(
                "SELECT last_insert_rowid() as id"
            ).fetchone()['id']

        return {
            'block_id':    block_id,
            'chain_hash':  chain_hash,
            'prev_hash':   prev_hash,
            'timestamp':   ts,
            'stay_id':     stay_id,
            'event_type':  event_type,
            'actor':       actor,
            'payload_hash':payload_hash,
        }

    # ─── Query ───────────────────────────────────────────────────────────────
    def get_trail(self, stay_id: str, limit: int = 50) -> List[Dict]:
        """Return audit trail for a specific patient."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT block_id, chain_hash, prev_hash, timestamp,
                       stay_id, event_type, actor, payload_hash, payload_json
                FROM audit_chain
                WHERE stay_id = ?
                ORDER BY block_id DESC
                LIMIT ?
            """, (str(stay_id), limit)).fetchall()
        return [dict(r) for r in rows]

    def get_all(self, limit: int = 200) -> List[Dict]:
        """Return most recent events across all patients."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT block_id, chain_hash, prev_hash, timestamp,
                       stay_id, event_type, actor, payload_hash
                FROM audit_chain
                ORDER BY block_id DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ─── Chain Verification ──────────────────────────────────────────────────
    def verify_chain(self) -> Tuple[bool, str]:
        """
        Verify tamper-evident integrity of the entire chain.
        Returns (is_valid, message).
        """
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT block_id, prev_hash, chain_hash, timestamp, payload_hash
                FROM audit_chain ORDER BY block_id ASC
            """).fetchall()

        if not rows:
            return True, "Chain is empty — no blocks to verify."

        prev_hash = GENESIS_HASH
        for row in rows:
            expected = self._sha256(row['prev_hash'] + row['payload_hash'] + row['timestamp'])

            if row['prev_hash'] != prev_hash:
                return False, (
                    f"CHAIN BROKEN at block {row['block_id']}: "
                    f"prev_hash mismatch. Expected {prev_hash[:16]}... "
                    f"got {row['prev_hash'][:16]}..."
                )

            if row['chain_hash'] != expected:
                return False, (
                    f"CHAIN TAMPERED at block {row['block_id']}: "
                    f"hash mismatch."
                )

            prev_hash = row['chain_hash']

        return True, f"Chain VALID — {len(rows)} blocks verified."

    def stats(self) -> Dict:
        with self._connect() as conn:
            total  = conn.execute("SELECT COUNT(*) as c FROM audit_chain").fetchone()['c']
            by_evt = conn.execute(
                "SELECT event_type, COUNT(*) as c FROM audit_chain GROUP BY event_type"
            ).fetchall()
        return {
            'total_blocks': total,
            'by_event': {r['event_type']: r['c'] for r in by_evt},
        }


# ─── Standalone demo ──────────────────────────────────────────────────────────
if __name__ == '__main__':
    bridge = AuditBridge()

    # Log some sample events
    b1 = bridge.log_event('RECOMMENDATION', '30004018', {
        'PEEP': 10, 'FiO2': 65, 'TidalVol': 400,
        'confidence': 0.87, 'hypoxia_risk': 0.72,
    })
    print("Block 1:", b1)

    b2 = bridge.log_event('ACCEPT', '30004018', {
        'block_ref': b1['block_id'], 'clinician_id': 'DR_001',
    }, actor='CLINICIAN')
    print("Block 2:", b2)

    # Verify chain
    valid, msg = bridge.verify_chain()
    print(f"\nVerification: {msg}")
    print("Stats:", bridge.stats())
