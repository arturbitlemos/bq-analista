import pytest
from datetime import date
from pydantic import ValidationError
from mcp_core.refresh_spec import RefreshSpec, RefreshQuery, DataBlockRef


def test_minimal_spec_validates():
    spec = RefreshSpec(
        queries=[RefreshQuery(id="top_lojas", sql="SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'")],
        data_blocks=[DataBlockRef(block_id="data_top_lojas", query_id="top_lojas")],
        original_period={"start": date(2026, 4, 1), "end": date(2026, 4, 23)},
    )
    assert spec.queries[0].id == "top_lojas"


def test_unknown_query_id_in_data_block_fails():
    with pytest.raises(ValidationError, match="references unknown query_id"):
        RefreshSpec(
            queries=[RefreshQuery(id="q1", sql="SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'")],
            data_blocks=[DataBlockRef(block_id="data_x", query_id="q_does_not_exist")],
            original_period={"start": date(2026, 4, 1), "end": date(2026, 4, 23)},
        )


def test_duplicate_query_id_fails():
    with pytest.raises(ValidationError, match="duplicate query id"):
        RefreshSpec(
            queries=[
                RefreshQuery(id="q1", sql="SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"),
                RefreshQuery(id="q1", sql="SELECT 2 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"),
            ],
            data_blocks=[],
            original_period={"start": date(2026, 4, 1), "end": date(2026, 4, 23)},
        )


def test_sql_must_contain_placeholders():
    with pytest.raises(ValidationError, match="missing placeholder"):
        RefreshSpec(
            queries=[RefreshQuery(id="q1", sql="SELECT 1")],
            data_blocks=[DataBlockRef(block_id="data_q1", query_id="q1")],
            original_period={"start": date(2026, 4, 1), "end": date(2026, 4, 23)},
        )


def test_render_substitutes_placeholders():
    q = RefreshQuery(id="q1", sql="SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'")
    sql = q.render(start=date(2026, 5, 1), end=date(2026, 5, 7))
    assert sql == "SELECT 1 WHERE d BETWEEN '2026-05-01' AND '2026-05-07'"
