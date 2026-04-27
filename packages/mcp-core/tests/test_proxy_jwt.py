import os
import time
import pytest
import jwt as pyjwt

from mcp_core.proxy_jwt import verify_proxy_jwt


def _mint(email: str, secret: str, *, exp_in: int = 60, aud: str = "mcp-core-proxy") -> str:
    return pyjwt.encode(
        {"email": email, "aud": aud, "exp": int(time.time()) + exp_in},
        secret, algorithm="HS256",
    )


def test_verify_returns_email(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    token = _mint("a@b.com", "secret123")
    assert verify_proxy_jwt(token) == "a@b.com"


def test_verify_rejects_wrong_audience(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    token = _mint("a@b.com", "secret123", aud="other")
    with pytest.raises(ValueError, match="audience"):
        verify_proxy_jwt(token)


def test_verify_rejects_expired(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    token = _mint("a@b.com", "secret123", exp_in=-10)
    with pytest.raises(ValueError, match="expired"):
        verify_proxy_jwt(token)


def test_verify_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "right")
    token = _mint("a@b.com", "wrong")
    with pytest.raises(ValueError, match="signature"):
        verify_proxy_jwt(token)


def test_verify_rejects_missing_email(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    token = pyjwt.encode(
        {"aud": "mcp-core-proxy", "exp": int(time.time()) + 60},
        "secret123", algorithm="HS256",
    )
    with pytest.raises(ValueError, match="missing email"):
        verify_proxy_jwt(token)
