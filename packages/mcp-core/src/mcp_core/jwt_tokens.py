from __future__ import annotations

import time
from dataclasses import dataclass
from typing import cast

import jwt


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

    def __post_init__(self) -> None:
        if not self.allow_short_secret and len(self.secret.encode()) < _MIN_SECRET_BYTES:
            raise ValueError(
                f"JWT secret must be at least {_MIN_SECRET_BYTES} bytes for HS256"
            )

    def _encode(self, kind: str, email: str, ttl: int) -> tuple[str, int]:
        now = int(time.time())
        exp = now + ttl
        payload = {
            "iss": self.issuer,
            "sub": email,
            "email": email,
            "kind": kind,
            "iat": now,
            "exp": exp,
        }
        return jwt.encode(payload, self.secret, algorithm=self.alg), exp

    def issue(self, email: str) -> TokenPair:
        access, exp = self._encode("access", email, self.access_ttl_s)
        refresh, _ = self._encode("refresh", email, self.refresh_ttl_s)
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

    def refresh(self, refresh_token: str) -> str:
        claims = self._decode(refresh_token)
        if claims.get("kind") != "refresh":
            raise TokenInvalidError("not a refresh token")
        access, _ = self._encode("access", cast(str, claims["email"]), self.access_ttl_s)
        return access
