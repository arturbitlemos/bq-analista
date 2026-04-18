import time

import pytest

from mcp_exec.jwt_tokens import TokenExpiredError, TokenInvalidError, TokenIssuer


def test_issue_and_verify() -> None:
    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="mcp-test", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    claims = iss.verify_access(pair.access_token)
    assert claims["email"] == "e@x.com"
    assert claims["kind"] == "access"


def test_access_token_expires() -> None:
    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=1, refresh_ttl_s=10)
    pair = iss.issue(email="e@x.com")
    time.sleep(2)
    with pytest.raises(TokenExpiredError):
        iss.verify_access(pair.access_token)


def test_tampered_token_rejected() -> None:
    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    tampered = pair.access_token[:-2] + ("AA" if pair.access_token[-2:] != "AA" else "BB")
    with pytest.raises(TokenInvalidError):
        iss.verify_access(tampered)


def test_refresh_issues_new_access() -> None:
    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    new_access = iss.refresh(pair.refresh_token)
    claims = iss.verify_access(new_access)
    assert claims["email"] == "e@x.com"


def test_refresh_rejects_access_token() -> None:
    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    with pytest.raises(TokenInvalidError):
        iss.refresh(pair.access_token)


def test_short_secret_rejected_by_default() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        TokenIssuer(secret="s", issuer="i", access_ttl_s=60, refresh_ttl_s=120)


def test_32_byte_secret_accepted() -> None:
    iss = TokenIssuer(secret="x" * 32, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    assert iss.verify_access(pair.access_token)["email"] == "e@x.com"
