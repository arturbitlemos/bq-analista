from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from mcp_exec.allowlist import Allowlist
from mcp_exec.auth_routes import build_auth_app
from mcp_exec.azure_auth import AzureTokenInfo
from mcp_exec.jwt_tokens import TokenIssuer


def _app(allowlist_emails: list[str]) -> TestClient:
    azure = MagicMock()
    azure.authorization_url.return_value = "https://login.microsoftonline.com/fake"
    azure.exchange_code.return_value = AzureTokenInfo(
        email="exec@azzas.com.br", aad_access_token="aad", expires_in_s=3600
    )
    issuer = TokenIssuer(
        secret="s", allow_short_secret=True,
        issuer="mcp", access_ttl_s=60, refresh_ttl_s=120,
    )

    import tempfile, json
    from pathlib import Path
    tmp = Path(tempfile.mkstemp(suffix=".json")[1])
    tmp.write_text(json.dumps({"allowed_emails": allowlist_emails}))

    return TestClient(
        build_auth_app(azure=azure, issuer=issuer, allowlist=Allowlist(path=tmp))
    )


def test_start_redirects_to_azure() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/start", follow_redirects=False)
    assert r.status_code == 302
    assert "microsoftonline.com" in r.headers["location"]


def test_callback_returns_tokens_for_allowed_exec() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/callback?code=abc&state=xyz")
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert r.json()["refresh_token"]


def test_callback_rejects_unauthorized_exec() -> None:
    c = _app(["other@azzas.com.br"])
    r = c.get("/auth/callback?code=abc&state=xyz")
    assert r.status_code == 403


def test_refresh_returns_new_access() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/callback?code=abc&state=xyz")
    refresh = r.json()["refresh_token"]
    r2 = c.post("/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    assert r2.json()["access_token"]


def test_refresh_missing_token_returns_422() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.post("/auth/refresh", json={"other": "field"})
    assert r.status_code == 422


def test_refresh_invalid_token_returns_401() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert r.status_code == 401
