from __future__ import annotations

import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mcp_exec.allowlist import Allowlist
from mcp_exec.azure_auth import AzureAuth, AzureAuthError
from mcp_exec.jwt_tokens import TokenInvalidError, TokenIssuer


def build_auth_app(
    *,
    azure: AzureAuth,
    issuer: TokenIssuer,
    allowlist: Allowlist,
) -> FastAPI:
    app = FastAPI()

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
        body = await req.json()
        try:
            access = issuer.refresh(body["refresh_token"])
        except TokenInvalidError as e:
            raise HTTPException(status_code=401, detail=str(e))
        return JSONResponse({"access_token": access})

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
