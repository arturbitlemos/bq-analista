import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from mcp_core.allowlist import Allowlist
from mcp_core.auth_routes import _pending_exchanges, _pending_states, build_auth_app
from mcp_core.azure_auth import AzureTokenInfo
from mcp_core.jwt_tokens import TokenIssuer


@pytest.fixture(autouse=True)
def _isolate_pending_states():
    """Module-level state stores are cleared before AND after each test
    so leftover entries from one test never leak into another."""
    _pending_states.clear()
    _pending_exchanges.clear()
    yield
    _pending_states.clear()
    _pending_exchanges.clear()


def _exchange_code_from_callback(client: TestClient, code: str, state: str) -> str:
    """Drive /auth/callback and pull the exchange code out of the HTML page."""
    import re

    r = client.get(f"/auth/callback?code={code}&state={state}")
    assert r.status_code == 200, r.text
    assert "text/html" in r.headers["content-type"]
    m = re.search(r"code=([A-Za-z0-9_-]+)", r.text)
    assert m, f"exchange code not found in HTML: {r.text}"
    return m.group(1)


def _login(client: TestClient) -> dict:
    """Full login flow: start → callback → token. Returns token JSON."""
    state = _start_and_get_state(client)
    exchange = _exchange_code_from_callback(client, "abc", state)
    r = client.post("/auth/token", json={"code": exchange})
    assert r.status_code == 200, r.text
    return r.json()


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


def test_callback_returns_html_without_tokens() -> None:
    """Tokens must not appear in the HTML response body — they live behind the
    single-use exchange code that the OAuth client redeems via /auth/token."""
    c = _app(["exec@azzas.com.br"])
    state = _start_and_get_state(c)
    r = c.get(f"/auth/callback?code=abc&state={state}")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    # No JWT-shaped substring in the HTML (would indicate a leak)
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert "eyJ" not in body  # JWT prefix


def test_token_endpoint_redeems_exchange_code() -> None:
    c = _app(["exec@azzas.com.br"])
    tok = _login(c)
    assert tok["access_token"]
    assert tok["refresh_token"]
    assert tok["email"] == "exec@azzas.com.br"
    assert tok["token_type"] == "Bearer"


def test_token_endpoint_accepts_form_encoded() -> None:
    """OAuth 2.0 standard token endpoint uses application/x-www-form-urlencoded."""
    c = _app(["exec@azzas.com.br"])
    state = _start_and_get_state(c)
    code = _exchange_code_from_callback(c, "abc", state)
    r = c.post("/auth/token", data={"code": code})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_exchange_code_is_single_use() -> None:
    c = _app(["exec@azzas.com.br"])
    state = _start_and_get_state(c)
    code = _exchange_code_from_callback(c, "abc", state)
    r1 = c.post("/auth/token", json={"code": code})
    assert r1.status_code == 200
    # Replaying the exchange code must fail
    r2 = c.post("/auth/token", json={"code": code})
    assert r2.status_code == 400


def test_token_endpoint_rejects_unknown_code() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.post("/auth/token", json={"code": "not-a-real-code"})
    assert r.status_code == 400


def test_token_endpoint_missing_code_returns_422() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.post("/auth/token", json={"other": "field"})
    assert r.status_code == 422


def test_callback_rejects_unauthorized_exec() -> None:
    c = _app(["other@azzas.com.br"])
    state = _start_and_get_state(c)
    r = c.get(f"/auth/callback?code=abc&state={state}")
    assert r.status_code == 403


def test_refresh_returns_new_access_and_rotates() -> None:
    c = _app(["exec@azzas.com.br"])
    tok = _login(c)
    r2 = c.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r2.status_code == 200
    assert r2.json()["access_token"]
    # Refresh token rotates: old token must no longer work
    assert r2.json()["refresh_token"] != tok["refresh_token"]
    r3 = c.post("/auth/refresh", json={"refresh_token": tok["refresh_token"]})
    assert r3.status_code == 401  # reuse → family revoked


def test_oauth_metadata_token_endpoint_points_to_token_route() -> None:
    """Regression guard: the discovered token_endpoint must NOT be /auth/callback
    (which is the browser-facing redirect handler, not a token endpoint)."""
    c = _app(["exec@azzas.com.br"])
    r = c.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    body = r.json()
    assert body["token_endpoint"].endswith("/auth/token")
    assert not body["token_endpoint"].endswith("/auth/callback")
    assert "refresh_token" in body["grant_types_supported"]


def test_token_endpoint_accepts_refresh_token_grant() -> None:
    """POST /auth/token with grant_type=refresh_token should rotate and return new tokens."""
    c = _app(["exec@azzas.com.br"])
    tok = _login(c)
    r = c.post("/auth/token", json={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"] != tok["refresh_token"]
    assert "expires_in" in body


def test_token_endpoint_refresh_grant_form_encoded() -> None:
    c = _app(["exec@azzas.com.br"])
    tok = _login(c)
    r = c.post("/auth/token", data={"grant_type": "refresh_token", "refresh_token": tok["refresh_token"]})
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_token_endpoint_refresh_grant_invalid_token() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.post("/auth/token", json={"grant_type": "refresh_token", "refresh_token": "invalid"})
    assert r.status_code == 400


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
