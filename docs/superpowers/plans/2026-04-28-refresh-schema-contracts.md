# Refresh Schema Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the refresh flow trivially correct by establishing a typed contract between the SQL queries and the HTML data blocks, validated at both publish and refresh time.

**Architecture:** Each `data_block` declares an `expected_schema` (shape + required fields). The agent's queries must produce that exact shape — SQL is the only transformation layer; JS does pure rendering. Both `publicar_dashboard` and `refresh_analysis` validate payloads against the schema before writing to the blob, so any mismatch fails loud with a clear error instead of silently producing `undefined` in the browser.

**Tech Stack:** Python 3.13, Pydantic v2, FastAPI, asyncpg, BigQuery, FastMCP. Tests use pytest + pytest-asyncio with the existing `db_pool` fixture.

---

## Background

A 2026-04-28 production refresh of `maria-fil-venda-por-loja-e-categoria-ytd-2026-366a05c2` returned `200 OK` but rendered the dashboard with `undefined` everywhere. Root cause: the JS expected `data_summary = {total_cy, total_ly, var_pct, lojas}` (object) and `data_stores = [{n, cy, v, c:[{l,g}]}]` (nested array), but the saved `refresh_spec` had a single flat query (`SELECT loja, linha, grupo_produto, venda_liquida FROM ...`) mapped to BOTH blocks. The agent had pre-aggregated the data at publish time, then stored a raw query that produces an entirely different shape on refresh — the contract between blocks and queries was implicit and unenforced.

This plan makes the contract explicit and enforced.

## File Structure

**Modify:**
- `packages/mcp-core/src/mcp_core/refresh_spec.py` — add `DataBlockSchema` model + optional `schema` on `DataBlockRef`
- `packages/mcp-core/src/mcp_core/html_swap.py` — add `validate_payload_schema`; teach `swap_data_blocks` to accept schemas + unwrap `object`-shape payloads
- `packages/mcp-core/src/mcp_core/refresh_handler.py:107-113` — pass schemas to `swap_data_blocks`
- `packages/mcp-core/src/mcp_core/server_factory.py:355-359` — `publicar_dashboard` extracts current block JSON and validates it against declared schema; reject on mismatch
- `agents/vendas-linx/src/agent/context/SKILL.md` — new convention: SQL-as-transformation; one block per query; declare schema; no client-side aggregation

**Modify (tests):**
- `packages/mcp-core/tests/test_refresh_spec.py` — schema field validation
- `packages/mcp-core/tests/test_html_swap.py` — schema-validated swap, object unwrap
- `packages/mcp-core/tests/test_refresh_handler.py` — refresh fails loud on schema mismatch
- `packages/mcp-core/tests/test_server_factory.py` — publish rejects HTML whose block contents violate the declared schema

**No DB migration needed** — `refresh_spec` is JSONB; existing rows without `schema` keep working (validation is opt-in per block).

## Cross-cutting Conventions

- All new fields are **optional** (`schema | None = None`) so old `refresh_spec` rows keep loading.
- A block with `schema=None` skips validation (legacy mode). New analyses MUST declare schema; the SKILL.md enforces this and `publicar_dashboard` warns (not yet rejects) when it's missing.
- Errors raised during validation use `RefreshError(500, ...)` from `refresh_handler` and `{"error": "..."}` return from `publicar_dashboard` — same surfaces as today, no new error types.
- Commits use Conventional Commits format with the existing `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` trailer (matches repo style).

---

### Task 1: Add `DataBlockSchema` model with shape + fields

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/refresh_spec.py`
- Test: `packages/mcp-core/tests/test_refresh_spec.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/mcp-core/tests/test_refresh_spec.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/mcp-core
uv run pytest tests/test_refresh_spec.py -v -k "schema"
```

Expected: FAIL — `DataBlockSchema` undefined; `schema_` attribute missing.

- [ ] **Step 3: Implement the model**

Replace the contents of `packages/mcp-core/src/mcp_core/refresh_spec.py` with:

```python
from __future__ import annotations
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class RefreshQuery(BaseModel):
    id: str = Field(min_length=1)
    sql: str = Field(min_length=1)

    def render(self, *, start: date, end: date) -> str:
        return self.sql.replace("{{start_date}}", start.isoformat()).replace("{{end_date}}", end.isoformat())


class DataBlockSchema(BaseModel):
    """Declares the shape a refreshed payload must have before being written
    into a `<script id=...>` block. `shape="array"` means the BQ rows go in
    as-is; `shape="object"` means the query MUST return exactly one row, and
    that row is unwrapped (so the JS sees an object, not a 1-element array)."""
    shape: Literal["array", "object"] = "array"
    fields: list[str] = Field(min_length=1)


