"""Refresh handler: re-run an analysis's saved queries with a new period and
swap fresh data into the HTML stored in Vercel Blob, all atomically with the
Postgres analyses + audit_log update.

Failure surfaces:
- 403 (RefreshError): caller is not the author
- 404: analysis not found
- 409: another refresh holds the advisory lock for this id
- 422: analysis has no refresh_spec (not refreshable)
- 500: HTML swap failed (missing blocks, malformed)
- 502 (raised as _BqError): BigQuery rejected one of the queries

The 502 path is special: the outer transaction is rolled back so the analyses
row keeps its old period/last_refreshed_at, but the API layer must record the
error in a SEPARATE transaction (after rollback) by catching _BqError and
calling analyses_repo.set_refresh_error.
"""
from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass
from datetime import date

from mcp_core import db, analyses_repo, actions_audit
from mcp_core.refresh_spec import RefreshSpec
from mcp_core.html_swap import swap_data_blocks, swap_period_block, make_period_payload


@dataclass
class RefreshResult:
    last_refreshed_at: str
    period_start: date
    period_end: date


class RefreshError(Exception):
    """Refresh failed for a deterministic reason (auth, validation, lock)."""
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class _BqError(Exception):
    """BigQuery rejected a query — surfaces as 502 at the API layer.

    Internal sentinel: kept distinct from RefreshError so the API layer can
    record the error in a fresh transaction after the outer one rolls back."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


async def refresh_analysis(
    *,
    analysis_id: str,
    actor_email: str,
    start: date,
    end: date,
    bq,
    blob,
) -> RefreshResult:
    """Run the refresh inside one Postgres transaction.

    `bq` must expose `run_query(sql, exec_email)` returning an object with
    `.rows: list[dict]` (matches mcp_core.bq_client.BqClient).
    `blob` must expose async `get(pathname)`/`put(pathname, body, content_type)`
    returning the blob URL on put."""

    if start > end:
        raise RefreshError(400, "start must be <= end")

    # Phase 1 — inside the DB transaction: validate, run queries, render new
    # HTML, update DB metadata, write audit log. Crucially we do NOT touch the
    # blob in here: if any DB statement after a blob.put failed, we'd end up
    # with a blob containing fresh data while the DB still pointed to the old
    # period, which is the bad failure mode. Phase 2 (the blob.put) happens
    # after the transaction commits, so the worst case is "DB says new period
    # but blob still has old HTML" — same content, just a stale render the
    # user can fix by retrying the refresh (idempotent at same pathname).
    _t0 = time.monotonic()
    async with db.transaction() as conn:
        got_lock = await analyses_repo.try_acquire_refresh_lock(conn, analysis_id)
        if not got_lock:
            raise RefreshError(409, "refresh already in progress")

        row = await analyses_repo.get(conn, analysis_id)
        if row is None:
            raise RefreshError(404, "analysis not found")
        if row.author_email != actor_email:
            raise RefreshError(403, "only author can refresh")
        if row.refresh_spec is None:
            raise RefreshError(422, "analysis has no refresh_spec; not refreshable")

        spec = RefreshSpec.model_validate(row.refresh_spec)

        # Run queries — BqClient is sync, so dispatch to a thread.
        # If anything fails we raise _BqError; outer `async with db.transaction()`
        # rolls back automatically. The API layer records the error separately.
        results: dict[str, list[dict]] = {}
        for q in spec.queries:
            rendered = q.render(start=start, end=end)
            try:
                bq_result = await asyncio.to_thread(bq.run_query, rendered, actor_email)
            except Exception as e:
                raise _BqError(str(e)[:500]) from e
            results[q.id] = list(bq_result.rows)

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
        # Soft-swap the reserved __period__ block so header/footer period labels
        # stay in sync with the new range. No-op for legacy reports.
        new_html = swap_period_block(new_html, make_period_payload(start, end))

        await analyses_repo.update_refresh_state(
            conn, analysis_id,
            period_start=start, period_end=end, actor_email=actor_email,
        )
        await actions_audit.record(
            conn, action="refresh", actor_email=actor_email,
            analysis_id=analysis_id,
            metadata={
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "queries_run": len(spec.queries),
                "duration_ms": round((time.monotonic() - _t0) * 1000),
            },
        )

        updated = await analyses_repo.get(conn, analysis_id)
        assert updated is not None and updated.last_refreshed_at is not None
        blob_pathname = row.blob_pathname
        old_blob_url = row.blob_url

    # Phase 2 — DB has committed. Overwrite the blob at the same pathname.
    # Failure here means the user sees stale HTML with a new period label
    # until they retry; safer than the inverse (fresh HTML / old period).
    new_blob_url = await blob.put(blob_pathname, new_html.encode("utf-8"), content_type="text/html")

    # Phase 3 — if the URL host/suffix changed (shouldn't with a stable
    # store + no random suffix, but defensive), record the new URL.
    if new_blob_url and new_blob_url != old_blob_url:
        async with db.transaction() as conn:
            await analyses_repo.update_blob_url(conn, analysis_id, blob_url=new_blob_url)

    return RefreshResult(
        last_refreshed_at=updated.last_refreshed_at.isoformat(),
        period_start=updated.period_start,
        period_end=updated.period_end,
    )
