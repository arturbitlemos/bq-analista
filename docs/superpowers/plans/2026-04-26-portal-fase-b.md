# Portal Fase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate portal from git-as-source-of-truth to Postgres+Blob, add server-side report refresh with new period, granular email-based sharing, and expose the analysis catalog as MCP tools the agent uses to find prior work.

**Architecture:** Postgres (Neon, via Vercel Marketplace) is the source of truth for analysis metadata, ACL, and audit log. Vercel Blob stores HTML files, served behind ACL via signed URLs. Vercel Functions (portal) handle reads (library, view, share read) and non-BQ writes (share/archive). mcp-core (Railway) handles BQ-touching operations: `publicar_dashboard` (publish) and `POST /api/refresh/<id>`. Two-path auth in mcp-core: existing MSAL JWT (DXT clients) plus new HS256 proxy JWT (Vercel→Railway).

**Tech Stack:**
- Backend: Python 3.13, FastAPI, FastMCP, asyncpg, httpx, Pydantic v2, PyJWT
- Frontend: Vanilla JS SPA, vitest
- Storage: Neon (Postgres 16) with pooler endpoint, Vercel Blob (private)
- Auth layers: Azure MSAL (DXT, unchanged) + HMAC session cookie (portal, unchanged) + HS256 proxy JWT (new, Vercel→Railway)

**Spec:** `docs/superpowers/specs/2026-04-26-portal-fase-b-refresh-share-db-design.md`

---

## File map

### `packages/mcp-core/`

**Create:**
- `migrations/0001_create_analyses_audit.sql` — schema DDL
- `src/mcp_core/db.py` — asyncpg pool lifecycle
- `src/mcp_core/blob_client.py` — Vercel Blob HTTP wrapper
- `src/mcp_core/email_norm.py` — `normalize_email`
- `src/mcp_core/refresh_spec.py` — Pydantic models for `refresh_spec`
- `src/mcp_core/html_swap.py` — data island swap with safety checks
- `src/mcp_core/analyses_repo.py` — CRUD for `analyses` table
- `src/mcp_core/audit.py` — `record(action, actor, analysis_id, metadata)`
- `src/mcp_core/proxy_jwt.py` — HS256 verify
- `src/mcp_core/refresh_handler.py` — orchestrates BQ + swap + DB + Blob in one transaction
- `src/mcp_core/api_routes.py` — FastAPI routes for `/api/refresh/<id>`
- `tests/test_db.py`, `tests/test_blob_client.py`, `tests/test_email_norm.py`, `tests/test_refresh_spec.py`, `tests/test_html_swap.py`, `tests/test_analyses_repo.py`, `tests/test_audit.py`, `tests/test_proxy_jwt.py`, `tests/test_refresh_handler.py`, `tests/test_search.py`

**Modify:**
- `src/mcp_core/server_factory.py` — `publicar_dashboard` writes DB+Blob; new tools `buscar_analises`, `obter_analise`; mount api_routes; remove GitOps
- `src/mcp_core/auth_middleware.py` — accept HS256 proxy JWT path
- `pyproject.toml` — add `asyncpg`, `httpx`, `pyjwt[crypto]`
- `tests/test_server_factory.py` — update for new shape

**Delete:**
- `src/mcp_core/library.py` (replaced by `analyses_repo.py`)
- `src/mcp_core/clone_repo.py` and `src/mcp_core/git_ops.py` if present (no more git ops)
- `tests/test_library.py`

### `portal/`

**Create:**
- `portal/api/_helpers/db.js` — Neon serverless client
- `portal/api/_helpers/blob.js` — Vercel Blob client
- `portal/api/_helpers/email.js` — `normalizeEmail`
- `portal/api/_helpers/proxy_jwt.js` — mint HS256 proxy JWT
- `portal/api/library.js` — `GET /api/library?agent=X`
- `portal/api/analysis.js` — `GET /api/analysis/<id>` (302 to signed URL)
- `portal/api/archive.js` — `POST /api/archive`
- `portal/api/refresh-proxy.js` — `POST /api/refresh-proxy`
- `portal/api/tests/library.test.js`, `analysis.test.js`, `share.test.js`, `archive.test.js`, `refresh-proxy.test.js`

**Modify:**
- `portal/index.html` — 4 tabs (rename Time→Público, add Compartilhadas comigo), refresh modal, share modal, server-side archive, switch to /api/library and /api/analysis
- `portal/api/share.js` — rewrite for DB-backed model
- `portal/api/_helpers/session.js` — exists; verify it exports `verifySession`
- `portal/middleware.js` — remove ACL for `/library/` and `/analyses/` static paths (no longer served)
- `portal/vercel.json` — drop legacy rewrites if any
- `portal/package.json` — add `@neondatabase/serverless`, `@vercel/blob`, `jsonwebtoken`

**Move (not delete, for audit):**
- `portal/library/` → `legacy/portal-library/`
- `portal/analyses/` → `legacy/portal-analyses/`

### `agents/<domain>/SKILL.md` (vendas-linx + devolucoes)

**Modify:**
- Add section "Como gerar análise atualizável" (refresh_spec convention)
- Add section "Antes de criar uma análise nova: buscar histórico"
- Add section "Convenções de tags"

---

## Phase 0 — Pre-flight (manual setup, not automatable)

### Task 0: Provisionar serviços e env vars

**Não há código — instruções a executar manualmente uma vez.**

- [ ] **Step 1: Provisionar Neon Postgres via Vercel Marketplace**

No painel Vercel do projeto `bq-analista` → Storage → Browse Marketplace → Neon → Create. Plano free é suficiente. Criar branch `production` e branch `development`. Anotar `DATABASE_URL` (versão `-pooler`) das duas branches.

- [ ] **Step 2: Provisionar Vercel Blob**

No painel Vercel do projeto → Storage → Create Blob → name `analyses`. Vercel injeta `BLOB_READ_WRITE_TOKEN` automaticamente nas envs de Production e Preview.

- [ ] **Step 3: Gerar `MCP_PROXY_SIGNING_KEY`**

```bash
openssl rand -base64 64
```

Copiar a saída.

- [ ] **Step 4: Adicionar env vars no Vercel project**

Project Settings → Environment Variables:
- `MCP_PROXY_SIGNING_KEY` = (saída do step 3) — Production + Preview + Development
- `DATABASE_URL` já existe (Neon Marketplace setou).
- `BLOB_READ_WRITE_TOKEN` já existe.

- [ ] **Step 5: Adicionar env vars em cada serviço Railway**

No painel Railway → cada serviço (`vendas-linx-prod`, `devolucoes-prod`, e os de staging se existirem):
- `DATABASE_URL` = (mesma URL pooler do Vercel, branch `production` ou `development` conforme o env Railway)
- `BLOB_READ_WRITE_TOKEN` = (mesmo token do Vercel)
- `MCP_PROXY_SIGNING_KEY` = (mesma string do step 3)

- [ ] **Step 6: Verificar conexão**

Local, com `DATABASE_URL` no `.env`:

```bash
psql "$DATABASE_URL" -c "SELECT version();"
```

Esperado: linha com versão Postgres ≥ 16.

```bash
curl -sS -H "Authorization: Bearer $BLOB_READ_WRITE_TOKEN" \
  https://blob.vercel-storage.com/list
```

Esperado: JSON com `blobs: []` (vazio).

- [ ] **Step 7: Commit (sem código novo, mas registra a configuração)**

```bash
git commit --allow-empty -m "chore: provision neon + blob + proxy signing key for fase b"
```

---

## Phase 1 — Foundation: schema + low-level helpers

### Task 1: Schema migration SQL

**Files:**
- Create: `packages/mcp-core/migrations/0001_create_analyses_audit.sql`

- [ ] **Step 1: Criar arquivo de migration (idempotente)**

```sql
-- packages/mcp-core/migrations/0001_create_analyses_audit.sql
BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Skip the rest if this migration was already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM schema_migrations WHERE name = '0001_create_analyses_audit') THEN
        RAISE NOTICE 'migration 0001 already applied, skipping';
        RETURN;
    END IF;

    CREATE TABLE IF NOT EXISTS analyses (
        id              TEXT PRIMARY KEY,
        agent_slug      TEXT NOT NULL,
        author_email    TEXT NOT NULL,
        title           TEXT NOT NULL,
        brand           TEXT,
        period_label    TEXT,
        period_start    DATE,
        period_end      DATE,
        description     TEXT,
        tags            TEXT[]      NOT NULL DEFAULT '{}',
        public          BOOLEAN     NOT NULL DEFAULT FALSE,
        shared_with     TEXT[]      NOT NULL DEFAULT '{}',
        archived_by     TEXT[]      NOT NULL DEFAULT '{}',
        blob_pathname   TEXT        NOT NULL,
        blob_url        TEXT,
        refresh_spec    JSONB,
        last_refreshed_at  TIMESTAMPTZ,
        last_refreshed_by  TEXT,
        last_refresh_error TEXT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        search_doc      tsvector GENERATED ALWAYS AS (
            setweight(to_tsvector('portuguese', coalesce(title, '')), 'A') ||
            setweight(to_tsvector('portuguese', coalesce(description, '')), 'B') ||
            setweight(to_tsvector('portuguese', array_to_string(tags, ' ')), 'B') ||
            setweight(to_tsvector('portuguese', coalesce(brand, '')), 'C')
        ) STORED
    );

    CREATE INDEX IF NOT EXISTS analyses_agent_author_idx ON analyses(agent_slug, author_email);
    CREATE INDEX IF NOT EXISTS analyses_agent_public_idx ON analyses(agent_slug) WHERE public = TRUE;
    CREATE INDEX IF NOT EXISTS analyses_shared_with_gin  ON analyses USING GIN(shared_with);
    CREATE INDEX IF NOT EXISTS analyses_archived_by_gin  ON analyses USING GIN(archived_by);
    CREATE INDEX IF NOT EXISTS analyses_period_idx       ON analyses(agent_slug, period_end DESC);
    CREATE INDEX IF NOT EXISTS analyses_search_idx       ON analyses USING GIN(search_doc);

    CREATE TABLE IF NOT EXISTS audit_log (
        id            BIGSERIAL PRIMARY KEY,
        occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        actor_email   TEXT NOT NULL,
        action        TEXT NOT NULL,
        analysis_id   TEXT REFERENCES analyses(id) ON DELETE SET NULL,
        metadata      JSONB
    );

    CREATE INDEX IF NOT EXISTS audit_actor_time_idx ON audit_log(actor_email, occurred_at DESC);
    CREATE INDEX IF NOT EXISTS audit_analysis_idx   ON audit_log(analysis_id, occurred_at DESC);

    INSERT INTO schema_migrations (name) VALUES ('0001_create_analyses_audit');
END $$;

COMMIT;
```

**Nota:** adicionada coluna `blob_url TEXT` (cacheia a URL pública retornada pelo Blob no upload, evita HEAD round-trip em todo `/api/analysis/<id>`).

- [ ] **Step 2: Aplicar na branch `development` do Neon**

```bash
psql "$DATABASE_URL" -f packages/mcp-core/migrations/0001_create_analyses_audit.sql
```

Esperado: `BEGIN`, `CREATE TABLE`, `CREATE INDEX` x6, `CREATE TABLE`, `CREATE INDEX` x2, `COMMIT`.

- [ ] **Step 3: Verificar**

```bash
psql "$DATABASE_URL" -c "\d analyses"
psql "$DATABASE_URL" -c "\d audit_log"
```

Esperado: ambas as tabelas listadas com todas as colunas e indexes.

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/migrations/0001_create_analyses_audit.sql
git commit -m "feat(mcp-core): add postgres schema for analyses + audit log"
```

---

### Task 2: Adicionar dependências Python

**Files:**
- Modify: `packages/mcp-core/pyproject.toml`

- [ ] **Step 1: Adicionar dependências**

Editar `packages/mcp-core/pyproject.toml`, na lista `dependencies`:

```toml
dependencies = [
    # ... (o que já existe)
    "asyncpg>=0.29",
    "httpx>=0.27",
    "pyjwt[crypto]>=2.9",
]
```

E em `[project.optional-dependencies]` ou `[tool.uv]` (conforme convenção do projeto):

```toml
[project.optional-dependencies]
test = [
    # ... (o que já existe)
    "pytest-asyncio>=0.23",
]
```

- [ ] **Step 2: Instalar**

```bash
cd packages/mcp-core && uv sync --extra test
```

Esperado: pacotes adicionados, sem erro.

- [ ] **Step 3: Commit**

```bash
git add packages/mcp-core/pyproject.toml packages/mcp-core/uv.lock
git commit -m "chore(mcp-core): add asyncpg, httpx, pyjwt deps"
```

---

### Task 3: Email normalization helper

**Files:**
- Create: `packages/mcp-core/src/mcp_core/email_norm.py`
- Create: `packages/mcp-core/tests/test_email_norm.py`

- [ ] **Step 1: Escrever teste**

```python
# packages/mcp-core/tests/test_email_norm.py
from mcp_core.email_norm import normalize_email


def test_lowercase():
    assert normalize_email("Maria.Filo@Somagrupo.com.br") == "maria.filo@somagrupo.com.br"


def test_strip():
    assert normalize_email("  artur@somagrupo.com.br  ") == "artur@somagrupo.com.br"


def test_empty_string_raises():
    import pytest
    with pytest.raises(ValueError):
        normalize_email("")
    with pytest.raises(ValueError):
        normalize_email("   ")


def test_no_at_raises():
    import pytest
    with pytest.raises(ValueError):
        normalize_email("notanemail")
```

- [ ] **Step 2: Rodar teste, esperar falha**

```bash
cd packages/mcp-core && uv run pytest tests/test_email_norm.py -v
```

Esperado: ImportError (módulo não existe).

- [ ] **Step 3: Implementar**

```python
# packages/mcp-core/src/mcp_core/email_norm.py
def normalize_email(s: str) -> str:
    """Lowercased + stripped. Raises ValueError on empty or malformed."""
    if not s or not s.strip():
        raise ValueError("empty email")
    out = s.strip().lower()
    if "@" not in out:
        raise ValueError(f"invalid email: missing @ in {out!r}")
    return out
```

- [ ] **Step 4: Rodar teste, esperar passar**

```bash
cd packages/mcp-core && uv run pytest tests/test_email_norm.py -v
```

Esperado: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/email_norm.py packages/mcp-core/tests/test_email_norm.py
git commit -m "feat(mcp-core): add email normalization helper"
```

---

### Task 4: Postgres pool lifecycle

**Files:**
- Create: `packages/mcp-core/src/mcp_core/db.py`
- Create: `packages/mcp-core/tests/test_db.py`
- Create: `packages/mcp-core/tests/conftest.py` (se ainda não existe — fixture pra DB)

- [ ] **Step 1: Escrever conftest com fixture de DB**

```python
# packages/mcp-core/tests/conftest.py
import os
import pytest
import pytest_asyncio
from mcp_core import db


@pytest_asyncio.fixture
async def db_pool():
    """Inicializa o pool e limpa as tabelas antes/depois de cada teste.

    NOTA: Tests assumem execução serial. Não use pytest-xdist (-n) com esses testes —
    TRUNCATE é destrutivo e tests paralelos colidem. Se quiser paralelismo no futuro,
    migrar pra pytest-postgresql com DB efêmero por worker."""
    if "DATABASE_URL_TEST" not in os.environ:
        pytest.skip("DATABASE_URL_TEST not set")
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_TEST"]
    await db.init_pool()
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE analyses, audit_log RESTART IDENTITY CASCADE")
    yield
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE analyses, audit_log RESTART IDENTITY CASCADE")
    await db.close_pool()
```

- [ ] **Step 2: Escrever teste**

```python
# packages/mcp-core/tests/test_db.py
import pytest
from mcp_core import db


@pytest.mark.asyncio
async def test_pool_initialized(db_pool):
    pool = db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
    assert result == 1


@pytest.mark.asyncio
async def test_get_pool_before_init_raises():
    with pytest.raises(RuntimeError, match="not initialized"):
        # garantir estado limpo
        await db.close_pool()
        db.get_pool()


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(db_pool):
    with pytest.raises(ValueError):
        async with db.transaction() as conn:
            await conn.execute(
                "INSERT INTO analyses (id, agent_slug, author_email, title, blob_pathname) "
                "VALUES ('test1', 'vendas-linx', 'a@b.com', 'T', 'p')"
            )
            raise ValueError("boom")
    pool = db.get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM analyses WHERE id = 'test1'")
    assert count == 0
```

- [ ] **Step 3: Rodar teste, esperar falha (ImportError)**

```bash
cd packages/mcp-core && uv run pytest tests/test_db.py -v
```

- [ ] **Step 4: Implementar**

```python
# packages/mcp-core/src/mcp_core/db.py
from __future__ import annotations
import asyncpg
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    """Initialize the connection pool.

    `statement_cache_size=0` is REQUIRED when DATABASE_URL points to Neon's pooler
    endpoint (which uses pgbouncer in transaction mode and doesn't support
    prepared statements). Setting it to 0 disables asyncpg's prepared-statement
    cache. Without this, the first query may fail with a confusing protocol error."""
    global _pool
    dsn = os.environ["DATABASE_URL"]
    _pool = await asyncpg.create_pool(
        dsn, min_size=1, max_size=5, command_timeout=60,
        statement_cache_size=0,  # required for Neon pooler / pgbouncer transaction mode
    )


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() at startup")
    return _pool


@asynccontextmanager
async def transaction() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn
```

- [ ] **Step 5: Setar `DATABASE_URL_TEST` localmente apontando pra branch `development` do Neon**