class DataBlockRef(BaseModel):
    block_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)
    # Aliased to `schema` in the JSON because Pydantic's `BaseModel.schema`
    # method shadows attribute access. Using `schema_` avoids the collision
    # while keeping the wire format intuitive.
    schema_: DataBlockSchema | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


class PeriodRange(BaseModel):
    start: date
    end: date


class RefreshSpec(BaseModel):
    queries: list[RefreshQuery]
    data_blocks: list[DataBlockRef]
    original_period: PeriodRange

    @model_validator(mode="after")
    def _validate(self) -> "RefreshSpec":
        ids = [q.id for q in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate query id in queries[]")

        for q in self.queries:
            if "{{start_date}}" not in q.sql or "{{end_date}}" not in q.sql:
                raise ValueError(f"query {q.id!r}: missing placeholder {{start_date}} or {{end_date}}")

        valid_ids = set(ids)
        for db_ref in self.data_blocks:
            if db_ref.query_id not in valid_ids:
                raise ValueError(f"data_block {db_ref.block_id!r} references unknown query_id {db_ref.query_id!r}")

        return self
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd packages/mcp-core
uv run pytest tests/test_refresh_spec.py -v
```

Expected: PASS — all schema tests + all pre-existing tests stay green.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/refresh_spec.py packages/mcp-core/tests/test_refresh_spec.py
git commit -m "$(cat <<'EOF'
feat(refresh-spec): add optional DataBlockSchema for typed data blocks

Each data_block can now declare {shape, fields}. Backward compat: spec rows
without schema parse fine and skip validation. shape=object signals the
query returns exactly one row that should be unwrapped before swap.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Add `validate_payload_schema` helper in `html_swap`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/html_swap.py`
- Test: `packages/mcp-core/tests/test_html_swap.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/mcp-core/tests/test_html_swap.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/mcp-core
uv run pytest tests/test_html_swap.py -v -k "validate_payload or validate_object or validate_array"
```

Expected: FAIL — `validate_payload_schema` and `SchemaError` not defined.

- [ ] **Step 3: Implement the helper**

Append to `packages/mcp-core/src/mcp_core/html_swap.py`:

```python
class SchemaError(ValueError):
    """Raised when a refreshed payload doesn't match its declared DataBlockSchema."""


def validate_payload_schema(
    block_id: str,
    payload: Any,
    schema: "DataBlockSchema | None",
) -> Any:
    """Validate `payload` (BQ rows: list[dict]) against `schema`. Returns the
    payload prepared for swap: unchanged for `array`, unwrapped (the single
    row) for `object`. Raises SchemaError with a clear message on mismatch.

    schema=None is a no-op — used for legacy specs that pre-date schema
    contracts. New analyses should always declare a schema."""
    if schema is None:
        return payload

    if schema.shape == "array":
        if not isinstance(payload, list):
            raise SchemaError(f"{block_id}: expected array, got {type(payload).__name__}")
        for i, row in enumerate(payload):
            if not isinstance(row, dict):
                raise SchemaError(f"{block_id}: row {i} is not an object")
            missing = [f for f in schema.fields if f not in row]
            if missing:
                raise SchemaError(f"{block_id}: row {i} missing fields: {missing}")
        return payload

    # shape == "object"
    if not isinstance(payload, list):
        raise SchemaError(f"{block_id}: expected list of 1 row, got {type(payload).__name__}")
    if len(payload) != 1:
        raise SchemaError(f"{block_id}: object shape expects 1 row, got {len(payload)}")
    row = payload[0]
    if not isinstance(row, dict):
        raise SchemaError(f"{block_id}: single row is not an object")
    missing = [f for f in schema.fields if f not in row]
    if missing:
        raise SchemaError(f"{block_id}: missing fields: {missing}")
    return row
```

Add the import at the top of the file (after `from typing import Any`):

```python
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_core.refresh_spec import DataBlockSchema
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd packages/mcp-core
uv run pytest tests/test_html_swap.py -v
```

Expected: PASS — new tests + all pre-existing tests stay green.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/html_swap.py packages/mcp-core/tests/test_html_swap.py
git commit -m "$(cat <<'EOF'
feat(html-swap): validate_payload_schema for typed data blocks

Pure validator — returns array unchanged, unwraps single-row object payloads.
Raises SchemaError on shape/field mismatch with a message that names the
block and the missing fields. None schema = legacy pass-through.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Wire schema validation into `swap_data_blocks`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/html_swap.py:46-65` (swap_data_blocks)
- Test: `packages/mcp-core/tests/test_html_swap.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/mcp-core/tests/test_html_swap.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/mcp-core
uv run pytest tests/test_html_swap.py -v -k "swap_validates or swap_unwraps or swap_raises_schema or swap_without_schemas"
```

Expected: FAIL — `swap_data_blocks` doesn't accept `schemas` kwarg.

- [ ] **Step 3: Update `swap_data_blocks`**

Replace the body of `swap_data_blocks` in `packages/mcp-core/src/mcp_core/html_swap.py` (lines 46-65) with:

```python
def swap_data_blocks(
    html: str,
    payloads: dict[str, Any],
    schemas: "dict[str, DataBlockSchema | None] | None" = None,
) -> str:
    """Replace each <script id="<block_id>" type="application/json"> body with JSON of payloads[block_id].

    If `schemas` is provided, each payload is validated and (for shape=object)
    unwrapped to a single dict before being encoded. Validation failure raises
    SchemaError — which the caller (refresh_handler / publicar_dashboard) maps
    to a user-visible 500.

    Raises ValueError if a block_id is not found, or if the resulting HTML lost the CSP meta tag
    (defensive — should never happen since we never touch <head>)."""
    csp_before = "Content-Security-Policy" in html

    out = html
    for block_id, payload in payloads.items():
        pattern = _block_pattern(block_id)
        match = pattern.search(out)
        if not match:
            raise ValueError(f"block_id {block_id!r} not found in HTML")
        schema = (schemas or {}).get(block_id)
        prepared = validate_payload_schema(block_id, payload, schema)
        encoded = encode_for_script_tag(prepared)
        out = pattern.sub(lambda m: m.group(1) + encoded + m.group(3), out, count=1)

    if csp_before and "Content-Security-Policy" not in out:
        raise ValueError("CSP meta tag was lost during swap (should never happen)")

    return out
```

- [ ] **Step 4: Run all html_swap tests to verify**

```bash
cd packages/mcp-core
uv run pytest tests/test_html_swap.py -v
```

Expected: PASS — all 13+ tests green (legacy + new schema tests).

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/html_swap.py packages/mcp-core/tests/test_html_swap.py
git commit -m "$(cat <<'EOF'
feat(html-swap): swap_data_blocks validates payloads against schemas

New optional `schemas` kwarg — when provided, each block's payload is shape-
checked + field-checked before encode. shape=object unwraps the single row so
the JS sees an object, not a 1-element array. Without schemas, behavior is
unchanged (existing callers + legacy specs keep working).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Pass schemas from `refresh_handler` into `swap_data_blocks`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/refresh_handler.py:107-113`
- Test: `packages/mcp-core/tests/test_refresh_handler.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/mcp-core/tests/test_refresh_handler.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/mcp-core
uv run pytest tests/test_refresh_handler.py -v -k "schema_mismatch or object_shape_unwraps"
```

Expected: FAIL — handler doesn't pass schemas, so missing fields wouldn't raise, and object payloads stay as 1-element lists.

- [ ] **Step 3: Update the handler**

In `packages/mcp-core/src/mcp_core/refresh_handler.py`, replace lines 107-113 with:

```python
        payloads = {ref.block_id: results[ref.query_id] for ref in spec.data_blocks}
        schemas = {ref.block_id: ref.schema_ for ref in spec.data_blocks}

        current_html_bytes = await blob.get(row.blob_pathname)
        try:
            new_html = swap_data_blocks(
                current_html_bytes.decode("utf-8"),
                payloads,
                schemas=schemas,
            )
        except ValueError as e:
            # Covers SchemaError (subclass of ValueError) and missing-block ValueError.
            # Both surface as 500 — the API layer will roll back the DB tx.
            raise RefreshError(500, f"html_swap_failed: {e}") from e
```

- [ ] **Step 4: Run all refresh tests to verify**

```bash
cd packages/mcp-core
uv run pytest tests/test_refresh_handler.py -v
```

Expected: PASS — new tests + happy_path test stays green (its spec has no schema → no validation).

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/refresh_handler.py packages/mcp-core/tests/test_refresh_handler.py
git commit -m "$(cat <<'EOF'
feat(refresh): validate payload schemas before swapping into HTML

refresh_handler now passes per-block schemas to swap_data_blocks. Mismatch
raises SchemaError → RefreshError(500), DB tx rolls back, blob is NOT
overwritten. Legacy specs (no schema) keep the previous behavior.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Validate published HTML against declared schema in `publicar_dashboard`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/html_swap.py` (add `extract_block_payload` + `validate_html_against_spec`)
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py:322, 354-359`
- Test: `packages/mcp-core/tests/test_html_swap.py`

This task ensures the publish path enforces the same contract the refresh path enforces — so the agent can't publish an HTML where the data block contents don't match the declared schema. That's exactly the bug we hit in production: the agent declared one shape in the SQL and embedded a different shape in the HTML.

The validation logic is extracted as a pure function `validate_html_against_spec` in `html_swap.py` so it's unit-testable in isolation (the existing `test_server_factory.py` doesn't have an end-to-end fixture for `publicar_dashboard`).

