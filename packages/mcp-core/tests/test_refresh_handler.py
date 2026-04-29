import pytest
import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from mcp_core import db, analyses_repo
from mcp_core.refresh_handler import refresh_analysis, RefreshResult, RefreshError, _BqError


def _spec_dict():
    return {
        "queries": [{"id": "q1", "sql": "SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"}],
        "data_blocks": [{"block_id": "data_q1", "query_id": "q1"}],
        "original_period": {"start": "2026-04-01", "end": "2026-04-23"},
    }


async def _seed(refresh_spec=None, author="author@x.com", id="t1", blob_url="https://blob.x/old.html"):
    """Insert a row using analyses_repo.insert (so refresh_spec is properly validated/cast)."""
    spec_for_insert = refresh_spec if refresh_spec is not None else _spec_dict()
    async with db.transaction() as conn:
        await analyses_repo.insert(conn, analyses_repo.AnalysisRow(
            id=id, agent_slug="vendas-linx", author_email=author,
            title="T", blob_pathname=f"analyses/vendas-linx/{id}.html",
            blob_url=blob_url,
            refresh_spec=spec_for_insert,
        ))


def _bq_ok(rows):
    bq = MagicMock()
    bq.run_query = MagicMock(return_value=MagicMock(rows=rows))
    return bq


def _blob_ok(html=b'<html><script id="data_q1" type="application/json">[]</script></html>'):
    b = MagicMock()
    b.get = AsyncMock(return_value=html)
    b.put = AsyncMock(return_value="https://blob.x/new.html")
    return b


@pytest.mark.asyncio
async def test_happy_path(db_pool):
    await _seed()
    bq = _bq_ok([{"x": 1, "y": 2}])
    blob = _blob_ok()

    result = await refresh_analysis(
        analysis_id="t1", actor_email="author@x.com",
        start=date(2026, 5, 1), end=date(2026, 5, 7),
        bq=bq, blob=blob,
    )
    assert isinstance(result, RefreshResult)
    assert result.period_start == date(2026, 5, 1)
    assert result.period_end == date(2026, 5, 7)

    # rendered SQL had placeholders substituted
    rendered_sql = bq.run_query.call_args.args[0]
    assert "'2026-05-01'" in rendered_sql
    assert "'2026-05-07'" in rendered_sql

    # blob was re-uploaded with the new payload swapped in
    put_call = blob.put.call_args
    new_body = put_call.args[1]
    assert b'"x":1' in new_body
    assert b'"y":2' in new_body
    # Old empty payload was replaced
    assert new_body.count(b'<script id="data_q1"') == 1

    # DB row reflects new state
    async with db.get_pool().acquire() as conn:
        row = await analyses_repo.get(conn, "t1")
    assert row.period_start == date(2026, 5, 1)
    assert row.period_end == date(2026, 5, 7)
    assert row.last_refreshed_by == "author@x.com"
    assert row.last_refreshed_at is not None
    assert row.last_refresh_error is None
    assert row.blob_url == "https://blob.x/new.html"


@pytest.mark.asyncio
async def test_rejects_non_author(db_pool):
    await _seed()
    with pytest.raises(RefreshError) as exc:
        await refresh_analysis(
            analysis_id="t1", actor_email="someone-else@x.com",
            start=date(2026, 5, 1), end=date(2026, 5, 7),
            bq=_bq_ok([]), blob=_blob_ok(),
        )
    assert exc.value.status == 403


@pytest.mark.asyncio
async def test_404_on_missing(db_pool):
    with pytest.raises(RefreshError) as exc:
        await refresh_analysis(
            analysis_id="does-not-exist", actor_email="author@x.com",
            start=date(2026, 5, 1), end=date(2026, 5, 7),
            bq=_bq_ok([]), blob=_blob_ok(),
        )
    assert exc.value.status == 404


