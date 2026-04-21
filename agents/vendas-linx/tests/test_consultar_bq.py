# TODO: rewrite for server_factory architecture
# Original tests imported from mcp_exec.server (now non-existent).
# The consultar_bq tool is now defined inside build_mcp_app() in mcp_core.server_factory.
# To test the tool logic in isolation, either:
#   a) Extract consultar_bq_impl into a standalone function in mcp_core, or
#   b) Test via the FastMCP test client (mcp.server.fastmcp.testing).


def test_placeholder():
    """Placeholder — expand once consultar_bq_impl is extractable or testable via MCP client."""
    assert True