- [ ] **Step 1: Write a test for `extract_block_payload`**

Append to `packages/mcp-core/tests/test_html_swap.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/mcp-core
uv run pytest tests/test_html_swap.py -v -k "extract_block_payload"
```

Expected: FAIL — `extract_block_payload` not defined.

- [ ] **Step 3: Implement `extract_block_payload`**

Append to `packages/mcp-core/src/mcp_core/html_swap.py`:

```python
def extract_block_payload(html: str, block_id: str) -> Any:
    """Parse the JSON inside `<script id="<block_id>" type="application/json">...</script>`.
    Used at publish time to validate the embedded payload against the declared schema —
    same contract the refresh handler enforces. Raises ValueError if the block is
    missing or the body isn't valid JSON."""
    pattern = _block_pattern(block_id)
    match = pattern.search(html)
    if not match:
        raise ValueError(f"block_id {block_id!r} not found in HTML")
    body = match.group(2)
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise ValueError(f"{block_id}: invalid JSON inside <script> body: {e}") from e
```

- [ ] **Step 4: Verify the new tests pass**

```bash
cd packages/mcp-core
uv run pytest tests/test_html_swap.py -v -k "extract_block_payload"
```

Expected: PASS.

- [ ] **Step 5: Write a failing test for `validate_html_against_spec`**

