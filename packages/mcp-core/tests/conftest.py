import os
import pytest
import pytest_asyncio
from mcp_core import db


@pytest_asyncio.fixture
async def db_pool():
    """Initialize pool and TRUNCATE tables before/after each test.

    NOTE: tests assume serial execution. Don't use pytest-xdist (-n) — TRUNCATE
    is destructive and parallel tests collide. If we need parallelism later,
    migrate to pytest-postgresql with ephemeral DB per worker.
    """
    if "DATABASE_URL_TEST" not in os.environ:
        pytest.skip("DATABASE_URL_TEST not set")
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_TEST"]
    await db.init_pool()
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE analyses, audit_log RESTART IDENTITY CASCADE")
    yield
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE analyses, audit_log RESTART IDENTITY CASCADE")
    await db.close_pool()
