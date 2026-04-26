from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import cast

import jwt

from mcp_core.allowlist import Allowlist


class TokenError(RuntimeError):
    pass


class TokenExpiredError(TokenError):
    pass


class TokenInvalidError(TokenError):
    pass


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_at: int


_MIN_SECRET_BYTES = 32


@dataclass
class TokenIssuer:
    secret: str
    issuer: str
    access_ttl_s: int
    refresh_ttl_s: int
    alg: str = "HS256"
    allow_short_secret: bool = False  # for unit tests only
    # Refresh-token rotation state. Each issue() seeds a new family; each
    # refresh() consumes a jti and mints a new one in the same family. Reusing
    # a consumed jti revokes the entire family (OAuth 2.1 §4.13.2). In-memory
    # only — single-process Railway deployment, restart forces re-login.
    _families: dict[str, set[str]] = field(default_factory=dict, init=False, repr=False)
    _revoked_families: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.allow_short_secret and len(self.secret.encode()) < _MIN_SECRET_BYTES:
            raise ValueError(
                f"JWT secret must be at least {_MIN_SECRET_BYTES} bytes for HS256"
            )

    def _encode(
        self,
        kind: str,
        email: str,
        ttl: int,
        *,
        family_id: str | None = None,
        jti: str | None = None,
    ) -> tuple[str, int]:
        now = int(time.time())
        exp = now + ttl
        payload: dict[str, object] = {
            "iss": self.issuer,
            "sub": email,
            "email": email,
            "kind": kind,
            "iat": now,
            "exp": exp,
        }
        if family_id is not None:
            payload["fid"] = family_id
        if jti is not None:
            payload["jti"] = jti
        return jwt.encode(payload, self.secret, algorithm=self.alg), exp

    def issue(self, email: str) -> TokenPair:
        family_id = secrets.token_urlsafe(16)
        jti = secrets.token_urlsafe(16)
        access, exp = self._encode("access", email, self.access_ttl_s)
        refresh, _ = self._encode(
            "refresh", email, self.refresh_ttl_s, family_id=family_id, jti=jti
        )
        self._families[family_id] = set()
        return TokenPair(access_token=access, refresh_token=refresh, expires_at=exp)

    def _decode(self, token: str) -> dict[str, object]:
        try:
            return jwt.decode(token, self.secret, algorithms=[self.alg], issuer=self.issuer)  # type: ignore[return-value]
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError("token expired") from e
        except jwt.InvalidTokenError as e:
            raise TokenInvalidError(str(e)) from e

    def verify_access(self, token: str) -> dict[str, object]:
        claims = self._decode(token)
        if claims.get("kind") != "access":
            raise TokenInvalidError("not an access token")
        return claims

    def refresh(
        self, refresh_token: str, *, allowlist: Allowlist | None = None
    ) -> TokenPair:
        """Rotate a refresh token: validate, consume, mint new pair.

        - Detects reuse of a consumed jti and revokes the entire family.
        - Optionally re-checks allowlist so removed users cannot mint access tokens
          via a previously-issued refresh token.
        - Returns a new pair with a fresh jti in the same family.
        """
        claims = self._decode(refresh_token)
        if claims.get("kind") != "refresh":
            raise TokenInvalidError("not a refresh token")
        email = cast(str, claims["email"])
        family_id = claims.get("fid")
        jti = claims.get("jti")
        if not isinstance(family_id, str) or not isinstance(jti, str):
            raise TokenInvalidError("refresh token missing rotation claims; please re-login")
        if family_id in self._revoked_families:
            raise TokenInvalidError("refresh family revoked")
        consumed = self._families.get(family_id)
        if consumed is None:
            # Family unknown — process restart drops the in-memory set, forcing re-login.
            raise TokenInvalidError("refresh family not recognized; please re-login")
        if jti in consumed:
            # Reuse of a previously-rotated jti — revoke the whole chain.
            self._revoked_families.add(family_id)
            self._families.pop(family_id, None)
            raise TokenInvalidError("refresh token reuse detected; family revoked")
        if allowlist is not None and not allowlist.is_allowed(email):
            raise TokenInvalidError(f"not_on_allowlist: {email}")
        consumed.add(jti)
        new_jti = secrets.token_urlsafe(16)
        new_access, exp = self._encode("access", email, self.access_ttl_s)
        new_refresh, _ = self._encode(
            "refresh", email, self.refresh_ttl_s, family_id=family_id, jti=new_jti
        )
        return TokenPair(access_token=new_access, refresh_token=new_refresh, expires_at=exp)
