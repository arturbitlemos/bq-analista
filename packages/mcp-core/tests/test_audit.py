import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_core.audit import PgAuditLog


@asynccontextmanager
async def _fake_pool(mock_conn):
    """Minimal asyncpg pool context manager for testing."""
    mock_pool = MagicMock()

    @asynccontextmanager
    async def acquire():
        yield mock_conn

    mock_pool.acquire = acquire
    yield mock_pool


async def test_pg_audit_log_record_executes_insert():
    """record() calls conn.execute with an INSERT INTO bq_audit statement."""
    mock_conn = AsyncMock()
    async with _fake_pool(mock_conn) as mock_pool:
        with patch("mcp_core.db.get_pool", return_value=mock_pool):
            audit = PgAuditLog(agent_name="test-agent")
            await audit.record(
                exec_email="user@soma.com",
                tool="consultar_bq",
                sql="SELECT 1",
                bytes_scanned=1024,
                row_count=5,
                duration_ms=200,
                result="ok",
                error=None,
            )

    mock_conn.execute.assert_called_once()
    sql_stmt = mock_conn.execute.call_args[0][0]
    assert "INSERT INTO bq_audit" in sql_stmt
    positional = mock_conn.execute.call_args[0]
    assert "user@soma.com" in positional
    assert "test-agent" in positional
    assert "consultar_bq" in positional
    assert "ok" in positional


async def test_pg_audit_log_record_passes_all_fields():
    """record() passes all 9 value fields in the correct order."""
    mock_conn = AsyncMock()
    async with _fake_pool(mock_conn) as mock_pool:
        with patch("mcp_core.db.get_pool", return_value=mock_pool):
            audit = PgAuditLog(agent_name="ciclo-agent")
            await audit.record(
                exec_email="a@soma.com",
                tool="consultar_bq",
                sql="SELECT 2",
                bytes_scanned=2048,
                row_count=10,
                duration_ms=350,
                result="error",
                error="bq_execution: quota exceeded",
            )

    # Positional indices verify INSERT column order hasn't been silently reordered.
    # Index [0] is the SQL string; [1]..[9] are the asyncpg positional params ($1..$9).
    # $1=exec_email $2=agent $3=tool $4=sql $5=bytes $6=rows $7=duration $8=result $9=error
    positional = mock_conn.execute.call_args[0]
    assert positional[1] == "a@soma.com"
    assert positional[2] == "ciclo-agent"
    assert positional[3] == "consultar_bq"
    assert positional[4] == "SELECT 2"
    assert positional[5] == 2048
    assert positional[6] == 10
    assert positional[7] == 350
    assert positional[8] == "error"
    assert positional[9] == "bq_execution: quota exceeded"


async def test_pg_audit_log_record_swallows_db_errors(caplog):
    """record() catches DB exceptions and logs them without re-raising."""
    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = RuntimeError("connection pool exhausted")
    async with _fake_pool(mock_conn) as mock_pool:
        with patch("mcp_core.db.get_pool", return_value=mock_pool):
            audit = PgAuditLog(agent_name="test-agent")
            with caplog.at_level(logging.ERROR, logger="mcp_core.audit"):
                await audit.record(
                    exec_email="user@soma.com",
                    tool="consultar_bq",
                    sql=None,
                    bytes_scanned=0,
                    row_count=0,
                    duration_ms=0,
                    result="error",
                    error="some error",
                )
    # Must not raise; must log the failure
    assert any("bq_audit" in r.message for r in caplog.records)
