import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from mcp_core.allowlist import Allowlist
from mcp_core.auth_routes import _pending_states, build_auth_app
from mcp_core.azure_auth import AzureTokenInfo
from mcp_core.jwt_tokens import TokenIssuer


def _app(allowlist_emails: list[str]) -> TestClient:
    azure = MagicMock()
    azure.authorization_url.side_effect = lambda state: (
        f"https://login.microsoftonline.com/fake?state={state}"
    )
    azure.exchange_code.return_value = AzureTokenInfo(
        email="exec@azzas.com.br", aad_access_token="aad", expires_in_s=3600
    )
    issuer = TokenIssuer(
        secret="s", allow_short_secret=True,
        issuer="mcp", access_ttl_s=60, refresh_ttl_s=120,
    )

    tmp = Path(tempfile.mkstemp(suffix=".json")[1])
    tmp.write_text(json.dumps({"allowed_emails": allowlist_emails}))

    return TestClient(
        build_auth_app(azure=azure, issuer=issuer, allowlist=Allowlist(path=tmp))
    )


def _start_and_get_state(client: TestClient) -> str:
    """Drive /auth/start and return the state token stored in _pending_states."""
    r = client.get("/auth/start", follow_redirects=False)
    assert r.status_code == 302
    location = r.headers["location"]
    qs = parse_qs(urlparse(location).query)
    return qs["state"][0]


def test_start_redirects_to_azure() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/start", follow_redirects=False)
    assert r.status_code == 302
    assert "microsoftonline.com" in r.headers["location"]


def test_start_includes_state_in_redirect() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/start", follow_redirects=False)
    location = r.headers["location"]
    qs = parse_qs(urlparse(location).query)
    assert "state" in qs
    assert len(qs["state"][0]) > 0


def test_callback_returns_tokens_for_allowed_exec() -> None:
    c = _app(["exec@azzas.com.br"])
    state = _start_and_get_state(c)
    r = c.get(f"/auth/callback?code=abc&state={state}")
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert r.json()["refresh_token"]


def test_callback_rejects_unauthorized_exec() -> None:
    c = _app(["other@azzas.com.br"])
    state = _start_and_get_state(c)
    r = c.get(f"/auth/callback?code=abc&state={state}")
    assert r.status_code == 403


def test_refresh_returns_new_access() -> None:
    c = _app(["exec@azzas.com.br"])
    state = _start_and_get_state(c)
    r = c.get(f"/auth/callback?code=abc&state={state}")
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


# --- CSRF state validation tests ---


def test_callback_missing_state_returns_400() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/callback?code=abc")
    assert r.status_code == 400
    assert "state" in r.json()["detail"]


def test_callback_unknown_state_returns_400() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/callback?code=abc&state=totally-unknown-state")
    assert r.status_code == 400
    assert "state" in r.json()["detail"]


def test_callback_expired_state_returns_400() -> None:
    _pending_states.clear()
    c = _app(["exec@azzas.com.br"])
    state = _start_and_get_state(c)
    # Backdate the stored timestamp by more than 10 minutes
    _pending_states[state] = time.time() - 601
    r = c.get(f"/auth/callback?code=abc&state={state}")
    assert r.status_code == 400
    assert "expired" in r.json()["detail"]


def test_callback_state_is_single_use() -> None:
    """A valid state token must be rejected on the second use."""
    c = _app(["exec@azzas.com.br"])
    state = _start_and_get_state(c)
    r1 = c.get(f"/auth/callback?code=abc&state={state}")
    assert r1.status_code == 200
    # Second request with same state must fail
    r2 = c.get(f"/auth/callback?code=abc&state={state}")
    assert r2.status_code == 400