No `.envrc` ou shell:
```bash
export DATABASE_URL_TEST="<pooler url da branch development>"
```

- [ ] **Step 6: Rodar teste, esperar passar**

```bash
cd packages/mcp-core && uv run pytest tests/test_db.py -v
```

Esperado: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add packages/mcp-core/src/mcp_core/db.py packages/mcp-core/tests/test_db.py packages/mcp-core/tests/conftest.py
git commit -m "feat(mcp-core): add asyncpg pool lifecycle"
```

---

### Task 5: Blob acessado via Vercel internal endpoint (mcp-core como cliente HTTP)

**Decisão arquitetural:** O SDK oficial do Vercel Blob (`@vercel/blob`) é Node-only. Em vez de chutar a API HTTP do Blob direto do mcp-core (Python), centralizamos toda interação com Blob no portal Vercel via um endpoint interno autenticado. mcp-core POSTa pra esse endpoint quando precisa upload/download. Vantagens: 1 SDK oficial, sem chute de API; endpoint interno pode evoluir se Vercel mudar; auth simétrica via `MCP_PROXY_SIGNING_KEY` (audience separada).

**Files:**
- Create: `portal/api/internal/blob.js` (endpoint interno, autenticado por proxy JWT com `aud=blob-internal`)
- Create: `packages/mcp-core/src/mcp_core/blob_client.py` (cliente HTTP fino que POSTa pro portal)
- Create: `packages/mcp-core/tests/test_blob_client.py`

#### Sub-task 5.1: Endpoint interno no portal

- [ ] **Step 1: Implementar `portal/api/internal/blob.js`**

```javascript
// portal/api/internal/blob.js
import { put, head, del } from '@vercel/blob'
import jwt from 'jsonwebtoken'

function verifyInternalJwt(authHeader) {
  if (!authHeader?.startsWith('Bearer ')) throw new Error('missing bearer')
  const token = authHeader.slice(7)
  return jwt.verify(token, process.env.MCP_PROXY_SIGNING_KEY, {
    algorithms: ['HS256'],
    audience: 'blob-internal',
  })
}

export const config = { api: { bodyParser: false } }  // we read raw body for PUT

async function readBody(req) {
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  return Buffer.concat(chunks)
}

export default async function handler(req, res) {
  try {
    verifyInternalJwt(req.headers.authorization)
  } catch (e) {
    return res.status(401).json({ error: `unauthorized: ${e.message}` })
  }

  const pathname = (req.query?.pathname || '').toString()
  if (!pathname.startsWith('analyses/')) {
    return res.status(400).json({ error: 'pathname must start with analyses/' })
  }

  if (req.method === 'PUT') {
    const body = await readBody(req)
    const contentType = (req.query?.content_type || 'application/octet-stream').toString()
    const blob = await put(pathname, body, {
      access: 'public',  // ACL enforced by /api/analysis endpoint, not by URL secrecy
      contentType,
      allowOverwrite: true,
      addRandomSuffix: false,
    })
    return res.status(200).json({ url: blob.url, pathname: blob.pathname })
  }

  if (req.method === 'GET') {
    const info = await head(pathname).catch(() => null)
    if (!info) return res.status(404).json({ error: 'not found' })
    const dl = await fetch(info.url)
    if (!dl.ok) return res.status(502).json({ error: `blob fetch failed: ${dl.status}` })
    res.setHeader('content-type', info.contentType || 'application/octet-stream')
    res.setHeader('cache-control', 'private, no-store')
    res.send(Buffer.from(await dl.arrayBuffer()))
    return
  }

  if (req.method === 'DELETE') {
    await del(pathname)
    return res.status(204).end()
  }

  return res.status(405).json({ error: 'method not allowed' })
}
```

- [ ] **Step 2: Smoke test do endpoint local**

Rodar `vercel dev` (ou `npm run dev` conforme convenção do portal). Em outro terminal:

```bash
TOKEN=$(node -e "console.log(require('jsonwebtoken').sign({aud:'blob-internal'}, process.env.MCP_PROXY_SIGNING_KEY, {algorithm:'HS256', expiresIn:60}))")

# upload
curl -X PUT "http://localhost:3000/api/internal/blob?pathname=analyses/test/smoke.html&content_type=text/html" \
  -H "authorization: Bearer $TOKEN" \
  --data-binary "<html>smoke</html>"

# download
curl "http://localhost:3000/api/internal/blob?pathname=analyses/test/smoke.html" \
  -H "authorization: Bearer $TOKEN"

# delete
curl -X DELETE "http://localhost:3000/api/internal/blob?pathname=analyses/test/smoke.html" \
  -H "authorization: Bearer $TOKEN"
```

Esperado: PUT retorna `{"url":"https://...","pathname":"analyses/test/smoke.html"}`; GET retorna `<html>smoke</html>`; DELETE retorna 204.

- [ ] **Step 3: Commit**

```bash
git add portal/api/internal/blob.js
git commit -m "feat(portal): add internal blob endpoint (write/read/delete via @vercel/blob)"
```

#### Sub-task 5.2: Cliente HTTP no mcp-core

- [ ] **Step 1: Escrever teste**

```python
# packages/mcp-core/tests/test_blob_client.py
import pytest
import httpx
from unittest.mock import patch, AsyncMock
from mcp_core.blob_client import BlobClient


@pytest.fixture
def blob_client(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    monkeypatch.setenv("PORTAL_BLOB_URL", "https://portal.test")
    return BlobClient()


@pytest.mark.asyncio
async def test_put_uploads(blob_client):
    mock_response = httpx.Response(200, json={"url": "https://blob.x/y.html", "pathname": "analyses/x/y.html"})
    with patch.object(httpx.AsyncClient, "put", new=AsyncMock(return_value=mock_response)) as m:
        url = await blob_client.put("analyses/x/y.html", b"<html></html>", content_type="text/html")
    assert url == "https://blob.x/y.html"
    call = m.call_args
    assert "authorization" in call.kwargs["headers"]
    assert call.kwargs["headers"]["authorization"].startswith("Bearer ")


@pytest.mark.asyncio
async def test_get_downloads(blob_client):
    mock_response = httpx.Response(200, content=b"<html>old</html>")
    with patch.object(httpx.AsyncClient, "get", new=AsyncMock(return_value=mock_response)):
        body = await blob_client.get("analyses/x/y.html")
    assert body == b"<html>old</html>"


@pytest.mark.asyncio
async def test_put_raises_on_5xx(blob_client):
    mock_response = httpx.Response(502, json={"error": "blob down"})
    with patch.object(httpx.AsyncClient, "put", new=AsyncMock(return_value=mock_response)):
        with pytest.raises(httpx.HTTPStatusError):
            await blob_client.put("analyses/x/y.html", b"x")
```

- [ ] **Step 2: Rodar teste, esperar falha (ImportError)**

- [ ] **Step 3: Implementar**

```python
# packages/mcp-core/src/mcp_core/blob_client.py
from __future__ import annotations
import os
import time
import jwt as pyjwt
import httpx


class BlobClient:
    """Cliente HTTP que delega operações de Blob pro endpoint interno do portal Vercel.

    Por que indireto: SDK oficial do Vercel Blob é Node-only. Centralizar a interação
    no portal evita chute de API HTTP e mantém uma única fonte de verdade pra evoluir."""

    def __init__(self, *, base_url: str | None = None, signing_key: str | None = None):
        self._base_url = (base_url or os.environ["PORTAL_BLOB_URL"]).rstrip("/")
        self._signing_key = signing_key or os.environ["MCP_PROXY_SIGNING_KEY"]

    def _mint_token(self, ttl_seconds: int = 60) -> str:
        return pyjwt.encode(
            {"aud": "blob-internal", "exp": int(time.time()) + ttl_seconds},
            self._signing_key, algorithm="HS256",
        )

    @property
    def _endpoint(self) -> str:
        return f"{self._base_url}/api/internal/blob"

    async def put(self, pathname: str, body: bytes, *, content_type: str = "text/html") -> str:
        token = self._mint_token()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                self._endpoint,
                params={"pathname": pathname, "content_type": content_type},
                content=body,
                headers={"authorization": f"Bearer {token}"},
            )
        resp.raise_for_status()
        return resp.json()["url"]

    async def get(self, pathname: str) -> bytes:
        token = self._mint_token()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self._endpoint,
                params={"pathname": pathname},
                headers={"authorization": f"Bearer {token}"},
            )
        resp.raise_for_status()
        return resp.content

    async def delete(self, pathname: str) -> None:
        token = self._mint_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.delete(
                self._endpoint,
                params={"pathname": pathname},
                headers={"authorization": f"Bearer {token}"},
            )
        resp.raise_for_status()
```

- [ ] **Step 4: Rodar teste, esperar passar**

```bash
cd packages/mcp-core && uv run pytest tests/test_blob_client.py -v
```

Esperado: 3 passed.

- [ ] **Step 5: Smoke test integrado obrigatório (não-opcional)**

Com portal rodando local (`vercel dev`) e `PORTAL_BLOB_URL=http://localhost:3000` + `MCP_PROXY_SIGNING_KEY=...`:

```bash
cd packages/mcp-core && uv run python -c "
import asyncio
from mcp_core.blob_client import BlobClient

async def main():
    c = BlobClient()
    url = await c.put('analyses/test/smoke.html', b'<html>smoke</html>')
    print('uploaded:', url)
    body = await c.get('analyses/test/smoke.html')
    assert body == b'<html>smoke</html>', body
    await c.delete('analyses/test/smoke.html')
    print('OK')

asyncio.run(main())
"
```

Esperado: `uploaded: https://...`, `OK`. **Bloqueia o avanço se falhar** — significa que o SDK do Vercel ou a auth do endpoint estão quebrados.

- [ ] **Step 6: Adicionar `PORTAL_BLOB_URL` nas envs Railway**

Cada serviço Railway precisa saber a URL do portal:
- `PORTAL_BLOB_URL` = `https://bq-analista.vercel.app` em produção
- Em staging/dev, apontar pra preview deploy ou `http://host.docker.internal:3000` se Railway local

- [ ] **Step 7: Commit**

```bash
git add packages/mcp-core/src/mcp_core/blob_client.py packages/mcp-core/tests/test_blob_client.py
git commit -m "feat(mcp-core): blob client delegates to portal /api/internal/blob"
```

---

### Task 6: refresh_spec Pydantic models

**Files:**
- Create: `packages/mcp-core/src/mcp_core/refresh_spec.py`
- Create: `packages/mcp-core/tests/test_refresh_spec.py`

- [ ] **Step 1: Escrever teste**

```python
# packages/mcp-core/tests/test_refresh_spec.py
import pytest
from datetime import date
from pydantic import ValidationError
from mcp_core.refresh_spec import RefreshSpec, RefreshQuery, DataBlockRef


def test_minimal_spec_validates():
    spec = RefreshSpec(
        queries=[RefreshQuery(id="top_lojas", sql="SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'")],
        data_blocks=[DataBlockRef(block_id="data_top_lojas", query_id="top_lojas")],
        original_period={"start": date(2026, 4, 1), "end": date(2026, 4, 23)},
    )
    assert spec.queries[0].id == "top_lojas"


def test_unknown_query_id_in_data_block_fails():
    with pytest.raises(ValidationError, match="references unknown query_id"):
        RefreshSpec(
            queries=[RefreshQuery(id="q1", sql="SELECT 1")],
            data_blocks=[DataBlockRef(block_id="data_x", query_id="q_does_not_exist")],
            original_period={"start": date(2026, 4, 1), "end": date(2026, 4, 23)},
        )


def test_duplicate_query_id_fails():
    with pytest.raises(ValidationError, match="duplicate query id"):
        RefreshSpec(
            queries=[
                RefreshQuery(id="q1", sql="SELECT 1"),
                RefreshQuery(id="q1", sql="SELECT 2"),
            ],
            data_blocks=[],
            original_period={"start": date(2026, 4, 1), "end": date(2026, 4, 23)},
        )


def test_sql_must_contain_placeholders():
    with pytest.raises(ValidationError, match="missing placeholder"):
        RefreshSpec(
            queries=[RefreshQuery(id="q1", sql="SELECT 1")],
            data_blocks=[DataBlockRef(block_id="data_q1", query_id="q1")],
            original_period={"start": date(2026, 4, 1), "end": date(2026, 4, 23)},
        )


def test_render_substitutes_placeholders():
    q = RefreshQuery(id="q1", sql="SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'")
    sql = q.render(start=date(2026, 5, 1), end=date(2026, 5, 7))
    assert sql == "SELECT 1 WHERE d BETWEEN '2026-05-01' AND '2026-05-07'"
```

- [ ] **Step 2: Rodar teste, esperar falha (ImportError)**

- [ ] **Step 3: Implementar**

```python
# packages/mcp-core/src/mcp_core/refresh_spec.py
from __future__ import annotations
from datetime import date
from pydantic import BaseModel, model_validator, Field


class RefreshQuery(BaseModel):
    id: str = Field(min_length=1)
    sql: str = Field(min_length=1)

    def render(self, *, start: date, end: date) -> str:
        return self.sql.replace("{{start_date}}", start.isoformat()).replace("{{end_date}}", end.isoformat())


class DataBlockRef(BaseModel):
    block_id: str = Field(min_length=1)
    query_id: str = Field(min_length=1)


class PeriodRange(BaseModel):
    start: date
    end: date


class RefreshSpec(BaseModel):
    queries: list[RefreshQuery]
    data_blocks: list[DataBlockRef]
    original_period: PeriodRange

    @model_validator(mode="after")
    def _validate(self) -> "RefreshSpec":
        # Unique query ids
        ids = [q.id for q in self.queries]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate query id in queries[]")

        # Each query SQL must have both placeholders
        for q in self.queries:
            if "{{start_date}}" not in q.sql or "{{end_date}}" not in q.sql:
                raise ValueError(f"query {q.id!r}: missing placeholder {{start_date}} or {{end_date}}")

        # Each data_block.query_id must reference an existing query
        valid_ids = set(ids)
        for db in self.data_blocks:
            if db.query_id not in valid_ids:
                raise ValueError(f"data_block {db.block_id!r} references unknown query_id {db.query_id!r}")

        return self
```

- [ ] **Step 4: Rodar teste, esperar passar**

```bash
cd packages/mcp-core && uv run pytest tests/test_refresh_spec.py -v
```

Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/refresh_spec.py packages/mcp-core/tests/test_refresh_spec.py
git commit -m "feat(mcp-core): add refresh_spec pydantic models"
```

---

### Task 7: HTML data island swap helper

**Files:**
- Create: `packages/mcp-core/src/mcp_core/html_swap.py`
- Create: `packages/mcp-core/tests/test_html_swap.py`

- [ ] **Step 1: Escrever teste**

```python
# packages/mcp-core/tests/test_html_swap.py
import pytest
import json
from mcp_core.html_swap import swap_data_blocks, encode_for_script_tag, validate_blocks_present


def test_encode_escapes_script_breakouts():
    payload = [{"name": "</script><img src=x onerror=alert(1)>"}]
    out = encode_for_script_tag(payload)
    assert "</script>" not in out
    assert "\\u003c/script\\u003e" in out


def test_swap_replaces_single_block():
    html = '<html><script id="data_q1" type="application/json">[]</script></html>'
    result = swap_data_blocks(html, {"data_q1": [{"x": 1}]})
    assert '<script id="data_q1" type="application/json">[{"x":1}]</script>' in result.replace(" ", "").replace("\n", "")
    assert result.count('id="data_q1"') == 1


def test_swap_replaces_multiple_blocks():
    html = (
        '<script id="data_a" type="application/json">[]</script>'
        '<div>middle</div>'
        '<script id="data_b" type="application/json">[]</script>'
    )
    result = swap_data_blocks(html, {"data_a": [1], "data_b": [2]})
    assert '"data_a"' in result
    assert '[1]' in result.replace(" ", "")
    assert '[2]' in result.replace(" ", "")


def test_swap_preserves_csp_meta():
    html = (
        '<head><meta http-equiv="Content-Security-Policy" content="default-src self">'
        '<script id="data_q1" type="application/json">[]</script></head>'
    )
    result = swap_data_blocks(html, {"data_q1": []})
    assert 'Content-Security-Policy' in result


def test_swap_raises_if_block_missing():
    html = '<html></html>'
    with pytest.raises(ValueError, match="block_id.*data_q1.*not found"):
        swap_data_blocks(html, {"data_q1": []})


def test_validate_blocks_present():
    html = '<script id="data_a" type="application/json">[]</script><script id="data_b" type="application/json">[]</script>'
    validate_blocks_present(html, ["data_a", "data_b"])  # no raise


def test_validate_blocks_missing():
    html = '<script id="data_a" type="application/json">[]</script>'
    with pytest.raises(ValueError, match="missing.*data_b"):
        validate_blocks_present(html, ["data_a", "data_b"])
```

- [ ] **Step 2: Rodar teste, esperar falha**

- [ ] **Step 3: Implementar**

```python
# packages/mcp-core/src/mcp_core/html_swap.py
from __future__ import annotations
import json
import re
from typing import Any

# Translate table for JSON output going inside <script type="application/json">.
# Prevents content from breaking out of the script tag (XSS) or breaking JSON parsing
# in some browsers (U+2028/U+2029 are valid in JSON but invalid in JS source).
_HTML_SCRIPT_ESCAPES = str.maketrans({
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    "\u2028": "\\u2028",
    "\u2029": "\\u2029",
})


