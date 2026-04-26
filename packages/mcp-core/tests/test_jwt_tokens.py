import time

import pytest

from mcp_core.jwt_tokens import TokenExpiredError, TokenInvalidError, TokenIssuer


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
    new_pair = iss.refresh(pair.refresh_token)
    claims = iss.verify_access(new_pair.access_token)
    assert claims["email"] == "e@x.com"


def test_refresh_rejects_access_token() -> None:
    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    with pytest.raises(TokenInvalidError):
        iss.refresh(pair.access_token)


def test_refresh_rotates_refresh_token() -> None:
    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    new_pair = iss.refresh(pair.refresh_token)
    assert new_pair.refresh_token != pair.refresh_token
    # The new refresh token works for further refreshes
    third = iss.refresh(new_pair.refresh_token)
    assert iss.verify_access(third.access_token)["email"] == "e@x.com"


def test_refresh_reuse_revokes_family() -> None:
    """Reusing a consumed refresh token must revoke the entire family — even
    the just-rotated 'good' token becomes unusable."""
    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    new_pair = iss.refresh(pair.refresh_token)
    # Replay the old refresh token — must fail and revoke the family
    with pytest.raises(TokenInvalidError, match="reuse"):
        iss.refresh(pair.refresh_token)
    # The legitimate new token is also dead now (chain compromised)
    with pytest.raises(TokenInvalidError, match="revoked"):
        iss.refresh(new_pair.refresh_token)


def test_refresh_unknown_family_rejected() -> None:
    """A refresh token from before a process restart must be rejected
    (in-memory family store is empty after restart)."""
    iss1 = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss1.issue(email="e@x.com")
    # Simulate a restart — new TokenIssuer instance
    iss2 = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    with pytest.raises(TokenInvalidError, match="not recognized"):
        iss2.refresh(pair.refresh_token)


def test_refresh_consults_allowlist_when_provided(tmp_path) -> None:
    """A user removed from the allowlist must not be able to refresh."""
    import json
    from mcp_core.allowlist import Allowlist

    f = tmp_path / "a.json"
    f.write_text(json.dumps({"allowed_emails": ["e@x.com"]}))
    allowlist = Allowlist(path=f)

    iss = TokenIssuer(secret="s", allow_short_secret=True, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    # While allowlisted, refresh works
    iss.refresh(pair.refresh_token, allowlist=allowlist)

    # Remove from allowlist
    f.write_text(json.dumps({"allowed_emails": []}))
    # Force reload (Allowlist has TTL — reset its cached state)
    allowlist._last_reload = 0.0

    pair2 = iss.issue(email="e@x.com")  # fresh family
    with pytest.raises(TokenInvalidError, match="not_on_allowlist"):
        iss.refresh(pair2.refresh_token, allowlist=allowlist)


def test_short_secret_rejected_by_default() -> None:
    with pytest.raises(ValueError, match="at least 32 bytes"):
        TokenIssuer(secret="s", issuer="i", access_ttl_s=60, refresh_ttl_s=120)


def test_32_byte_secret_accepted() -> None:
    iss = TokenIssuer(secret="x" * 32, issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    assert iss.verify_access(pair.access_token)["email"] == "e@x.com"
