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
    """Append a row to audit_log. Caller controls the transaction.

    Caller responsibilities: pass an `asyncpg.Connection` already inside a transaction
    (typically via `mcp_core.db.transaction()`). This helper does NOT begin/commit on
    its own — the audit row should commit/rollback together with whatever business
    operation triggered it (e.g., publish writes the analyses row + audit in one tx)."""
    await conn.execute(
        "INSERT INTO audit_log (action, actor_email, analysis_id, metadata) VALUES ($1, $2, $3, $4)",
        action,
        actor_email,
        analysis_id,
        json.dumps(metadata) if metadata is not None else None,
    )
