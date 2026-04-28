from __future__ import annotations
import json
import re
from decimal import Decimal
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_core.refresh_spec import DataBlockSchema


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


def swap_data_blocks(html: str, payloads: dict[str, Any]) -> str:
    """Replace each <script id="<block_id>" type="application/json"> body with JSON of payloads[block_id].

    Raises ValueError if a block_id is not found, or if the resulting HTML lost the CSP meta tag
    (defensive — should never happen since we never touch <head>)."""
    csp_before = "Content-Security-Policy" in html

    out = html
    for block_id, payload in payloads.items():
        pattern = _block_pattern(block_id)
        match = pattern.search(out)
        if not match:
            raise ValueError(f"block_id {block_id!r} not found in HTML")
        encoded = encode_for_script_tag(payload)
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
