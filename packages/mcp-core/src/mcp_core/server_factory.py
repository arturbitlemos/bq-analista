# packages/mcp-core/src/mcp_core/server_factory.py
from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import os
import re
import subprocess
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, cast

import uvicorn
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.streamable_http_manager import TransportSecuritySettings as _TSS

from mcp_core.allowlist import Allowlist
from mcp_core.audit import AuditLog
from mcp_core.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_core.auth_routes import build_auth_app
from mcp_core.azure_auth import AzureAuth
from mcp_core.bq_client import BqClient, DatasetNotAllowedError
from mcp_core.context_loader import load_exec_context
from mcp_core.git_ops import GitOps
from mcp_core.jwt_tokens import TokenIssuer
from mcp_core.library import LibraryEntry, prepend_entry
from mcp_core.sandbox import PathSandboxError, exec_analysis_path, public_library_path
from mcp_core.settings import load_settings
from mcp_core.sql_validator import SqlValidationError, validate_readonly_sql


def _repo_root() -> Path:
    return Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))


def _settings_path() -> Path:
    return Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "analise"


def build_mcp_app(agent_name: str) -> tuple[FastMCP, Callable]:
    """
    Build a FastMCP app with the 4 base tools registered.

    Returns (app, main):
    - app:  FastMCP instance — use @app.tool() to add domain-specific tools
    - main: callable entrypoint — use as if __name__ == '__main__': main()

    All configuration is read from env vars and /app/config/settings.toml at runtime.
    """
    public_host = os.environ.get("MCP_PUBLIC_HOST", "localhost")
    mcp = FastMCP(
        agent_name,
        transport_security=_TSS(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                public_host,
                f"{public_host}:443",
                "localhost",
                "localhost:8080",
                "127.0.0.1",
            ],
            allowed_origins=[
                f"https://{public_host}",
                "https://claude.ai",
            ],
        ),
    )

    # ── Internal singletons ────────────────────────────────────────────────

    _audit: AuditLog | None = None

    def _get_audit() -> AuditLog:
        nonlocal _audit
        if _audit is None:
            settings = load_settings(_settings_path())
            _audit = AuditLog(db_path=Path(settings.audit.db_path))
        return _audit

    # lru_cache(1) caches the AuthContext across requests so PyJWKClient is reused
    @functools.lru_cache(maxsize=1)
    def _get_auth_context() -> AuthContext:
        settings = load_settings(_settings_path())
        secret = os.environ.get("MCP_JWT_SECRET")
        if not secret:
            raise RuntimeError(
                "MCP_JWT_SECRET environment variable is required. "
                "Generate with: openssl rand -hex 32"
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
        return AuthContext(
            issuer=issuer,
            allowlist=allowlist,
            azure_tenant_id=os.environ.get("MCP_AZURE_TENANT_ID", ""),
            azure_client_id=os.environ.get("MCP_AZURE_CLIENT_ID", ""),
        )

    def _current_email(ctx: Context) -> str:
        if os.environ.get("MCP_DEV_EXEC_EMAIL"):
            return os.environ["MCP_DEV_EXEC_EMAIL"]
        headers = getattr(ctx.request_context.request, "headers", {}) or {}
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        if not auth.lower().startswith("bearer "):
            raise AuthError("missing bearer token")
        token = auth.split(None, 1)[1].strip()
        return extract_exec_email(token=token, ctx=_get_auth_context())

    def _build_bq_client() -> BqClient:
        settings = load_settings(_settings_path())
        return BqClient(settings=settings.bigquery)

    # ── Base tool: get_context ─────────────────────────────────────────────
    @mcp.tool()
    def get_context(ctx: Context) -> dict[str, object]:
        """Return merged context: shared principles + agent schema + business rules.
        Call once at session start to prime Claude with domain knowledge."""
        _current_email(ctx)
        settings = load_settings(_settings_path())
        repo_root = _repo_root()
        domain = settings.server.domain
        shared_root = repo_root / "shared" / "context"
        agent_root = repo_root / "agents" / domain / "src" / "agent"
        loaded = load_exec_context(agent_root=agent_root, shared_root=shared_root)
        return {"text": loaded.text, "allowed_tables": loaded.allowed_tables}

    # ── Base tool: consultar_bq ────────────────────────────────────────────
    @mcp.tool()
    async def consultar_bq(sql: str, ctx: Context) -> dict[str, object]:
        """Run a SELECT query against BigQuery. Only SELECT/WITH is accepted.
        Returns rows, bytes_billed, bytes_processed."""
        exec_email = _current_email(ctx)
        start = _time.time()
        await ctx.report_progress(progress=0.0, total=1.0, message="validating query...")
        try:
            validate_readonly_sql(sql)
        except SqlValidationError as e:
            return {"error": f"sql_validation: {e}"}
        await ctx.report_progress(progress=0.2, total=1.0, message="checking dataset access...")
        client = _build_bq_client()
        try:
            result = client.run_query(sql=sql, exec_email=exec_email)
        except DatasetNotAllowedError as e:
            return {"error": f"dataset_not_allowed: {e}"}
        except Exception as e:
            return {"error": f"bq_execution: {e}"}
        duration_ms = int((_time.time() - start) * 1000)
        await ctx.report_progress(progress=1.0, total=1.0, message="query complete")
        _get_audit().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=cast(int, result.bytes_processed or 0),
            row_count=result.row_count,
            duration_ms=duration_ms,
            result="ok", error=None,
        )
        return {
            "rows": result.rows,
            "row_count": result.row_count,
            "bytes_billed": result.bytes_billed,
            "bytes_processed": result.bytes_processed,
            "truncated": result.truncated,
        }

    # ── Base tool: publicar_dashboard ─────────────────────────────────────
    @mcp.tool()
    async def publicar_dashboard(
        title: str, brand: str, period: str,
        description: str, html_content: str,
        tags: list[str], ctx: Context,
    ) -> dict[str, object]:
        """Publish an HTML dashboard to the exec's sandbox and update the library."""
        exec_email = _current_email(ctx)
        settings = load_settings(_settings_path())
        repo_root = _repo_root()
        domain = settings.server.domain

        today = datetime.now(timezone.utc).date().isoformat()
        short_hash = hashlib.sha1(
            f"{exec_email}{title}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:8]
        slug = _slugify(title)
        filename = f"{slug}-{today}-{short_hash}.html"

        portal_root = repo_root / "portal"
        try:
            analysis_path = exec_analysis_path(portal_root, domain, exec_email, filename)
            library_path = public_library_path(portal_root, domain)
        except PathSandboxError as e:
            return {"error": f"path_sandbox: {e}"}

        await ctx.report_progress(progress=0.0, total=1.0, message="rendering dashboard...")
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        analysis_path.write_text(html_content)

        entry_id = f"{slug}-{short_hash}"
        link = f"/analyses/{domain}/{exec_email}/{filename}"
        library_path.parent.mkdir(parents=True, exist_ok=True)
        prepend_entry(
            library_path,
            LibraryEntry(
                id=entry_id, title=title, brand=brand, date=today,
                link=link, description=description, tags=tags, filename=filename,
            ),
        )

        await ctx.report_progress(progress=0.5, total=1.0, message="publishing to git...")
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

        await ctx.report_progress(progress=1.0, total=1.0, message="dashboard published")
        return {"id": entry_id, "link": link, "published_at": today, "commit_sha": sha}

    # ── Base tool: listar_analises ─────────────────────────────────────────
    @mcp.tool()
    async def listar_analises(escopo: str, ctx: Context) -> dict[str, object]:
        """List analyses. escopo: 'mine' (own sandbox) or 'public' (shared library)."""
        if escopo not in ("mine", "public"):
            return {"error": "invalid_escopo: must be 'mine' or 'public'"}
        exec_email = _current_email(ctx)
        settings = load_settings(_settings_path())
        repo_root = _repo_root()
        domain = settings.server.domain
        email_key = exec_email if escopo == "mine" else "public"
        lib = repo_root / "portal" / "library" / domain / f"{email_key}.json"
        if not lib.exists():
            return {"items": []}
        try:
            data = json.loads(lib.read_text() or "[]")
        except json.JSONDecodeError as e:
            return {"error": f"library_parse: {e}"}
        return {"items": data}

    # ── main() entrypoint ──────────────────────────────────────────────────
    def main() -> None:
        settings = load_settings(_settings_path())
        azure = AzureAuth(
            tenant_id=os.environ["MCP_AZURE_TENANT_ID"],
            client_id=os.environ["MCP_AZURE_CLIENT_ID"],
            client_secret=os.environ["MCP_AZURE_CLIENT_SECRET"],
            redirect_uri=os.environ.get(
                "MCP_AZURE_REDIRECT_URI",
                f"https://{os.environ.get('MCP_PUBLIC_HOST', 'localhost')}/auth/callback",
            ),
        )
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

        @contextlib.asynccontextmanager
        async def lifespan(app):
            async with mcp.session_manager.run():
                yield

        auth_app = build_auth_app(
            azure=azure, issuer=issuer, allowlist=allowlist, lifespan=lifespan
        )
        auth_app.mount("/", mcp.streamable_http_app())
        port = int(os.environ.get("PORT", settings.server.port))
        uvicorn.run(auth_app, host=settings.server.host, port=port)

    return mcp, main
