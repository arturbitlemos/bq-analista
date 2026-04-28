from __future__ import annotations
import json
from typing import Any
import asyncpg


async def record(
    conn: asyncpg.Connection,
    *,
    action: str,
    actor_email: str,
    analysis_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a row to the Postgres audit_log table tracking portal actions
    (publish, refresh, share, archive, etc.).

    Distinct from the SQLite-based mcp_core.audit module, which tracks individual
    BigQuery query executions (bytes_scanned, duration). This module tracks user
    actions on published analyses.

    Caller responsibilities: pass an `asyncpg.Connection` already inside a
    transaction (typically via `mcp_core.db.transaction()`). This helper does NOT
    begin/commit on its own — the audit row should commit/rollback together with
    whatever business operation triggered it (e.g., publish writes the analyses
    row + audit in one tx).
    """
    await conn.execute(
        "INSERT INTO audit_log (action, actor_email, analysis_id, metadata) VALUES ($1, $2, $3, $4)",
        action,
        actor_email,
        analysis_id,
        json.dumps(metadata) if metadata is not None else None,
    )
