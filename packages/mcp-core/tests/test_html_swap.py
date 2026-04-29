import pytest
import json
from mcp_core.html_swap import swap_data_blocks, encode_for_script_tag, validate_blocks_present, make_data_block


def test_encode_escapes_script_breakouts():
    payload = [{"name": "</script><img src=x onerror=alert(1)>"}]
    out = encode_for_script_tag(payload)
    assert "</script>" not in out
    assert "\\u003c/script\\u003e" in out


def test_swap_replaces_single_block():
    html = '<html><script id="data_q1" type="application/json">[]</script></html>'
    result = swap_data_blocks(html, {"data_q1": [{"x": 1}]})
    # Tag preserved (id+type still there, exactly once) and body swapped to the new payload.
    assert '<script id="data_q1" type="application/json">' in result
    assert '[{"x":1}]</script>' in result
    assert result.count('id="data_q1"') == 1


def test_swap_replaces_multiple_blocks():
    html = (
        '<script id="data_a" type="application/json">[]</script>'
        '<div>middle</div>'
        '<script id="data_b" type="application/json">[]</script>'
    )
    result = swap_data_blocks(html, {"data_a": [1], "data_b": [2]})
    assert '"data_a"' in result
    assert '[1]' in result.replace(" ", "")
    assert '[2]' in result.replace(" ", "")


def test_swap_preserves_csp_meta():
    html = (
        '<head><meta http-equiv="Content-Security-Policy" content="default-src self">'
        '<script id="data_q1" type="application/json">[]</script></head>'
    )
    result = swap_data_blocks(html, {"data_q1": []})
    assert 'Content-Security-Policy' in result


def test_swap_raises_if_block_missing():
    html = '<html></html>'
    with pytest.raises(ValueError, match="block_id.*data_q1.*not found"):
        swap_data_blocks(html, {"data_q1": []})


def test_validate_blocks_present():
    html = '<script id="data_a" type="application/json">[]</script><script id="data_b" type="application/json">[]</script>'
    validate_blocks_present(html, ["data_a", "data_b"])  # no raise


def test_validate_blocks_missing():
    html = '<script id="data_a" type="application/json">[]</script>'
    with pytest.raises(ValueError, match="missing.*data_b"):
        validate_blocks_present(html, ["data_a", "data_b"])


def test_make_data_block_roundtrips_through_swap():
    block = make_data_block("data_q1", [{"x": 1}])
    html = f"<html>{block}</html>"
    result = swap_data_blocks(html, {"data_q1": [{"x": 2}]})
    assert '"x":2' in result.replace(" ", "")


from mcp_core.html_swap import validate_payload_schema, SchemaError
from mcp_core.refresh_spec import DataBlockSchema


def test_validate_array_payload_passes():
    schema = DataBlockSchema(shape="array", fields=["loja", "venda"])
    payload = [{"loja": "A", "venda": 10.0}, {"loja": "B", "venda": 20.0}]
    out = validate_payload_schema("data_x", payload, schema)
    assert out == payload  # array passes through unchanged


def test_validate_array_payload_missing_field_fails():
    schema = DataBlockSchema(shape="array", fields=["loja", "venda"])
    payload = [{"loja": "A"}]
    with pytest.raises(SchemaError, match="data_x.*row 0.*missing.*venda"):
        validate_payload_schema("data_x", payload, schema)


def test_validate_array_rejects_non_list():
    schema = DataBlockSchema(shape="array", fields=["x"])
    with pytest.raises(SchemaError, match="data_x.*expected array"):
        validate_payload_schema("data_x", {"x": 1}, schema)


def test_validate_object_payload_unwraps_single_row():
    schema = DataBlockSchema(shape="object", fields=["total_cy", "total_ly"])
    payload = [{"total_cy": 100.0, "total_ly": 90.0}]
    out = validate_payload_schema("data_summary", payload, schema)
    assert out == {"total_cy": 100.0, "total_ly": 90.0}


def test_validate_object_rejects_multi_row():
    schema = DataBlockSchema(shape="object", fields=["x"])
    payload = [{"x": 1}, {"x": 2}]
    with pytest.raises(SchemaError, match="data_x.*object shape expects 1 row.*got 2"):
        validate_payload_schema("data_x", payload, schema)


def test_validate_object_rejects_zero_rows():
    schema = DataBlockSchema(shape="object", fields=["x"])
    with pytest.raises(SchemaError, match="data_x.*object shape expects 1 row.*got 0"):
        validate_payload_schema("data_x", [], schema)


def test_validate_object_missing_field_fails():
    schema = DataBlockSchema(shape="object", fields=["total_cy", "total_ly"])
    payload = [{"total_cy": 100.0}]
    with pytest.raises(SchemaError, match="data_summary.*missing.*total_ly"):
        validate_payload_schema("data_summary", payload, schema)