Append to `packages/mcp-core/tests/test_html_swap.py`:

```python
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
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
cd packages/mcp-core
uv run pytest tests/test_html_swap.py -v -k "validate_html_against_spec"
```

Expected: FAIL — `validate_html_against_spec` not defined.

- [ ] **Step 7: Implement `validate_html_against_spec`**

Append to `packages/mcp-core/src/mcp_core/html_swap.py`:

```python
def validate_html_against_spec(html: str, spec: "RefreshSpec") -> None:
    """Verify each data block's embedded JSON matches its declared schema.
    Raises SchemaError on the first mismatch with a message naming the block
    and the offending field. Used by publicar_dashboard at publish time —
    same contract the refresh handler enforces.

    Blocks without a declared schema are skipped (legacy compatibility)."""
    for ref in spec.data_blocks:
        if ref.schema_ is None:
            continue
        payload = extract_block_payload(html, ref.block_id)
        # Object-shape blocks are stored as `{...}` directly in the HTML; the
        # validator's uniform interface expects a list-of-rows, so wrap it.
        normalized = [payload] if ref.schema_.shape == "object" else payload
        validate_payload_schema(ref.block_id, normalized, ref.schema_)
```

Add the type-only import at the top of `html_swap.py` (extending the existing `TYPE_CHECKING` block from Task 2):

```python
if TYPE_CHECKING:
    from mcp_core.refresh_spec import DataBlockSchema, RefreshSpec
```

- [ ] **Step 8: Verify the validation tests pass**

```bash
cd packages/mcp-core
uv run pytest tests/test_html_swap.py -v
```

Expected: PASS — all html_swap tests green.

- [ ] **Step 9: Wire into the publish path**

In `packages/mcp-core/src/mcp_core/server_factory.py` line 322, expand the existing import:

```python
from mcp_core.html_swap import validate_blocks_present, validate_html_against_spec, SchemaError
```

Then replace lines 354-359 (the existing try/except validating the spec) with:

```python
        try:
            spec_obj = RefreshSpec.model_validate(refresh_spec)
            block_ids = [b.block_id for b in spec_obj.data_blocks]
            validate_blocks_present(html_content, block_ids)
            validate_html_against_spec(html_content, spec_obj)
        except SchemaError as e:
            return {"error": f"refresh_spec_invalid: {e}"}
        except Exception as e:
            return {"error": f"refresh_spec_invalid: {e}"}
```

- [ ] **Step 10: Run the full mcp-core test suite to verify no regressions**

```bash
cd packages/mcp-core
uv run pytest -v
```

Expected: PASS — all tests green.

- [ ] **Step 11: Commit**

