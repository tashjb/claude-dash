import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "./data/metrics.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS metric_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            metric_key TEXT NOT NULL,
            metric_value REAL,
            metric_label TEXT,
            source TEXT,
            snapshot_date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connector TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            records_synced INTEGER DEFAULT 0,
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT,
            title TEXT,
            severity TEXT,
            status TEXT,
            detected_at TEXT,
            resolved_at TEXT,
            mttd_hours REAL,
            mttr_hours REAL,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS vulnerabilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vuln_id TEXT,
            asset TEXT,
            severity TEXT,
            status TEXT,
            discovered_at TEXT,
            patched_at TEXT,
            days_open INTEGER,
            source TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_domain ON metric_snapshots(domain);
        CREATE INDEX IF NOT EXISTS idx_snapshots_date ON metric_snapshots(snapshot_date);
        CREATE INDEX IF NOT EXISTS idx_snapshots_key ON metric_snapshots(metric_key);
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")
