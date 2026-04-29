from __future__ import annotations
import asyncpg
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """Initialize the connection pool.

    `statement_cache_size=0` is REQUIRED when DATABASE_URL points to Neon's pooler
    endpoint (which uses pgbouncer in transaction mode and doesn't support
    prepared statements). Without this flag, the first query may fail with a
    confusing protocol error."""
    global _pool
    dsn = os.environ["DATABASE_URL"]
    _pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=5, command_timeout=60,
        statement_cache_size=0,
    )


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() at startup")
    return _pool


@asynccontextmanager
async def transaction() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn
