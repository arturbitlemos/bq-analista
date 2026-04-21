from __future__ import annotations

from dataclasses import dataclass

from mcp_exec.allowlist import Allowlist
from mcp_exec.jwt_tokens import TokenError, TokenIssuer
from typing import cast


class AuthError(RuntimeError):
    pass


@dataclass
class AuthContext:
    issuer: TokenIssuer
    allowlist: Allowlist


def extract_exec_email(token: str, ctx: AuthContext) -> str:
    try:
        claims = ctx.issuer.verify_access(token)
    except TokenError as e:
        raise AuthError(f"invalid_token: {e}") from e
    email = cast(str, claims["email"])
    if not ctx.allowlist.is_allowed(email):
        raise AuthError(f"not_on_allowlist: {email}")
    return email