```bash
git add packages/mcp-core/src/mcp_core/html_swap.py packages/mcp-core/src/mcp_core/server_factory.py packages/mcp-core/tests/test_html_swap.py
git commit -m "$(cat <<'EOF'
feat(publish): validate embedded data blocks against declared schema

publicar_dashboard now runs validate_html_against_spec — extracts each
data_block payload from html_content and shape-checks it against the
declared schema. Same contract the refresh handler enforces, so the agent
can't ship an HTML whose embedded data won't survive a refresh.

Closes the publish/refresh contract gap that caused the maria-fil
2026-04-28 incident (one query mapped to two blocks of different shapes).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Update vendas-linx SKILL.md with the new convention

**Files:**
- Modify: `agents/vendas-linx/src/agent/context/SKILL.md`

This task encodes the architectural rule into the agent's instructions so future analyses follow it.

- [ ] **Step 1: Read the current SKILL.md to find the right insertion point**

```bash
grep -n "publicar_dashboard\|refresh_spec\|data_block\|html_data_block" agents/vendas-linx/src/agent/context/SKILL.md
```

Note the line numbers for the `publicar_dashboard` / `refresh_spec` section.

- [ ] **Step 2: Replace the existing publish guidance with the new convention**

In `agents/vendas-linx/src/agent/context/SKILL.md`, find the section that documents `publicar_dashboard` + refresh and replace its body with:

```markdown
## Publicação com refresh garantido — contrato do data block

Toda análise publicada deve atender este contrato:

> **SQL é a única camada de transformação. JS só renderiza. Cada data block tem uma query que retorna EXATAMENTE a forma que o JS lê.**

Isso significa:

- Não pré-agregue, não pré-junte e não calcule deltas em Python antes de embutir no HTML. Faça tudo em SQL (window functions, STRUCT, ARRAY_AGG, self-join CY/LY).
- Cada `<script id="data_X" type="application/json">` recebe o resultado da query `X`. Sem reuso (não mapeie 2 blocks pra mesma query a menos que ambos consumam o resultado idêntico).
- O JS no HTML faz `JSON.parse(...)` e renderiza. Sem agregação no browser.

### Como declarar o schema

No `refresh_spec`, cada `data_block` deve ter `schema = {shape, fields}`:

```jsonc
{
  "queries": [
    { "id": "summary", "sql": "SELECT total_cy, total_ly, ... FROM (...)" },
    { "id": "stores",  "sql": "SELECT n, cy, ly, v, c FROM (...) ORDER BY cy DESC" }
  ],
  "data_blocks": [
    { "block_id": "data_summary", "query_id": "summary",
      "schema": { "shape": "object", "fields": ["total_cy", "total_ly", "var_pct", "lojas"] } },
    { "block_id": "data_stores",  "query_id": "stores",
      "schema": { "shape": "array",  "fields": ["n", "cy", "ly", "v", "c"] } }
  ],
  "original_period": { "start": "2026-01-01", "end": "2026-04-27" }
}
```

- `shape: "array"` — bloco recebe a lista de rows como veio do BQ. JS faz `JSON.parse` e itera.
- `shape: "object"` — query DEVE retornar exatamente 1 row. O servidor desembrulha pra `{...}` antes de gravar. JS lê como objeto.
- `fields` — lista de campos obrigatórios em cada row. Validação roda em publish E em refresh; mismatch falha alta com nome do campo faltante.

### Comparativo CY vs LY — fazer em SQL

A regra "comparação sempre vs LY" continua. A diferença: o cálculo do delta vai pra dentro do SQL. Padrão:

```sql
WITH cy AS (SELECT ..., SUM(...) AS cy_val FROM ... WHERE data BETWEEN '{{start_date}}' AND '{{end_date}}' GROUP BY ...),
     ly AS (SELECT ..., SUM(...) AS ly_val FROM ... WHERE data BETWEEN DATE_SUB(DATE '{{start_date}}', INTERVAL 1 YEAR)
                                                                    AND DATE_SUB(DATE '{{end_date}}',   INTERVAL 1 YEAR) GROUP BY ...)
SELECT cy.dim, cy.cy_val AS cy, ly.ly_val AS ly, SAFE_DIVIDE(cy.cy_val - ly.ly_val, ly.ly_val) * 100 AS v
FROM cy LEFT JOIN ly USING (dim)
ORDER BY cy DESC
```

O placeholder `'{{start_date}}'` / `'{{end_date}}'` é substituído com a string ISO; LY se calcula com `DATE_SUB(..., INTERVAL 1 YEAR)` direto na query.

### Anti-padrões (vão quebrar refresh)

- ❌ Agregar em Python e jogar dict pronto no HTML sem schema correspondente.
- ❌ Mesma query mapeada pra 2 blocks com shapes diferentes.
- ❌ JS que faz `data.reduce(...)` pra calcular total — total deve vir da SQL.
- ❌ Schema declarado com campo `venda` mas SQL retornando `venda_liquida`.
```

- [ ] **Step 3: Verify the file still parses (no broken markdown)**

```bash
head -40 agents/vendas-linx/src/agent/context/SKILL.md
wc -l agents/vendas-linx/src/agent/context/SKILL.md
```

Expected: file size grew, no obvious truncation, frontmatter intact.

- [ ] **Step 4: Commit**

```bash
git add agents/vendas-linx/src/agent/context/SKILL.md
git commit -m "$(cat <<'EOF'
docs(vendas-linx): codify SQL-as-transformation contract for refresh

