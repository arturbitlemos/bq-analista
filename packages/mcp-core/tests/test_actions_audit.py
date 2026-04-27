import pytest
import json
from mcp_core import db
from mcp_core.actions_audit import record


@pytest.mark.asyncio
async def test_record_inserts_row(db_pool):
    pool = db.get_pool()
    async with pool.acquire() as conn:
        # need a parent row for FK
        await conn.execute(
            "INSERT INTO analyses (id, agent_slug, author_email, title, blob_pathname) "
            "VALUES ('a1', 'vendas-linx', 'a@b.com', 'T', 'p')"
        )
    async with db.transaction() as conn:
        await record(conn, action="publish", actor_email="a@b.com", analysis_id="a1", metadata={"foo": "bar"})

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM audit_log WHERE analysis_id = 'a1'")
    assert row["action"] == "publish"
    assert row["actor_email"] == "a@b.com"
    md = row["metadata"]
    if isinstance(md, str):
        md = json.loads(md)
    assert md == {"foo": "bar"}


@pytest.mark.asyncio
async def test_record_with_null_analysis_id(db_pool):
    async with db.transaction() as conn:
        await record(conn, action="login_failed", actor_email="x@y.com", analysis_id=None, metadata={"reason": "bad_token"})

    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM audit_log WHERE actor_email = 'x@y.com'")
    assert row["analysis_id"] is None
    assert row["action"] == "login_failed"
