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


from mcp_core.refresh_spec import RefreshSpec, DataBlockSchema


def test_data_block_schema_array_shape():
    s = DataBlockSchema(shape="array", fields=["loja", "venda_liquida"])
    assert s.shape == "array"
    assert s.fields == ["loja", "venda_liquida"]


def test_data_block_schema_object_shape():
    s = DataBlockSchema(shape="object", fields=["total_cy", "total_ly"])
    assert s.shape == "object"


def test_data_block_schema_rejects_unknown_shape():
    import pytest
    with pytest.raises(ValueError):
        DataBlockSchema(shape="dict", fields=["x"])


def test_data_block_schema_rejects_empty_fields():
    import pytest
    with pytest.raises(ValueError):
        DataBlockSchema(shape="array", fields=[])


def test_refresh_spec_accepts_optional_schema_per_block():
    spec = RefreshSpec.model_validate({
        "queries": [{"id": "q1", "sql": "SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"}],
        "data_blocks": [{
            "block_id": "data_q1",
            "query_id": "q1",
            "schema": {"shape": "array", "fields": ["x"]},
        }],
        "original_period": {"start": "2026-04-01", "end": "2026-04-23"},
    })
    assert spec.data_blocks[0].schema_.shape == "array"
    assert spec.data_blocks[0].schema_.fields == ["x"]


def test_refresh_spec_schema_is_optional_for_legacy_specs():
    spec = RefreshSpec.model_validate({
        "queries": [{"id": "q1", "sql": "SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"}],
        "data_blocks": [{"block_id": "data_q1", "query_id": "q1"}],
        "original_period": {"start": "2026-04-01", "end": "2026-04-23"},
    })
    assert spec.data_blocks[0].schema_ is None