New convention: every data_block declares shape+fields; SQL produces the
exact shape JS renders; LY comparison happens in SQL via DATE_SUB. Calls
out the anti-patterns that caused the maria-fil 2026-04-28 incident.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Rebuild the broken Maria Filó analysis as a proof of concept

**Files:**
- New: `scripts/rebuild_maria_filo.py` (one-shot script, can delete after)

The broken analysis `maria-fil-venda-por-loja-e-categoria-ytd-2026-366a05c2` is in production with a refresh_spec that violates the new contract. We need to either rebuild it or delete it. Rebuild is more useful as a proof point — it validates that an HTML following the new convention actually refreshes correctly.

- [ ] **Step 1: Write the rebuild script**

Create `scripts/rebuild_maria_filo.py`:

```python
"""One-shot: rebuild the broken Maria Filó analysis using the new schema-
contract convention. Deletes the existing row + blob, publishes a fresh
analysis with two queries (summary, stores) following the schema rules.

Usage:
    DATABASE_URL=$(railway variables --json | jq -r .DATABASE_URL) \\
    BLOB_READ_WRITE_TOKEN=... \\
    python scripts/rebuild_maria_filo.py
"""
from __future__ import annotations
import asyncio
import os

from mcp_core import db, analyses_repo
from mcp_core.refresh_spec import RefreshSpec
from mcp_core.blob_client import BlobClient


OLD_ID = "maria-fil-venda-por-loja-e-categoria-ytd-2026-366a05c2"


SUMMARY_SQL = """
WITH cy AS (
  SELECT SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS total,
         COUNT(DISTINCT v.CODIGO_FILIAL_DESTINO) AS lojas
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  WHERE v.DATA_VENDA BETWEEN '{{start_date}}' AND '{{end_date}}'
    AND v.TIPO_VENDA = 'VENDA_LOJA' AND CAST(v.RL_DESTINO AS STRING) = '15'
),
ly AS (
  SELECT SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS total
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  WHERE v.DATA_VENDA BETWEEN DATE_SUB(DATE '{{start_date}}', INTERVAL 1 YEAR)
                          AND DATE_SUB(DATE '{{end_date}}',   INTERVAL 1 YEAR)
    AND v.TIPO_VENDA = 'VENDA_LOJA' AND CAST(v.RL_DESTINO AS STRING) = '15'
)
SELECT cy.total AS total_cy, ly.total AS total_ly,
       SAFE_DIVIDE(cy.total - ly.total, ly.total) * 100 AS var_pct,
       cy.lojas AS lojas
FROM cy CROSS JOIN ly
"""

STORES_SQL = """
WITH cy AS (
  SELECT f.FILIAL AS n, SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS cy_val,
         ARRAY_AGG(STRUCT(COALESCE(p.LINHA,'SEM LINHA') AS l, COALESCE(p.GRUPO_PRODUTO,'SEM GRUPO') AS g)
                   ORDER BY SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC) DESC LIMIT 3) AS c
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
  LEFT JOIN `soma-pipeline-prd.silver_linx.PRODUTOS` p ON v.PRODUTO = p.PRODUTO
  WHERE v.DATA_VENDA BETWEEN '{{start_date}}' AND '{{end_date}}'
    AND v.TIPO_VENDA = 'VENDA_LOJA' AND CAST(v.RL_DESTINO AS STRING) = '15'
  GROUP BY f.FILIAL
),
ly AS (
  SELECT f.FILIAL AS n, SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS ly_val
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
  WHERE v.DATA_VENDA BETWEEN DATE_SUB(DATE '{{start_date}}', INTERVAL 1 YEAR)
                          AND DATE_SUB(DATE '{{end_date}}',   INTERVAL 1 YEAR)
    AND v.TIPO_VENDA = 'VENDA_LOJA' AND CAST(v.RL_DESTINO AS STRING) = '15'
  GROUP BY f.FILIAL
)
SELECT cy.n, cy.cy_val AS cy, ly.ly_val AS ly,
       SAFE_DIVIDE(cy.cy_val - ly.ly_val, ly.ly_val) * 100 AS v,
       cy.c
FROM cy LEFT JOIN ly USING (n)
ORDER BY cy DESC
"""


HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Maria Filó · Venda por Loja e Categoria · YTD 2026</title>
<style>body{font-family:system-ui;padding:24px;max-width:960px;margin:auto}
.kpi{display:flex;gap:24px;margin-bottom:24px}.k{padding:16px;border:1px solid #ddd;border-radius:8px;flex:1}
.kt{font-size:28px;font-weight:600}.kv{font-size:14px;margin-top:4px}.pos{color:#0a7c2f}.neg{color:#b03a2e}
table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #eee;text-align:left}
.p1{background:#fff5e1;padding:2px 6px;border-radius:4px;font-size:12px}
.p2{background:#e1f0ff;padding:2px 6px;border-radius:4px;font-size:12px;margin-left:4px}
.p3{background:#f0f0f0;padding:2px 6px;border-radius:4px;font-size:12px;margin-left:4px}</style>
</head><body>
<h1>Maria Filó · Venda por Loja e Categoria · YTD 2026</h1>
<div class="kpi">
  <div class="k"><div id="kt" class="kt"></div><div id="kv" class="kv"></div><div id="kly" class="kv" style="color:#666"></div></div>
  <div class="k"><div id="klj" class="kt"></div><div class="kv">lojas ativas</div></div>
</div>
<table><thead><tr><th>#</th><th>Loja</th><th>Venda CY</th><th>vs LY</th><th>Top categorias</th></tr></thead><tbody id="tb"></tbody></table>
<script id="data_summary" type="application/json">{}</script>
<script id="data_stores" type="application/json">[]</script>
<script>
function fmt(v){if(v>=1e6)return'R$ '+(v/1e6).toFixed(1)+'M';if(v>=1e3)return'R$ '+Math.round(v/1e3)+'K';return'R$ '+Math.round(v)}
function vc(v){return v>0?'pos':v<0?'neg':''}
function vs(v){if(v===null||v===undefined)return'—';return(v>0?'+':'')+v.toFixed(1)+'%'}
var S=JSON.parse(document.getElementById('data_summary').textContent);
var D=JSON.parse(document.getElementById('data_stores').textContent);
document.getElementById('kt').textContent=S.total_cy?'R$ '+(S.total_cy/1e6).toFixed(1)+'M':'—';
var ve=document.getElementById('kv');ve.textContent=vs(S.var_pct);ve.className='kv '+vc(S.var_pct);
document.getElementById('kly').textContent=S.total_ly?'LY: R$ '+(S.total_ly/1e6).toFixed(1)+'M':'';
document.getElementById('klj').textContent=S.lojas;
var rows='';D.forEach(function(s,i){
  var cls=['p1','p2','p3'];
  var pills=(s.c||[]).map(function(c,ci){return'<span class="'+cls[ci]+'">'+c.l+' · '+c.g+'</span>';}).join('');
  rows+='<tr><td style="color:#999;font-size:11px">'+(i+1)+'</td><td>'+s.n+'</td><td>'+fmt(s.cy)+'</td><td class="'+vc(s.v)+'">'+vs(s.v)+'</td><td>'+pills+'</td></tr>';
});
document.getElementById('tb').innerHTML=rows;
</script>
</body></html>"""


async def main():
    await db.init_pool(os.environ["DATABASE_URL"])

    spec = RefreshSpec.model_validate({
        "queries": [
            {"id": "summary", "sql": SUMMARY_SQL},
            {"id": "stores",  "sql": STORES_SQL},
        ],
        "data_blocks": [
            {"block_id": "data_summary", "query_id": "summary",
             "schema": {"shape": "object", "fields": ["total_cy", "total_ly", "var_pct", "lojas"]}},
            {"block_id": "data_stores",  "query_id": "stores",
             "schema": {"shape": "array",  "fields": ["n", "cy", "ly", "v", "c"]}},
        ],
        "original_period": {"start": "2026-01-01", "end": "2026-04-27"},
    })

    async with db.transaction() as conn:
        old = await analyses_repo.get(conn, OLD_ID)
        if old is None:
            print(f"No row for {OLD_ID}; nothing to delete.")
        else:
            await analyses_repo.delete(conn, OLD_ID)
            print(f"Deleted old row {OLD_ID}")

    blob = BlobClient()
    pathname = f"analyses/vendas-linx/{OLD_ID}.html"
    # Pre-fill the data blocks with empty shells so the agent's first refresh
    # populates them. The user clicks "Atualizar período" to render real data.
    blob_url = await blob.put(pathname, HTML.encode("utf-8"), content_type="text/html")

    async with db.transaction() as conn:
        await analyses_repo.insert(conn, analyses_repo.AnalysisRow(
            id=OLD_ID, agent_slug="vendas-linx", author_email="abitlemos@gmail.com",
            title="Maria Filó · Venda por Loja e Categoria · YTD 2026",
            brand="Maria Filó",
            period_label="2026-01-01 a 2026-04-27",
            description="Ranking de lojas por venda líquida YTD 2026 com top 3 categorias por loja e comparativo vs LY. Canal físico.",
            tags=["maria-filo", "loja", "categoria", "ytd", "ranking"],
            blob_pathname=pathname,
            blob_url=blob_url,
            refresh_spec=spec.model_dump(mode="json"),
        ))
    print(f"Rebuilt {OLD_ID} with new schema contract. Click 'Atualizar período' in the portal to populate.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the script against production**

```bash
cd /Users/arturlemos/Documents/bq-analista
DATABASE_URL=$(railway variables --json | python3 -c "import sys,json;print(json.load(sys.stdin)['DATABASE_URL'])") \
BLOB_READ_WRITE_TOKEN=$(railway variables --json | python3 -c "import sys,json;print(json.load(sys.stdin).get('BLOB_READ_WRITE_TOKEN',''))") \
uv run --package mcp-core python scripts/rebuild_maria_filo.py
```

Expected: `Rebuilt maria-fil-... with new schema contract.`

- [ ] **Step 3: Trigger a refresh from the portal and confirm**

Open the portal → Maria Filó analysis → "Atualizar período" → leave period as YTD → save. The dashboard should now render real numbers (no `undefined`).

If `undefined` appears anywhere, STOP and run systematic-debugging — the issue is not in this plan but in the HTML/SQL contract; report findings before continuing.

- [ ] **Step 4: Commit the script**

```bash
git add scripts/rebuild_maria_filo.py
git commit -m "$(cat <<'EOF'
chore(scripts): one-shot rebuild for maria-filo analysis with schema contract

