from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from mcp.server.fastmcp import FastMCP

from mcp_exec.allowlist import Allowlist
from mcp_exec.audit import AuditLog
from mcp_exec.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_exec.bq_client import BqClient
from mcp_exec.context_loader import load_exec_context
from mcp_exec.git_ops import GitOps
from mcp_exec.jwt_tokens import TokenIssuer
from mcp_exec.library import LibraryEntry, prepend_entry
from mcp_exec.sandbox import PathSandboxError, exec_analysis_path, exec_library_path
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


_AUDIT: AuditLog | None = None


def _audit_log() -> AuditLog:
    global _AUDIT
    if _AUDIT is None:
        settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
        settings = load_settings(settings_path)
        _AUDIT = AuditLog(db_path=Path(settings.audit.db_path))
    return _AUDIT


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


def _auth_context() -> AuthContext:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    settings = load_settings(settings_path)
    secret = os.environ["MCP_JWT_SECRET"]
    issuer = TokenIssuer(
        secret=secret,
        issuer=settings.auth.jwt_issuer,
        access_ttl_s=settings.auth.access_token_ttl_s,
        refresh_ttl_s=settings.auth.refresh_token_ttl_s,
    )
    allowlist = Allowlist(
        path=Path(os.environ.get("MCP_ALLOWLIST", "/app/config/allowed_execs.json"))
    )
    return AuthContext(issuer=issuer, allowlist=allowlist)


def _current_exec_email(ctx) -> str:
    # Dev shortcut: short-circuit auth when MCP_DEV_EXEC_EMAIL is set.
    if os.environ.get("MCP_DEV_EXEC_EMAIL"):
        return os.environ["MCP_DEV_EXEC_EMAIL"]

    headers = getattr(ctx.request_context.request, "headers", {}) or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    token = auth.split(None, 1)[1].strip()
    return extract_exec_email(token=token, ctx=_auth_context())


@mcp.tool()
async def consultar_bq(sql: str, ctx) -> dict:
    """Run a SELECT query against BigQuery.

    Only SELECT / WITH single-statement SQL is accepted.
    Returns rows (capped) plus bytes_billed / bytes_processed.
    """
    exec_email = _current_exec_email(ctx)
    start = _time.time()
    try:
        validate_readonly_sql(sql)
    except SqlValidationError as e:
        out = {"error": f"sql_validation: {e}"}
        _audit_log().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=out["error"],
        )
        return out

    await ctx.report_progress(progress=0.0, total=1.0, message="querying BigQuery...")
    client = _build_bq_client()
    try:
        result = client.run_query(sql=sql, exec_email=exec_email)
    except Exception as e:  # noqa: BLE001
        out = {"error": f"bq_execution: {e}"}
        _audit_log().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=out["error"],
        )
        return out
    await ctx.report_progress(progress=1.0, total=1.0, message="query complete")
    _audit_log().record(
        exec_email=exec_email, tool="consultar_bq", sql=sql,
        bytes_scanned=result.bytes_processed or 0,
        row_count=result.row_count,
        duration_ms=int((_time.time() - start) * 1000),
        result="ok", error=None,
    )
    return {
        "rows": result.rows,
        "row_count": result.row_count,
        "bytes_billed": result.bytes_billed,
        "bytes_processed": result.bytes_processed,
        "truncated": result.truncated,
    }


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "analise"


