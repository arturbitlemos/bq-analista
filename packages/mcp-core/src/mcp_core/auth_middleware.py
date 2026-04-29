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


def _peek_aud(token: str) -> str:
    """Decode `aud` claim without verifying the signature."""
    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
        aud = payload.get("aud", "")
        return str(aud) if isinstance(aud, str) else ""
    except Exception:
        return ""


def _validate_azure_signature(token: str, ctx: AuthContext) -> dict[str, object]:
    """Verify Azure AD token signature, audience, issuer, and tenant; return validated payload.

    Pins the configured tenant in two ways: pyjwt's `issuer=` parameter rejects
    tokens whose `iss` claim is not exactly `https://login.microsoftonline.com/{tid}/v2.0`,
    and the post-decode `tid` check rejects tokens that somehow carry a matching
    `iss` but a foreign `tid`. Without this, any Azure token whose audience equals
    `azure_client_id` would be accepted regardless of source tenant.
    """
    signing_key = ctx._get_jwks_client().get_signing_key_from_jwt(token)
    expected_issuer = f"https://login.microsoftonline.com/{ctx.azure_tenant_id}/v2.0"
    payload = pyjwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=ctx.azure_client_id,
        issuer=expected_issuer,
    )
    if payload.get("tid") != ctx.azure_tenant_id:
        raise AuthError(
            f"azure token tid mismatch: expected {ctx.azure_tenant_id!r}, "
            f"got {payload.get('tid')!r}"
        )
    return payload


def _extract_azure_email(payload: dict[str, object]) -> str:
    email = payload.get("preferred_username") or payload.get("upn") or ""
    if not email:
        raise AuthError("azure token missing preferred_username/upn claim")
    return cast(str, email)


def extract_exec_email(token: str, ctx: AuthContext) -> str:
    aud = _peek_aud(token)

    if aud == "mcp-core-proxy":
        # Portal proxy JWT (Vercel function → Railway). Audience-scoped HS256
        # signed with MCP_PROXY_SIGNING_KEY shared between portal and mcp-core.
        # Distinct from the internal-issuer HS256 path (which uses ctx.issuer
        # with its own secret + jti tracking) and from Azure RS256.
        from mcp_core.proxy_jwt import verify_proxy_jwt
        try:
            email = verify_proxy_jwt(token)
        except ValueError as e:
            raise AuthError(f"invalid_proxy_token: {e}") from e
    else:
        iss = _peek_iss(token)

        if iss == ctx.issuer.issuer:
            # Internal JWT issued by this server
            try:
                claims = ctx.issuer.verify_access(token)
            except TokenError as e:
                raise AuthError(f"invalid_token: {e}") from e
            email = cast(str, claims["email"])

        elif iss.startswith("https://login.microsoftonline.com/"):
            # Azure AD SSO passthrough — frontend sends its own token directly.
            # The exact-prefix match is only for routing; the actual issuer/tenant
            # pinning happens inside _validate_azure_signature.
            if not ctx.azure_tenant_id or not ctx.azure_client_id:
                raise AuthError("azure passthrough not configured on this agent")
            payload = _validate_azure_signature(token, ctx)
            email = _extract_azure_email(payload)

        else:
            raise AuthError(f"unknown token issuer: {iss!r}")

    if not ctx.allowlist.is_allowed(email):
        raise AuthError(f"not_on_allowlist: {email}")
    return email
