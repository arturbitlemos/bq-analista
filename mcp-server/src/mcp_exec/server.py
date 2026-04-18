from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_exec.context_loader import load_exec_context
from mcp_exec.settings import load_settings

mcp = FastMCP("mcp-exec-azzas")


def _repo_root() -> Path:
    # Repo is mounted into container at /app/repo in prod; dev uses MCP_REPO_ROOT env.
    return Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))


@mcp.tool()
def get_context() -> dict:
    """Return concatenated docs (schema.md, business-rules.md, SKILL.md) plus allowed tables.

    Call once at session start to prime Claude with the analytics context.
    """
    ctx = load_exec_context(_repo_root())
    return {"text": ctx.text, "allowed_tables": ctx.allowed_tables}


def main() -> None:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    # Load once to fail fast if settings are bad; server doesn't use them yet.
    load_settings(settings_path)
    mcp.run()


if __name__ == "__main__":
    main()
