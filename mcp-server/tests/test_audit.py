from pathlib import Path

from mcp_exec.audit import AuditLog


def test_record_and_query(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    log.record(
        exec_email="e@x.com", tool="consultar_bq",
        sql="SELECT 1", bytes_scanned=10, row_count=1,
        duration_ms=55, result="ok", error=None,
    )
    rows = log.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["exec_email"] == "e@x.com"
    assert rows[0]["tool"] == "consultar_bq"


def test_purge_older_than(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    log.record(exec_email="e", tool="t", sql=None, bytes_scanned=0, row_count=0,
               duration_ms=0, result="ok", error=None)
    deleted = log.purge_older_than_days(0)
    assert deleted == 1
    assert log.list_recent() == []
