"""Development server runner (no Azure AD required).

Use for local testing. Production uses main() which requires Azure env vars.
"""

import os
from pathlib import Path

from mcp_exec.allowlist import Allowlist
from mcp_exec.jwt_tokens import TokenIssuer
from mcp_exec.settings import load_settings

from mcp_exec.server import mcp


def dev_main() -> None:
    """Start MCP server for local development (no Azure, mock auth)."""
    import uvicorn
    from fastapi import FastAPI, HTTPException

    settings_path = Path(os.environ.get("MCP_SETTINGS", "./config/settings.toml"))
    settings = load_settings(settings_path)

    # Ensure server.py tool handlers can read these (they access os.environ directly).
    os.environ.setdefault("MCP_JWT_SECRET", "local-dev-secret-1234567890abcdefghij")
    os.environ.setdefault(
        "MCP_ALLOWLIST",
        str((settings_path.parent / "allowed_execs.json").resolve()),
    )
    os.environ.setdefault("MCP_GIT_PUSH", "1")
    issuer = TokenIssuer(
        secret=os.environ["MCP_JWT_SECRET"],
        issuer=settings.auth.jwt_issuer,
        access_ttl_s=settings.auth.access_token_ttl_s,
        refresh_ttl_s=settings.auth.refresh_token_ttl_s,
    )
    allowlist = Allowlist(
        path=Path(os.environ.get("MCP_ALLOWLIST", "./config/allowed_execs.json"))
    )

    # Create FastAPI app with minimal auth (no Azure AD)
    app = FastAPI(title="mcp-exec-dev")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {"status": "ok", "mode": "development"}

    @app.get("/auth/issue-token")
    def issue_token(email: str) -> dict[str, object]:
        """Dev-only: issue a token for an email without Azure AD flow."""
        if not allowlist.is_allowed(email):
            raise HTTPException(status_code=403, detail=f"{email} not in allowlist")
        tokens = issuer.issue(email)
        return {"access_token": tokens.access_token, "email": email}

    app.mount("/mcp", mcp.streamable_http_app())

    print(f"\n✓ Dev server ready (http://{settings.server.host}:{settings.server.port})")
    print(f"  GET  /health                   — health check")
    print(f"  GET  /auth/issue-token?email=X — get token (dev only)")
    print(f"  MCP tools at /mcp/...")
    uvicorn.run(app, host=settings.server.host, port=settings.server.port)


if __name__ == "__main__":
    dev_main()