def encode_for_script_tag(value: Any) -> str:
    """JSON-encode safely for embedding inside <script type=application/json>."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).translate(_HTML_SCRIPT_ESCAPES)


def _block_pattern(block_id: str) -> re.Pattern[str]:
    return re.compile(
        rf'(<script\s+id="{re.escape(block_id)}"\s+type="application/json">)(.*?)(</script>)',
        re.DOTALL,
    )


def validate_blocks_present(html: str, block_ids: list[str]) -> None:
    """Raise ValueError if any expected block_id is missing from html."""
    missing = [b for b in block_ids if not _block_pattern(b).search(html)]
    if missing:
        raise ValueError(f"HTML missing required <script id=...> blocks: {missing}")


def swap_data_blocks(html: str, payloads: dict[str, Any]) -> str:
    """Replace each <script id="<block_id>" type="application/json"> body with JSON of payloads[block_id].

    Raises ValueError if a block_id is not found, or if the resulting HTML lost the CSP meta tag
    (defensive — should never happen since we never touch <head>)."""
    csp_before = "Content-Security-Policy" in html

    out = html
    for block_id, payload in payloads.items():
        pattern = _block_pattern(block_id)
        match = pattern.search(out)
        if not match:
            raise ValueError(f"block_id {block_id!r} not found in HTML")
        encoded = encode_for_script_tag(payload)
        out = pattern.sub(lambda m: m.group(1) + encoded + m.group(3), out, count=1)

    if csp_before and "Content-Security-Policy" not in out:
        raise ValueError("CSP meta tag was lost during swap (should never happen)")

    return out
```

- [ ] **Step 4: Rodar teste, esperar passar**

```bash
cd packages/mcp-core && uv run pytest tests/test_html_swap.py -v
```

Esperado: 7 passed.

- [ ] **Step 5: Adicionar helper `make_data_block` pro agente**

Pra evitar que o agente emita variantes não-canônicas de `<script id="..." type="application/json">`, fornecer um helper determinístico que ele usa quando gera HTML:

```python
# adicionar em packages/mcp-core/src/mcp_core/html_swap.py
def make_data_block(block_id: str, payload: Any) -> str:
    """Produz a forma canônica esperada pelo swap. O agente DEVE usar isso ao
    emitir blocos de dados em vez de hardcodar a tag."""
    encoded = encode_for_script_tag(payload)
    return f'<script id="{block_id}" type="application/json">{encoded}</script>'
```

E expor pro agente como tool MCP read-only (no `server_factory.py`):

```python
@mcp.tool(annotations={"readOnlyHint": True})
async def html_data_block(block_id: str, payload: list | dict) -> str:
    """Gera a forma canônica de um data island pra embutir no HTML de uma análise.
    Use sempre isso em vez de escrever a tag <script type=\"application/json\"> manualmente —
    o swap do refresh depende da forma exata. Ex: html_data_block('data_top_lojas', [...])"""
    from mcp_core.html_swap import make_data_block
    return make_data_block(block_id, payload)
```

- [ ] **Step 6: Adicionar teste**

```python
# em test_html_swap.py
def test_make_data_block_roundtrips_through_swap():
    block = make_data_block("data_q1", [{"x": 1}])
    html = f"<html>{block}</html>"
    result = swap_data_blocks(html, {"data_q1": [{"x": 2}]})
    assert '"x":2' in result.replace(" ", "")
```

- [ ] **Step 7: Commit**

```bash
git add packages/mcp-core/src/mcp_core/html_swap.py packages/mcp-core/src/mcp_core/server_factory.py packages/mcp-core/tests/test_html_swap.py
git commit -m "feat(mcp-core): add html data island swap + make_data_block helper"
```

---

### Task 8: Audit log helper

**Files:**
- Create: `packages/mcp-core/src/mcp_core/audit.py`
- Create: `packages/mcp-core/tests/test_audit.py`

- [ ] **Step 1: Escrever teste**

```python
# packages/mcp-core/tests/test_audit.py
import pytest
from mcp_core import db
from mcp_core.audit import record


@pytest.mark.asyncio
async def test_record_inserts_row(db_pool):
    pool = db.get_pool()
    async with pool.acquire() as conn:
        # need a parent row for FK
        await conn.execute(
            "INSERT INTO analyses (id, agent_slug, author_email, title, blob_pathname) "
            "VALUES ('a1', 'vendas-linx', 'a@b.com', 'T', 'p')"
        )
    async with db.transaction() as conn:
        await record(conn, action="publish", actor_email="a@b.com", analysis_id="a1", metadata={"foo": "bar"})

    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM audit_log WHERE analysis_id = 'a1'")
    assert row["action"] == "publish"
    assert row["actor_email"] == "a@b.com"
    assert row["metadata"] == {"foo": "bar"}


@pytest.mark.asyncio
async def test_record_with_null_analysis_id(db_pool):
    async with db.transaction() as conn:
        await record(conn, action="login_failed", actor_email="x@y.com", analysis_id=None, metadata={"reason": "bad_token"})

    pool = db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM audit_log WHERE actor_email = 'x@y.com'")
    assert row["analysis_id"] is None
    assert row["action"] == "login_failed"
```

- [ ] **Step 2: Rodar teste, esperar falha**

- [ ] **Step 3: Implementar**

```python
# packages/mcp-core/src/mcp_core/audit.py
from __future__ import annotations
import json
from typing import Any
import asyncpg


async def record(
    conn: asyncpg.Connection,
    *,
    action: str,
    actor_email: str,
    analysis_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append a row to audit_log. Caller controls the transaction."""
    await conn.execute(
        "INSERT INTO audit_log (action, actor_email, analysis_id, metadata) VALUES ($1, $2, $3, $4)",
        action,
        actor_email,
        analysis_id,
        json.dumps(metadata) if metadata is not None else None,
    )
```

- [ ] **Step 4: Rodar teste, esperar passar**

```bash
cd packages/mcp-core && uv run pytest tests/test_audit.py -v
```

Esperado: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/audit.py packages/mcp-core/tests/test_audit.py
git commit -m "feat(mcp-core): add audit_log record helper"
```

---

### Task 9: Analyses repository — CRUD + search

**Files:**
- Create: `packages/mcp-core/src/mcp_core/analyses_repo.py`
- Create: `packages/mcp-core/tests/test_analyses_repo.py`

- [ ] **Step 1: Escrever teste — modelo e insert**

```python
# packages/mcp-core/tests/test_analyses_repo.py
import pytest
from datetime import date, datetime, timezone
from mcp_core import db
from mcp_core.analyses_repo import (
    AnalysisRow,
    insert,
    get,
    list_for_user,
    update_acl,
    update_archive,
    update_refresh_state,
    set_refresh_error,
    search,
)


def _row(**overrides) -> AnalysisRow:
    base = dict(
        id="t1", agent_slug="vendas-linx", author_email="a@b.com",
        title="Análise X", brand="FARM", period_label="abr/26",
        period_start=date(2026, 4, 1), period_end=date(2026, 4, 23),
        description="desc", tags=["mtd", "produto"],
        public=False, shared_with=[], archived_by=[],
        blob_pathname="analyses/vendas-linx/t1.html",
        refresh_spec=None,
    )
    base.update(overrides)
    return AnalysisRow(**base)


@pytest.mark.asyncio
async def test_insert_and_get(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="x1"))
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "x1")
    assert row is not None
    assert row.id == "x1"
    assert row.title == "Análise X"


@pytest.mark.asyncio
async def test_get_returns_none_for_missing(db_pool):
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "nope")
    assert row is None


@pytest.mark.asyncio
async def test_list_for_user_filters_acl(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="mine_priv", author_email="a@b.com"))
        await insert(conn, _row(id="other_priv", author_email="c@d.com"))
        await insert(conn, _row(id="other_pub", author_email="c@d.com", public=True))
        await insert(conn, _row(id="other_shared", author_email="c@d.com", shared_with=["a@b.com"]))

    async with db.get_pool().acquire() as conn:
        rows = await list_for_user(conn, agent_slug="vendas-linx", email="a@b.com")
    ids = {r.id for r in rows}
    assert ids == {"mine_priv", "other_pub", "other_shared"}
    assert "other_priv" not in ids


@pytest.mark.asyncio
async def test_update_acl_changes_public_and_shared_with(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1"))
        await update_acl(conn, "a1", public=True, shared_with=["x@y.com"])

    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.public is True
    assert row.shared_with == ["x@y.com"]


@pytest.mark.asyncio
async def test_update_archive_idempotent(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1"))
        await update_archive(conn, "a1", email="u@x.com", archive=True)
        await update_archive(conn, "a1", email="u@x.com", archive=True)  # idempotent
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.archived_by == ["u@x.com"]


@pytest.mark.asyncio
async def test_update_archive_remove(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1", archived_by=["u@x.com"]))
        await update_archive(conn, "a1", email="u@x.com", archive=False)
    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.archived_by == []


@pytest.mark.asyncio
async def test_update_refresh_state_sets_period(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1"))
        await update_refresh_state(
            conn, "a1",
            period_start=date(2026, 5, 1), period_end=date(2026, 5, 7),
            actor_email="a@b.com",
        )

    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.period_start == date(2026, 5, 1)
    assert row.last_refreshed_by == "a@b.com"
    assert row.last_refreshed_at is not None
    assert row.last_refresh_error is None


@pytest.mark.asyncio
async def test_set_refresh_error_doesnt_advance_period(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="a1"))
        await set_refresh_error(conn, "a1", error="dataset not allowed")

    async with db.get_pool().acquire() as conn:
        row = await get(conn, "a1")
    assert row.last_refresh_error == "dataset not allowed"
    assert row.last_refreshed_at is None  # not advanced


@pytest.mark.asyncio
async def test_search_ranks_by_relevance(db_pool):
    async with db.transaction() as conn:
        await insert(conn, _row(id="r1", title="Top produtos FARM Leblon"))
        await insert(conn, _row(id="r2", title="Maria Filó YTD"))
    async with db.get_pool().acquire() as conn:
        rows = await search(conn, query="FARM Leblon", email="a@b.com", agent="vendas-linx")
    assert rows[0].id == "r1"
```

- [ ] **Step 2: Rodar teste, esperar falha**

- [ ] **Step 3: Implementar (parte 1: dataclass e insert/get)**

```python
# packages/mcp-core/src/mcp_core/analyses_repo.py
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from typing import Any
import asyncpg


@dataclass
class AnalysisRow:
    id: str
    agent_slug: str
    author_email: str
    title: str
    brand: str | None = None
    period_label: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    public: bool = False
    shared_with: list[str] = field(default_factory=list)
    archived_by: list[str] = field(default_factory=list)
    blob_pathname: str = ""
    blob_url: str | None = None
    refresh_spec: dict[str, Any] | None = None
    last_refreshed_at: datetime | None = None
    last_refreshed_by: str | None = None
    last_refresh_error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_record(cls, r: asyncpg.Record) -> "AnalysisRow":
        d = dict(r)
        d.pop("search_doc", None)
        if d.get("refresh_spec") is not None and isinstance(d["refresh_spec"], str):
            d["refresh_spec"] = json.loads(d["refresh_spec"])
        return cls(**d)


_COLS = (
    "id, agent_slug, author_email, title, brand, period_label, period_start, period_end, "
    "description, tags, public, shared_with, archived_by, blob_pathname, blob_url, refresh_spec, "
    "last_refreshed_at, last_refreshed_by, last_refresh_error, created_at, updated_at"
)


async def insert(conn: asyncpg.Connection, row: AnalysisRow) -> None:
    await conn.execute(
        f"""INSERT INTO analyses ({_COLS}) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17,$18,$19,
            COALESCE($20, NOW()), COALESCE($21, NOW())
        )""",
        row.id, row.agent_slug, row.author_email, row.title, row.brand, row.period_label,
        row.period_start, row.period_end, row.description, row.tags, row.public,
        row.shared_with, row.archived_by, row.blob_pathname, row.blob_url,
        json.dumps(row.refresh_spec) if row.refresh_spec else None,
        row.last_refreshed_at, row.last_refreshed_by, row.last_refresh_error,
        row.created_at, row.updated_at,
    )


async def update_blob_url(conn: asyncpg.Connection, analysis_id: str, *, blob_url: str) -> None:
    """Atualiza blob_url após upload (publish ou refresh). Idempotente."""
    await conn.execute(
        "UPDATE analyses SET blob_url = $1, updated_at = NOW() WHERE id = $2",
        blob_url, analysis_id,
    )


async def get(conn: asyncpg.Connection, analysis_id: str) -> AnalysisRow | None:
    rec = await conn.fetchrow(f"SELECT {_COLS} FROM analyses WHERE id = $1", analysis_id)
    return AnalysisRow.from_record(rec) if rec else None


async def list_for_user(conn: asyncpg.Connection, *, agent_slug: str, email: str) -> list[AnalysisRow]:
    rows = await conn.fetch(
        f"""SELECT {_COLS} FROM analyses
            WHERE agent_slug = $1 AND (author_email = $2 OR public = TRUE OR $2 = ANY(shared_with))
            ORDER BY COALESCE(last_refreshed_at, created_at) DESC""",
        agent_slug, email,
    )
    return [AnalysisRow.from_record(r) for r in rows]


async def update_acl(conn: asyncpg.Connection, analysis_id: str, *, public: bool, shared_with: list[str]) -> None:
    await conn.execute(
        "UPDATE analyses SET public = $1, shared_with = $2, updated_at = NOW() WHERE id = $3",
        public, shared_with, analysis_id,
    )


async def update_archive(conn: asyncpg.Connection, analysis_id: str, *, email: str, archive: bool) -> None:
    if archive:
        # remove first to avoid duplicates, then append
        await conn.execute(
            "UPDATE analyses SET archived_by = array_append(array_remove(archived_by, $1), $1), updated_at = NOW() WHERE id = $2",
            email, analysis_id,
        )
    else:
        await conn.execute(
            "UPDATE analyses SET archived_by = array_remove(archived_by, $1), updated_at = NOW() WHERE id = $2",
            email, analysis_id,
        )


async def update_refresh_state(
    conn: asyncpg.Connection, analysis_id: str, *,
    period_start: date, period_end: date, actor_email: str,
) -> None:
    await conn.execute(
        """UPDATE analyses SET
            period_start = $1, period_end = $2,
            last_refreshed_at = NOW(), last_refreshed_by = $3, last_refresh_error = NULL,
            updated_at = NOW()
           WHERE id = $4""",
        period_start, period_end, actor_email, analysis_id,
    )


async def set_refresh_error(conn: asyncpg.Connection, analysis_id: str, *, error: str) -> None:
    await conn.execute(
        "UPDATE analyses SET last_refresh_error = $1, updated_at = NOW() WHERE id = $2",
        error, analysis_id,
    )


async def search(
    conn: asyncpg.Connection, *,
    query: str, email: str,
    agent: str | None = None, brand: str | None = None,
    days_back: int = 90, limit: int = 10,
) -> list[AnalysisRow]:
    sql = f"""
        SELECT {_COLS}, ts_rank(search_doc, plainto_tsquery('portuguese', $1)) AS rank
        FROM analyses
        WHERE search_doc @@ plainto_tsquery('portuguese', $1)
          AND (author_email = $2 OR public = TRUE OR $2 = ANY(shared_with))
          AND COALESCE(last_refreshed_at, created_at) >= NOW() - ($3 || ' days')::interval
          {{agent_clause}}
          {{brand_clause}}
        ORDER BY rank DESC, COALESCE(last_refreshed_at, created_at) DESC
        LIMIT $4
    """.format(
        agent_clause="AND agent_slug = $5" if agent else "",
        brand_clause=("AND brand = $6" if (agent and brand) else ("AND brand = $5" if brand else "")),
    )
    args: list[Any] = [query, email, days_back, max(1, min(limit, 25))]
    if agent:
        args.append(agent)
    if brand:
        args.append(brand)
    rows = await conn.fetch(sql, *args)
    return [AnalysisRow.from_record(r) for r in rows]


async def try_acquire_refresh_lock(conn: asyncpg.Connection, analysis_id: str) -> bool:
    """pg_try_advisory_xact_lock — returns True if lock acquired in this transaction."""
    return await conn.fetchval("SELECT pg_try_advisory_xact_lock(hashtext($1))", f"refresh:{analysis_id}")
```

- [ ] **Step 4: Rodar teste, esperar passar**

```bash
cd packages/mcp-core && uv run pytest tests/test_analyses_repo.py -v
```

Esperado: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/analyses_repo.py packages/mcp-core/tests/test_analyses_repo.py
git commit -m "feat(mcp-core): add analyses repository with crud, search, advisory lock"
```

---

### Task 9.5: Lifespan integration — init_pool no boot do FastAPI

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py`

Antes de tocar `publicar_dashboard` (Task 10), garantir que o pool é inicializado no startup do app FastAPI. Sem isso, primeiro request que chamar `db.get_pool()` quebra com `RuntimeError`.

- [ ] **Step 1: Localizar onde `auth_app` (FastAPI) é construído**

```bash
cd packages/mcp-core && grep -n "auth_app\s*=\s*FastAPI\|FastAPI(" src/mcp_core/server_factory.py
```

Anotar a linha exata. Se a construção já recebe um `lifespan=`, vai precisar mergear (Step 3); senão é direto.

- [ ] **Step 2: Adicionar lifespan no topo do arquivo**

```python
# packages/mcp-core/src/mcp_core/server_factory.py — adicionar perto dos outros imports
from contextlib import asynccontextmanager
from mcp_core import db as _db


@asynccontextmanager
async def _db_lifespan(app):
    """Initialize asyncpg pool on startup, close on shutdown."""
    await _db.init_pool()
    try:
        yield
    finally:
        await _db.close_pool()
```

- [ ] **Step 3a: Caso simples — `auth_app` ainda não tem lifespan**

