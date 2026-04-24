from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from mcp_core.allowlist import Allowlist
from mcp_core.azure_auth import AzureAuth, AzureAuthError
from mcp_core.jwt_tokens import TokenError, TokenIssuer

_LifespanT = Callable[[Any], AbstractAsyncContextManager[None]] | None


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
        state = secrets.token_urlsafe(16)
        return RedirectResponse(azure.authorization_url(state=state), status_code=302)

    @app.get("/auth/callback")
    def callback(code: str, state: str | None = None) -> JSONResponse:
        try:
            info = azure.exchange_code(code=code)
        except AzureAuthError as e:
            raise HTTPException(status_code=400, detail=f"azure_auth: {e}")
        if not allowlist.is_allowed(info.email):
            raise HTTPException(status_code=403, detail=f"not on allowlist: {info.email}")
        pair = issuer.issue(email=info.email)
        return JSONResponse({
            "access_token": pair.access_token,
            "refresh_token": pair.refresh_token,
            "expires_at": pair.expires_at,
            "email": info.email,
        })

    @app.post("/auth/refresh")
    async def refresh(req: Request) -> JSONResponse:
        try:
            body = await req.json()
            refresh_token = body["refresh_token"]
        except (ValueError, KeyError, TypeError):
            raise HTTPException(status_code=422, detail="refresh_token required")
        try:
            access = issuer.refresh(refresh_token)
        except TokenError as e:
            raise HTTPException(status_code=401, detail=str(e))
        return JSONResponse({"access_token": access})

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

    @app.get("/.well-known/oauth-authorization-server")
    def oauth_metadata(req: Request) -> dict[str, object]:
        """OAuth 2.0 Authorization Server Metadata (RFC 8414) for Claude.ai discovery."""
        proto = req.headers.get("x-forwarded-proto", "https")
        host = req.headers.get("x-forwarded-host") or req.headers.get("host", "localhost:3000")
        base_url = f"{proto}://{host}"

        return {
            "issuer": base_url,
            "authorization_endpoint": f"{base_url}/auth/start",
            "token_endpoint": f"{base_url}/auth/callback",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "token_endpoint_auth_methods_supported": ["none"],
            "revocation_endpoint_supported": False,
            "introspection_endpoint_supported": False,
        }

    @app.get("/.well-known/oauth-protected-resource")
    def oauth_protected_resource(req: Request) -> dict[str, object]:
        """OAuth 2.0 Protected Resource Metadata (RFC 9728) for Claude.ai discovery."""
        proto = req.headers.get("x-forwarded-proto", "https")
        host = req.headers.get("x-forwarded-host") or req.headers.get("host", "localhost")
        base_url = f"{proto}://{host}"
        return {
            "resource": f"{base_url}/mcp",
            "authorization_servers": [base_url],
            "bearer_methods_supported": ["header"],
            "resource_signing_alg_values_supported": ["RS256"],
        }

    return app
