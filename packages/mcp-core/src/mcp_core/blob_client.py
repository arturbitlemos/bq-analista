from __future__ import annotations
import os
import time
import jwt as pyjwt
import httpx


class BlobClient:
    """Cliente HTTP que delega operações de Blob pro endpoint interno do portal Vercel.

    Por que indireto: SDK oficial do Vercel Blob é Node-only. Centralizar a interação
    no portal evita chute de API HTTP e mantém uma única fonte de verdade pra evoluir."""

    def __init__(self, *, base_url: str | None = None, signing_key: str | None = None):
        self._base_url = (base_url or os.environ["PORTAL_BLOB_URL"]).rstrip("/")
        # Distinct from MCP_PROXY_SIGNING_KEY (which signs portal→Railway proxy
        # JWTs). Splitting the keys means a Railway compromise can't mint
        # blob-internal tokens to read/delete arbitrary blobs.
        self._signing_key = signing_key or os.environ["MCP_BLOB_SIGNING_KEY"]

    def _mint_token(self, ttl_seconds: int = 60) -> str:
        return pyjwt.encode(
            {"aud": "blob-internal", "exp": int(time.time()) + ttl_seconds},
            self._signing_key, algorithm="HS256",
        )

    @property
    def _endpoint(self) -> str:
        return f"{self._base_url}/api/internal/blob"

    async def put(self, pathname: str, body: bytes, *, content_type: str = "text/html") -> str:
        token = self._mint_token()
        # 90s — large dashboards with embedded charts can push past 30s
        # over slower connections; happy path is sub-second so the higher
        # ceiling has no practical cost.
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.put(
                self._endpoint,
                params={"pathname": pathname, "content_type": content_type},
                content=body,
                headers={
                    "authorization": f"Bearer {token}",
                    # Force application/octet-stream on the WIRE so Vercel dev's body
                    # parser doesn't mangle the payload. Stored blob's content-type is
                    # passed via the `content_type` query param.
                    "content-type": "application/octet-stream",
                },
            )
        resp.raise_for_status()
        return resp.json()["url"]

    async def get(self, pathname: str) -> bytes:
        token = self._mint_token()
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.get(
                self._endpoint,
                params={"pathname": pathname},
                headers={"authorization": f"Bearer {token}"},
            )
        resp.raise_for_status()
        return resp.content

    async def delete(self, pathname: str) -> None:
        token = self._mint_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                self._endpoint,
                params={"pathname": pathname},
                headers={"authorization": f"Bearer {token}"},
            )
        resp.raise_for_status()
