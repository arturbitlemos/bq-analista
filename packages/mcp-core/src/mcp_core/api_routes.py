"""REST API routes mounted on the auth_app FastAPI app.

Currently only `POST /api/refresh/{analysis_id}`. Kept separate from auth_routes
because these are application-level (analysis lifecycle) and don't share state
with the OAuth flow."""
from __future__ import annotations
from datetime import date

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from mcp_core import db, analyses_repo, actions_audit
from mcp_core.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_core.refresh_handler import refresh_analysis, RefreshError, _BqError


class _RefreshBody(BaseModel):
    start_date: date
    end_date: date


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    return authorization[len("Bearer "):].strip()


def register_api_routes(
    app: FastAPI,
    *,
    auth_ctx: AuthContext,
    bq_factory,
    blob_factory,
) -> None:
    """Register refresh route on the given FastAPI app.

    `bq_factory` is called with no args, returns a BqClient instance.
    `blob_factory` is called with no args, returns a BlobClient instance.
    Both are factories so handlers get fresh instances per request (cheap)."""

    @app.post("/api/refresh/{analysis_id}")
    async def refresh(analysis_id: str, body: _RefreshBody, request: Request,
                       authorization: str | None = Header(None)):
        token = _bearer_token(authorization)
        try:
            email = extract_exec_email(token, auth_ctx)
        except AuthError as e:
            raise HTTPException(401, f"auth: {e}")

        try:
            result = await refresh_analysis(
                analysis_id=analysis_id,
                actor_email=email,
                start=body.start_date,
                end=body.end_date,
                bq=bq_factory(),
                blob=blob_factory(),
            )
            return {
                "ok": True,
                "id": analysis_id,
                "last_refreshed_at": result.last_refreshed_at,
                "period_start": result.period_start.isoformat(),
                "period_end": result.period_end.isoformat(),
            }
        except _BqError as e:
            # Outer transaction has rolled back. Record the error in a fresh tx
            # so the user sees `last_refresh_error` even though period stays old.
            try:
                async with db.transaction() as conn:
                    await analyses_repo.set_refresh_error(conn, analysis_id, error=e.message)
                    await actions_audit.record(
                        conn, action="refresh_failed", actor_email=email,
                        analysis_id=analysis_id,
                        metadata={"error": e.message},
                    )
            except Exception:
                # Best-effort logging — don't mask the original BQ error
                pass
            raise HTTPException(502, f"bigquery: {e.message}")
        except RefreshError as e:
            raise HTTPException(e.status, e.message)
