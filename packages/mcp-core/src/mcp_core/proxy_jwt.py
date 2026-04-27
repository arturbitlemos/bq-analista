from __future__ import annotations
import os
import jwt as pyjwt


def verify_proxy_jwt(token: str) -> str:
    """Verify HS256 proxy JWT signed with MCP_PROXY_SIGNING_KEY. Returns email claim.

    Raises ValueError if token is invalid, expired, has wrong audience, or wrong signature."""
    secret = os.environ.get("MCP_PROXY_SIGNING_KEY")
    if not secret:
        raise RuntimeError("MCP_PROXY_SIGNING_KEY not set")
    try:
        payload = pyjwt.decode(token, secret, algorithms=["HS256"], audience="mcp-core-proxy")
    except pyjwt.ExpiredSignatureError:
        raise ValueError("expired")
    except pyjwt.InvalidAudienceError:
        raise ValueError("audience")
    except pyjwt.InvalidSignatureError:
        raise ValueError("signature")
    except pyjwt.PyJWTError as e:
        raise ValueError(f"invalid: {e}")
    email = payload.get("email")
    if not email:
        raise ValueError("missing email claim")
    return email