def publicar_dashboard_impl(
    *,
    title: str,
    brand: str,
    period: str,
    description: str,
    html_content: str,
    tags: list[str],
    exec_email: str,
    progress,
) -> dict:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    settings = load_settings(settings_path)
    repo_root = _repo_root()

    today = datetime.now(timezone.utc).date().isoformat()
    short_hash = hashlib.sha1(
        f"{exec_email}{title}{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()[:8]
    slug = _slugify(title)
    filename = f"{slug}-{today}-{short_hash}.html"

    try:
        analysis_path = exec_analysis_path(repo_root, exec_email, filename)
        library_path = exec_library_path(repo_root, exec_email)
    except PathSandboxError as e:
        return {"error": f"path_sandbox: {e}"}

    if progress:
        progress("rendering dashboard...")
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.write_text(html_content)

    entry_id = f"{slug}-{short_hash}"
    link = f"/analyses/{exec_email}/{filename}"
    prepend_entry(
        library_path,
        LibraryEntry(
            id=entry_id, title=title, brand=brand, date=today,
            link=link, description=description, tags=tags, filename=filename,
        ),
    )

    if progress:
        progress("publishing to Vercel...")
    git = GitOps(
        repo_path=repo_root,
        author_name=settings.github.author_name,
        author_email=settings.github.author_email,
        branch=settings.github.branch,
        push=os.environ.get("MCP_GIT_PUSH", "0") == "1",
    )
    try:
        sha = git.commit_paths(
            paths=[analysis_path, library_path],
            message=f"análise dispatched para {exec_email}: {title}",
        )
    except subprocess.CalledProcessError as e:
        output = e.output.decode(errors="replace") if e.output else str(e)
        return {"error": f"git_commit: {output.strip()}"}
    return {
        "id": entry_id,
        "link": link,
        "published_at": today,
        "commit_sha": sha,
    }


@mcp.tool()
async def publicar_dashboard(
    title: str,
    brand: str,
    period: str,
    description: str,
    html_content: str,
    tags: list[str],
    ctx,
) -> dict:
    """Publish an HTML dashboard to the exec's analysis sandbox + update library."""
    exec_email = _current_exec_email(ctx)
    start = _time.time()
    await ctx.report_progress(progress=0.0, total=1.0, message="rendering dashboard...")
    result = publicar_dashboard_impl(
        title=title, brand=brand, period=period, description=description,
        html_content=html_content, tags=tags,
        exec_email=exec_email, progress=None,
    )
    if "error" in result:
        _audit_log().record(
            exec_email=exec_email, tool="publicar_dashboard", sql=None,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=result["error"],
        )
        return result
    await ctx.report_progress(progress=0.5, total=1.0, message="publishing to Vercel...")
    await ctx.report_progress(progress=1.0, total=1.0, message="dashboard published")
    _audit_log().record(
        exec_email=exec_email, tool="publicar_dashboard", sql=None,
        bytes_scanned=0, row_count=0,
        duration_ms=int((_time.time() - start) * 1000),
        result="ok", error=None,
    )
    return result


def listar_analises_impl(escopo: str, exec_email: str) -> dict:
    if escopo not in {"mine", "public"}:
        return {"error": "escopo must be 'mine' or 'public'"}
    repo_root = _repo_root()
    email_key = exec_email if escopo == "mine" else "public"
    lib = repo_root / "library" / f"{email_key}.json"
    if not lib.exists():
        return {"items": []}
    try:
        data = json.loads(lib.read_text() or "[]")
    except json.JSONDecodeError as e:
        return {"error": f"library_parse: {e}"}
    return {"items": data}


@mcp.tool()
async def listar_analises(escopo: str, ctx) -> dict:
    """List analyses. escopo: 'mine' (own sandbox) or 'public' (shared library)."""
    exec_email = _current_exec_email(ctx)
    start = _time.time()
    result = listar_analises_impl(escopo=escopo, exec_email=exec_email)
    if "error" in result:
        _audit_log().record(
            exec_email=exec_email, tool="listar_analises", sql=None,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=result["error"],
        )
    else:
        _audit_log().record(
            exec_email=exec_email, tool="listar_analises", sql=None,
            bytes_scanned=0, row_count=len(result.get("items", [])),
            duration_ms=int((_time.time() - start) * 1000),
            result="ok", error=None,
        )
    return result


def main() -> None:
    import uvicorn
    from mcp_exec.auth_routes import build_auth_app
    from mcp_exec.azure_auth import AzureAuth

    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    settings = load_settings(settings_path)

    azure = AzureAuth(
        tenant_id=os.environ["MCP_AZURE_TENANT_ID"],
        client_id=os.environ["MCP_AZURE_CLIENT_ID"],
        client_secret=os.environ["MCP_AZURE_CLIENT_SECRET"],
        redirect_uri=os.environ.get("MCP_AZURE_REDIRECT_URI", "http://localhost:8765/"),
    )
    issuer = TokenIssuer(
        secret=os.environ["MCP_JWT_SECRET"],
        issuer=settings.auth.jwt_issuer,
        access_ttl_s=settings.auth.access_token_ttl_s,
        refresh_ttl_s=settings.auth.refresh_token_ttl_s,
    )
    allowlist = Allowlist(
        path=Path(os.environ.get("MCP_ALLOWLIST", "/app/config/allowed_execs.json"))
    )

    auth_app = build_auth_app(azure=azure, issuer=issuer, allowlist=allowlist)

    # Mount MCP SSE transport under /mcp path
    try:
        auth_app.mount("/mcp", mcp.sse_app())
    except AttributeError:
        # Some FastMCP versions expose `.streamable_http_app()` instead
        auth_app.mount("/mcp", mcp.streamable_http_app())

    uvicorn.run(auth_app, host=settings.server.host, port=settings.server.port)


if __name__ == "__main__":
    main()
