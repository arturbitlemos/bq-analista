import importlib
import os
import sys
from unittest.mock import patch

ENV = {
    "MCP_PUBLIC_HOST": "test.example.com",
    "MCP_JWT_SECRET": "testsecret123456789012345678901",
    "MCP_AZURE_TENANT_ID": "tenant-id",
    "MCP_AZURE_CLIENT_ID": "client-id",
    "MCP_AZURE_CLIENT_SECRET": "client-secret",
}


def _reload_server():
    """Force a fresh import of agent.server, clearing any cached module."""
    if "agent.server" in sys.modules:
        del sys.modules["agent.server"]
    import agent.server as m
    return m


def test_agent_imports_and_builds():
    with patch.dict(os.environ, ENV):
        m = _reload_server()
    assert m.app is not None
    assert callable(m.main)


def test_agent_has_base_tools():
    with patch.dict(os.environ, ENV):
        m = _reload_server()
    registered = set(m.app._tool_manager._tools.keys())
    assert {"get_context", "consultar_bq", "publicar_dashboard", "listar_analises"}.issubset(registered)


def test_agent_has_no_extra_tools_by_default():
    """devolucoes registers exactly the mcp-core base tool set — no
    domain-specific extras. Compares dynamically so adding a base tool in
    mcp-core won't break this assertion."""
    from mcp_core.server_factory import build_mcp_app
    with patch.dict(os.environ, ENV):
        m = _reload_server()
        # Build baseline with the same optional features the agent uses, so
        # the comparison checks for *domain* tools only — not opt-in extras
        # provided by mcp-core itself.
        baseline_app, _ = build_mcp_app(agent_name="baseline", exemplos="x")
    registered = set(m.app._tool_manager._tools.keys())
    base = set(baseline_app._tool_manager._tools.keys())
    assert registered == base
