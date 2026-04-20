from __future__ import annotations

import secrets

import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

from mcp_exec.allowlist import Allowlist
from mcp_exec.azure_auth import AzureAuth, AzureAuthError
from mcp_exec.jwt_tokens import TokenError, TokenIssuer


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            logger.info(f"{request.method} {request.url.path} {request.headers.get('authorization', 'no-auth')}")
        return await call_next(request)


def build_auth_app(
    *,
    azure: AzureAuth,
    issuer: TokenIssuer,
    allowlist: Allowlist,
    lifespan=None,
) -> FastAPI:
    # redirect_slashes=False prevents FastAPI from redirecting /mcp → /mcp/
    app = FastAPI(redirect_slashes=False, lifespan=lifespan)
    app.add_middleware(LoggingMiddleware)

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

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/mcp-info")
    def mcp_info() -> dict:
        """Debug endpoint to verify MCP server is responding."""
        return {
            "name": "mcp-exec-azzas",
            "version": "1.0",
            "status": "ok",
            "auth_required": True,
            "message": "Use Bearer token to access /mcp SSE endpoint",
        }

    @app.get("/.well-known/oauth-authorization-server")
    def oauth_metadata(req: Request) -> dict:
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

    @app.get("/.well-known/oauth-protected-resource/mcp")
    def oauth_protected_resource() -> dict:
        """OAuth 2.0 Protected Resource Metadata for Claude.ai MCP integration."""
        return {
            "resource": "mcp-exec-azzas",
            "uri": "/mcp",
            "access_token_type": "Bearer",
            "auth_required": True,
        }

    return app
