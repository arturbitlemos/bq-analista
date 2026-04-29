from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import os
import re
import subprocess
import time as _time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, cast

import uvicorn
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.streamable_http_manager import TransportSecuritySettings as _TSS

from mcp_core.allowlist import Allowlist
from mcp_core.audit import AuditLog
from mcp_core.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_core.auth_routes import build_auth_app
from mcp_core.azure_auth import AzureAuth
from mcp_core.bq_client import BqClient, DatasetNotAllowedError
from mcp_core.context_loader import ExecContext, extract_table_section, load_exec_context, parse_table_index
from mcp_core.jwt_tokens import TokenIssuer
from mcp_core.settings import Settings, load_settings
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


def build_mcp_app(
    agent_name: str,
    *,
    instructions: str | None = None,
    exemplos: str | None = None,
) -> tuple[FastMCP, Callable]:
    """
    Build a FastMCP app with the 7 base tools registered.

    Returns (app, main):
    - app:  FastMCP instance — use @app.tool() to add domain-specific tools
    - main: callable entrypoint — use as if __name__ == '__main__': main()

    instructions: short text shown to the client during MCP `initialize`
    handshake (treated by Claude as system context). Use it to introduce the
    agent's domain and give 2–3 example questions on first connect.

    exemplos: longer catalog of example questions returned by the optional
    `exemplos` tool. Registered only when this argument is provided.

    All configuration is read from env vars and /app/config/settings.toml at runtime.
    """
    public_host = os.environ.get("MCP_PUBLIC_HOST", "localhost")
    mcp = FastMCP(
        agent_name,
        instructions=instructions,
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

    # ── Cached app state (settings, BqClient, context files) ──────────────

    @dataclass
    class _AppState:
        settings: Settings
        bq_client: BqClient
        schema_text: str | None   # contents of schema.md, or None
        rules_text: str | None    # contents of business-rules.md, or None
        exec_context: ExecContext

    @functools.lru_cache(maxsize=1)
    def _load_cached_state() -> _AppState:
        settings = load_settings(_settings_path())
        image_root = _image_root()
        domain = settings.server.domain
        agent_root = image_root / "agents" / domain / "src" / "agent"
        schema_path = agent_root / "context" / "schema.md"
        rules_path = agent_root / "context" / "business-rules.md"
        shared_root = image_root / "shared" / "context"
        loaded = load_exec_context(agent_root=agent_root, shared_root=shared_root)
        return _AppState(
            settings=settings,
            bq_client=BqClient(settings.bigquery),
            schema_text=schema_path.read_text() if schema_path.exists() else None,
            rules_text=rules_path.read_text() if rules_path.exists() else None,
            exec_context=loaded,
        )

    # ── Internal singletons ────────────────────────────────────────────────

    _audit: AuditLog | None = None

    def _get_audit() -> AuditLog:
        nonlocal _audit
        if _audit is None:
            settings = _load_cached_state().settings
            _audit = AuditLog(db_path=Path(settings.audit.db_path))
        return _audit

    # lru_cache(1) caches the AuthContext across requests so PyJWKClient is reused
    @functools.lru_cache(maxsize=1)
    def _get_auth_context() -> AuthContext:
        settings = _load_cached_state().settings
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
        headers = getattr(ctx.request_context.request, "headers", {}) or {}
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        if not auth.lower().startswith("bearer "):
            raise AuthError("missing bearer token")
        token = auth.split(None, 1)[1].strip()
        return extract_exec_email(token=token, ctx=_get_auth_context())

    # ── Base tool: get_context ─────────────────────────────────────────────
    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    def get_context(ctx: Context) -> dict[str, object]:
        """Lightweight context: analyst principles, PII rules, and table index.
        Call once at session start. For full table schema use describe_table().
        For business rules and canonical SQL use get_business_rules()."""
        _current_email(ctx)
        state = _load_cached_state()
        return {"text": state.exec_context.text, "allowed_tables": state.exec_context.allowed_tables}

    # ── Base tool: describe_table ──────────────────────────────────────────
    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    def describe_table(table_name: str, ctx: Context) -> dict[str, object]:
        """Full schema for a BigQuery table: columns, types, PII flags, join patterns.
        Call before writing SQL that targets this table.
        table_name: exact name in UPPER_CASE (e.g. TB_WANMTP_VENDAS_LOJA_CAPTADO)."""
        _current_email(ctx)
        schema_text = _load_cached_state().schema_text
        if schema_text is None:
            return {"error": "schema.md não encontrado"}
        section = extract_table_section(schema_text, table_name)
        if not section:
            available = parse_table_index(schema_text)
            return {"error": f"Tabela '{table_name}' não encontrada.", "tabelas_disponíveis": available}
        return {"table_name": table_name.upper(), "schema": section}

    # ── Base tool: get_business_rules ──────────────────────────────────────
    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    def get_business_rules(ctx: Context) -> dict[str, object]:
        """Business rules: KPI definitions, canonical SQL patterns, known gotchas.
        Consult when calculating venda líquida, LY comparison, giro, or cobertura."""
        _current_email(ctx)
        rules_text = _load_cached_state().rules_text
        if rules_text is None:
            return {"error": "business-rules.md não encontrado"}
        return {"business_rules": rules_text}

    # ── Base tool: ping ────────────────────────────────────────────────────
    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    def ping(ctx: Context) -> dict[str, object]:
        """Health-check: returns server status, BigQuery project, and visible datasets.
        Call before any query to verify connectivity and confirm available datasets."""
        _current_email(ctx)
        settings = _load_cached_state().settings
        return {
            "status": "ok",
            "domain": settings.server.domain,
            "bq_project": settings.bigquery.project_id,
            "billing_project": settings.bigquery.billing_project_id,
            "allowed_datasets": settings.bigquery.allowed_datasets,
        }

    # ── Optional tool: exemplos (catalog of example questions) ─────────────
    if exemplos is not None:
        _exemplos_text = exemplos

        @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
        def exemplos_perguntas(ctx: Context) -> dict[str, object]:
            """Catálogo de perguntas que este agente sabe responder, com formatos de saída esperados.
            Chame quando o usuário perguntar 'o que você faz?' ou 'que tipo de pergunta posso fazer?'."""
            _current_email(ctx)
            return {"exemplos": _exemplos_text}

    # ── Base tool: consultar_bq ────────────────────────────────────────────
    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
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
        client = _load_cached_state().bq_client
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
    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def publicar_dashboard(
        title: str, brand: str, period: str,
        description: str, html_content: str,
        tags: list[str],
        refresh_spec: dict,
        ctx: Context,
        public: bool = False,
        shared_with: list[str] | None = None,
    ) -> dict[str, object]:
        """Publish an HTML dashboard to the analysis catalog (Postgres + Vercel Blob).

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
                refresh_spec={...},   # REQUIRED — see below
            )

        REQUIRED `refresh_spec` (dict) — every published analysis MUST be
        refreshable. The user expects to click "Atualizar período" in the
        portal and get the same analysis with a new date range. Without
        `refresh_spec` we don't know which SQLs to re-run, so the publish
        is rejected. Shape:

            {
              "queries": [{"id": "<query_id>", "sql": "SELECT ... '{{start_date}}' ... '{{end_date}}' ..."}, ...],
              "data_blocks": [{"block_id": "data_<id>", "query_id": "<query_id>"}, ...],
              "original_period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            }

        Build the HTML so every chart/number reads from a `<script id="data_X"
        type="application/json">…</script>` block — use the `html_data_block`
        tool to emit the canonical form. Each `data_blocks[i].block_id` MUST
        match a script tag id in `html_content`; validation rejects mismatches.
        SQLs use the literal placeholders `'{{start_date}}'` / `'{{end_date}}'`
        (with single quotes — they're substituted as ISO date strings).

        `public` — if True, anyone in the tenant can see the analysis.
        `shared_with` — explicit recipients (lowercased emails) granted read access
        even when public=False. Defaults to empty.

        After publishing, share the returned `url` so the user can open the
        report. Using PT aliases (titulo/marca/periodo/descricao) will fail with
        `Field required`."""
        from mcp_core.refresh_spec import RefreshSpec
        from mcp_core.html_swap import validate_blocks_present, validate_html_against_spec, SchemaError
        from mcp_core.email_norm import normalize_email
        from mcp_core import db as _db, analyses_repo, actions_audit
        from mcp_core.blob_client import BlobClient

        exec_email = normalize_email(_current_email(ctx))
        settings = _load_cached_state().settings
        domain = settings.server.domain

        today = datetime.now(timezone.utc).date().isoformat()
        short_hash = hashlib.sha1(
            f"{exec_email}{title}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:8]
        slug = _slugify(title)
        analysis_id = f"{slug}-{short_hash}"
        blob_pathname = f"analyses/{domain}/{analysis_id}.html"

        # refresh_spec is REQUIRED — analyses without one can't be refreshed
        # via the portal, which defeats the catalog's main value prop. Reject
        # with a message that tells the model exactly how to fix the call.
        if not refresh_spec or not isinstance(refresh_spec, dict):
            return {
                "error": (
                    "refresh_spec_required: every published analysis must be "
                    "refreshable. Build the HTML so each chart/number reads from a "
                    "<script id=\"data_X\" type=\"application/json\"> block (use "
                    "html_data_block to emit canonical form), then pass "
                    "refresh_spec={'queries':[{'id':'X','sql':\"SELECT ... '{{start_date}}' ... '{{end_date}}' ...\"}], "
                    "'data_blocks':[{'block_id':'data_X','query_id':'X'}], "
                    "'original_period':{'start':'YYYY-MM-DD','end':'YYYY-MM-DD'}}."
                )
            }
        try:
            spec_obj = RefreshSpec.model_validate(refresh_spec)
            block_ids = [b.block_id for b in spec_obj.data_blocks]
            validate_blocks_present(html_content, block_ids)
            validate_html_against_spec(html_content, spec_obj)
        except SchemaError as e:
            return {"error": f"refresh_spec_invalid: {e}"}
        except Exception as e:
            return {"error": f"refresh_spec_invalid: {e}"}
        period_start_d = spec_obj.original_period.start
        period_end_d = spec_obj.original_period.end

        await ctx.report_progress(progress=0.1, total=1.0, message="injecting CSP...")
        # CSP same as before — restrict network/form to same-origin (defense in depth)
        _csp = (
            "<meta http-equiv=\"Content-Security-Policy\" content=\""
            "default-src 'self' data: blob:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.plot.ly; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "form-action 'none';"
            "\">"
        )
        safe_html, n = re.subn(
            r"(?i)<head([^>]*)>",
            lambda m: f"<head{m.group(1)}>{_csp}",
            html_content, count=1,
        )
        if n == 0:
            safe_html = _csp + html_content

        await ctx.report_progress(progress=0.4, total=1.0, message="uploading to blob storage...")
        try:
            blob = BlobClient()
            blob_url = await blob.put(blob_pathname, safe_html.encode("utf-8"), content_type="text/html")
        except Exception as e:
            return {"error": f"blob_upload: {e}"}

        await ctx.report_progress(progress=0.8, total=1.0, message="indexing analysis...")
        try:
            async with _db.transaction() as conn:
                await analyses_repo.insert(conn, analyses_repo.AnalysisRow(
                    id=analysis_id,
                    agent_slug=domain,
                    author_email=exec_email,
                    title=title,
                    brand=brand,
                    period_label=period,
                    period_start=period_start_d,
                    period_end=period_end_d,
                    description=description,
                    tags=tags,
                    public=public,
                    shared_with=[normalize_email(e) for e in (shared_with or [])],
                    archived_by=[],
                    blob_pathname=blob_pathname,
                    blob_url=blob_url,
                    refresh_spec=spec_obj.model_dump(mode="json") if spec_obj else None,
                ))
                await actions_audit.record(
                    conn, action="publish", actor_email=exec_email,
                    analysis_id=analysis_id,
                    metadata={"public": public, "shared_with_count": len(shared_with or [])},
                )
        except Exception as e:
            # Blob is already uploaded but DB insert failed — orphan blob.
            # Cleanup attempt (best-effort).
            try:
                await blob.delete(blob_pathname)
            except Exception:
                pass
            return {"error": f"db_insert: {e}"}

        portal_base = os.environ.get("MCP_PORTAL_URL", "https://bq-analista.vercel.app").rstrip("/")
        link = f"/api/analysis/{analysis_id}"
        url = f"{portal_base}{link}"
        await ctx.report_progress(progress=1.0, total=1.0, message="dashboard published")
        return {"id": analysis_id, "link": link, "url": url, "published_at": today}

    # ── Base tool: listar_analises ─────────────────────────────────────────
    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    async def listar_analises(escopo: Literal["mine", "public"], ctx: Context, limit: int = 20) -> dict[str, object]:
        """List analyses. escopo: 'mine' (own authorship) or 'public' (catalog
        excluding own). limit: max items returned (default 20, capped at 100).

        Reads from the Postgres analyses table. ACL is applied automatically:
        you only see analyses you own, public ones, or ones explicitly shared
        with you. For richer search use `buscar_analises`."""
        from mcp_core.email_norm import normalize_email
        from mcp_core import db as _db, analyses_repo

        exec_email = normalize_email(_current_email(ctx))
        settings = _load_cached_state().settings
        domain = settings.server.domain
        capped_limit = max(1, min(int(limit), 100))

        async with _db.get_pool().acquire() as conn:
            rows = await analyses_repo.list_for_user(conn, agent_slug=domain, email=exec_email)

        if escopo == "mine":
            filtered = [r for r in rows if r.author_email == exec_email]
        else:  # "public": catalog excluding the user's own analyses
            filtered = [r for r in rows if r.author_email != exec_email]

        # PRIVACY: author_email is only revealed when the analysis is public or
        # the caller is the author. Recipients of a private-shared analysis
        # don't get to see who shared it (matches portal /api/library behavior).
        def _author(r):
            return r.author_email if (r.author_email == exec_email or r.public) else None

        items = [
            {
                "id": r.id, "title": r.title, "brand": r.brand, "period_label": r.period_label,
                "description": r.description, "tags": r.tags, "author_email": _author(r),
                "public": r.public,
                "last_refreshed_at": r.last_refreshed_at.isoformat() if r.last_refreshed_at else None,
                "has_refresh_spec": r.refresh_spec is not None,
            }
            for r in filtered[:capped_limit]
        ]
        return {"items": items, "total": len(filtered), "limit": capped_limit}

    # ── Helper tool: html_data_block ───────────────────────────────────────
    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    async def html_data_block(block_id: str, payload: list | dict) -> str:
        """Build the canonical <script id="..." type="application/json">…</script>
        block expected by the refresh swap regex. Use this whenever you embed
        query results in an HTML you'll publish via `publicar_dashboard` with
        a `refresh_spec` — handcrafted tags with different attribute order
        will break refresh.

        Example: html_data_block('data_top_lojas', [{'filial': 'X', 'venda': 100}])
        → '<script id="data_top_lojas" type="application/json">[{"filial":"X","venda":100}]</script>'"""
        from mcp_core.html_swap import make_data_block
        return make_data_block(block_id, payload)

    # ── Catalog tools: buscar_analises + obter_analise ─────────────────────
    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    async def buscar_analises(
        query: str,
        ctx: Context,
        brand: str | None = None,
        agent: str | None = None,
        days_back: int = 90,
        limit: int = 10,
    ) -> dict[str, object]:
        """Full-text search of previously published analyses (your own + public + shared with you).

        Use BEFORE generating a new non-trivial analysis to detect recent similar
        work — if a match exists from the last 30 days with the same brand/theme,
        suggest the user click "Atualizar período" on the existing card instead
        of recreating from scratch. For larger reuse, follow up with `obter_analise`
        to fetch the SQLs of the closest match and adapt them.

        Returns up to `limit` (capped at 25) entries ranked by Postgres FTS
        relevance × recency."""
        from mcp_core.email_norm import normalize_email
        from mcp_core import db as _db, analyses_repo

        exec_email = normalize_email(_current_email(ctx))
        async with _db.get_pool().acquire() as conn:
            rows = await analyses_repo.search(
                conn, query=query, email=exec_email,
                agent=agent, brand=brand,
                days_back=days_back, limit=min(int(limit), 25),
            )
        # PRIVACY: same masking as listar_analises — recipients of a private
        # share don't see the author's email.
        def _author(r):
            return r.author_email if (r.author_email == exec_email or r.public) else None

        return {
            "results": [
                {
                    "id": r.id, "title": r.title, "description": r.description,
                    "brand": r.brand, "author_email": _author(r), "agent_slug": r.agent_slug,
                    "period_label": r.period_label, "tags": r.tags,
                    "last_refreshed_at": r.last_refreshed_at.isoformat() if r.last_refreshed_at else None,
                    "has_refresh_spec": r.refresh_spec is not None,
                }
                for r in rows
            ],
        }

    @mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False})
    async def obter_analise(id: str, ctx: Context) -> dict[str, object]:
        """Fetch full metadata + refresh_spec (with SQLs) for one analysis.

        Use after `buscar_analises` when one of the results looks reusable —
        gives you the original SQLs (with `{{start_date}}`/`{{end_date}}`
        placeholders) so you can adapt them for the current request. ACL is
        enforced — returns `{"error": "forbidden"}` if you can't see the
        analysis, `{"error": "not_found"}` if the id doesn't exist.

        Does NOT return the rendered HTML (too large for context). If you
        actually need the HTML, ask the user to open the link directly."""
        from mcp_core.email_norm import normalize_email
        from mcp_core import db as _db, analyses_repo

        exec_email = normalize_email(_current_email(ctx))
        async with _db.get_pool().acquire() as conn:
            row = await analyses_repo.get(conn, id)
        if row is None:
            return {"error": "not_found"}
        allowed = (
            row.author_email == exec_email
            or row.public
            or (exec_email in (row.shared_with or []))
        )
        if not allowed:
            return {"error": "forbidden"}
        author_visible = (row.author_email == exec_email) or row.public
        return {
            "id": row.id, "title": row.title, "description": row.description,
            "brand": row.brand,
            "author_email": row.author_email if author_visible else None,
            "agent_slug": row.agent_slug,
            "period_label": row.period_label, "tags": row.tags,
            "refresh_spec": row.refresh_spec,
            "last_refreshed_at": row.last_refreshed_at.isoformat() if row.last_refreshed_at else None,
        }

    # ── main() entrypoint ──────────────────────────────────────────────────
    def main() -> None:
        _load_cached_state()  # validate credentials and load context files at startup
        settings = _load_cached_state().settings
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
            from mcp_core import db as _db
            await _db.init_pool()
            try:
                async with mcp.session_manager.run():
                    yield
            finally:
                await _db.close_pool()

        auth_app = build_auth_app(
            azure=azure, issuer=issuer, allowlist=allowlist, lifespan=lifespan
        )

        # Register portal-driven REST endpoints (e.g. /api/refresh/{id}).
        # Mount BEFORE the catch-all /mcp app so /api/* paths are matched first.
        from mcp_core.api_routes import register_api_routes
        from mcp_core.auth_middleware import AuthContext
        from mcp_core.blob_client import BlobClient
        api_auth_ctx = AuthContext(
            issuer=issuer, allowlist=allowlist,
            azure_tenant_id=os.environ["MCP_AZURE_TENANT_ID"],
            azure_client_id=os.environ["MCP_AZURE_CLIENT_ID"],
        )
        register_api_routes(
            auth_app,
            auth_ctx=api_auth_ctx,
            bq_factory=lambda: _load_cached_state().bq_client,
            blob_factory=lambda: BlobClient(),
        )

        auth_app.mount("/", mcp.streamable_http_app())
        port = int(os.environ.get("PORT", settings.server.port))
        # In-memory state (refresh-token families in TokenIssuer, OAuth states
        # in auth_routes._pending_states / _pending_exchanges) is per-process.
        # Multi-worker deployments would let an attacker bypass refresh-token
        # reuse detection by hitting a worker that hasn't seen the consumed jti.
        # Fail loud if an operator tries to scale horizontally.
        workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
        if workers > 1:
            raise RuntimeError(
                f"WEB_CONCURRENCY={workers} but mcp-core requires a single worker. "
                "Refresh-token rotation, OAuth state, and exchange codes are kept "
                "in-process; multi-worker would silently break their reuse detection. "
                "Move to a shared store (Redis) before scaling."
            )
        uvicorn.run(auth_app, host=settings.server.host, port=port, workers=1)

    return mcp, main