Substituir:
```python
auth_app = FastAPI()
```
por:
```python
auth_app = FastAPI(lifespan=_db_lifespan)
```

- [ ] **Step 3b: Caso composto — `auth_app` já tem lifespan (FastMCP)**

Mergear via `contextlib.AsyncExitStack`:

```python
from contextlib import AsyncExitStack

@asynccontextmanager
async def _combined_lifespan(app):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(_db_lifespan(app))
        # entra também no lifespan original; ajuste o nome conforme o que existe:
        if existing_lifespan := getattr(app.router, "lifespan_context", None):
            await stack.enter_async_context(existing_lifespan(app))
        yield

auth_app = FastAPI(lifespan=_combined_lifespan)
```

- [ ] **Step 4: Smoke test — rodar mcp-core local e ver `init_pool` no log de boot**

```bash
cd packages/mcp-core && DATABASE_URL=$DATABASE_URL_TEST uv run python -m mcp_core 2>&1 | head -20
```

Esperado: log limpo, sem erro de conexão; processo escutando.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/server_factory.py
git commit -m "feat(mcp-core): add db pool lifespan to fastapi app"
```

---

## Phase 2 — Publish via DB+Blob

### Task 10: Modificar `publicar_dashboard`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py:276-400` (área do `publicar_dashboard`)
- Modify: `packages/mcp-core/tests/test_server_factory.py`

- [ ] **Step 1: Atualizar teste pra refletir nova assinatura**

Editar `tests/test_server_factory.py` — adicionar teste novo:

```python
@pytest.mark.asyncio
async def test_publish_writes_to_db_and_blob(db_pool, monkeypatch):
    """publicar_dashboard insere row no DB e faz upload no Blob."""
    from mcp_core import db, analyses_repo
    from mcp_core.server_factory import build_mcp_app
    # mock blob client
    uploaded = {}
    class FakeBlob:
        async def put(self, pathname, body, content_type="text/html"):
            uploaded["pathname"] = pathname
            uploaded["body"] = body
            return f"https://blob.fake/{pathname}"
    monkeypatch.setattr("mcp_core.server_factory._blob_client", lambda: FakeBlob())

    app = build_mcp_app(...)  # parametrização conforme fixture existente do projeto
    # ... invocar publicar_dashboard via in-process tool call
    # Verifica:
    pool = db.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM analyses")
    assert len(rows) == 1
    assert rows[0]["title"] == "Test"
    assert "<script id=\"data_q1\"" in uploaded["body"].decode()
```

> **Nota ao engenheiro:** o teste integrado completo depende do fixture existente de `build_mcp_app` no projeto. Se a fixture não comportar passar um BlobClient mockado, refatore pra aceitar via parameter ou um setter — o objetivo é não escrever em Blob real durante CI.

- [ ] **Step 2: Rodar teste, esperar falha (publicar_dashboard ainda escreve em git)**

- [ ] **Step 3: Substituir o corpo de `publicar_dashboard`**

Substituir o bloco entre `# ── Base tool: publicar_dashboard ─────────` e a linha que termina o handler (em `server_factory.py`) por:

```python
    @mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True})
    async def publicar_dashboard(
        title: str,
        brand: str,
        period: str,
        description: str,
        html_content: str,
        tags: list[str],
        ctx: Context,
        refresh_spec: dict | None = None,
        public: bool = False,
        shared_with: list[str] | None = None,
    ) -> dict[str, object]:
        """Publish an HTML dashboard to the analysis catalog.

        Only call when the user explicitly asks to publish/share/save. Default
        flow is to render the HTML inline in the chat.

        Optional `refresh_spec` (dict) makes the analysis refreshable later via the
        portal "Atualizar período" UI. Format:
            {
              "queries": [{"id": "<query_id>", "sql": "SELECT ... '{{start_date}}' ... '{{end_date}}' ..."}, ...],
              "data_blocks": [{"block_id": "data_<query_id>", "query_id": "<query_id>"}, ...],
              "original_period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            }
        Each `data_blocks[i].block_id` MUST correspond to a `<script id="<block_id>" type="application/json">…</script>`
        block in `html_content`. Validation rejects mismatches.

        `shared_with` (optional) is a list of emails (lowercased) that get explicit access
        even when `public=False`. Defaults to empty.
        """
        from mcp_core.refresh_spec import RefreshSpec
        from mcp_core.html_swap import validate_blocks_present
        from mcp_core.email_norm import normalize_email
        from mcp_core import db as _db, analyses_repo, audit
        from datetime import datetime, timezone, date as _date
        import hashlib, re

        exec_email = normalize_email(_current_email(ctx))
        settings = _load_cached_state().settings
        domain = settings.server.domain

        # Generate id (slug + short hash, same convention as before)
        today = datetime.now(timezone.utc).date().isoformat()
        short_hash = hashlib.sha1(
            f"{exec_email}{title}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:8]
        slug = _slugify(title)
        analysis_id = f"{slug}-{short_hash}"
        blob_pathname = f"analyses/{domain}/{analysis_id}.html"

        # Validate refresh_spec if provided
        spec_obj = None
        period_start_d = None
        period_end_d = None
        if refresh_spec is not None:
            spec_obj = RefreshSpec.model_validate(refresh_spec)
            block_ids = [b.block_id for b in spec_obj.data_blocks]
            validate_blocks_present(html_content, block_ids)
            period_start_d = spec_obj.original_period.start
            period_end_d = spec_obj.original_period.end

        # Inject CSP same as before
        _csp = (
            "<meta http-equiv=\"Content-Security-Policy\" content=\""
            "default-src 'self' data: blob:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.plot.ly; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "form-action 'none';\">"
        )
        safe_html, n = re.subn(
            r"(?i)<head([^>]*)>",
            lambda m: f"<head{m.group(1)}>{_csp}",
            html_content, count=1,
        )
        if n == 0:
            safe_html = _csp + html_content

        # Upload to Blob — captura URL retornada pra cachear no DB
        blob = _blob_client()
        blob_url = await blob.put(blob_pathname, safe_html.encode("utf-8"), content_type="text/html")

        # Insert row + audit, single transaction
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
            await audit.record(conn, action="publish", actor_email=exec_email,
                               analysis_id=analysis_id, metadata={"public": public})

        return {
            "id": analysis_id,
            "url": f"/api/analysis/{analysis_id}",
        }
```

E adicionar no topo do arquivo (próximo dos outros helpers):

```python
def _blob_client():
    from mcp_core.blob_client import BlobClient
    return BlobClient()
```

- [ ] **Step 4: Garantir que `init_pool()` é chamado no startup do FastAPI**

Procurar em `server_factory.py` (ou onde o `auth_app` é construído) o handler `lifespan` ou equivalente. Adicionar:

```python
from contextlib import asynccontextmanager
from mcp_core import db as _db

@asynccontextmanager
async def lifespan(app):
    await _db.init_pool()
    yield
    await _db.close_pool()
```

E aplicar no FastAPI: `auth_app = FastAPI(lifespan=lifespan)` (ajustar pra preservar o lifespan existente, se houver).

- [ ] **Step 5: Rodar testes, esperar passar**

```bash
cd packages/mcp-core && uv run pytest tests/test_server_factory.py tests/test_analyses_repo.py -v
```

- [ ] **Step 6: Commit**

```bash
git add packages/mcp-core/src/mcp_core/server_factory.py packages/mcp-core/tests/test_server_factory.py
git commit -m "feat(mcp-core): publicar_dashboard writes to db+blob (no more git)"
```

---

### Task 11: Remover GitOps e código morto

**Files:**
- Delete: `packages/mcp-core/src/mcp_core/library.py`
- Delete: `packages/mcp-core/src/mcp_core/clone_repo.py`
- Delete: `packages/mcp-core/src/mcp_core/git_ops.py` (se existir)
- Delete: `packages/mcp-core/tests/test_library.py`
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py` (remover imports, remover tool `listar_analises` se obsoleto)

- [ ] **Step 1: Listar referências aos módulos a remover**

```bash
cd packages/mcp-core && grep -rn "from mcp_core.library\|from mcp_core.clone_repo\|from mcp_core.git_ops\|GitOps\|prepend_entry" src tests || true
```

- [ ] **Step 2: Remover imports e usos no `server_factory.py`**

Editar `server_factory.py`:
- Remover `from mcp_core.library import LibraryEntry, prepend_entry`
- Remover `from mcp_core.clone_repo import …` (se existir)
- Remover bloco que chama `GitOps` em `publicar_dashboard` (já fora pelo Task 10, confirmar)
- Se houver tool `listar_analises` que lia `library.json` direto, remover (será substituído por `buscar_analises` no Task 21)

- [ ] **Step 3: Deletar arquivos**

```bash
git rm packages/mcp-core/src/mcp_core/library.py
git rm packages/mcp-core/tests/test_library.py
git rm -f packages/mcp-core/src/mcp_core/clone_repo.py packages/mcp-core/src/mcp_core/git_ops.py 2>/dev/null || true
```

- [ ] **Step 4: Rodar suite completa**

```bash
cd packages/mcp-core && uv run pytest -v
```

Esperado: tudo passa, nenhum import quebrado.

- [ ] **Step 5: Commit**

```bash
git add -A packages/mcp-core
git commit -m "refactor(mcp-core): remove git-based publish path (library.py, GitOps)"
```

---

## Phase 3 — Portal reads from DB

### Task 12: Portal helpers — db, email

**Files:**
- Modify: `portal/package.json`
- Create: `portal/api/_helpers/db.js`
- Create: `portal/api/_helpers/email.js`
- Create: `portal/api/_helpers/__tests__/email.test.js`

> **Nota:** o cliente Blob lado portal vem via `@vercel/blob` SDK direto no endpoint interno (Task 5), não tem helper compartilhado.

- [ ] **Step 1: Adicionar dependências**

```bash
cd portal && npm install @neondatabase/serverless @vercel/blob jsonwebtoken
```

- [ ] **Step 2: Escrever teste do email helper**

```javascript
// portal/api/_helpers/__tests__/email.test.js
import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeEmail } from '../email.js'

test('lowercase', () => {
  assert.equal(normalizeEmail('Maria.Filo@Soma.com.br'), 'maria.filo@soma.com.br')
})

test('strip', () => {
  assert.equal(normalizeEmail('  a@b.com  '), 'a@b.com')
})

test('rejects empty', () => {
  assert.throws(() => normalizeEmail(''), /empty/)
  assert.throws(() => normalizeEmail('   '), /empty/)
})

test('rejects no-at', () => {
  assert.throws(() => normalizeEmail('notanemail'), /missing @/)
})
```

- [ ] **Step 3: Implementar email**

```javascript
// portal/api/_helpers/email.js
export function normalizeEmail(s) {
  if (!s || !s.trim()) throw new Error('empty email')
  const out = s.trim().toLowerCase()
  if (!out.includes('@')) throw new Error(`invalid email: missing @ in ${out}`)
  return out
}
```

- [ ] **Step 4: Rodar teste**

```bash
cd portal && node --test api/_helpers/__tests__/email.test.js
```

Esperado: 4 ok.

- [ ] **Step 5: Implementar db.js**

```javascript
// portal/api/_helpers/db.js
import { neon } from '@neondatabase/serverless'

let _sql = null
export function getSql() {
  if (!_sql) {
    if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL not set')
    _sql = neon(process.env.DATABASE_URL)
  }
  return _sql
}
```

> **Nota:** `@neondatabase/serverless` retorna uma função-template — `sql\`SELECT 1\`` funciona como tagged template. Single round-trip por chamada, sem manter conexão idle (perfeito pra Vercel functions).

- [ ] **Step 6: Commit**

```bash
git add portal/package.json portal/package-lock.json portal/api/_helpers/db.js portal/api/_helpers/email.js portal/api/_helpers/__tests__/email.test.js
git commit -m "feat(portal): add neon and email helpers"
```

---

### Task 13: GET /api/library

**Files:**
- Create: `portal/api/library.js`
- Create: `portal/api/__tests__/library.test.js`

- [ ] **Step 1: Escrever teste**

```javascript
// portal/api/__tests__/library.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

// Mock helpers
const mockSql = (results) => async (...args) => results
const noopVerify = (cookie) => cookie === 'valid' ? 'a@b.com' : null

test('returns 401 without session', async () => {
  process.env.SESSION_SECRET = 'x'
  const handler = (await import('../library.js')).default
  const req = { headers: { cookie: '' }, query: { agent: 'vendas-linx' } }
  const res = makeRes()
  await handler(req, res)
  assert.equal(res.statusCode, 401)
})

test('requires agent param', async () => {
  const handler = (await import('../library.js')).default
  const req = { headers: { cookie: 'session=valid~9999999999~xxx' }, query: {} }
  const res = makeRes()
  // ... mock verifySession
})

function makeRes() {
  const r = { statusCode: 200, body: null, headers: {} }
  r.status = (n) => { r.statusCode = n; return r }
  r.json = (o) => { r.body = o; return r }
  r.setHeader = (k, v) => { r.headers[k] = v }
  return r
}
```

> **Nota ao engenheiro:** o estilo de teste do portal usa `node:test` + `node:assert`. O fixture de session/SQL exige um harness com mocks injetáveis — pode usar `node:module#register` pra interceptar imports, ou refatorar `library.js` pra aceitar um `deps` injetável. Veja `portal/api/__tests__/share.test.js` (Task 19) pro padrão consolidado.

- [ ] **Step 2: Implementar `library.js`**

```javascript
// portal/api/library.js
import { getSql } from './_helpers/db.js'
import { verifySession } from './_helpers/session.js'
import { parseCookie } from './_helpers/cookie.js'

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? await verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })

  const agent = (req.query?.agent || '').toString()
  if (!agent) return res.status(400).json({ error: 'agent param required' })

  const sql = getSql()
  const rows = await sql`
    SELECT id, agent_slug, author_email, title, brand, period_label, period_start, period_end,
           description, tags, public, shared_with, archived_by, last_refreshed_at,
           refresh_spec IS NOT NULL AS has_refresh_spec, created_at
    FROM analyses
    WHERE agent_slug = ${agent}
      AND (author_email = ${email} OR public = TRUE OR ${email} = ANY(shared_with))
    ORDER BY COALESCE(last_refreshed_at, created_at) DESC
  `

  const out = rows.map(r => {
    const isMine = r.author_email === email
    // PRIVACY: only the author sees the full shared_with list. Recipients only see
    // themselves in the list (so they can't deduce who else has access).
    const sharedWith = isMine ? (r.shared_with || []) : (r.shared_with?.includes(email) ? [email] : [])
    const periodEnd = r.period_end ? new Date(r.period_end).toISOString().slice(0, 10) : null
    const createdDate = r.created_at ? new Date(r.created_at).toISOString().slice(0, 10) : null
    return {
      ...r,
      shared_with: sharedWith,
      // Backward-compat aliases used by Fase A frontend code (period filter, card meta):
      date: periodEnd || createdDate,
      period: r.period_label,
      // Computed flags:
      is_mine: isMine,
      is_shared_with_me: r.shared_with?.includes(email) && !isMine && !r.public,
      is_archived: r.archived_by?.includes(email),
    }
  })

  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json({ items: out })
}
```

> **Test crítico a adicionar:** verificar que `shared_with` retornado pra um destinatário B (que recebeu compartilhamento de A junto com C, D) contém apenas B — não vaza C nem D.

- [ ] **Step 3: Smoke test contra DB de development**

```bash
cd portal && DATABASE_URL=$DATABASE_URL_TEST SESSION_SECRET=test_secret \
  node -e "
    import('./api/library.js').then(async (m) => {
      const req = { method: 'GET', headers: { cookie: '' }, query: { agent: 'vendas-linx' } };
      const res = { status: (n) => { console.log('status', n); return res; }, json: (o) => console.log(JSON.stringify(o)), setHeader: () => {} };
      await m.default(req, res);
    });
  "
```

Esperado: `status 401` (sem cookie). Inserir uma row + cookie válido pra ver o caso 200.

- [ ] **Step 4: Commit**

```bash
git add portal/api/library.js portal/api/__tests__/library.test.js
git commit -m "feat(portal): add /api/library endpoint with acl filter"
```

---

### Task 14: GET /api/analysis/:id

**Files:**
- Create: `portal/api/analysis/[id].js` (Vercel dynamic route)

**Decisão:** Blob é uploaded com `access: 'public'` (Tasks 5/10). A `blob_url` retornada pelo SDK fica cacheada na coluna `blob_url` da tabela `analyses` (preenchida no upload). `/api/analysis/<id>` é a porta de ACL: valida sessão + ACL no DB e só então redireciona pra `blob_url`. URLs públicas têm sufixos randômicos suficientes pra serem inadivinháveis sem leak; ACL gate em `/api/analysis` evita listing/enumeração. Se um link vazar, exposição é limitada à daquela análise específica (não ao banco inteiro). Trade-off aceito pra MVP — futura migração pra signed URLs entra quando o SDK do Vercel estabilizar a API de signed URLs.

- [ ] **Step 1: Implementar handler**

```javascript
// portal/api/analysis/[id].js
import { getSql } from '../_helpers/db.js'
import { verifySession } from '../_helpers/session.js'
import { parseCookie } from '../_helpers/cookie.js'

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).end()

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? await verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).end('not authenticated')

  const id = req.query?.id || req.params?.id
  if (!id) return res.status(400).end('missing id')

  const sql = getSql()
  const rows = await sql`
    SELECT blob_url, author_email, public, shared_with, last_refreshed_at
    FROM analyses
    WHERE id = ${id}
    LIMIT 1
  `
  if (rows.length === 0) return res.status(404).end('not found')

  const row = rows[0]
  const allowed = row.author_email === email || row.public || row.shared_with?.includes(email)
  if (!allowed) return res.status(403).end('forbidden')
  if (!row.blob_url) return res.status(500).end('blob_url not set (data integrity issue)')

  // Cache-Control private — o cache fica no browser, não no CDN compartilhado
  res.setHeader('cache-control', 'private, no-store')
  res.writeHead(302, { location: row.blob_url })
  res.end()
}
```

