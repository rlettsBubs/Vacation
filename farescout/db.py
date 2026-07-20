"""SQLite helpers with the backup guard.

Standing rule: never run schema changes or destructive SQL against the live
DB unless a data/FareScout.backup-*.db file exists.
"""

import sqlite3
from pathlib import Path

from . import DB_PATH


class BackupMissing(RuntimeError):
    pass


def backup_files():
    return sorted(DB_PATH.parent.glob("FareScout.backup-*.db"))


def require_backup():
    if not backup_files():
        raise BackupMissing(
            "No data/FareScout.backup-*.db found. Copy the live DB first:\n"
            "  cp data/FareScout.db data/FareScout.backup-<date>.db"
        )


def connect(path=None):
    con = sqlite3.connect(path or DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def table_columns(con, table):
    return [r["name"] for r in con.execute(f"PRAGMA table_info({table})")]


def table_exists(con, table):
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None
