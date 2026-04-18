from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from mcp.server.fastmcp import FastMCP

from mcp_exec.bq_client import BqClient
from mcp_exec.context_loader import load_exec_context
from mcp_exec.settings import load_settings
from mcp_exec.sql_validator import SqlValidationError, validate_readonly_sql

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


def _build_bq_client() -> BqClient:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    settings = load_settings(settings_path)
    return BqClient(settings=settings.bigquery)


def consultar_bq_impl(
    sql: str,
    exec_email: str,
    progress: Optional[Callable[[str], None]],
) -> dict:
    try:
        validate_readonly_sql(sql)
    except SqlValidationError as e:
        return {"error": f"sql_validation: {e}"}

    client = _build_bq_client()
    if progress:
        progress("querying BigQuery...")
    try:
        result = client.run_query(sql=sql, exec_email=exec_email)
    except Exception as e:  # noqa: BLE001
        return {"error": f"bq_execution: {e}"}
    return {
        "rows": result.rows,
        "row_count": result.row_count,
        "bytes_billed": result.bytes_billed,
        "bytes_processed": result.bytes_processed,
        "truncated": result.truncated,
    }


def _current_exec_email(ctx) -> str:
    # Stub until Phase 5 wires real Azure AD auth. Always returns the test exec.
    return os.environ.get("MCP_DEV_EXEC_EMAIL", "artur.lemos@somagrupo.com.br")


@mcp.tool()
async def consultar_bq(sql: str, ctx) -> dict:
    """Run a SELECT query against BigQuery.

    Only SELECT / WITH single-statement SQL is accepted.
    Returns rows (capped) plus bytes_billed / bytes_processed.
    """
    exec_email = _current_exec_email(ctx)

    def report(msg: str) -> None:
        ctx.info(msg)

    return consultar_bq_impl(sql=sql, exec_email=exec_email, progress=report)


def main() -> None:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    # Load once to fail fast if settings are bad; server doesn't use them yet.
    load_settings(settings_path)
    mcp.run()


if __name__ == "__main__":
    main()