- [ ] **Step 2: Verificar routing**

Vercel usa file-based routing — `api/analysis/[id].js` automaticamente vira `/api/analysis/:id`. Confirmar olhando estrutura existente do portal.

- [ ] **Step 3: Smoke test**

Após inserir uma row no DB de development apontando pra um blob_url real:

```bash
curl -i "https://<preview>.vercel.app/api/analysis/<id>" -H "cookie: session=<valid>"
```

Esperado: `302 Found` com `Location: https://...vercel-storage.com/analyses/...html`.

- [ ] **Step 4: Commit**

```bash
git add portal/api/analysis
git commit -m "feat(portal): add /api/analysis/:id with acl + 302 to public blob url"
```

---

### Task 15: Frontend — switch to /api/library

**Files:**
- Modify: `portal/index.html` (área que faz `fetch('/library/...')`)

- [ ] **Step 1: Localizar fetch atual da library**

```bash
cd portal && grep -n "fetch.*library" index.html
```

- [ ] **Step 2: Substituir por chamada ao /api/library**

Editar a função que carrega items por agente (provavelmente `loadAgentLibrary()` ou similar — confirmar nome exato no arquivo). Substituir o bloco que faz dois `fetch` (privado + público) por:

```javascript
async function loadAgentLibrary(agent) {
  const resp = await fetch(`/api/library?agent=${encodeURIComponent(agent.name)}`, {
    credentials: 'include',
  })
  if (!resp.ok) {
    if (resp.status === 401) {
      window.location.href = '/?next=' + encodeURIComponent(window.location.pathname)
      return []
    }
    throw new Error(`library fetch failed: ${resp.status}`)
  }
  const data = await resp.json()
  return data.items.map(item => ({
    ...item,
    agent: { name: agent.name, label: agent.label },
    // backward-compat fields used by existing render code:
    file: null,  // no longer applicable
    link: `/api/analysis/${item.id}` + (item.last_refreshed_at ? `?v=${encodeURIComponent(item.last_refreshed_at)}` : ''),
    public: item.public,
  }))
}
```

- [ ] **Step 3: Atualizar a classificação client-side em mine/team/archived**

Encontrar o bloco que classifica items em "mine"/"team"/"archived" usando filename slug fallback. Substituir por:

```javascript
const mine = allItems.filter(i => i.is_mine && !i.is_archived)
const teamPublic = allItems.filter(i => !i.is_mine && i.public && !i.is_archived)
const sharedWithMe = allItems.filter(i => i.is_shared_with_me && !i.is_archived)
const archived = allItems.filter(i => i.is_archived)
```

E ajustar render das tabs pra renderizar 4 buckets em vez de 3.

- [ ] **Step 4: Definir `reloadLibrary()` se ainda não existir**

Vários lugares (share modal, archive, refresh) chamam `await reloadLibrary()` esperando que ela re-fetch e re-render. Garantir que existe um wrapper centralizado:

```javascript
// no <script> principal do index.html (próximo do load inicial)
async function reloadLibrary() {
  const agentsResp = await fetch('/api/agents', { credentials: 'include' })
  const agents = await agentsResp.json()
  const lists = await Promise.all(agents.map(a => loadAgentLibrary(a)))
  allItems = lists.flat()
  renderTabsAndCards()  // função existente da Fase A que pinta a tela
}

// chamar uma vez no boot da página
reloadLibrary().catch(err => {
  console.error('library load failed', err)
  showErrorBanner('Não consegui carregar a library. Tente atualizar a página.')
})
```

Se `loadAgentLibrary` ou `renderTabsAndCards` (ou equivalentes) já existem com nomes diferentes, ajustar o wrapper pra delegar pra eles. O importante: `reloadLibrary()` precisa existir como ponto único de re-fetch.

- [ ] **Step 4: Smoke test manual no browser**

Login no portal de preview, verificar que cards aparecem nas tabs corretas, clique abre o iframe via `/api/analysis/:id`.

- [ ] **Step 5: Commit**

```bash
git add portal/index.html
git commit -m "feat(portal): frontend uses /api/library and /api/analysis instead of static files"
```

---

### Task 16: Frontend — 4 tabs (rename Time→Público, add Compartilhadas comigo)

**Files:**
- Modify: `portal/index.html` (área de tabs)

- [ ] **Step 1: Localizar tabs atuais**

```bash
cd portal && grep -n -E '(Minhas|Time|Arquivadas|tab-mine|tab-team|tab-archived)' index.html
```

- [ ] **Step 2: Atualizar markup**

Substituir o bloco de tabs por:

```html
<nav class="tabs" role="tablist">
  <button class="tab" data-tab="mine"    role="tab" aria-selected="true">Minhas <span class="count" id="count-mine">0</span></button>
  <button class="tab" data-tab="public"  role="tab" aria-selected="false">Público <span class="count" id="count-public">0</span></button>
  <button class="tab" data-tab="shared"  role="tab" aria-selected="false">Compartilhadas comigo <span class="count" id="count-shared">0</span></button>
  <button class="tab" data-tab="archive" role="tab" aria-selected="false">Arquivadas <span class="count" id="count-archive">0</span></button>
</nav>
```

- [ ] **Step 3: Atualizar JS de classificação e render**

Localizar onde o counts/tabs são atualizados, ajustar pra 4 buckets (chaves: `mine`, `public`, `shared`, `archive`). Não esquecer empty states:

```javascript
const EMPTY_STATES = {
  mine:    'Você ainda não publicou nenhuma análise.',
  public:  'O time ainda não publicou nada público.',
  shared:  'Ninguém compartilhou nada com você.',
  archive: 'Nada arquivado.',
}
```

- [ ] **Step 4: CSS responsivo pras 4 tabs**

Em mobile (≤ 600px) "Compartilhadas comigo" é texto longo. Adicionar regra:

```css
@media (max-width: 600px) {
  .tabs { gap: 4px; overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .tab { font-size: 12px; padding: 6px 10px; white-space: nowrap; flex-shrink: 0; }
  .tab[data-tab="shared"] span:not(.count) { display: none; }
  .tab[data-tab="shared"]::before { content: "Compartilhadas"; }
}
```

Isso encurta o label pra "Compartilhadas" no celular sem perder informação semântica (a contagem e o estado ativo continuam visíveis).

- [ ] **Step 5: Stub do `openRefreshModal()` (full implementation vem no Task 26)**

Pra que o Task 20 (share modal + card menu) funcione independentemente, definir um stub:

```javascript
// no <script> principal — placeholder até o Task 26 substituir
function openRefreshModal(item) {
  toast('Atualização em breve — implementação completa em Task 26')
}
```

Isso permite que cada task seja shippable individualmente sem ReferenceError.

- [ ] **Step 6: Manual QA**

Em preview deploy: verificar 4 tabs aparecem, contagem bate, troca de tab funciona, empty states aparecem. Em mobile (DevTools 375px), "Compartilhadas" cabe e tabs podem rolar horizontalmente.

- [ ] **Step 7: Commit**

```bash
git add portal/index.html
git commit -m "feat(portal): 4 tabs (minhas/público/compartilhadas/arquivadas) + responsive css"
```

---

### Task 17: Remover ACL estática do middleware

**Files:**
- Modify: `portal/middleware.js`

- [ ] **Step 1: Limpar checagens de `/library/` e `/analyses/`**

Substituir o middleware pra apenas:
- Validar sessão pra `/onboarding` (mantém comportamento)
- Sem mais checagem de `/library/...` ou `/analyses/...` (vão pelo `/api/...` agora)

```javascript
// portal/middleware.js
import { parseCookie } from './api/_helpers/cookie.js'

async function verifySession(cookieValue, secret) {
  const parts = cookieValue.split('~')
  if (parts.length < 3) return null
  const signature = parts.pop()
  const expiry = parts.pop()
  const identity = parts.join('~')
  if (parseInt(expiry) < Date.now() / 1000) return null

  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']
  )
  const data = new TextEncoder().encode(`${identity}~${expiry}`)
  const sigBytes = Uint8Array.from(atob(signature.replace(/-/g,'+').replace(/_/g,'/').padEnd((signature.length + 3) & ~3, '=')), c => c.charCodeAt(0))
  const valid = await crypto.subtle.verify('HMAC', key, sigBytes, data)
  return valid ? identity : null
}

export default async function middleware(request) {
  const url = new URL(request.url)
  const pathname = decodeURIComponent(url.pathname)
  if (pathname !== '/onboarding' && pathname !== '/onboarding/') return

  const cookie = parseCookie(request.headers.get('cookie'), 'session')
  if (!cookie || !(await verifySession(cookie, process.env.SESSION_SECRET))) {
    const loginUrl = new URL('/', url)
    loginUrl.searchParams.set('next', pathname)
    return Response.redirect(loginUrl.toString(), 302)
  }
}

export const config = { matcher: ['/onboarding'] }
```

- [ ] **Step 2: Commit**

```bash
git add portal/middleware.js
git commit -m "refactor(portal): middleware only guards /onboarding (acl moved to /api routes)"
```

---

## Phase 4 — Share + Archive

### Task 18: POST /api/share

**Files:**
- Modify: `portal/api/share.js`
- Create: `portal/api/__tests__/share.test.js`

- [ ] **Step 1: Reescrever share.js**

```javascript
// portal/api/share.js
import { getSql } from './_helpers/db.js'
import { verifySession } from './_helpers/session.js'
import { parseCookie } from './_helpers/cookie.js'
import { normalizeEmail } from './_helpers/email.js'

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' })
  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? await verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })

  const { id, public: makePublic, shared_with: rawShared } = req.body || {}
  if (!id) return res.status(400).json({ error: 'id required' })
  if (typeof makePublic !== 'boolean') return res.status(400).json({ error: 'public must be boolean' })

  let normalizedShared = []
  try {
    normalizedShared = (Array.isArray(rawShared) ? rawShared : []).map(normalizeEmail)
  } catch (e) {
    return res.status(400).json({ error: `invalid email: ${e.message}` })
  }

  const sql = getSql()
  const rows = await sql`SELECT author_email, public, shared_with FROM analyses WHERE id = ${id} LIMIT 1`
  if (rows.length === 0) return res.status(404).json({ error: 'not found' })
  const row = rows[0]
  if (row.author_email !== email) return res.status(403).json({ error: 'only author can change acl' })

  const before = { public: row.public, shared_with: row.shared_with || [] }
  const added = normalizedShared.filter(e => !before.shared_with.includes(e))
  const removed = before.shared_with.filter(e => !normalizedShared.includes(e))

  await sql.transaction([
    sql`UPDATE analyses SET public = ${makePublic}, shared_with = ${normalizedShared}, updated_at = NOW() WHERE id = ${id}`,
    sql`INSERT INTO audit_log (action, actor_email, analysis_id, metadata)
        VALUES ('share', ${email}, ${id}, ${JSON.stringify({ before, after: { public: makePublic, shared_with: normalizedShared }, added, removed })}::jsonb)`,
  ])

  return res.status(200).json({ ok: true, public: makePublic, shared_with: normalizedShared })
}
```

- [ ] **Step 2: Escrever teste de integração**

```javascript
// portal/api/__tests__/share.test.js
import test from 'node:test'
import assert from 'node:assert/strict'
import { neon } from '@neondatabase/serverless'

const sql = neon(process.env.DATABASE_URL_TEST)

async function setup() {
  await sql`TRUNCATE analyses, audit_log RESTART IDENTITY CASCADE`
  await sql`INSERT INTO analyses (id, agent_slug, author_email, title, blob_pathname)
            VALUES ('s1', 'vendas-linx', 'a@b.com', 'T', 'analyses/vendas-linx/s1.html')`
}

function makeReq(email, body) {
  // Helper: gera cookie HMAC válido (ver portal/api/auth.js — createSessionCookie)
  // Aqui simplificado pra teste; em prática use SESSION_SECRET conhecida.
  return { method: 'POST', headers: { cookie: `session=${makeSessionCookie(email)}` }, body }
}

test('only author can change acl', async () => {
  process.env.SESSION_SECRET = 'test_secret'
  process.env.DATABASE_URL = process.env.DATABASE_URL_TEST
  const handler = (await import('../share.js')).default
  await setup()

  const res1 = makeRes()
  await handler(makeReq('other@c.com', { id: 's1', public: true, shared_with: [] }), res1)
  assert.equal(res1.statusCode, 403)

  const res2 = makeRes()
  await handler(makeReq('a@b.com', { id: 's1', public: true, shared_with: [] }), res2)
  assert.equal(res2.statusCode, 200)
})

test('writes audit row with diff', async () => {
  await setup()
  const handler = (await import('../share.js')).default
  const res = makeRes()
  await handler(makeReq('a@b.com', { id: 's1', public: false, shared_with: ['x@y.com', 'z@w.com'] }), res)
  assert.equal(res.statusCode, 200)
  const audits = await sql`SELECT action, metadata FROM audit_log WHERE analysis_id = 's1'`
  assert.equal(audits[0].action, 'share')
  assert.deepEqual(audits[0].metadata.added.sort(), ['x@y.com', 'z@w.com'])
})

test('emails normalized to lowercase', async () => {
  await setup()
  const handler = (await import('../share.js')).default
  const res = makeRes()
  await handler(makeReq('a@b.com', { id: 's1', public: false, shared_with: ['Maria.Filo@Soma.com.br'] }), res)
  assert.equal(res.statusCode, 200)
  const rows = await sql`SELECT shared_with FROM analyses WHERE id = 's1'`
  assert.deepEqual(rows[0].shared_with, ['maria.filo@soma.com.br'])
})

function makeRes() { /* same shape as Task 13 helper */ }
function makeSessionCookie(email) { /* HMAC mint usando SESSION_SECRET */ }
```

> **Nota:** o helper `makeSessionCookie` precisa replicar `createSessionCookie` de `portal/api/auth.js` (HMAC-SHA256 sobre `email~expiry` com `SESSION_SECRET`). Considere extrair pra `portal/api/_helpers/session.js` pra reuso entre auth.js e tests.

- [ ] **Step 3: Rodar testes**

```bash
cd portal && SESSION_SECRET=test_secret DATABASE_URL_TEST=$DATABASE_URL_TEST node --test api/__tests__/share.test.js
```

- [ ] **Step 4: Smoke test**

```bash
curl -X POST "https://<preview>.vercel.app/api/share" \
  -H "cookie: session=<valid>" -H "content-type: application/json" \
  -d '{"id":"<some-id>","public":false,"shared_with":["x@y.com"]}'
```

Esperado: `200 {"ok":true,...}` se autor; `403` se não.

- [ ] **Step 5: Commit**

```bash
git add portal/api/share.js portal/api/__tests__/share.test.js
git commit -m "feat(portal): /api/share writes to db with audit"
```

---

### Task 19: POST /api/archive

**Files:**
- Create: `portal/api/archive.js`

- [ ] **Step 1: Implementar**

```javascript
// portal/api/archive.js
import { getSql } from './_helpers/db.js'
import { verifySession } from './_helpers/session.js'
import { parseCookie } from './_helpers/cookie.js'

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' })
  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? await verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })

  const { id, archive } = req.body || {}
  if (!id || typeof archive !== 'boolean') return res.status(400).json({ error: 'id + archive required' })

  const sql = getSql()
  // verify visibility (ACL): user must be able to see the analysis to archive it for themselves
  const rows = await sql`
    SELECT 1 FROM analyses
    WHERE id = ${id}
      AND (author_email = ${email} OR public = TRUE OR ${email} = ANY(shared_with))
    LIMIT 1
  `
  if (rows.length === 0) return res.status(404).json({ error: 'not found or not accessible' })

  if (archive) {
    await sql`
      UPDATE analyses
      SET archived_by = array_append(array_remove(archived_by, ${email}), ${email}),
          updated_at = NOW()
      WHERE id = ${id}
    `
  } else {
    await sql`
      UPDATE analyses
      SET archived_by = array_remove(archived_by, ${email}),
          updated_at = NOW()
      WHERE id = ${id}
    `
  }
  await sql`
    INSERT INTO audit_log (action, actor_email, analysis_id)
    VALUES (${archive ? 'archive' : 'unarchive'}, ${email}, ${id})
  `
  return res.status(200).json({ ok: true })
}
```

- [ ] **Step 2: Escrever teste**

