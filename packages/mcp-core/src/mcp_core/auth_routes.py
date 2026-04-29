from __future__ import annotations

import os
import secrets
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from mcp_core.allowlist import Allowlist
from mcp_core.azure_auth import AzureAuth, AzureAuthError
from mcp_core.jwt_tokens import TokenError, TokenIssuer, TokenPair

_LifespanT = Callable[[Any], AbstractAsyncContextManager[None]] | None

# In-memory CSRF state store: state_token → creation timestamp (time.time()).
# Single-process Railway deployments only — no Redis needed.
_pending_states: dict[str, float] = {}

_STATE_TTL_S = 600  # 10 minutes

# In-memory exchange-code store: code → (TokenPair, email, created_at).
# /auth/callback mints a code and renders an HTML success page (no tokens
# leak to the browser); the OAuth client back-channels POST /auth/token
# to redeem the code for the actual tokens.
_pending_exchanges: dict[str, tuple[TokenPair, str, float]] = {}

_EXCHANGE_TTL_S = 60  # 1 minute — code is meant to be redeemed immediately


def build_auth_app(
    *,
    azure: AzureAuth,
    issuer: TokenIssuer,
    allowlist: Allowlist,
    lifespan: _LifespanT = None,
) -> FastAPI:
    # redirect_slashes=False prevents FastAPI from redirecting /mcp → /mcp/
    app = FastAPI(redirect_slashes=False, lifespan=lifespan)

    @app.get("/auth/start")
    def start() -> RedirectResponse:
        # Prune expired entries
        now = time.time()
        stale = [k for k, v in _pending_states.items() if now - v > _STATE_TTL_S]
        for k in stale:
            del _pending_states[k]

        state = secrets.token_urlsafe(16)
        _pending_states[state] = time.time()
        return RedirectResponse(azure.authorization_url(state=state), status_code=302)

    @app.get("/auth/callback")
    def callback(code: str, state: str | None = None) -> HTMLResponse:
        """Browser-facing OAuth redirect handler.

        Exchanges the Azure code for tokens, then mints a single-use exchange
        code and renders a tokenless HTML page. The OAuth client back-channels
        POST /auth/token with the exchange code to retrieve the actual tokens —
        tokens never reach the browser address bar, history, or response body.
        """
        # CSRF state validation
        if state is None or state not in _pending_states:
            raise HTTPException(status_code=400, detail="invalid_state: missing or unknown state parameter")
        created_at = _pending_states.pop(state)
        if time.time() - created_at > _STATE_TTL_S:
            raise HTTPException(status_code=400, detail="invalid_state: state parameter has expired")

        try:
            info = azure.exchange_code(code=code)
        except AzureAuthError as e:
            raise HTTPException(status_code=400, detail=f"azure_auth: {e}")
        if not allowlist.is_allowed(info.email):
            raise HTTPException(status_code=403, detail="not authorized")
        pair = issuer.issue(email=info.email)

        # Prune expired exchanges before storing the new one
        now = time.time()
        for k in [k for k, v in _pending_exchanges.items() if now - v[2] > _EXCHANGE_TTL_S]:
            del _pending_exchanges[k]
        exchange_code = secrets.token_urlsafe(32)
        _pending_exchanges[exchange_code] = (pair, info.email, now)

        # Surface the exchange code via URL fragment (never sent to the server,
        # per RFC 6749 §3.1.2). OAuth clients listening for window.location.hash
        # pick it up and POST it to /auth/token.
        return HTMLResponse(
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            "<title>Login completo</title>"
            "<style>body{font-family:system-ui;padding:40px;max-width:480px;margin:0 auto;text-align:center}</style>"
            "</head><body>"
            "<h1>Login completo</h1>"
            "<p>Você pode fechar esta janela.</p>"
            "<script>"
            f"window.location.hash='code={exchange_code}';"
            "</script>"
            "</body></html>"
        )

    @app.post("/auth/token")
    async def token_endpoint(req: Request) -> JSONResponse:
        """OAuth 2.0 token endpoint — handles authorization_code and refresh_token grants.

        Accepts both `application/json` and `application/x-www-form-urlencoded`.
        """
        ct = req.headers.get("content-type", "")
        try:
            if "application/json" in ct:
                body: dict[str, object] = await req.json()
            else:
                form = await req.form()
                body = dict(form)
        except Exception:
            raise HTTPException(status_code=422, detail="invalid request body")

        grant_type = body.get("grant_type", "authorization_code")

        if grant_type == "refresh_token":
            refresh_token = body.get("refresh_token")
            if not isinstance(refresh_token, str) or not refresh_token:
                raise HTTPException(status_code=422, detail="refresh_token required")
            try:
                pair = issuer.refresh(refresh_token, allowlist=allowlist)
            except TokenError as e:
                raise HTTPException(status_code=400, detail=str(e))
            return JSONResponse({
                "access_token": pair.access_token,
                "refresh_token": pair.refresh_token,
                "expires_at": pair.expires_at,
                "expires_in": pair.expires_at - int(time.time()),
                "token_type": "Bearer",
            })

        # authorization_code grant — exchange single-use code for tokens
        code = body.get("code")
        if not isinstance(code, str) or not code:
            raise HTTPException(status_code=422, detail="code required")

        entry = _pending_exchanges.pop(code, None)
        if entry is None:
            raise HTTPException(status_code=400, detail="invalid_grant")
        pair, email, created_at = entry
        if time.time() - created_at > _EXCHANGE_TTL_S:
            raise HTTPException(status_code=400, detail="invalid_grant: code expired")

        return JSONResponse({
            "access_token": pair.access_token,
            "refresh_token": pair.refresh_token,
            "expires_at": pair.expires_at,
            "expires_in": pair.expires_at - int(time.time()),
            "email": email,
            "token_type": "Bearer",
        })

    @app.post("/auth/refresh")
    async def refresh(req: Request) -> JSONResponse:
        try:
            body = await req.json()
            refresh_token = body["refresh_token"]
        except (ValueError, KeyError, TypeError):
            raise HTTPException(status_code=422, detail="refresh_token required")
        try:
            pair = issuer.refresh(refresh_token, allowlist=allowlist)
        except TokenError as e:
            raise HTTPException(status_code=401, detail=str(e))
        # Refresh token rotates on every use — clients must persist the new
        # refresh_token; the old one is now consumed and reuse will revoke the chain.
        return JSONResponse({
            "access_token": pair.access_token,
            "refresh_token": pair.refresh_token,
            "expires_at": pair.expires_at,
        })

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> FileResponse:
        repo_root = Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))
        path = repo_root / "portal" / "public" / "assets" / "favicon-32x32.png"
        if not path.exists():
            raise HTTPException(status_code=404, detail="favicon not found")
        return FileResponse(path, media_type="image/png")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok"}

    def _base_url() -> str:
        """Return the canonical public base URL.

        Uses the MCP_PUBLIC_HOST env var (set at deploy time) so attacker-
        controlled request headers cannot redirect OAuth flows to a foreign
        host.  MCP_PUBLIC_PROTO can override the auto-detected scheme; by
        default localhost / 127.0.0.1 / 0.0.0.0 use http and everything else
        uses https. The hostname is exact-matched against the dev set so
        names like "localhost.evil.com" are correctly classified as remote.
        """
        host = os.environ.get("MCP_PUBLIC_HOST", "localhost:3000")
        proto = os.environ.get("MCP_PUBLIC_PROTO")
        if not proto:
            hostname = host.split(":", 1)[0].lower()
            proto = "http" if hostname in {"localhost", "127.0.0.1", "0.0.0.0"} else "https"
        return f"{proto}://{host}"

    @app.get("/.well-known/oauth-authorization-server")
    def oauth_metadata() -> dict[str, object]:
        """OAuth 2.0 Authorization Server Metadata (RFC 8414) for Claude.ai discovery."""
        base_url = _base_url()
        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/auth/start",
            "token_endpoint": f"{base_url}/auth/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["none"],
            "revocation_endpoint_supported": False,
            "introspection_endpoint_supported": False,
        }

    @app.get("/.well-known/oauth-protected-resource")
    def oauth_protected_resource() -> dict[str, object]:
        """OAuth 2.0 Protected Resource Metadata (RFC 9728) for Claude.ai discovery."""
        base_url = _base_url()
        return {
            "resource": f"{base_url}/mcp",
            "authorization_servers": [base_url],
            "bearer_methods_supported": ["header"],
            "resource_signing_alg_values_supported": ["RS256"],
        }

    return app