Deletes + republishes the analysis using two queries (summary/stores) that
each produce exactly the shape declared in the schema. Used to validate the
schema-contract refactor against a real production case. Safe to delete
after the portal refresh proves green.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8 (OPTIONAL): Headless smoke test in CI

**Files:**
- New: `packages/mcp-core/tests/test_smoke_render.py`

This is the safety net: after publish or refresh, render the HTML in a JS engine and assert no `undefined` shows up in the body and no JS errors fire. Catches the class of bug where the schema validates but the JS expects a different field name than the SQL produced.

If the team's CI doesn't already have a Node + jsdom or playwright setup, this task is non-trivial — flag it and skip on first pass.

- [ ] **Step 1: Decide test runner**

Check if the repo already has Node available in CI:

```bash
cat .github/workflows/*.yml 2>/dev/null | grep -i 'node\|playwright\|jsdom'
```

If yes → use `playwright` (Python binding) for headless render.
If no → defer this task; document it in `docs/superpowers/specs/2026-04-28-refresh-smoke-test.md` for a follow-up plan.

- [ ] **Step 2 (if proceeding): Write the smoke test**

```python
# packages/mcp-core/tests/test_smoke_render.py
import pytest
import asyncio
from playwright.async_api import async_playwright


SAMPLE_HTML = """<!doctype html><html><body><div id="t"></div>
<script id="data_x" type="application/json">{"v":42}</script>
<script>document.getElementById('t').textContent=JSON.parse(document.getElementById('data_x').textContent).v;</script>
</body></html>"""


@pytest.mark.asyncio
async def test_smoke_no_undefined_in_body():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.set_content(SAMPLE_HTML)
        body_text = await page.locator("body").inner_text()
        await browser.close()

    assert "undefined" not in body_text.lower()
    assert errors == [], f"JS errors: {errors}"
```

