import pytest

from mcp_core.allowlist import Allowlist
from mcp_core.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_core.jwt_tokens import TokenIssuer


def _ctx(tmp_path, allowed: list[str]) -> AuthContext:
    import json
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"allowed_emails": allowed}))
    return AuthContext(
        issuer=TokenIssuer(
            secret="s", allow_short_secret=True,
            issuer="mcp", access_ttl_s=60, refresh_ttl_s=120,
        ),
        allowlist=Allowlist(path=f),
    )


def test_valid_token_returns_email(tmp_path) -> None:
    actx = _ctx(tmp_path, ["e@x.com"])
    token = actx.issuer.issue("e@x.com").access_token
    email = extract_exec_email(token=token, ctx=actx)
    assert email == "e@x.com"


def test_invalid_token_raises(tmp_path) -> None:
    actx = _ctx(tmp_path, ["e@x.com"])
    with pytest.raises(AuthError):
        extract_exec_email(token="nope", ctx=actx)


def test_removed_from_allowlist_raises(tmp_path) -> None:
    actx = _ctx(tmp_path, [])  # empty allowlist
    token = actx.issuer.issue("e@x.com").access_token
    with pytest.raises(AuthError):
        extract_exec_email(token=token, ctx=actx)


import time
import jwt as pyjwt
from unittest.mock import MagicMock, patch

TENANT_ID = "test-tenant"
CLIENT_ID = "test-client"


def _azure_token(email: str, expired: bool = False) -> str:
    now = int(time.time())
    return pyjwt.encode(
        {
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "aud": CLIENT_ID,
            "preferred_username": email,
            "exp": now - 10 if expired else now + 3600,
            "iat": now,
        },
        "secret",
        algorithm="HS256",
    )


def _make_ctx(allowed: list[str]) -> AuthContext:
    issuer = MagicMock()
    issuer.issuer = "mcp-exec-azzas"
    issuer.verify_access.side_effect = Exception("should not be called for Azure tokens")
    allowlist = MagicMock()
    allowlist.is_allowed.side_effect = lambda e: e in allowed
    return AuthContext(
        issuer=issuer,
        allowlist=allowlist,
        azure_tenant_id=TENANT_ID,
        azure_client_id=CLIENT_ID,
    )


def test_azure_token_accepted_when_on_allowlist():
    token = _azure_token("user@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    payload = {"preferred_username": "user@soma.com.br"}
    with patch("mcp_core.auth_middleware._validate_azure_signature", return_value=payload):
        email = extract_exec_email(token, ctx)
    assert email == "user@soma.com.br"


def test_azure_token_rejected_when_not_on_allowlist():
    token = _azure_token("other@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    payload = {"preferred_username": "other@soma.com.br"}
    with patch("mcp_core.auth_middleware._validate_azure_signature", return_value=payload):
        with pytest.raises(AuthError, match="not_on_allowlist"):
            extract_exec_email(token, ctx)


def test_unknown_issuer_rejected():
    token = pyjwt.encode(
        {"iss": "https://evil.example.com", "exp": int(time.time()) + 3600},
        "secret",
        algorithm="HS256",
    )
    ctx = _make_ctx([])
    with pytest.raises(AuthError, match="unknown token issuer"):
        extract_exec_email(token, ctx)


def test_azure_passthrough_not_configured_raises():
    token = _azure_token("user@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    ctx.azure_tenant_id = ""  # not configured
    with pytest.raises(AuthError, match="not configured"):
        extract_exec_email(token, ctx)


def test_jwks_client_reused_across_calls():
    """PyJWKClient should be instantiated once (lazy init), not on every call."""
    ctx = _make_ctx(["user@soma.com.br"])
    with patch("jwt.PyJWKClient", return_value=MagicMock()) as mock_cls:
        client1 = ctx._get_jwks_client()
        client2 = ctx._get_jwks_client()
    assert mock_cls.call_count == 1
    assert client1 is client2


def test_azure_rs256_signature_validated():
    """_validate_azure_signature verifies RS256 with JWKS, returns payload with email claim."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    import jwt as pyjwt
    from mcp_core.auth_middleware import _validate_azure_signature, AuthContext

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    now = int(time.time())
    token = pyjwt.encode(
        {
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "aud": CLIENT_ID,
            "tid": TENANT_ID,
            "preferred_username": "rsuser@soma.com.br",
            "exp": now + 3600,
            "iat": now,
        },
        private_key,
        algorithm="RS256",
    )

    mock_signing_key = MagicMock()
    mock_signing_key.key = private_key.public_key()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    ctx = _make_ctx(["rsuser@soma.com.br"])
    ctx._jwks_client = mock_client  # inject cached client

    payload = _validate_azure_signature(token, ctx)
    assert payload["preferred_username"] == "rsuser@soma.com.br"


def test_azure_token_from_foreign_tenant_rejected():
    """Token signed by Microsoft for a different tenant must not be accepted
    (would have passed the substring routing check, fails issuer/tid pinning)."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    from mcp_core.auth_middleware import _validate_azure_signature

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    now = int(time.time())
    foreign_tid = "attacker-tenant"
    token = pyjwt.encode(
        {
            "iss": f"https://login.microsoftonline.com/{foreign_tid}/v2.0",
            "aud": CLIENT_ID,
            "tid": foreign_tid,
            "preferred_username": "ceo@azzas.com.br",
            "exp": now + 3600,
            "iat": now,
        },
        private_key,
        algorithm="RS256",
    )
    mock_signing_key = MagicMock()
    mock_signing_key.key = private_key.public_key()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    ctx = _make_ctx(["ceo@azzas.com.br"])
    ctx._jwks_client = mock_client

    # pyjwt's issuer= check fires first — foreign issuer rejected before tid is read
    with pytest.raises(pyjwt.InvalidIssuerError):
        _validate_azure_signature(token, ctx)


def test_azure_token_with_mismatched_tid_rejected():
    """Token whose iss matches expected tenant but tid claim is foreign must be rejected.
    Defends against a hypothetical Azure misconfig where iss and tid disagree."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.backends import default_backend
    from mcp_core.auth_middleware import _validate_azure_signature

    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    now = int(time.time())
    token = pyjwt.encode(
        {
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "aud": CLIENT_ID,
            "tid": "attacker-tenant",  # disagrees with iss
            "preferred_username": "ceo@azzas.com.br",
            "exp": now + 3600,
            "iat": now,
        },
        private_key,
        algorithm="RS256",
    )
    mock_signing_key = MagicMock()
    mock_signing_key.key = private_key.public_key()
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    ctx = _make_ctx(["ceo@azzas.com.br"])
    ctx._jwks_client = mock_client

    with pytest.raises(AuthError, match="tid mismatch"):
        _validate_azure_signature(token, ctx)
