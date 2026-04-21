# packages/mcp-core/tests/test_server_factory.py
import os
import pytest
from unittest.mock import patch


ENV = {
    "MCP_PUBLIC_HOST": "test.example.com",
    "MCP_JWT_SECRET": "testsecret123456789012345678901",
    "MCP_AZURE_TENANT_ID": "tenant-id",
    "MCP_AZURE_CLIENT_ID": "client-id",
    "MCP_AZURE_CLIENT_SECRET": "client-secret",
}

# Extra env vars required by _settings_from_env() when settings.toml is absent
_SETTINGS_ENV = {
    "MCP_DOMAIN": "test-domain",
    "MCP_BQ_PROJECT_ID": "test-project",
}


def test_build_mcp_app_returns_app_and_main():
    with patch.dict(os.environ, ENV):
        from mcp_core.server_factory import build_mcp_app
        app, main = build_mcp_app(agent_name="test-agent")
    assert app is not None
    assert callable(main)


def test_build_mcp_app_registers_base_tools():
    with patch.dict(os.environ, ENV):
        from mcp_core.server_factory import build_mcp_app
        app, _ = build_mcp_app(agent_name="test-agent")
    # FastMCP stores tools in _tool_manager._tools dict
    registered = set(app._tool_manager._tools.keys())
    assert {"get_context", "consultar_bq", "publicar_dashboard", "listar_analises"}.issubset(registered)


def test_build_mcp_app_raises_without_jwt_secret():
    env_no_secret = {k: v for k, v in ENV.items() if k != "MCP_JWT_SECRET"}
    # Also provide the settings env vars so load_settings() can build from env
    env_no_secret.update(_SETTINGS_ENV)
    with patch.dict(os.environ, env_no_secret, clear=False):
        os.environ.pop("MCP_JWT_SECRET", None)
        from mcp_core.server_factory import build_mcp_app
        # build_mcp_app itself doesn't fail — _get_auth_context() fails at request time
        # but main() should fail if MCP_JWT_SECRET is absent
        _, main = build_mcp_app(agent_name="test-agent")
        with pytest.raises((RuntimeError, KeyError)):
            main()  # tries to read MCP_JWT_SECRET