@pytest.mark.asyncio
async def test_422_when_no_refresh_spec(db_pool):
    # Insert a row without refresh_spec by hand (analyses_repo.insert via the dataclass
    # default = None is fine — _spec_dict not used here).
    async with db.transaction() as conn:
        await analyses_repo.insert(conn, analyses_repo.AnalysisRow(
            id="t1", agent_slug="vendas-linx", author_email="author@x.com",
            title="T", blob_pathname="analyses/vendas-linx/t1.html",
            blob_url="https://blob.x/old.html",
            refresh_spec=None,
        ))
    with pytest.raises(RefreshError) as exc:
        await refresh_analysis(
            analysis_id="t1", actor_email="author@x.com",
            start=date(2026, 5, 1), end=date(2026, 5, 7),
            bq=_bq_ok([]), blob=_blob_ok(),
        )
    assert exc.value.status == 422


@pytest.mark.asyncio
async def test_bq_failure_raises_bqerror(db_pool):
    """BigQuery error rolls back the transaction; period is not advanced.

    The API layer is responsible for catching _BqError and writing
    last_refresh_error in a separate transaction."""
    await _seed()
    bq = MagicMock()
    bq.run_query = MagicMock(side_effect=RuntimeError("dataset not allowed"))
    with pytest.raises(_BqError) as exc:
        await refresh_analysis(
            analysis_id="t1", actor_email="author@x.com",
            start=date(2026, 5, 1), end=date(2026, 5, 7),
            bq=bq, blob=_blob_ok(),
        )
    assert "dataset not allowed" in exc.value.message

    # period unchanged (rollback worked) — seed row didn't set period explicitly,
    # so it was None and stays None
    async with db.get_pool().acquire() as conn:
        row = await analyses_repo.get(conn, "t1")
    assert row.period_start is None  # rollback preserved the seeded state
    assert row.period_end is None
    assert row.last_refreshed_at is None
    # last_refresh_error remains None — API layer would set it in a separate tx
    assert row.last_refresh_error is None


@pytest.mark.asyncio
async def test_html_swap_failure_returns_500(db_pool):
    """HTML doesn't have the expected data island block → swap_data_blocks raises."""
    await _seed()
    bq = _bq_ok([{"x": 1}])
    blob = _blob_ok(html=b"<html>no data block here</html>")
    with pytest.raises(RefreshError) as exc:
        await refresh_analysis(
            analysis_id="t1", actor_email="author@x.com",
            start=date(2026, 5, 1), end=date(2026, 5, 7),
            bq=bq, blob=blob,
        )
    assert exc.value.status == 500
    assert "html_swap_failed" in exc.value.message


@pytest.mark.asyncio
async def test_400_on_inverted_dates(db_pool):
    await _seed()
    with pytest.raises(RefreshError) as exc:
        await refresh_analysis(
            analysis_id="t1", actor_email="author@x.com",
            start=date(2026, 5, 7), end=date(2026, 5, 1),
            bq=_bq_ok([]), blob=_blob_ok(),
        )
    assert exc.value.status == 400


