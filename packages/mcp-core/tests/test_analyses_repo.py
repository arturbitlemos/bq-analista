import pytest
from datetime import date, datetime, timezone
from mcp_core import db
from mcp_core.analyses_repo import (
    AnalysisRow,
    insert,
    get,
    list_for_user,
    update_acl,
    update_archive,
    update_refresh_state,
    set_refresh_error,
    update_blob_url,
    search,
    try_acquire_refresh_lock,
)


def _row(**overrides) -> AnalysisRow:
    base = dict(
        id="t1", agent_slug="vendas-linx", author_email="a@b.com",
        title="Análise X", brand="FARM", period_label="abr/26",
        period_start=date(2026, 4, 1), period_end=date(2026, 4, 23),
        description="desc", tags=["mtd", "produto"],
        public=False, shared_with=[], archived_by=[],
        blob_pathname="analyses/vendas-linx/t1.html",
        blob_url=None,
        refresh_spec=None,
    )
    base.update(overrides)
    return AnalysisRow(**base)


@pytest.mark.asyncio
async def test_insert_and_get(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="x1"))
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "x1")
    assert row is not None
    assert row.id == "x1"
    assert row.title == "Análise X"


@pytest.mark.asyncio
async def test_get_returns_none_for_missing(db_pool):
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "nope")
    assert row is None


@pytest.mark.asyncio
async def test_list_for_user_filters_acl(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="mine_priv", author_email="a@b.com"))
        await insert(conn, _row(id="other_priv", author_email="c@d.com"))
        await insert(conn, _row(id="other_pub", author_email="c@d.com", public=True))
        await insert(conn, _row(id="other_shared", author_email="c@d.com", shared_with=["a@b.com"]))

    async with db.get_pool().acquire() as conn:
        rows = await list_for_user(conn, agent_slug="vendas-linx", email="a@b.com")
    ids = {r.id for r in rows}
    assert ids == {"mine_priv", "other_pub", "other_shared"}
    assert "other_priv" not in ids


@pytest.mark.asyncio
async def test_update_acl_changes_public_and_shared_with(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1"))
        await update_acl(conn, "a1", public=True, shared_with=["x@y.com"])

    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.public is True
    assert row.shared_with == ["x@y.com"]


@pytest.mark.asyncio
async def test_update_archive_idempotent(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1"))
        await update_archive(conn, "a1", email="u@x.com", archive=True)
        await update_archive(conn, "a1", email="u@x.com", archive=True)  # idempotent
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.archived_by == ["u@x.com"]


@pytest.mark.asyncio
async def test_update_archive_remove(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1", archived_by=["u@x.com"]))
        await update_archive(conn, "a1", email="u@x.com", archive=False)
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.archived_by == []


@pytest.mark.asyncio
async def test_update_refresh_state_sets_period(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1"))
        await update_refresh_state(
            conn, "a1",
            period_start=date(2026, 5, 1), period_end=date(2026, 5, 7),
            actor_email="a@b.com",
        )

    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.period_start == date(2026, 5, 1)
    assert row.last_refreshed_by == "a@b.com"
    assert row.last_refreshed_at is not None
    assert row.last_refresh_error is None


@pytest.mark.asyncio
async def test_set_refresh_error_doesnt_advance_period(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1"))
        await set_refresh_error(conn, "a1", error="dataset not allowed")

    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.last_refresh_error == "dataset not allowed"
    assert row.last_refreshed_at is None  # not advanced


@pytest.mark.asyncio
async def test_update_blob_url(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1", blob_url="https://old.url/x"))
        await update_blob_url(conn, "a1", blob_url="https://new.url/x")
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.blob_url == "https://new.url/x"


@pytest.mark.asyncio
async def test_search_ranks_by_relevance(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="r1", title="Top produtos FARM Leblon"))
        await insert(conn, _row(id="r2", title="Maria Filó YTD"))
    async with db.get_pool().acquire() as conn:
        rows = await search(conn, query="FARM Leblon", email="a@b.com", agent="vendas-linx")
    assert len(rows) >= 1
    assert rows[0].id == "r1"


@pytest.mark.asyncio
async def test_search_filters_by_acl(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="r1", author_email="other@c.com", title="Top produtos privado"))
    async with db.get_pool().acquire() as conn:
        rows = await search(conn, query="produtos", email="a@b.com")
    assert all(r.id != "r1" for r in rows)


@pytest.mark.asyncio
async def test_advisory_lock(db_pool):
    pool = db.get_pool()
    async with pool.acquire() as conn1, conn1.transaction():
        got1 = await try_acquire_refresh_lock(conn1, "a1")
        assert got1 is True
        # second acquire from a different connection on same key should fail
        async with pool.acquire() as conn2, conn2.transaction():
            got2 = await try_acquire_refresh_lock(conn2, "a1")
            assert got2 is False
