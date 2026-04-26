"""Stdio entrypoint for local Claude Desktop (MVP conversacional).

Seta defaults pro MCP_SETTINGS (settings.toml local) e MCP_DEV_EXEC_EMAIL
(bypass de auth no transporte stdio — sem Bearer token, sem Azure AD)."""
import os
from pathlib import Path
from dotenv import load_dotenv

_AGENT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_AGENT_ROOT / ".env")
os.environ.setdefault("MCP_SETTINGS", str(_AGENT_ROOT / "config" / "settings.toml"))
os.environ.setdefault("MCP_DEV_EXEC_EMAIL", "luiz.vasconcelos@somagrupo.com")

from agent.server import app  # noqa: E402  — env vars must be set before import

if __name__ == "__main__":
    app.run()
