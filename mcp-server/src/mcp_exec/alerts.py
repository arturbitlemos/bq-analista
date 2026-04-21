from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from mcp_exec.audit import AuditLog
from mcp_exec.settings import load_settings

HUGE_QUERY_THRESHOLD_BYTES = 10 * 1024**3
HIGH_CALL_RATE_PER_HOUR = 50
HIGH_ERROR_RATE_THRESHOLD = 0.05


def detect_anomalies(log: AuditLog, now: float | None = None) -> list[dict[str, object]]:
    now = now or time.time()
    since = now - 3600
    alerts: list[dict[str, object]] = []

    with sqlite3.connect(log.db_path) as c:
        c.row_factory = sqlite3.Row
        # huge queries
        for r in c.execute(
            "SELECT exec_email, bytes_scanned, sql FROM audit WHERE ts >= ? AND bytes_scanned > ?",
            (since, HUGE_QUERY_THRESHOLD_BYTES),
        ):
            alerts.append({
                "kind": "huge_query",
                "exec_email": r["exec_email"],
                "bytes_scanned": r["bytes_scanned"],
                "sql": r["sql"],
            })
        # high call rate per exec
        for r in c.execute(
            "SELECT exec_email, COUNT(*) as n FROM audit WHERE ts >= ? GROUP BY exec_email HAVING n > ?",
            (since, HIGH_CALL_RATE_PER_HOUR),
        ):
            alerts.append({"kind": "high_call_rate", "exec_email": r["exec_email"], "count": r["n"]})
        # error rate
        row = c.execute(
            "SELECT "
            "SUM(CASE WHEN result='error' THEN 1 ELSE 0 END) as errs, COUNT(*) as total "
            "FROM audit WHERE ts >= ?",
            (since,),
        ).fetchone()
        if row and row["total"] and (row["errs"] / row["total"]) > HIGH_ERROR_RATE_THRESHOLD:
            alerts.append({"kind": "high_error_rate", "rate": row["errs"] / row["total"], "total": row["total"]})
    return alerts


def main() -> int:
    settings = load_settings(Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml")))
    log = AuditLog(db_path=Path(settings.audit.db_path))
    alerts = detect_anomalies(log)
    if alerts:
        for a in alerts:
            print("ALERT", a)
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
