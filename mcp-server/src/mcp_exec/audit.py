from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  exec_email TEXT NOT NULL,
  tool TEXT NOT NULL,
  sql TEXT,
  bytes_scanned INTEGER DEFAULT 0,
  row_count INTEGER DEFAULT 0,
  duration_ms INTEGER DEFAULT 0,
  result TEXT NOT NULL,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit (ts);
CREATE INDEX IF NOT EXISTS idx_audit_exec ON audit (exec_email);
"""


@dataclass
class AuditLog:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as c:
            c.executescript(SCHEMA)

    def record(
        self, *, exec_email: str, tool: str, sql: str | None,
        bytes_scanned: int, row_count: int, duration_ms: int,
        result: str, error: str | None,
    ) -> None:
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT INTO audit (ts, exec_email, tool, sql, bytes_scanned, row_count, duration_ms, result, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), exec_email, tool, sql, bytes_scanned, row_count, duration_ms, result, error),
            )

    def list_recent(self, limit: int = 100) -> list[dict[str, object]]:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory = sqlite3.Row
            cur = c.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def purge_older_than_days(self, days: int) -> int:
        cutoff = time.time() - days * 86400
        with sqlite3.connect(self.db_path) as c:
            cur = c.execute("DELETE FROM audit WHERE ts < ?", (cutoff,))
            return cur.rowcount