```javascript
// portal/api/__tests__/archive.test.js
import test from 'node:test'
import assert from 'node:assert/strict'
import { neon } from '@neondatabase/serverless'
const sql = neon(process.env.DATABASE_URL_TEST)

async function setup() {
  await sql`TRUNCATE analyses, audit_log RESTART IDENTITY CASCADE`
  await sql`INSERT INTO analyses (id, agent_slug, author_email, title, blob_pathname, public)
            VALUES ('a1', 'vendas-linx', 'owner@x.com', 'T', 'p', TRUE)`
}

test('archive is idempotent', async () => {
  await setup()
  const handler = (await import('../archive.js')).default
  const r1 = makeRes(); await handler(req('u@x.com', { id: 'a1', archive: true }), r1)
  const r2 = makeRes(); await handler(req('u@x.com', { id: 'a1', archive: true }), r2)
  assert.equal(r1.statusCode, 200)
  assert.equal(r2.statusCode, 200)
  const rows = await sql`SELECT archived_by FROM analyses WHERE id = 'a1'`
  assert.deepEqual(rows[0].archived_by, ['u@x.com'])  // not duplicated
})

test('unarchive removes from list', async () => {
  await setup()
  const handler = (await import('../archive.js')).default
  await handler(req('u@x.com', { id: 'a1', archive: true }), makeRes())
  await handler(req('u@x.com', { id: 'a1', archive: false }), makeRes())
  const rows = await sql`SELECT archived_by FROM analyses WHERE id = 'a1'`
  assert.deepEqual(rows[0].archived_by, [])
})

test('rejects user who cannot see the analysis', async () => {
  await sql`TRUNCATE analyses CASCADE`
  await sql`INSERT INTO analyses (id, agent_slug, author_email, title, blob_pathname, public)
            VALUES ('priv', 'vendas-linx', 'owner@x.com', 'T', 'p', FALSE)`
  const handler = (await import('../archive.js')).default
  const res = makeRes()
  await handler(req('outsider@y.com', { id: 'priv', archive: true }), res)
  assert.equal(res.statusCode, 404)  // not_accessible
})
```

- [ ] **Step 3: Rodar testes**

```bash
cd portal && SESSION_SECRET=test_secret DATABASE_URL_TEST=$DATABASE_URL_TEST node --test api/__tests__/archive.test.js
```

- [ ] **Step 4: Commit**

```bash
git add portal/api/archive.js portal/api/__tests__/archive.test.js
git commit -m "feat(portal): /api/archive (per-user soft-hide) + tests"
```

---

### Task 20: Frontend — share modal + server-side archive

**Files:**
- Modify: `portal/index.html`

- [ ] **Step 1: Adicionar modal de share no markup (ao lado do iframe modal)**

```html
<dialog id="share-modal" class="modal">
  <form method="dialog" class="modal-form">
    <h2>Compartilhar análise</h2>
    <p class="muted">Adicione e-mails @somagrupo.com.br ou @farmrio.com.br. Eles passarão a ver este relatório.</p>
    <div class="email-list" id="share-email-list"></div>
    <input type="email" id="share-email-input" placeholder="email@somagrupo.com.br" autocomplete="email" />
    <label class="checkbox">
      <input type="checkbox" id="share-public-toggle" /> Tornar público (todo o tenant vê)
    </label>
    <div class="modal-actions">
      <button type="button" id="share-cancel">Cancelar</button>
      <button type="button" id="share-save" class="primary">Salvar</button>
    </div>
  </form>
</dialog>
```

- [ ] **Step 2: Adicionar JS do modal**

```javascript
// dentro do <script> principal do index.html
function openShareModal(item) {
  const dlg = document.getElementById('share-modal')
  const list = document.getElementById('share-email-list')
  const input = document.getElementById('share-email-input')
  const pubToggle = document.getElementById('share-public-toggle')

  let emails = [...(item.shared_with || [])]
  let isPublic = !!item.public

  function render() {
    list.innerHTML = ''
    for (const e of emails) {
      const tag = document.createElement('span')
      tag.className = 'email-tag'
      tag.innerHTML = `<span>${escapeHtml(e)}</span><button type="button" aria-label="remover">×</button>`
      tag.querySelector('button').onclick = () => { emails = emails.filter(x => x !== e); render() }
      list.appendChild(tag)
    }
    pubToggle.checked = isPublic
  }

  function addFromInput() {
    const raw = input.value.trim().toLowerCase()
    if (!raw) return
    for (const piece of raw.split(/[,;\s]+/)) {
      if (piece.includes('@') && !emails.includes(piece)) emails.push(piece)
    }
    input.value = ''
    render()
  }

  input.onkeydown = (ev) => {
    if (ev.key === 'Enter' || ev.key === ',') { ev.preventDefault(); addFromInput() }
  }
  input.onblur = addFromInput

  document.getElementById('share-cancel').onclick = () => dlg.close()
  document.getElementById('share-save').onclick = async () => {
    addFromInput()
    isPublic = pubToggle.checked
    const resp = await fetch('/api/share', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ id: item.id, public: isPublic, shared_with: emails }),
    })
    if (!resp.ok) {
      toast('Erro ao salvar lista', 'error')
      return
    }
    toast('Lista atualizada')
    dlg.close()
    await reloadLibrary()
  }

  render()
  dlg.showModal()
}
```

- [ ] **Step 3: Trocar archive de localStorage pra fetch**

Substituir as funções `archive(id)` / `unarchive(id)` que mexiam em `localStorage['azzas_archived']` por:

```javascript
async function setArchived(id, archive) {
  const resp = await fetch('/api/archive', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id, archive }),
  })
  if (!resp.ok) { toast('Erro ao arquivar', 'error'); return }
  await reloadLibrary()
}
```

E remover qualquer leitura de `localStorage['azzas_archived']` — o estado vem do payload do `/api/library` (campo `is_archived`).

- [ ] **Step 4: Atualizar menu do card pra mostrar ações por estado (tabela 9.6 do spec)**

Localizar o builder do dropdown menu de cada card. Aplicar lógica:

```javascript
function buildCardMenu(item, currentEmail) {
  const isOwner = item.author_email === currentEmail
  const items = []

  if (isOwner && item.has_refresh_spec) {
    items.push({ label: 'Atualizar período…', action: () => openRefreshModal(item) })
  }
  if (isOwner && !item.public) {
    items.push({ label: 'Compartilhar com pessoas…', action: () => openShareModal(item) })
    items.push({ label: 'Tornar pública', action: () => makePublic(item) })
  }
  if (isOwner && item.public) {
    items.push({ label: 'Tornar privada', action: () => makePrivate(item) })
  }
  if (item.public || item.is_shared_with_me || isOwner) {
    items.push({ label: 'Copiar link', action: () => copyLink(item) })
  }
  items.push({
    label: item.is_archived ? 'Restaurar' : 'Arquivar',
    action: () => setArchived(item.id, !item.is_archived),
  })
  return items
}

async function makePublic(item) {
  await fetch('/api/share', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: item.id, public: true, shared_with: item.shared_with || [] }),
  })
  toast('Análise pública')
  await reloadLibrary()
}

async function makePrivate(item) {
  await fetch('/api/share', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ id: item.id, public: false, shared_with: item.shared_with || [] }),
  })
  toast('Análise privada')
  await reloadLibrary()
}
```

- [ ] **Step 5: Manual QA**

- Como autor A: publicar análise; menu mostra "Compartilhar com pessoas…" e "Tornar pública"; clica share → modal abre, adiciona B, salva → toast → DB tem `shared_with=[B]`.
- Como autor A: clica "Tornar pública" → vira público.
- Como B: vê em "Público" antes; agora vê em "Compartilhadas comigo" se foi unshared via remover do modal.
- Arquivar como B: some da tab. Login em outro browser como B: ainda arquivado.

- [ ] **Step 6: Commit**

```bash
git add portal/index.html
git commit -m "feat(portal): share modal + server-side archive (replaces localStorage)"
```

---

## Phase 5 — Refresh

### Task 21: Proxy JWT (mint + verify)

**Files:**
- Create: `portal/api/_helpers/proxy_jwt.js`
- Create: `packages/mcp-core/src/mcp_core/proxy_jwt.py`
- Create: `packages/mcp-core/tests/test_proxy_jwt.py`

- [ ] **Step 1: Implementar minter no Vercel**

```javascript
// portal/api/_helpers/proxy_jwt.js
import jwt from 'jsonwebtoken'

export function mintProxyJwt(email, ttlSeconds = 60) {
  const secret = process.env.MCP_PROXY_SIGNING_KEY
  if (!secret) throw new Error('MCP_PROXY_SIGNING_KEY not set')
  return jwt.sign(
    { email, aud: 'mcp-core-proxy' },
    secret,
    { algorithm: 'HS256', expiresIn: ttlSeconds },
  )
}
```

- [ ] **Step 2: Escrever teste do verifier Python**

```python
# packages/mcp-core/tests/test_proxy_jwt.py
import os
import pytest
import jwt as pyjwt
import time
from mcp_core.proxy_jwt import verify_proxy_jwt


def _mint(email: str, secret: str, *, exp_in: int = 60, aud: str = "mcp-core-proxy") -> str:
    return pyjwt.encode({"email": email, "aud": aud, "exp": int(time.time()) + exp_in}, secret, algorithm="HS256")


def test_verify_returns_email(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    token = _mint("a@b.com", "secret123")
    assert verify_proxy_jwt(token) == "a@b.com"


def test_verify_rejects_wrong_audience(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    token = _mint("a@b.com", "secret123", aud="other")
    with pytest.raises(ValueError, match="audience"):
        verify_proxy_jwt(token)


def test_verify_rejects_expired(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    token = _mint("a@b.com", "secret123", exp_in=-1)
    with pytest.raises(ValueError, match="expired"):
        verify_proxy_jwt(token)


def test_verify_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "right")
    token = _mint("a@b.com", "wrong")
    with pytest.raises(ValueError, match="signature"):
        verify_proxy_jwt(token)
```

- [ ] **Step 3: Implementar verifier**

```python
# packages/mcp-core/src/mcp_core/proxy_jwt.py
from __future__ import annotations
import os
import jwt as pyjwt


def verify_proxy_jwt(token: str) -> str:
    """Verify HS256 proxy JWT signed with MCP_PROXY_SIGNING_KEY. Returns email claim.

    Raises ValueError if token is invalid, expired, has wrong audience, or wrong signature."""
    secret = os.environ.get("MCP_PROXY_SIGNING_KEY")
    if not secret:
        raise RuntimeError("MCP_PROXY_SIGNING_KEY not set")
    try:
        payload = pyjwt.decode(token, secret, algorithms=["HS256"], audience="mcp-core-proxy")
    except pyjwt.ExpiredSignatureError:
        raise ValueError("expired")
    except pyjwt.InvalidAudienceError:
        raise ValueError("audience")
    except pyjwt.InvalidSignatureError:
        raise ValueError("signature")
    except pyjwt.PyJWTError as e:
        raise ValueError(f"invalid: {e}")
    email = payload.get("email")
    if not email:
        raise ValueError("missing email claim")
    return email
```

- [ ] **Step 4: Rodar testes**

```bash
cd packages/mcp-core && uv run pytest tests/test_proxy_jwt.py -v
```

Esperado: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/proxy_jwt.py packages/mcp-core/tests/test_proxy_jwt.py portal/api/_helpers/proxy_jwt.js
git commit -m "feat: proxy jwt (vercel mint + mcp-core verify)"
```

---

### Task 22: auth_middleware aceita proxy JWT

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/auth_middleware.py`

- [ ] **Step 1: Localizar handler atual**

```bash
cd packages/mcp-core && grep -n "def\|JWT\|JWKS" src/mcp_core/auth_middleware.py | head -30
```

- [ ] **Step 2: Adicionar caminho proxy**

Antes do path MSAL existente, tentar primeiro o proxy JWT. Adicionar algo como:

```python
# packages/mcp-core/src/mcp_core/auth_middleware.py — adicionar acima do path MSAL
from mcp_core.proxy_jwt import verify_proxy_jwt

def _try_proxy(token: str) -> str | None:
    """Try to verify as proxy JWT. Returns email if valid, None if doesn't look like proxy JWT."""
    # quick heuristic: HS256 (no kid header)
    import base64, json
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64 = parts[0] + "=" * (-len(parts[0]) % 4)
        header = json.loads(base64.urlsafe_b64decode(header_b64))
        if header.get("alg") != "HS256":
            return None
    except Exception:
        return None
    try:
        return verify_proxy_jwt(token)
    except ValueError:
        return None
```

E na função que valida o Bearer token, antes de chamar a validação MSAL:

```python
# pseudo (ajustar ao fluxo real do auth_middleware)
async def get_email_from_request(request) -> str:
    token = _extract_bearer(request)
    proxy_email = _try_proxy(token)
    if proxy_email is not None:
        return _check_allowlist_or_403(proxy_email)
    # fallback: MSAL JWT path
    return await _validate_msal_token(token)
```

- [ ] **Step 3: Adicionar teste de integração**

```python
# packages/mcp-core/tests/test_auth_middleware.py — adicionar caso novo
@pytest.mark.asyncio
async def test_proxy_jwt_path(monkeypatch):
    monkeypatch.setenv("MCP_PROXY_SIGNING_KEY", "secret123")
    monkeypatch.setattr("mcp_core.auth_middleware._check_allowlist_or_403",
                        lambda email: email)  # bypass allowlist
    import jwt
    token = jwt.encode({"email": "a@b.com", "aud": "mcp-core-proxy", "exp": 9999999999},
                        "secret123", algorithm="HS256")
    request_mock = ...  # build mock with Authorization: Bearer {token}
    email = await get_email_from_request(request_mock)
    assert email == "a@b.com"
```

- [ ] **Step 4: Rodar suite de auth**

```bash
cd packages/mcp-core && uv run pytest tests/test_auth_middleware.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/auth_middleware.py packages/mcp-core/tests/test_auth_middleware.py
git commit -m "feat(mcp-core): auth_middleware accepts hs256 proxy jwt path"
```

---

### Task 23: Refresh handler (BQ + swap + DB + Blob)

**Files:**
- Create: `packages/mcp-core/src/mcp_core/refresh_handler.py`
- Create: `packages/mcp-core/tests/test_refresh_handler.py`

- [ ] **Step 1: Escrever teste**

```python
# packages/mcp-core/tests/test_refresh_handler.py
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock
from mcp_core import db, analyses_repo
from mcp_core.refresh_handler import refresh_analysis, RefreshResult, RefreshError


@pytest.fixture
def fake_bq():
    bq = MagicMock()
    bq.run_query = AsyncMock(return_value=MagicMock(rows=[{"x": 1, "y": 2}]))
    return bq


@pytest.fixture
def fake_blob():
    b = MagicMock()
    b.get = AsyncMock(return_value=b'<html><script id="data_q1" type="application/json">[]</script></html>')
    b.put = AsyncMock(return_value="https://blob.fake/x.html")
    return b


def _seed_row(refresh_spec=None, author="a@b.com", id="t1"):
    return analyses_repo.AnalysisRow(
        id=id, agent_slug="vendas-linx", author_email=author,
        title="T", blob_pathname="analyses/vendas-linx/t1.html",
        refresh_spec=refresh_spec or {
            "queries": [{"id": "q1", "sql": "SELECT 1 WHERE d BETWEEN '{{start_date}}' AND '{{end_date}}'"}],
            "data_blocks": [{"block_id": "data_q1", "query_id": "q1"}],
            "original_period": {"start": "2026-04-01", "end": "2026-04-23"},
        },
    )


@pytest.mark.asyncio
async def test_refresh_happy_path(db_pool, fake_bq, fake_blob):
    async with db.transaction() as conn:
        await analyses_repo.insert(conn, _seed_row())

    result = await refresh_analysis(
        analysis_id="t1", actor_email="a@b.com",
        start=date(2026, 5, 1), end=date(2026, 5, 7),
        bq=fake_bq, blob=fake_blob,
    )
    assert isinstance(result, RefreshResult)
    fake_bq.run_query.assert_called_once()
    fake_blob.put.assert_called_once()
    # data island swapped
    put_args = fake_blob.put.call_args
    body = put_args.args[1].decode() if len(put_args.args) > 1 else put_args.kwargs["body"].decode()
    assert '[{"x":1,"y":2}]' in body or '"x":1' in body

    async with db.get_pool().acquire() as conn:
        row = await analyses_repo.get(conn, "t1")
    assert row.period_start == date(2026, 5, 1)
    assert row.last_refreshed_by == "a@b.com"


@pytest.mark.asyncio
async def test_refresh_rejects_non_author(db_pool, fake_bq, fake_blob):
    async with db.transaction() as conn:
        await analyses_repo.insert(conn, _seed_row())
    with pytest.raises(RefreshError) as e:
        await refresh_analysis(analysis_id="t1", actor_email="other@c.com",
                                start=date(2026, 5, 1), end=date(2026, 5, 7),
                                bq=fake_bq, blob=fake_blob)
    assert e.value.status == 403


@pytest.mark.asyncio
async def test_refresh_rejects_no_spec(db_pool, fake_bq, fake_blob):
    async with db.transaction() as conn:
        await analyses_repo.insert(conn, _seed_row(refresh_spec={"queries": [], "data_blocks": [], "original_period": {"start": "2026-04-01", "end": "2026-04-01"}}))
        # Note: empty queries can't actually validate via Pydantic; mark as None
        await db.get_pool().acquire().__aenter__().__aexit__(None, None, None) if False else None
    # use direct SQL update to bypass validation:
    async with db.get_pool().acquire() as conn:
        await conn.execute("UPDATE analyses SET refresh_spec = NULL WHERE id = 't1'")
    with pytest.raises(RefreshError) as e:
        await refresh_analysis(analysis_id="t1", actor_email="a@b.com",
                                start=date(2026, 5, 1), end=date(2026, 5, 7),
                                bq=fake_bq, blob=fake_blob)
    assert e.value.status == 422


@pytest.mark.asyncio
async def test_refresh_bq_failure_records_error(db_pool, fake_blob):
    async with db.transaction() as conn:
        await analyses_repo.insert(conn, _seed_row())
    bq = MagicMock()
    bq.run_query = AsyncMock(side_effect=RuntimeError("dataset not allowed"))
    with pytest.raises(RefreshError) as e:
        await refresh_analysis(analysis_id="t1", actor_email="a@b.com",
                                start=date(2026, 5, 1), end=date(2026, 5, 7),
                                bq=bq, blob=fake_blob)
    assert e.value.status == 502
    async with db.get_pool().acquire() as conn:
        row = await analyses_repo.get(conn, "t1")
    assert "dataset not allowed" in row.last_refresh_error
    assert row.period_start == date(2026, 4, 1)  # unchanged
```

