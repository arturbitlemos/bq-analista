import pytest

from mcp_exec.allowlist import Allowlist
from mcp_exec.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_exec.jwt_tokens import TokenIssuer


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