def test_validate_with_none_schema_returns_payload_unchanged():
    payload = [{"anything": 1}]
    assert validate_payload_schema("data_x", payload, None) == payload


def test_swap_validates_array_schema_and_passes():
    schema = DataBlockSchema(shape="array", fields=["x"])
    html = '<script id="data_q1" type="application/json">[]</script>'
    out = swap_data_blocks(html, {"data_q1": [{"x": 1}]}, schemas={"data_q1": schema})
    assert '"x":1' in out


def test_swap_unwraps_object_payload_before_writing():
    schema = DataBlockSchema(shape="object", fields=["total"])
    html = '<script id="data_summary" type="application/json">{}</script>'
    out = swap_data_blocks(html, {"data_summary": [{"total": 42}]}, schemas={"data_summary": schema})
    # Object form, not array
    assert '{"total":42}' in out
    assert '[{"total"' not in out


def test_swap_raises_schema_error_when_field_missing():
    schema = DataBlockSchema(shape="array", fields=["loja", "venda"])
    html = '<script id="data_q1" type="application/json">[]</script>'
    with pytest.raises(SchemaError, match="data_q1.*missing.*venda"):
        swap_data_blocks(html, {"data_q1": [{"loja": "A"}]}, schemas={"data_q1": schema})


def test_swap_without_schemas_dict_works_unchanged():
    """Backward compat: callers that don't pass `schemas` get the legacy behavior."""
    html = '<script id="data_q1" type="application/json">[]</script>'
    out = swap_data_blocks(html, {"data_q1": [{"x": 1}]})
    assert '"x":1' in out


from mcp_core.html_swap import extract_block_payload


def test_extract_block_payload_returns_parsed_json_array():
    html = '<script id="data_q1" type="application/json">[{"x":1}]</script>'
    assert extract_block_payload(html, "data_q1") == [{"x": 1}]


def test_extract_block_payload_returns_parsed_json_object():
    html = '<script id="data_summary" type="application/json">{"total":42}</script>'
    assert extract_block_payload(html, "data_summary") == {"total": 42}


def test_extract_block_payload_raises_when_block_missing():
    with pytest.raises(ValueError, match="block_id.*data_q1.*not found"):
        extract_block_payload("<html></html>", "data_q1")


def test_extract_block_payload_raises_on_invalid_json():
    html = '<script id="data_q1" type="application/json">not json</script>'
    with pytest.raises(ValueError, match="data_q1.*invalid JSON"):
        extract_block_payload(html, "data_q1")


from mcp_core.html_swap import validate_html_against_spec
from mcp_core.refresh_spec import RefreshSpec


def _spec_with_schema(shape="array", fields=None):
    return RefreshSpec.model_validate({
        "queries": [{"id": "q1", "sql": "SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"}],
        "data_blocks": [{
            "block_id": "data_q1", "query_id": "q1",
            "schema": {"shape": shape, "fields": fields or ["x"]},
        }],
        "original_period": {"start": "2026-04-01", "end": "2026-04-23"},
    })


def test_validate_html_against_spec_passes_for_matching_array():
    html = '<script id="data_q1" type="application/json">[{"x":1}]</script>'
    spec = _spec_with_schema(shape="array", fields=["x"])
    validate_html_against_spec(html, spec)  # no raise


def test_validate_html_against_spec_passes_for_matching_object():
    html = '<script id="data_q1" type="application/json">{"total":42}</script>'
    spec = _spec_with_schema(shape="object", fields=["total"])
    validate_html_against_spec(html, spec)  # no raise


def test_validate_html_against_spec_rejects_array_with_missing_field():
    html = '<script id="data_q1" type="application/json">[{"loja":"A"}]</script>'
    spec = _spec_with_schema(shape="array", fields=["loja", "venda"])
    with pytest.raises(SchemaError, match="data_q1.*missing.*venda"):
        validate_html_against_spec(html, spec)


def test_validate_html_against_spec_rejects_object_with_wrong_shape():
    html = '<script id="data_q1" type="application/json">[{"x":1},{"x":2}]</script>'
    spec = _spec_with_schema(shape="object", fields=["x"])
    with pytest.raises(SchemaError, match="data_q1.*object shape expects 1 row.*got 2"):
        validate_html_against_spec(html, spec)


def test_validate_html_against_spec_skips_blocks_without_schema():
    """Legacy specs (no per-block schema) skip payload validation entirely."""
    html = '<script id="data_q1" type="application/json">[{"anything":1}]</script>'
    spec = RefreshSpec.model_validate({
        "queries": [{"id": "q1", "sql": "SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"}],
        "data_blocks": [{"block_id": "data_q1", "query_id": "q1"}],  # no schema
        "original_period": {"start": "2026-04-01", "end": "2026-04-23"},
    })
    validate_html_against_spec(html, spec)  # no raise
