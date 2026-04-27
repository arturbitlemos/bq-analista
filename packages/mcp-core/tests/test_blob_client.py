import pytest
import httpx
from unittest.mock import patch, AsyncMock
from mcp_core.blob_client import BlobClient


# httpx 0.28+ requires a Request to be attached for raise_for_status() to work.
# Mocked responses don't get one automatically, so we attach a stub.
_STUB_REQUEST = httpx.Request("PUT", "https://portal.test/api/internal/blob")


@pytest.fixture
def blob_client(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    monkeypatch.setenv("PORTAL_BLOB_URL", "https://portal.test")
    return BlobClient()


@pytest.mark.asyncio
async def test_put_uploads(blob_client):
    mock_response = httpx.Response(200, json={"url": "https://blob.x/y.html", "pathname": "analyses/x/y.html"}, request=_STUB_REQUEST)
    with patch("httpx.AsyncClient.put", new=AsyncMock(return_value=mock_response)) as m:
        url = await blob_client.put("analyses/x/y.html", b"<html></html>", content_type="text/html")
    assert url == "https://blob.x/y.html"
    call = m.call_args
    assert call.kwargs["headers"]["authorization"].startswith("Bearer ")
    # IMPORTANT: transport content-type must be application/octet-stream
    # so Vercel dev's body parser doesn't munge the payload. The intended
    # content-type for the stored blob travels via the `content_type` query param.
    assert call.kwargs["headers"]["content-type"] == "application/octet-stream"
    assert call.kwargs["params"]["content_type"] == "text/html"
    assert call.kwargs["params"]["pathname"] == "analyses/x/y.html"


@pytest.mark.asyncio
async def test_get_downloads(blob_client):
    mock_response = httpx.Response(200, content=b"<html>old</html>", request=_STUB_REQUEST)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
        body = await blob_client.get("analyses/x/y.html")
    assert body == b"<html>old</html>"


@pytest.mark.asyncio
async def test_put_raises_on_5xx(blob_client):
    mock_response = httpx.Response(502, json={"error": "blob down"}, request=_STUB_REQUEST)
    with patch("httpx.AsyncClient.put", new=AsyncMock(return_value=mock_response)):
        with pytest.raises(httpx.HTTPStatusError):
            await blob_client.put("analyses/x/y.html", b"x")


@pytest.mark.asyncio
async def test_delete(blob_client):
    mock_response = httpx.Response(204, request=_STUB_REQUEST)
    with patch("httpx.AsyncClient.delete", new=AsyncMock(return_value=mock_response)) as m:
        await blob_client.delete("analyses/x/y.html")
    assert m.call_args.kwargs["params"]["pathname"] == "analyses/x/y.html"


@pytest.mark.asyncio
async def test_jwt_minted_with_correct_audience(blob_client):
    """The JWT sent to the portal endpoint must have audience='blob-internal'."""
    import jwt as pyjwt
    captured_headers = {}

    async def fake_put(*args, **kwargs):
        captured_headers.update(kwargs.get("headers", {}))
        return httpx.Response(200, json={"url": "u", "pathname": "p"}, request=_STUB_REQUEST)

    with patch("httpx.AsyncClient.put", new=AsyncMock(side_effect=fake_put)):
        await blob_client.put("analyses/x.html", b"x")

    token = captured_headers["authorization"].replace("Bearer ", "")
    payload = pyjwt.decode(token, "secret123", algorithms=["HS256"], audience="blob-internal")
    assert payload["aud"] == "blob-internal"
