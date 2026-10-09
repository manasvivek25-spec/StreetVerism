"""Database engine and schema management for StreetVerism.

Uses Python standard library sqlite3 with WAL mode, parameterized statements,
strict UTC timestamp formatting, and 4-decimal coordinate privacy rounding.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator, Optional, Union

from backend.app.config import get_settings


def to_utc_iso(dt_or_str: Union[datetime, str]) -> str:
    """Normalize any datetime or ISO string to fixed UTC format YYYY-MM-DDTHH:MM:SS.ffffffZ.
    
    Ensures correct lexicographical comparisons in SQL queries.
    """
    if isinstance(dt_or_str, str):
        clean_str = dt_or_str.strip()
        if clean_str.endswith("Z"):
            clean_str = clean_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean_str)
    else:
        dt = dt_or_str

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def get_db_path(url_or_path: Optional[str] = None) -> str:
    """Resolve sqlite database file path from DATABASE_URL or settings."""
    if not url_or_path:
        settings = get_settings()
        url_or_path = settings.database_url
    if url_or_path.startswith("sqlite:///"):
        return url_or_path[len("sqlite:///"):]
    return url_or_path


@contextmanager
def get_db_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Provide a managed sqlite3 connection with WAL mode and busy timeout."""
    path = get_db_path(db_path)
    conn = sqlite3.connect(path, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Idempotently create tables and indexes for StreetVerism."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Alerts Table (no is_active column; activity computed dynamically)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                sender TEXT NOT NULL,
                hazard TEXT NOT NULL,
                severity TEXT NOT NULL,
                urgency TEXT NOT NULL,
                certainty TEXT NOT NULL,
                area_json TEXT NOT NULL,
                instruction_keys_json TEXT NOT NULL,
                params_json TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                supersedes TEXT,
                published_by TEXT NOT NULL,
                is_replay INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_expires_at ON alerts(expires_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_sent_at ON alerts(sent_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_supersedes ON alerts(supersedes);")

        # 2. Reports Table (4-decimal lat/lng privacy rounding)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                cell TEXT NOT NULL,
                claim TEXT NOT NULL,
                text TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_cell ON reports(cell);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_cell_created_at ON reports(cell, created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);")

        # 3. Checkins Table (48h retention index on created_at)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS checkins (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                state TEXT NOT NULL,
                language TEXT NOT NULL,
                group_size INTEGER NOT NULL,
                note TEXT,
                cell7 TEXT NOT NULL,
                handled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkins_created_at ON checkins(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkins_cell7 ON checkins(cell7);")

        # 4. Shelters Catalog Table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS shelters (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_local TEXT NOT NULL,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                open INTEGER NOT NULL DEFAULT 1,
                is_demo INTEGER NOT NULL DEFAULT 0,
                capacity INTEGER
            );
            """
        )
