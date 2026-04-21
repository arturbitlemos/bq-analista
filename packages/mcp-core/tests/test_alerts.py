import time
from pathlib import Path

from mcp_core.alerts import detect_anomalies
from mcp_core.audit import AuditLog


def test_detects_high_calls_per_hour(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    for _ in range(60):
        log.record(
            exec_email="busy@x.com", tool="consultar_bq", sql="SELECT 1",
            bytes_scanned=1, row_count=1, duration_ms=1, result="ok", error=None,
        )
    alerts = detect_anomalies(log, now=time.time())
    assert any(a["kind"] == "high_call_rate" and a["exec_email"] == "busy@x.com" for a in alerts)


def test_detects_huge_query(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    log.record(
        exec_email="e@x.com", tool="consultar_bq", sql="SELECT 1",
        bytes_scanned=11 * 1024**3, row_count=1, duration_ms=1, result="ok", error=None,
    )
    alerts = detect_anomalies(log, now=time.time())
    assert any(a["kind"] == "huge_query" for a in alerts)


def test_detects_error_rate(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    for i in range(20):
        log.record(
            exec_email="e@x.com", tool="consultar_bq", sql="SELECT 1",
            bytes_scanned=0, row_count=0, duration_ms=0,
            result="ok" if i < 10 else "error",
            error=None if i < 10 else "boom",
        )
    alerts = detect_anomalies(log, now=time.time())
    assert any(a["kind"] == "high_error_rate" for a in alerts)
