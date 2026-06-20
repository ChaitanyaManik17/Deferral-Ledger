"""
audit.py — SQLite-backed governance audit persistent store for Deferral Ledger.

Saves run snapshots (SRS FR-GOV-2) and logs explicit user consent events
for contested causal edges (SRS FR-GOV-3, RAI-1).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from models import AuditRecord

DB_FILE = Path(__file__).parent / "data" / "audit.db"


def init_db() -> None:
    """Initialise SQLite audit logs and database schema."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    # Audit records table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_records (
            run_id TEXT PRIMARY KEY,
            user TEXT,
            inputs_snapshot_ref TEXT,
            catalog_version TEXT,
            overrides TEXT,
            contested_edges_enabled TEXT,
            timestamp TEXT
        )
    """)
    
    # Contested edge consent events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user TEXT,
            action TEXT,
            edge_id TEXT,
            details TEXT
        )
    """)
    
    conn.commit()
    conn.close()


def save_audit_record(record: AuditRecord) -> None:
    """Persist an immutable AuditRecord to the SQLite store (FR-GOV-2)."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO audit_records 
        (run_id, user, inputs_snapshot_ref, catalog_version, overrides, contested_edges_enabled, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        record.run_id,
        record.user or "system_operator",
        record.inputs_snapshot_ref,
        record.catalog_version,
        json.dumps(record.overrides),
        json.dumps(record.contested_edges_enabled),
        record.timestamp
    ))
    conn.commit()
    conn.close()


def get_audit_record(run_id: str) -> AuditRecord | None:
    """Retrieve a stored AuditRecord by run ID (FR-GOV-2)."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT run_id, user, inputs_snapshot_ref, catalog_version, overrides, contested_edges_enabled, timestamp
        FROM audit_records WHERE run_id = ?
    """, (run_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row is None:
        return None
        
    return AuditRecord(
        run_id=row[0],
        user=row[1],
        inputs_snapshot_ref=row[2],
        catalog_version=row[3],
        overrides=json.loads(row[4]),
        contested_edges_enabled=json.loads(row[5]),
        timestamp=row[6]
    )


def log_consent_event(user: str, edge_id: str, action: str = "enable", details: str | None = None) -> None:
    """Log an explicit contested-edge consent event (SRS FR-GOV-3, RAI-1)."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    timestamp = datetime.now(UTC).isoformat().replace("+00:00", "") + "Z"
    cursor.execute("""
        INSERT INTO consent_logs (timestamp, user, action, edge_id, details)
        VALUES (?, ?, ?, ?, ?)
    """, (
        timestamp,
        user,
        action,
        edge_id,
        details or f"Contested edge {edge_id} was explicitly {action}d."
    ))
    conn.commit()
    conn.close()


def get_consent_logs() -> list[dict[str, Any]]:
    """Retrieve all logged consent events from the database (descending)."""
    init_db()
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, user, action, edge_id, details FROM consent_logs ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "timestamp": r[0],
            "user": r[1],
            "action": r[2],
            "edge_id": r[3],
            "details": r[4]
        }
        for r in rows
    ]
