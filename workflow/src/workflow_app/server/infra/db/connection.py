from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_db(root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(root / "state" / "workflow.db")
    conn.row_factory = sqlite3.Row
    return conn
