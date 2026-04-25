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
from mcp_core.context_loader import extract_table_section, load_exec_context, parse_table_index
from mcp_core.git_ops import GitOps
from mcp_core.jwt_tokens import TokenIssuer
from mcp_core.library import LibraryEntry, prepend_entry
from mcp_core.sandbox import (
    PathSandboxError,
    exec_analysis_path,
    exec_library_path,
    public_analysis_path,
    public_library_path,
)
from mcp_core.settings import load_settings
from mcp_core.sql_validator import SqlValidationError, validate_readonly_sql


def _repo_root() -> Path:
    return Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))


def _image_root() -> Path:
    """Root of the immutable code image (shared/, agents/, .claude/).

    Distinct from _repo_root() which points to the mutable git clone used by
    publicar_dashboard. Defaults to /app to match the Dockerfile layout."""
    return Path(os.environ.get("MCP_IMAGE_ROOT", "/app"))


def _settings_path() -> Path:
    return Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "analise"


def build_mcp_app(agent_name: str) -> tuple[FastMCP, Callable]:
    """
    Build a FastMCP app with the 7 base tools registered.

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
        """Lightweight context: analyst principles, PII rules, and table index.
        Call once at session start. For full table schema use describe_table().
        For business rules and canonical SQL use get_business_rules()."""
        _current_email(ctx)
        settings = load_settings(_settings_path())
        image_root = _image_root()
        domain = settings.server.domain
        shared_root = image_root / "shared" / "context"
        agent_root = image_root / "agents" / domain / "src" / "agent"
        loaded = load_exec_context(agent_root=agent_root, shared_root=shared_root)
        return {"text": loaded.text, "allowed_tables": loaded.allowed_tables}

    # ── Base tool: describe_table ──────────────────────────────────────────
    @mcp.tool()
    def describe_table(table_name: str, ctx: Context) -> dict[str, object]:
        """Full schema for a BigQuery table: columns, types, PII flags, join patterns.
        Call before writing SQL that targets this table.
        table_name: exact name in UPPER_CASE (e.g. TB_WANMTP_VENDAS_LOJA_CAPTADO)."""
        _current_email(ctx)
        settings = load_settings(_settings_path())
        image_root = _image_root()
        domain = settings.server.domain
        agent_root = image_root / "agents" / domain / "src" / "agent"
        schema_path = agent_root / "context" / "schema.md"
        if not schema_path.exists():
            return {"error": "schema.md não encontrado"}
        schema_text = schema_path.read_text()
        section = extract_table_section(schema_text, table_name)
        if not section:
            available = parse_table_index(schema_text)
            return {"error": f"Tabela '{table_name}' não encontrada.", "tabelas_disponíveis": available}
        return {"table_name": table_name.upper(), "schema": section}

    # ── Base tool: get_business_rules ──────────────────────────────────────
    @mcp.tool()
    def get_business_rules(ctx: Context) -> dict[str, object]:
        """Business rules: KPI definitions, canonical SQL patterns, known gotchas.
        Consult when calculating venda líquida, LY comparison, giro, or cobertura."""
        _current_email(ctx)
        settings = load_settings(_settings_path())
        image_root = _image_root()
        domain = settings.server.domain
        agent_root = image_root / "agents" / domain / "src" / "agent"
        rules_path = agent_root / "context" / "business-rules.md"
        if not rules_path.exists():
            return {"error": "business-rules.md não encontrado"}
        return {"business_rules": rules_path.read_text()}

    # ── Base tool: ping ────────────────────────────────────────────────────
    @mcp.tool()
    def ping(ctx: Context) -> dict[str, object]:
        """Health-check: returns server status, BigQuery project, and visible datasets.
        Call before any query to verify connectivity and confirm available datasets."""
        _current_email(ctx)
        settings = load_settings(_settings_path())
        return {
            "status": "ok",
            "domain": settings.server.domain,
            "bq_project": settings.bigquery.project_id,
            "billing_project": settings.bigquery.billing_project_id,
            "allowed_datasets": settings.bigquery.allowed_datasets,
        }

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
        """Publish an HTML dashboard to the public library and return the URL.

        Only call when the user explicitly asks to publish/share/save. Default
        flow is to render the HTML inline in the chat.

        Args are English — do not translate field names. Example call:

            publicar_dashboard(
                title="Farm · Produtividade por Loja · Abril/2026",
                brand="Farm",
                period="2026-04-01 a 2026-04-23",
                description="Comparativo de venda líquida e PA por filial vs LY.",
                html_content="<!doctype html>...",
                tags=["farm", "produtividade", "lojas"],
            )

        Using PT aliases (titulo/marca/periodo/descricao) will fail with
        `Field required`.

        After publishing, share the returned `url` so the user can open the
        report at https://analysis-lib.vercel.app/."""
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

        # Temporary: while Azure auth is not ready, force all publishes to public
        # so collaborators testing with a shared email can read each other's reports.
        force_public = os.environ.get("MCP_FORCE_PUBLIC", "0") == "1"

        portal_root = repo_root / "portal"
        try:
            if force_public:
                email_slug = re.sub(r"[^a-z0-9]+", "-", exec_email.lower()).strip("-")[:24] or "user"
                public_filename = f"{email_slug}-{filename}"
                analysis_path = public_analysis_path(portal_root, domain, public_filename)
                library_path = public_library_path(portal_root, domain)
                link = f"/analyses/{domain}/public/{public_filename}"
            else:
                analysis_path = exec_analysis_path(portal_root, domain, exec_email, filename)
                library_path = exec_library_path(portal_root, domain, exec_email)
                link = f"/analyses/{domain}/{exec_email}/{filename}"
        except PathSandboxError as e:
            return {"error": f"path_sandbox: {e}"}

        await ctx.report_progress(progress=0.0, total=1.0, message="rendering dashboard...")
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        analysis_path.write_text(html_content)

        entry_id = f"{slug}-{short_hash}"
        entry_filename = analysis_path.name
        library_path.parent.mkdir(parents=True, exist_ok=True)
        prepend_entry(
            library_path,
            LibraryEntry(
                id=entry_id, title=title, brand=brand, date=today,
                link=link, description=description, tags=tags, filename=entry_filename,
                author_email=exec_email,
            ),
        )

        await ctx.report_progress(progress=0.5, total=1.0, message="publishing to git...")
        git = GitOps(
            repo_path=repo_root,
            author_name=settings.github.author_name,
            author_email=settings.github.author_email,
            branch=settings.github.branch,
            push=os.environ.get("MCP_GIT_PUSH", "0") == "1",
            github_app_id=os.environ.get("GITHUB_APP_ID"),
            github_app_private_key=os.environ.get("GITHUB_APP_PRIVATE_KEY"),
        )
        try:
            sha = git.commit_paths(
                paths=[analysis_path, library_path],
                message=f"análise dispatched para {exec_email}: {title}",
            )
        except subprocess.CalledProcessError as e:
            output = e.output.decode(errors="replace") if e.output else str(e)
            return {"error": f"git_commit: {output.strip()}"}

        portal_base = os.environ.get("MCP_PORTAL_URL", "https://analysis-lib.vercel.app").rstrip("/")
        url = f"{portal_base}{link}"
        await ctx.report_progress(progress=1.0, total=1.0, message="dashboard published")
        return {"id": entry_id, "link": link, "url": url, "published_at": today, "commit_sha": sha}

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