@pytest.mark.asyncio
async def test_refresh_fails_loud_on_schema_mismatch(db_pool):
    spec = {
        "queries": [{"id": "q1", "sql": "SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"}],
        "data_blocks": [{
            "block_id": "data_q1", "query_id": "q1",
            "schema": {"shape": "array", "fields": ["loja", "venda"]},
        }],
        "original_period": {"start": "2026-04-01", "end": "2026-04-23"},
    }
    await _seed(refresh_spec=spec, id="t_schema_bad")

    # BQ returns rows missing the required `venda` field
    bq = _bq_ok([{"loja": "A"}])
    blob = _blob_ok()

    with pytest.raises(RefreshError) as exc:
        await refresh_analysis(
            analysis_id="t_schema_bad", actor_email="author@x.com",
            start=date(2026, 5, 1), end=date(2026, 5, 7),
            bq=bq, blob=blob,
        )
    assert exc.value.status == 500
    assert "data_q1" in exc.value.message
    assert "venda" in exc.value.message

    # Blob was NOT overwritten
    blob.put.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_injects_period_block_when_present(db_pool):
    """Reports that opt into the __period__ convention get the new period
    auto-injected on every refresh — keeps header/footer labels in sync with
    the data without requiring a separate SQL query."""
    await _seed(id="t_period")
    bq = _bq_ok([{"x": 1}])
    blob = MagicMock()
    blob.get = AsyncMock(return_value=(
        b'<html>'
        b'<script id="__period__" type="application/json">'
        b'{"start_date":"2026-04-01","end_date":"2026-04-23"}</script>'
        b'<script id="data_q1" type="application/json">[]</script>'
        b'</html>'
    ))
    blob.put = AsyncMock(return_value="https://blob.x/new.html")

    await refresh_analysis(
        analysis_id="t_period", actor_email="author@x.com",
        start=date(2026, 5, 1), end=date(2026, 5, 7),
        bq=bq, blob=blob,
    )
    new_body = blob.put.call_args.args[1]
    assert b'"start_date":"2026-05-01"' in new_body
    assert b'"end_date":"2026-05-07"' in new_body
    assert b'"label_long":"1 a 7 de maio de 2026"' in new_body
    # Legacy old-period strings must be gone from the __period__ block
    assert new_body.count(b'id="__period__"') == 1


@pytest.mark.asyncio
async def test_refresh_succeeds_when_period_block_absent(db_pool):
    """Legacy reports without the __period__ block must not break refresh."""
    await _seed(id="t_no_period")
    bq = _bq_ok([{"x": 1}])
    blob = _blob_ok()  # default fixture HTML has no __period__ block

    result = await refresh_analysis(
        analysis_id="t_no_period", actor_email="author@x.com",
        start=date(2026, 5, 1), end=date(2026, 5, 7),
        bq=bq, blob=blob,
    )
    assert result.period_start == date(2026, 5, 1)
    blob.put.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_object_shape_unwraps_single_row(db_pool):
    spec = {
        "queries": [{"id": "qsum", "sql": "SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"}],
        "data_blocks": [{
            "block_id": "data_summary", "query_id": "qsum",
            "schema": {"shape": "object", "fields": ["total_cy"]},
        }],
        "original_period": {"start": "2026-04-01", "end": "2026-04-23"},
    }
    await _seed(refresh_spec=spec, id="t_obj")

    bq = _bq_ok([{"total_cy": 1234.5}])
    blob = MagicMock()
    blob.get = AsyncMock(return_value=b'<script id="data_summary" type="application/json">{}</script>')
    blob.put = AsyncMock(return_value="https://blob.x/new.html")

    await refresh_analysis(
        analysis_id="t_obj", actor_email="author@x.com",
        start=date(2026, 5, 1), end=date(2026, 5, 7),
        bq=bq, blob=blob,
    )
    new_body = blob.put.call_args.args[1]
    # Object form, not [{...}]
    assert b'{"total_cy":1234.5}' in new_body
    assert b'[{"total_cy"' not in new_body


@pytest.mark.asyncio
async def test_refresh_metadata_includes_duration_ms(db_pool):
    """audit_log deve conter duration_ms no metadata do evento refresh."""
    await _seed()
    bq = _bq_ok([{"x": 1}])
    blob = _blob_ok()

    await refresh_analysis(
        analysis_id="t1", actor_email="author@x.com",
        start=date(2026, 3, 1), end=date(2026, 3, 31),
        bq=bq, blob=blob,
    )

    async with db.transaction() as conn:
        row = await conn.fetchrow(
            "SELECT metadata FROM audit_log WHERE action='refresh' AND analysis_id='t1'"
        )
    assert row is not None
    meta = json.loads(row["metadata"])
    assert "duration_ms" in meta, "metadata deve conter duration_ms"
    assert isinstance(meta["duration_ms"], (int, float))
    assert meta["duration_ms"] >= 0
