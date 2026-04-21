from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, cast

from mcp.server.fastmcp import Context, FastMCP

from mcp_exec.allowlist import Allowlist
from mcp_exec.audit import AuditLog
from mcp_exec.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_exec.bq_client import BqClient, QueryResult
from mcp_exec.context_loader import load_exec_context
from mcp_exec.git_ops import GitOps
from mcp_exec.jwt_tokens import TokenIssuer
from mcp_exec.library import LibraryEntry, prepend_entry
from mcp_exec.sandbox import PathSandboxError, exec_analysis_path, exec_library_path
from mcp_exec.settings import load_settings
from mcp_exec.sql_validator import SqlValidationError, validate_readonly_sql

from mcp.server.streamable_http_manager import TransportSecuritySettings as _TSS

_public_host = os.environ.get("MCP_PUBLIC_HOST", "bq-analista-production-59a9.up.railway.app")
mcp = FastMCP(
    "mcp-exec-azzas",
    transport_security=_TSS(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            _public_host,
            f"{_public_host}:443",
            "localhost",
            "localhost:8080",
            "127.0.0.1",
        ],
        allowed_origins=[
            f"https://{_public_host}",
            "https://claude.ai",
        ],
    ),
)


def _repo_root() -> Path:
    # Repo is mounted into container at /app/repo in prod; dev uses MCP_REPO_ROOT env.
    return Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))


def _settings_path() -> Path:
    return Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))


@mcp.tool()
def get_context(ctx: Context) -> dict[str, object]:
    """Return concatenated docs (schema.md, business-rules.md, SKILL.md) plus allowed tables.

    Call once at session start to prime Claude with the analytics context.
    Requires a valid bearer token (same auth gate as other tools) so the
    schema and business rules are not exposed to unauthenticated callers.
    """
    _current_exec_email(ctx)  # enforces bearer + allowlist, raises AuthError otherwise
    loaded = load_exec_context(_repo_root())
    return {"text": loaded.text, "allowed_tables": loaded.allowed_tables}


def _build_bq_client() -> BqClient:
    settings = load_settings(_settings_path())
    return BqClient(settings=settings.bigquery)


def _bq_result_to_dict(result: QueryResult) -> dict[str, object]:
    return {
        "rows": result.rows,
        "row_count": result.row_count,
        "bytes_billed": result.bytes_billed,
        "bytes_processed": result.bytes_processed,
        "truncated": result.truncated,
    }


_AUDIT: AuditLog | None = None


def _audit_log() -> AuditLog:
    global _AUDIT
    if _AUDIT is None:
        settings = load_settings(_settings_path())
        _AUDIT = AuditLog(db_path=Path(settings.audit.db_path))
    return _AUDIT


def consultar_bq_impl(
    sql: str,
    exec_email: str,
    progress: Callable[[str], None] | None,
) -> dict[str, object]:
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
    return _bq_result_to_dict(result)


def _auth_context() -> AuthContext:
    settings = load_settings(_settings_path())
    secret = os.environ.get("MCP_JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "MCP_JWT_SECRET environment variable is required. "
            "Generate one with: openssl rand -hex 32"
        )
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


def _current_exec_email(ctx: Context) -> str:
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
async def consultar_bq(sql: str, ctx: Context) -> dict[str, object]:
    """Run a SELECT query against BigQuery.

    Only SELECT / WITH single-statement SQL is accepted.
    Returns rows (capped) plus bytes_billed / bytes_processed.
    """
    exec_email = _current_exec_email(ctx)
    start = _time.time()
    await ctx.report_progress(progress=0.0, total=1.0, message="querying BigQuery...")
    out = consultar_bq_impl(sql=sql, exec_email=exec_email, progress=None)
    duration_ms = int((_time.time() - start) * 1000)
    if "error" in out:
        _audit_log().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=duration_ms,
            result="error", error=cast(str, out["error"]),
        )
        return out
    await ctx.report_progress(progress=1.0, total=1.0, message="query complete")
    _audit_log().record(
        exec_email=exec_email, tool="consultar_bq", sql=sql,
        bytes_scanned=cast(int, out.get("bytes_processed") or 0),
        row_count=cast(int, out.get("row_count", 0)),
        duration_ms=duration_ms,
        result="ok", error=None,
    )
    return out


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
    progress: Callable[[str], None] | None,
) -> dict[str, object]:
    settings = load_settings(_settings_path())
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
    ctx: Context,
) -> dict[str, object]:
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
            result="error", error=cast(str, result["error"]),
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


def listar_analises_impl(escopo: str, exec_email: str) -> dict[str, object]:
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
async def listar_analises(escopo: str, ctx: Context) -> dict[str, object]:
    """List analyses. escopo: 'mine' (own sandbox) or 'public' (shared library)."""
    exec_email = _current_exec_email(ctx)
    start = _time.time()
    result = listar_analises_impl(escopo=escopo, exec_email=exec_email)
    if "error" in result:
        _audit_log().record(
            exec_email=exec_email, tool="listar_analises", sql=None,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=cast(str, result["error"]),
        )
    else:
        _audit_log().record(
            exec_email=exec_email, tool="listar_analises", sql=None,
            bytes_scanned=0, row_count=len(cast(list[object], result.get("items", []))),
            duration_ms=int((_time.time() - start) * 1000),
            result="ok", error=None,
        )
    return result


def main() -> None:
    import contextlib
    import uvicorn
    from mcp_exec.auth_routes import build_auth_app
    from mcp_exec.azure_auth import AzureAuth

    settings = load_settings(_settings_path())

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

    # StreamableHTTP requires its session_manager to be started via lifespan.
    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with mcp.session_manager.run():
            yield

    auth_app = build_auth_app(azure=azure, issuer=issuer, allowlist=allowlist, lifespan=lifespan)

    # streamable_http_app() exposes /mcp — mount at root so it lands at /mcp.
    auth_app.mount("/", mcp.streamable_http_app())

    port = int(os.environ.get("PORT", settings.server.port))
    uvicorn.run(auth_app, host=settings.server.host, port=port)


if __name__ == "__main__":
    main()