- [ ] **Step 3: Add to CI**

(Specifics depend on existing CI; flag for human review.)

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/tests/test_smoke_render.py
git commit -m "test(smoke): headless render asserts no undefined + no JS errors

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `cd packages/mcp-core && uv run pytest -v` — all tests green
- [ ] `git log --oneline -10` — commits in expected order, none amended
- [ ] Manual: in the portal, refresh the rebuilt Maria Filó analysis with a different period (e.g., MTD April) — numbers update, no `undefined`, no JS console errors
- [ ] Manual: try publishing a deliberately-broken analysis (HTML embeds `[{"foo":1}]`, schema declares `fields=["bar"]`) via the agent — `publicar_dashboard` returns `{"error": "refresh_spec_invalid: ..."}`
- [ ] Spot-check: an existing pre-Task-1 analysis with no `schema` field still refreshes successfully (legacy path)

## Out of Scope (intentional)

- Migrating existing legacy analyses to declared schemas — they keep working with the legacy pass-through path. Migration is per-analysis as users hit the rebuild flow.
- Changing the refresh API surface — `POST /api/refresh/{id}` shape and status codes are unchanged.
- Two-phase blob commit (write to temp path, atomic swap) — the existing same-path overwrite is acceptable now that schema validation gates the write. Revisit if we see partial writes in prod.
- Schema versioning (e.g., `schema_version: 2`) — not needed yet because the schema field is additive and optional.