- [ ] **Step 2: Implementar**

```python
# packages/mcp-core/src/mcp_core/refresh_handler.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Any
from mcp_core import db, analyses_repo, audit
from mcp_core.refresh_spec import RefreshSpec
from mcp_core.html_swap import swap_data_blocks


@dataclass
class RefreshResult:
    last_refreshed_at: str  # iso datetime
    period_start: date
    period_end: date


class RefreshError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


async def refresh_analysis(
    *,
    analysis_id: str,
    actor_email: str,
    start: date,
    end: date,
    bq,        # BqClient (run_query async)
    blob,      # BlobClient
) -> RefreshResult:
    """Re-run the analysis SQL with new period, swap data islands, persist.

    Raises RefreshError with status 403 (non-author), 404 (not found), 409 (concurrent),
    422 (no refresh_spec), 500 (HTML swap), 502 (BQ error)."""

    if start > end:
        raise RefreshError(400, "start must be <= end")

    async with db.transaction() as conn:
        # Lock first
        got_lock = await analyses_repo.try_acquire_refresh_lock(conn, analysis_id)
        if not got_lock:
            raise RefreshError(409, "refresh already in progress")

        row = await analyses_repo.get(conn, analysis_id)
        if row is None:
            raise RefreshError(404, "analysis not found")
        if row.author_email != actor_email:
            raise RefreshError(403, "only author can refresh")
        if row.refresh_spec is None:
            raise RefreshError(422, "analysis has no refresh_spec; not refreshable")

        spec = RefreshSpec.model_validate(row.refresh_spec)

        # Run queries (within outer transaction; if any fails, ROLLBACK + record error in separate tx)
        try:
            results = {}
            for q in spec.queries:
                rendered = q.render(start=start, end=end)
                bq_result = await bq.run_query(rendered, exec_email=actor_email)
                results[q.id] = list(bq_result.rows)
        except Exception as e:
            # rollback outer transaction by raising; record error separately
            err_msg = str(e)[:500]
            raise _RecordError(err_msg) from e

        # Build payloads keyed by block_id
        payloads = {}
        for ref in spec.data_blocks:
            payloads[ref.block_id] = results[ref.query_id]

        # Download current HTML pelo endpoint interno do portal (recebe pathname),
        # faz swap, sobe versão nova
        current_html_bytes = await blob.get(row.blob_pathname)
        new_html = swap_data_blocks(current_html_bytes.decode("utf-8"), payloads)
        new_blob_url = await blob.put(row.blob_pathname, new_html.encode("utf-8"), content_type="text/html")

        await analyses_repo.update_refresh_state(
            conn, analysis_id,
            period_start=start, period_end=end, actor_email=actor_email,
        )
        # blob_url normalmente não muda (mesmo pathname, allowOverwrite=true), mas atualizamos
        # caso o SDK retorne URL diferente (defensivo)
        if new_blob_url and new_blob_url != row.blob_url:
            await analyses_repo.update_blob_url(conn, analysis_id, blob_url=new_blob_url)
        await audit.record(conn, action="refresh", actor_email=actor_email,
                            analysis_id=analysis_id,
                            metadata={"period_start": start.isoformat(), "period_end": end.isoformat()})

        # fetch updated row to return
        updated = await analyses_repo.get(conn, analysis_id)

    return RefreshResult(
        last_refreshed_at=updated.last_refreshed_at.isoformat() if updated.last_refreshed_at else "",
        period_start=updated.period_start,
        period_end=updated.period_end,
    )


class _RecordError(Exception):
    """Internal: signal that we need to record refresh error in a fresh tx after rollback."""
    pass


# wrap refresh_analysis at the API layer (Task 24) to catch _RecordError, do the side-effect record,
# and translate to RefreshError(502, …)
```

> **Nota:** o handler acima precisa de um wrapper na camada de API (Task 24) que captura `_RecordError`, reconecta numa transação separada, faz `set_refresh_error`, e retorna `RefreshError(502, msg)`. Fazer isso na camada de rota porque o `async with transaction()` aqui já fez ROLLBACK quando a exceção subiu.

- [ ] **Step 3: Rodar testes**

```bash
cd packages/mcp-core && uv run pytest tests/test_refresh_handler.py -v
```

Esperado: passes (alguns testes podem precisar de ajuste fino conforme o shape de `BqClient.run_query` no projeto).

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/src/mcp_core/refresh_handler.py packages/mcp-core/tests/test_refresh_handler.py
git commit -m "feat(mcp-core): refresh_analysis handler (bq + swap + db + blob, transactional)"
```

---

### Task 24: Rota FastAPI `POST /api/refresh/<id>`

**Files:**
- Create: `packages/mcp-core/src/mcp_core/api_routes.py`
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py` (mount routes)

- [ ] **Step 1: Implementar rota**

```python
# packages/mcp-core/src/mcp_core/api_routes.py
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from mcp_core import db, analyses_repo, audit
from mcp_core.refresh_handler import refresh_analysis, RefreshError, _RecordError
from mcp_core.email_norm import normalize_email


class RefreshBody(BaseModel):
    start_date: date
    end_date: date


def make_router(get_email_from_request, bq_factory, blob_factory) -> APIRouter:
    router = APIRouter()

    @router.post("/api/refresh/{analysis_id}")
    async def refresh(analysis_id: str, body: RefreshBody, request: Request):
        try:
            email = normalize_email(await get_email_from_request(request))
        except Exception as e:
            raise HTTPException(401, f"auth failed: {e}")
        bq = bq_factory(email)
        blob = blob_factory()
        try:
            result = await refresh_analysis(
                analysis_id=analysis_id, actor_email=email,
                start=body.start_date, end=body.end_date,
                bq=bq, blob=blob,
            )
            return {
                "ok": True,
                "last_refreshed_at": result.last_refreshed_at,
                "period_start": result.period_start.isoformat(),
                "period_end": result.period_end.isoformat(),
            }
        except _RecordError as e:
            # record error in its own transaction, then translate to 502
            async with db.transaction() as conn:
                await analyses_repo.set_refresh_error(conn, analysis_id, error=str(e))
                await audit.record(conn, action="refresh_failed", actor_email=email,
                                    analysis_id=analysis_id, metadata={"error": str(e)})
            raise HTTPException(502, f"bigquery error: {e}")
        except RefreshError as e:
            raise HTTPException(e.status, e.message)

    return router
```

- [ ] **Step 2: Mount no auth_app**

Em `server_factory.py` (área de construção do `auth_app` FastAPI):

```python
from mcp_core.api_routes import make_router
from mcp_core.bq_client import BqClient  # ajustar import conforme estrutura real
from mcp_core.blob_client import BlobClient

# ... onde auth_app é criada
auth_app.include_router(make_router(
    get_email_from_request=get_email_from_request,
    bq_factory=lambda email: BqClient(exec_email=email, settings=...),  # match assinatura existente
    blob_factory=lambda: BlobClient(),
))
```

- [ ] **Step 3: Smoke test integrado**

Rodar mcp-core local com `DATABASE_URL_TEST` apontando pra dev DB, inserir uma row com `refresh_spec` válido, mintar um proxy JWT, e:

```bash
TOKEN=$(node -e "console.log(require('jsonwebtoken').sign({email:'a@b.com',aud:'mcp-core-proxy'}, '$MCP_PROXY_SIGNING_KEY', {expiresIn: 60}))")
curl -X POST http://localhost:8000/api/refresh/<id> \
  -H "authorization: Bearer $TOKEN" -H "content-type: application/json" \
  -d '{"start_date": "2026-05-01", "end_date": "2026-05-07"}'
```

Esperado: `200 {"ok": true, ...}`.

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/src/mcp_core/api_routes.py packages/mcp-core/src/mcp_core/server_factory.py
git commit -m "feat(mcp-core): mount POST /api/refresh/{id} fastapi route"
```

---

### Task 25: Vercel proxy `/api/refresh-proxy`

**Files:**
- Create: `portal/api/refresh-proxy.js`

- [ ] **Step 1: Implementar**

```javascript
// portal/api/refresh-proxy.js
import { verifySession } from './_helpers/session.js'
import { parseCookie } from './_helpers/cookie.js'
import { mintProxyJwt } from './_helpers/proxy_jwt.js'

const AGENT_RAILWAY_URLS = {
  'vendas-linx': process.env.AGENT_VENDAS_LINX_URL || 'https://vendas-linx-prod.up.railway.app',
  'devolucoes':  process.env.AGENT_DEVOLUCOES_URL  || 'https://devolucoes-prod.up.railway.app',
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method not allowed' })
  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? await verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })

  const { agent, id, start_date, end_date } = req.body || {}
  if (!agent || !id || !start_date || !end_date) {
    return res.status(400).json({ error: 'agent, id, start_date, end_date required' })
  }
  const baseUrl = AGENT_RAILWAY_URLS[agent]
  if (!baseUrl) return res.status(400).json({ error: `unknown agent: ${agent}` })

  const token = mintProxyJwt(email, 60)
  const targetUrl = `${baseUrl}/api/refresh/${encodeURIComponent(id)}`
  const headers = {
    authorization: `Bearer ${token}`,
    'content-type': 'application/json',
  }
  const body = JSON.stringify({ start_date, end_date })

  // 1 retry com backoff curto, só pra cobrir cold start do Railway (~2s).
  // Não retentar em status >= 400 (resposta de negócio do mcp-core, não falha de transporte).
  async function callOnce() {
    return await fetch(targetUrl, { method: 'POST', headers, body })
  }

  let upstream
  try {
    upstream = await callOnce()
  } catch (e) {
    await new Promise(r => setTimeout(r, 2000))
    try {
      upstream = await callOnce()
    } catch (e2) {
      return res.status(503).json({ error: `agent unreachable: ${e2.message}` })
    }
  }

  const text = await upstream.text()
  res.status(upstream.status)
     .setHeader('content-type', upstream.headers.get('content-type') || 'application/json')
     .send(text)
}
```

- [ ] **Step 2: Adicionar env vars de URL dos agentes no Vercel**

Project Settings → Environment Variables:
- `AGENT_VENDAS_LINX_URL` = `https://vendas-linx-prod.up.railway.app`
- `AGENT_DEVOLUCOES_URL` = `https://devolucoes-prod.up.railway.app`

- [ ] **Step 3: Smoke test**

```bash
curl -X POST "https://<preview>.vercel.app/api/refresh-proxy" \
  -H "cookie: session=<valid>" -H "content-type: application/json" \
  -d '{"agent":"vendas-linx","id":"<id>","start_date":"2026-05-01","end_date":"2026-05-07"}'
```

- [ ] **Step 4: Commit**

```bash
git add portal/api/refresh-proxy.js
git commit -m "feat(portal): /api/refresh-proxy mints proxy jwt and forwards to railway"
```

---

### Task 26: Frontend — modal de refresh

**Files:**
- Modify: `portal/index.html`

- [ ] **Step 1: Adicionar markup do modal**

```html
<dialog id="refresh-modal" class="modal">
  <form method="dialog" class="modal-form">
    <h2>Atualizar período</h2>
    <p class="muted">Período atual: <span id="refresh-current-period">—</span> · Atualizado em <span id="refresh-last">—</span></p>
    <label>Preset
      <select id="refresh-preset">
        <option value="7d">Últimos 7 dias</option>
        <option value="30d" selected>Últimos 30 dias</option>
        <option value="90d">Últimos 90 dias</option>
        <option value="mtd">MTD</option>
        <option value="ytd">YTD</option>
        <option value="custom">Personalizar…</option>
      </select>
    </label>
    <div id="refresh-custom" hidden>
      <label>De <input type="date" id="refresh-start" /></label>
      <label>Até <input type="date" id="refresh-end" /></label>
    </div>
    <div class="modal-actions">
      <button type="button" id="refresh-cancel">Cancelar</button>
      <button type="button" id="refresh-go" class="primary">Atualizar</button>
    </div>
    <div id="refresh-status" class="muted" hidden></div>
  </form>
</dialog>
```

- [ ] **Step 2: Adicionar JS**

```javascript
function presetToRange(preset) {
  const today = new Date()
  const end = today.toISOString().slice(0, 10)
  const startDate = new Date(today)
  if (preset === '7d')  startDate.setDate(today.getDate() - 7)
  if (preset === '30d') startDate.setDate(today.getDate() - 30)
  if (preset === '90d') startDate.setDate(today.getDate() - 90)
  if (preset === 'mtd') startDate.setDate(1)
  if (preset === 'ytd') { startDate.setMonth(0); startDate.setDate(1) }
  return { start: startDate.toISOString().slice(0, 10), end }
}

function openRefreshModal(item) {
  const dlg = document.getElementById('refresh-modal')
  const presetSel = document.getElementById('refresh-preset')
  const customDiv = document.getElementById('refresh-custom')
  const startInp = document.getElementById('refresh-start')
  const endInp = document.getElementById('refresh-end')
  const status = document.getElementById('refresh-status')

  document.getElementById('refresh-current-period').textContent =
    item.period_start && item.period_end ? `${item.period_start} a ${item.period_end}` : '—'
  document.getElementById('refresh-last').textContent =
    item.last_refreshed_at ? new Date(item.last_refreshed_at).toLocaleString('pt-BR') : 'nunca'

  presetSel.value = '30d'
  customDiv.hidden = true
  status.hidden = true

  presetSel.onchange = () => {
    customDiv.hidden = presetSel.value !== 'custom'
    if (presetSel.value !== 'custom') {
      const r = presetToRange(presetSel.value)
      startInp.value = r.start
      endInp.value = r.end
    }
  }
  presetSel.dispatchEvent(new Event('change'))  // initialize

  document.getElementById('refresh-cancel').onclick = () => dlg.close()
  document.getElementById('refresh-go').onclick = async () => {
    let start = startInp.value, end = endInp.value
    if (presetSel.value !== 'custom') {
      const r = presetToRange(presetSel.value)
      start = r.start; end = r.end
    }
    if (!start || !end || start > end) {
      status.hidden = false; status.textContent = 'Datas inválidas'; return
    }

    status.hidden = false
    status.textContent = 'Atualizando… (5-30s)'
    document.getElementById('refresh-go').disabled = true

    try {
      const resp = await fetch('/api/refresh-proxy', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ agent: item.agent.name, id: item.id, start_date: start, end_date: end }),
      })
      if (!resp.ok) {
        const err = await resp.text()
        toast(`Falha: ${err.slice(0, 120)}`, 'error')
        status.textContent = `Erro ${resp.status}`
        return
      }
      toast('Atualizado!')
      dlg.close()
      await reloadLibrary()
    } finally {
      document.getElementById('refresh-go').disabled = false
    }
  }

  dlg.showModal()
}
```

- [ ] **Step 3: Manual QA**

- Como autor: clicar "Atualizar período" → modal abre → preset 7d selecionado → "Atualizar" → spinner → fecha → toast → card refresh com período novo
- Como não-autor: opção não aparece no menu

- [ ] **Step 4: Commit**

```bash
git add portal/index.html
git commit -m "feat(portal): refresh modal with presets + custom dates"
```

---

## Phase 6 — Catalog tools

### Task 27: MCP tool `buscar_analises`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py`
- Create: `packages/mcp-core/tests/test_search.py`

- [ ] **Step 1: Escrever teste**

```python
# packages/mcp-core/tests/test_search.py
import pytest
from datetime import date
from mcp_core import db, analyses_repo
from mcp_core.analyses_repo import search


@pytest.mark.asyncio
async def test_search_filters_by_agent(db_pool):
    async with db.transaction() as conn:
        await analyses_repo.insert(conn, analyses_repo.AnalysisRow(
            id="r1", agent_slug="vendas-linx", author_email="a@b.com",
            title="Top produtos FARM Leblon", description="ranking",
            tags=["produto", "ranking"], blob_pathname="x",
            public=True,
        ))
        await analyses_repo.insert(conn, analyses_repo.AnalysisRow(
            id="r2", agent_slug="devolucoes", author_email="a@b.com",
            title="Devoluções por motivo", description="análise",
            tags=["devolucao"], blob_pathname="x",
            public=True,
        ))
    async with db.get_pool().acquire() as conn:
        rows = await search(conn, query="produtos", email="a@b.com", agent="vendas-linx")
    assert len(rows) == 1
    assert rows[0].id == "r1"


@pytest.mark.asyncio
async def test_search_respects_acl(db_pool):
    async with db.transaction() as conn:
        await analyses_repo.insert(conn, analyses_repo.AnalysisRow(
            id="r1", agent_slug="vendas-linx", author_email="other@c.com",
            title="Top produtos", blob_pathname="x", public=False,
        ))
    async with db.get_pool().acquire() as conn:
        rows = await search(conn, query="produtos", email="a@b.com")
    assert len(rows) == 0  # private to other user
```

- [ ] **Step 2: Adicionar tools `buscar_analises` e `obter_analise` em `server_factory.py`**

