"""
Integration test — requires the agent server to be running locally.
Start the server before running:

  MCP_DEV_EXEC_EMAIL=test@test.com \
  MCP_JWT_SECRET=dev-secret \
  MCP_REPO_ROOT=/tmp/test-repo \
  uv run python -m agent.server

Then run: uv run pytest tests/test_integration.py -v -m integration
"""
import os
import pytest

pytestmark = pytest.mark.integration  # skip unless -m integration


@pytest.fixture
def mcp_url():
    return os.environ.get("MCP_TEST_URL", "http://localhost:3000/mcp")


@pytest.fixture
def headers():
    token = os.environ.get("MCP_TEST_TOKEN", "")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.mark.asyncio
async def test_health_endpoint(mcp_url):
    import httpx
    base = mcp_url.replace("/mcp", "")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{base}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_get_context_returns_text(mcp_url, headers):
    from mcp.client.streamable_http import streamable_http_client
    from mcp.client.session import ClientSession

    async with streamable_http_client(mcp_url, headers=headers) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool("get_context", {})
    assert result.content
    text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
    assert "Analytics Context" in text


@pytest.mark.asyncio
async def test_unauthorized_dataset_blocked(mcp_url, headers):
    from mcp.client.streamable_http import streamable_http_client
    from mcp.client.session import ClientSession

    async with streamable_http_client(mcp_url, headers=headers) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(
                "consultar_bq",
                {"sql": "SELECT 1 FROM `soma-pipeline-prd.silver_ecomm.VENDAS` LIMIT 1"},
            )
    content_text = str(result.content)
    assert "dataset_not_allowed" in content_text
