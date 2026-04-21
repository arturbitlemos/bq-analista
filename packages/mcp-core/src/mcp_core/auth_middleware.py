from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import jwt as pyjwt

from mcp_core.allowlist import Allowlist
from mcp_core.jwt_tokens import TokenError, TokenIssuer


class AuthError(RuntimeError):
    pass


@dataclass
class AuthContext:
    issuer: TokenIssuer
    allowlist: Allowlist
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    # PyJWKClient cached here — one HTTP fetch per process, not per request
    _jwks_client: object = field(default=None, init=False, repr=False)

    def _get_jwks_client(self) -> pyjwt.PyJWKClient:
        if self._jwks_client is None:
            jwks_uri = (
                f"https://login.microsoftonline.com"
                f"/{self.azure_tenant_id}/discovery/v2.0/keys"
            )
            self._jwks_client = pyjwt.PyJWKClient(
                jwks_uri, cache_jwk_set=True, lifespan=300
            )
        return self._jwks_client  # type: ignore[return-value]


def _peek_iss(token: str) -> str:
    """Decode `iss` claim without verifying the signature."""
    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
        return str(payload.get("iss", ""))
    except Exception as e:
        raise AuthError(f"malformed token: {e}") from e


def _validate_azure_signature(token: str, ctx: AuthContext) -> None:
    """Verify Azure AD token signature and audience using cached JWKS."""
    signing_key = ctx._get_jwks_client().get_signing_key_from_jwt(token)
    pyjwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=ctx.azure_client_id,
    )


def _extract_azure_email(token: str) -> str:
    payload = pyjwt.decode(token, options={"verify_signature": False})
    email = payload.get("preferred_username") or payload.get("upn") or ""
    if not email:
        raise AuthError("azure token missing preferred_username/upn claim")
    return cast(str, email)


def extract_exec_email(token: str, ctx: AuthContext) -> str:
    iss = _peek_iss(token)

    if iss == ctx.issuer.issuer:
        # Internal JWT issued by this server
        try:
            claims = ctx.issuer.verify_access(token)
        except TokenError as e:
            raise AuthError(f"invalid_token: {e}") from e
        email = cast(str, claims["email"])

    elif "login.microsoftonline.com" in iss:
        # Azure AD SSO passthrough — frontend sends its own token directly
        if not ctx.azure_tenant_id or not ctx.azure_client_id:
            raise AuthError("azure passthrough not configured on this agent")
        _validate_azure_signature(token, ctx)
        email = _extract_azure_email(token)

    else:
        raise AuthError(f"unknown token issuer: {iss!r}")

    if not ctx.allowlist.is_allowed(email):
        raise AuthError(f"not_on_allowlist: {email}")
    return email