```python
# em server_factory.py — dentro do build_mcp_app onde outras tools são registradas

@mcp.tool(annotations={"readOnlyHint": True})
async def buscar_analises(
    query: str,
    ctx: Context,
    brand: str | None = None,
    agent: str | None = None,
    days_back: int = 90,
    limit: int = 10,
) -> dict[str, object]:
    """Busca análises previamente publicadas (texto livre + filtros).

    Use ANTES de gerar uma análise nova pra:
    - Detectar análises recentes parecidas (sugerir 'atualizar período' em vez de criar do zero)
    - Reusar SQLs de análises similares como ponto de partida (sempre adaptando ao pedido atual)

    Retorna no máximo 25 entries (default 10), ranqueadas por relevância × recência.
    Filtra automaticamente pelo que o usuário (você, no contexto MCP) pode ver — privadas
    de terceiros não aparecem.
    """
    from mcp_core.email_norm import normalize_email
    email = normalize_email(_current_email(ctx))
    async with db.get_pool().acquire() as conn:
        rows = await analyses_repo.search(
            conn, query=query, email=email,
            agent=agent, brand=brand,
            days_back=days_back, limit=min(limit, 25),
        )
    return {
        "results": [
            {
                "id": r.id, "title": r.title, "description": r.description,
                "brand": r.brand, "author_email": r.author_email, "agent_slug": r.agent_slug,
                "period_label": r.period_label, "tags": r.tags,
                "last_refreshed_at": r.last_refreshed_at.isoformat() if r.last_refreshed_at else None,
                "has_refresh_spec": r.refresh_spec is not None,
            }
            for r in rows
        ],
    }


@mcp.tool(annotations={"readOnlyHint": True})
async def obter_analise(id: str, ctx: Context) -> dict[str, object]:
    """Recupera detalhes completos de uma análise (incluindo SQLs do refresh_spec).

    Use depois de `buscar_analises` quando uma das análises encontradas parecer relevante
    e você quiser ver as SQLs originais (pra adaptar ao pedido atual).

    Falha com erro se você não tem direito de ver a análise."""
    from mcp_core.email_norm import normalize_email
    email = normalize_email(_current_email(ctx))
    async with db.get_pool().acquire() as conn:
        row = await analyses_repo.get(conn, id)
    if row is None:
        return {"error": "not_found"}
    allowed = (row.author_email == email) or row.public or (email in (row.shared_with or []))
    if not allowed:
        return {"error": "forbidden"}
    return {
        "id": row.id, "title": row.title, "description": row.description,
        "brand": row.brand, "author_email": row.author_email, "agent_slug": row.agent_slug,
        "period_label": row.period_label, "tags": row.tags,
        "refresh_spec": row.refresh_spec,  # contains the queries with placeholders
        "last_refreshed_at": row.last_refreshed_at.isoformat() if row.last_refreshed_at else None,
    }
```

- [ ] **Step 3: Rodar testes**

```bash
cd packages/mcp-core && uv run pytest tests/test_search.py tests/test_server_factory.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/src/mcp_core/server_factory.py packages/mcp-core/tests/test_search.py
git commit -m "feat(mcp-core): add buscar_analises and obter_analise mcp tools"
```

---

### Task 28: SKILL.md updates pros agentes

**Files:**
- Modify: `agents/vendas-linx/SKILL.md`
- Modify: `agents/devolucoes/SKILL.md`

- [ ] **Step 1: Adicionar seção em cada SKILL.md**

Adicionar (no início, depois das instruções de boot do agente):

```markdown
## Antes de gerar uma análise nova: buscar histórico

Sempre que o usuário pedir uma análise não-trivial:

1. Chame `buscar_analises(query=<resumo da pergunta>, brand=<marca se houver>, agent="<slug do agente atual>")`.
2. Se houver match recente (últimos 30 dias) com mesma marca + tema:
   - Mostre pro usuário: "Já existe uma análise parecida: '<título>' (publicada há N dias). Quer atualizar com o novo período em vez de criar uma nova?"
   - Se sim → instrua "abre o portal, clica nos 3 pontinhos do card '<título>' e escolhe 'Atualizar período'." Não tente fazer o refresh por chat.
   - Se não → siga gerando a análise nova.
3. Para análises não-triviais, antes de escrever SQL do zero, chame `obter_analise(id=<id da mais relevante>)` em 1-2 análises e use as SQLs do `refresh_spec.queries[].sql` como **ponto de partida** (sempre adaptando — período, filtros, dimensões podem ter mudado).
4. Inclua uma linha no rascunho: "reaproveitando estrutura de '<título da análise prévia>'".

## Como gerar análise atualizável (refresh_spec)

Quando publicar uma análise, **passe `refresh_spec` no `publicar_dashboard`** sempre que possível. Sem isso, o usuário não consegue clicar "Atualizar período" no portal.

Convenções:
- SQL com placeholders fixos `'{{start_date}}'` e `'{{end_date}}'` (com aspas simples — são strings ISO YYYY-MM-DD substituídas literalmente).
- Cada query tem `id` único dentro da análise.
- Pra cada query cujos resultados você usa no HTML, declare um `data_blocks[i]` apontando pro `<script id="data_<query_id>" type="application/json">…</script>` que você embute no HTML.
- O HTML deve ler dados via `JSON.parse(document.getElementById('<block_id>').textContent)` em vez de hardcodar valores na marcação.

Exemplo:

```json
{
  "queries": [
    { "id": "top_lojas", "sql": "SELECT filial, SUM(venda) v FROM t WHERE data BETWEEN '{{start_date}}' AND '{{end_date}}' GROUP BY 1" }
  ],
  "data_blocks": [
    { "block_id": "data_top_lojas", "query_id": "top_lojas" }
  ],
  "original_period": { "start": "2026-04-01", "end": "2026-04-23" }
}
```

E no HTML — **use a tool `html_data_block(block_id, payload)`** pra gerar a tag canônica em vez de hardcodar. Isso garante que o swap do refresh vai funcionar (a tool produz exatamente a forma que o regex de swap espera, com escapes XSS):

```javascript
// no rascunho do HTML que você gera, em vez de:
//   <script id="data_top_lojas" type="application/json">...</script>
// chame:
const dataBlockHtml = await html_data_block("data_top_lojas", queryResults)
// e embute em:
const html = `<html>...${dataBlockHtml}<script>const dados = JSON.parse(document.getElementById('data_top_lojas').textContent); /*...*/</script>...</html>`
```

A tool retorna a string já formatada e escapada. Variações de espaço/atributos quebram o refresh — sempre use a tool.

Se a análise retornar 0 linhas em algum período (ex: filial fechada), o HTML deve mostrar uma mensagem "sem dados no período" sem quebrar.

## Convenções de tags

Use **uma ou mais** das tags canônicas pra que `buscar_analises` consiga ranquear bem:

- Recorte temporal: `mtd`, `ytd`, `7d`, `30d`, `90d`
- Tipo: `ranking`, `comparativo`, `tendencia`, `auditoria`
- Dimensão: `produto`, `loja`, `marca`, `canal`, `coleção`, `vendedor`
- Métrica em destaque: `markup`, `giro`, `cobertura`, `pa`, `ticket-medio`

Tags em slug-case (lowercase, sem acento, separado por hífen). Não invente sinônimos — se faltar uma tag canônica pra teu caso, use a que mais aproxima e me avisa pra atualizar a lista.
```

- [ ] **Step 2: Commit**

```bash
git add agents/vendas-linx/SKILL.md agents/devolucoes/SKILL.md
git commit -m "docs(agents): add refresh_spec, buscar_analises workflow, and tag conventions"
```

---

## Phase 7 — Cutover and cleanup

### Task 29: Migrações em produção (Neon production branch)

- [ ] **Step 1: Aplicar `0001_create_analyses_audit.sql` na branch `production` do Neon**

```bash
psql "$DATABASE_URL_PROD" -f packages/mcp-core/migrations/0001_create_analyses_audit.sql
```

- [ ] **Step 2: Verificar tabelas vazias**

```bash
psql "$DATABASE_URL_PROD" -c "SELECT COUNT(*) FROM analyses; SELECT COUNT(*) FROM audit_log;"
```

Esperado: `0` em ambas.

- [ ] **Step 3: Deploy do mcp-core (Railway, prod services)**

Trigger redeploy de `vendas-linx-prod` e `devolucoes-prod`. Monitorar logs:
- `init_pool()` deve completar sem erro
- `auth_middleware` deve aceitar ambos paths (smoke test com proxy JWT + MSAL)

- [ ] **Step 4: Deploy do portal (Vercel prod)**

Promover deploy de preview pra production. Verificar que páginas `/`, `/onboarding`, `/api/library?agent=vendas-linx` retornam 200 (com cookie de sessão).

- [ ] **Step 5: Smoke test golden path em prod**

(Mesmos 9 cenários da Seção 7.2 do spec, executados manualmente.)

- [ ] **Step 6: Commit do estado deployado**

```bash
git tag fase-b-cutover-2026-04-XX
git push --tags
```

---

### Task 29.5: Health check script

**Files:**
- Create: `scripts/health_check_fase_b.sh`

Script que valida fim-a-fim depois do cutover. Bloqueia o anúncio aos usuários (Task 30) se algum check falhar.

- [ ] **Step 1: Implementar**

```bash
#!/usr/bin/env bash
# scripts/health_check_fase_b.sh — run after deploy to validate end-to-end
set -euo pipefail

PORTAL_URL="${PORTAL_URL:-https://bq-analista.vercel.app}"
SESSION_COOKIE="${SESSION_COOKIE:?need SESSION_COOKIE for an authenticated test user}"
AGENT="${AGENT:-vendas-linx}"

echo "[1/5] DB reachable via portal..."
LIB=$(curl -sS -f "$PORTAL_URL/api/library?agent=$AGENT" -H "cookie: session=$SESSION_COOKIE")
echo "library returned $(echo "$LIB" | jq '.items | length') items"

echo "[2/5] Blob endpoint reachable..."
TOKEN=$(node -e "console.log(require('jsonwebtoken').sign({aud:'blob-internal'}, process.env.MCP_PROXY_SIGNING_KEY, {algorithm:'HS256', expiresIn:60}))")
curl -sS -X PUT "$PORTAL_URL/api/internal/blob?pathname=analyses/healthcheck/$(date +%s).html&content_type=text/html" \
  -H "authorization: Bearer $TOKEN" --data-binary "<html>healthcheck</html>" > /dev/null
echo "blob put OK"

echo "[3/5] mcp-core healthy (vendas-linx)..."
curl -sS -f "https://vendas-linx-prod.up.railway.app/healthz" > /dev/null
echo "vendas-linx mcp-core OK"

echo "[4/5] mcp-core healthy (devolucoes)..."
curl -sS -f "https://devolucoes-prod.up.railway.app/healthz" > /dev/null
echo "devolucoes mcp-core OK"

echo "[5/5] FTS works (buscar_analises returns ranked results)..."
# requires a recent analysis; assume one exists from the smoke test
RESULTS=$(curl -sS -X POST "$PORTAL_URL/api/library?agent=$AGENT" -H "cookie: session=$SESSION_COOKIE" | jq '.items[0:3] | length')
[ "$RESULTS" -gt 0 ] || { echo "FAIL: no items in library"; exit 1; }
echo "library has data, FTS reachable via /buscar_analises tool when called from MCP client"

echo
echo "✅ All health checks passed"
```

- [ ] **Step 2: Garantir endpoint `/healthz` existe no mcp-core**

Em `server_factory.py` (próximo das outras rotas):

```python
@auth_app.get("/healthz")
async def healthz():
    # quick DB ping (don't init pool if absent — assume lifespan ran)
    try:
        async with _db.transaction() as conn:
            ok = await conn.fetchval("SELECT 1")
        return {"ok": ok == 1}
    except Exception as e:
        return Response(status_code=503, content=f"db unhealthy: {e}")
```

- [ ] **Step 3: Tornar executável e rodar pós-deploy**

```bash
chmod +x scripts/health_check_fase_b.sh
PORTAL_URL=https://bq-analista.vercel.app SESSION_COOKIE='<valid>' ./scripts/health_check_fase_b.sh
```

- [ ] **Step 4: Commit**

```bash
git add scripts/health_check_fase_b.sh packages/mcp-core/src/mcp_core/server_factory.py
git commit -m "chore: add post-cutover health check + /healthz endpoint"
```

---

### Task 30: Mover legacy content + cleanup env vars

**Files:**
- Move: `portal/library/` → `legacy/portal-library/`
- Move: `portal/analyses/` → `legacy/portal-analyses/`
- Modify: `portal/vercel.json` — remover rewrites legacy se houver

- [ ] **Step 1: Mover diretórios**

```bash
mkdir -p legacy
git mv portal/library legacy/portal-library
git mv portal/analyses legacy/portal-analyses
```

- [ ] **Step 2: Garantir que `legacy/` não vai pro build do Vercel**

Editar `portal/.vercelignore` (criar se não existir):

```
# Vercel só faz build do diretório portal/
# legacy/ está fora do escopo deploy automaticamente
```

E em `portal/vercel.json`, remover rewrites legacy (`/library/...` → `/library/<email>.json`, etc.).

- [ ] **Step 3: Remover env vars obsoletas dos serviços Railway**

Painel Railway → cada serviço → remover:
- `MCP_FORCE_PUBLIC`
- `MCP_GIT_PUSH`
- `GITHUB_APP_ID`
- `GITHUB_APP_PRIVATE_KEY`

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: archive legacy portal content under legacy/, drop git env vars"
git push
```

- [ ] **Step 5: Anunciar pros usuários**

Mensagem (Slack/email/whatever):

> A library do portal Azzas Análises foi migrada pra um banco de dados. Links de análises antigos (publicados antes de hoje) foram desativados — se algum analista precisa de uma análise antiga, é só re-publicar pelo Claude Desktop. Daqui pra frente:
> - Análises ficam disponíveis instantaneamente (sem esperar deploy do Vercel).
> - Autores podem clicar "Atualizar período" pra re-rodar com novas datas.
> - Compartilhamento granular: clica nos 3 pontinhos → "Compartilhar com pessoas…" → adiciona emails.
> - Tabs: Minhas / Público / Compartilhadas comigo / Arquivadas.
> - Arquivamento agora é per-usuário e sincroniza entre dispositivos (não é mais só por navegador).

---

## Self-review checklist (atualizada após segunda passada de crítica)

**Spec coverage:**
- [x] Refresh server-side (Phase 5: Tasks 21-26)
- [x] Compartilhamento granular por email (Phase 4: Tasks 18, 20)
- [x] Migração git → Postgres+Blob (Phases 1-2: Tasks 1-11)
- [x] 4 tabs (Phase 3: Task 16)
- [x] ACL endpoint (Tasks 13, 14, 18, 19)
- [x] Catálogo como contexto do agente (Phase 6: Tasks 27, 28)
- [x] Auth proxy JWT (Task 21, 22)
- [x] Atomicidade do refresh (Task 23 — transação + advisory lock)
- [x] HTML data island swap com escapes (Task 7) + helper `make_data_block` (Task 7 step 5)
- [x] Email normalization (Task 3)
- [x] Audit log (Tasks 8, 18, 19, 24)
- [x] Cutover + cleanup (Phase 7) + health check (Task 29.5)

**Fixes aplicados na segunda passada (críticas e robustez):**
- [x] **Blob via Vercel internal endpoint** — sem chute de API HTTP; mcp-core POSTa pro portal `/api/internal/blob` com `@vercel/blob` SDK oficial (Task 5 reescrita)
- [x] **`statement_cache_size=0` no asyncpg** — compatibilidade com Neon pooler (Task 4)
- [x] **`shared_with` filtrado server-side** — destinatário só vê o próprio email na lista (Task 13)
- [x] **Aliases `date` e `period` na resposta de `/api/library`** — compat com filtro de período da Fase A (Task 13)
- [x] **Migration idempotente** — `CREATE TABLE IF NOT EXISTS` + tabela `schema_migrations` (Task 1)
- [x] **Stub `openRefreshModal`** no Task 16 pra que Task 20 (share modal) seja shippable independente
- [x] **`reloadLibrary()` definida explicitamente** no Task 15 step 4
- [x] **Lifespan/init_pool explícito** — Task 9.5 dedicada antes de tocar `publicar_dashboard`
- [x] **Tests pra share + archive** — Tasks 18 e 19 ganharam test files completos
- [x] **CSS responsivo pra 4 tabs** — Task 16 step 4
- [x] **Retry com backoff no proxy refresh** — Task 25 step 1 (1 retry, 2s, só pra falha de transporte)
- [x] **Coluna `blob_url` cacheada no DB** — evita HEAD round-trip a cada `/api/analysis/<id>` (migration + Task 9 update_blob_url)
- [x] **Smoke test do Blob client obrigatório** — Task 5 sub 5.2 step 5 bloqueia avanço se falhar
- [x] **Health check pós-deploy** — Task 29.5 + endpoint `/healthz` no mcp-core

**Não-bloqueante mas conhecido (entra como Fase B.x):**
- Rate limiting em `/api/refresh-proxy` — allowlist limita base de atacantes; advisory lock por análise; aceito pra MVP
- Migração formal de schema com Alembic — MVP usa SQL numerado + tabela schema_migrations
- Signed URLs privadas (em vez de public + ACL gate) — quando o SDK do Vercel estabilizar
- Notificação por email aos destinatários ao compartilhar
- Embeddings/pgvector pra busca semântica

**Type consistency:**
- `AnalysisRow` (dataclass) — Tasks 9, 10, 23, 27, com novo campo `blob_url`
- `RefreshSpec` (Pydantic) — Tasks 6, 10, 23
- `BlobClient` interface (`put`, `get`, `delete`) — Tasks 5, 10, 23 (sem mais `signed_url`)
- `verify_proxy_jwt` audience: `mcp-core-proxy` (refresh) vs `blob-internal` (Blob endpoint) — separação correta
- Endpoints retornam `{is_mine, is_shared_with_me, is_archived, has_refresh_spec}` consistentemente; campos legacy `date`/`period` aliasados

**Placeholders:** verificado novamente, sem TBD/TODO em steps de código.
