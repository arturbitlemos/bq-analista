from __future__ import annotations
import json
import re
from decimal import Decimal
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_core.refresh_spec import DataBlockSchema, RefreshSpec


class _SafeEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)

# Translate table for JSON output going inside <script type="application/json">.
# Prevents content from breaking out of the script tag (XSS) or breaking JSON parsing
# in some browsers (U+2028/U+2029 are valid in JSON but invalid in JS source).
_HTML_SCRIPT_ESCAPES = str.maketrans({
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    "\u2028": "\\u2028",
    "\u2029": "\\u2029",
})


def encode_for_script_tag(value: Any) -> str:
    """JSON-encode safely for embedding inside <script type=application/json>."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), cls=_SafeEncoder).translate(_HTML_SCRIPT_ESCAPES)


def make_data_block(block_id: str, payload: Any) -> str:
    """Produces the canonical <script id="..." type="application/json">…</script> form
    expected by swap_data_blocks. The agent should always use this helper instead of
    hand-writing the tag — variations in attribute order or whitespace will defeat the
    refresh swap regex."""
    encoded = encode_for_script_tag(payload)
    return f'<script id="{block_id}" type="application/json">{encoded}</script>'


def _block_pattern(block_id: str) -> re.Pattern[str]:
    return re.compile(
        rf'(<script\s+id="{re.escape(block_id)}"\s+type="application/json">)(.*?)(</script>)',
        re.DOTALL,
    )


def validate_blocks_present(html: str, block_ids: list[str]) -> None:
    """Raise ValueError if any expected block_id is missing from html."""
    missing = [b for b in block_ids if not _block_pattern(b).search(html)]
    if missing:
        raise ValueError(f"HTML missing required <script id=...> blocks: {missing}")


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
        # Object-shape blocks are stored as `{...}` directly in the HTML; wrap
        # the dict to a 1-element list so validate_payload_schema's uniform
        # list-of-rows interface can validate it. If the HTML embeds a list
        # when object was declared (i.e. the agent shipped the wrong shape),
        # leave it as-is so the validator reports the accurate "expected 1
        # row, got N" message instead of the misleading "single row is not
        # an object".
        if ref.schema_.shape == "object" and not isinstance(payload, list):
            normalized = [payload]
        else:
            normalized = payload
        validate_payload_schema(ref.block_id, normalized, ref.schema_)
