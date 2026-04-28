import pytest
from mcp_core import db


@pytest.mark.asyncio
async def test_pool_initialized(db_pool):
    pool = db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1


@pytest.mark.asyncio
async def test_get_pool_before_init_raises():
    # Make sure pool is closed first
    await db.close_pool()
    with pytest.raises(RuntimeError, match="not initialized"):
        db.get_pool()


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db_pool):
    with pytest.raises(ValueError):
        async with db.transaction() as conn:
            await conn.execute(
                "INSERT INTO analyses (id, agent_slug, author_email, title, blob_pathname) "
                "VALUES ('test1', 'vendas-linx', 'a@b.com', 'T', 'p')"
            )
            raise ValueError("boom")
    pool = db.get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM analyses WHERE id = 'test1'")
    assert count == 0
