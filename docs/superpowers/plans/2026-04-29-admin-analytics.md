# Admin Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tela de admin no portal que exibe analytics de uso do sistema com base nos logs de auditoria existentes (PostgreSQL `audit_log` + endpoint de stats BQ no servidor MCP Railway).

**Architecture:** Novo helper `adminAuth.js` para verificação de admins por env var; rota `/admin` protegida por middleware.js (server-side) + rewrite em `vercel.json`; endpoint `/api/admin/analytics` (Neon PostgreSQL) e `/api/admin/bq-stats-proxy` (proxy para Railway) no portal; novo endpoint `GET /api/admin/bq-stats` no servidor MCP (FastAPI + SQLite); página `admin.html` estática com renderização XSS-safe. Permissionamento via `ADMIN_EMAILS` env var — sem mudança de schema.

**Tech Stack:** Vanilla Node.js Vercel Functions, `node:test` (test runner nativo), `@neondatabase/serverless` (Neon), FastAPI + SQLite (Railway), HTML/CSS/JS vanilla.

---

## File Map

| Ação | Arquivo | Responsabilidade |
|------|---------|-----------------|
| Criar | `portal/api/_helpers/adminAuth.js` | `isAdmin(email, adminEmailsEnv)` — lógica de autorização |
| Criar | `portal/api/_helpers/__tests__/adminAuth.test.js` | Testes unitários do helper |
| Modificar | `portal/vercel.json` | Rewrite `/admin` → `admin.html`; maxDuration do novo endpoint |
| Modificar | `portal/middleware.js` | Proteger `/admin` server-side (matcher + guard) |
| Criar | `portal/api/admin/analytics.js` | Agrega `audit_log` do PostgreSQL |
| Criar | `portal/api/admin/bq-stats-proxy.js` | Proxy portal → Railway para stats do SQLite |
| Modificar | `packages/mcp-core/src/mcp_core/api_routes.py` | Adicionar `GET /api/admin/bq-stats` + `audit_db_path` param |
| Modificar | `packages/mcp-core/src/mcp_core/server_factory.py` | Passar `audit_db_path` para `register_api_routes` |
| Modificar | `packages/mcp-core/src/mcp_core/refresh_handler.py` | Adicionar `duration_ms` ao metadata do evento `refresh` |
| Criar | `packages/mcp-core/tests/test_bq_stats_endpoint.py` | Testes do endpoint `/api/admin/bq-stats` |
| Criar | `portal/admin.html` | Página de analytics com renderização XSS-safe |

---

## Task 1: Helper `adminAuth.js` + testes

Helper puro que verifica se um email pertence à lista de admins. Testado isoladamente antes de qualquer endpoint depender dele.

**Files:**
- Create: `portal/api/_helpers/adminAuth.js`
- Create: `portal/api/_helpers/__tests__/adminAuth.test.js`

- [ ] **Step 1: Criar o helper**

Crie `portal/api/_helpers/adminAuth.js`:

```js
/**
 * Returns true if email is in the ADMIN_EMAILS env var list.
 * adminEmailsEnv: comma-separated string, e.g. "a@soma.com,b@soma.com"
 * Comparison is case-insensitive; extra whitespace around emails is trimmed.
 */
function isAdmin(email, adminEmailsEnv) {
  if (!email || !adminEmailsEnv) return false
  const list = adminEmailsEnv.split(',').map(e => e.trim().toLowerCase()).filter(Boolean)
  return list.includes(email.toLowerCase().trim())
}

module.exports = { isAdmin }
```

- [ ] **Step 2: Criar os testes unitários**

Crie `portal/api/_helpers/__tests__/adminAuth.test.js`:

```js
const { test } = require('node:test')
const assert = require('node:assert/strict')
const { isAdmin } = require('../adminAuth')

test('retorna true para email exato na lista', () => {
  assert.equal(isAdmin('artur@soma.com', 'artur@soma.com,outro@soma.com'), true)
})

test('retorna true case-insensitive', () => {
  assert.equal(isAdmin('ARTUR@SOMA.COM', 'artur@soma.com'), true)
})

test('retorna true com espaços ao redor do email na lista', () => {
  assert.equal(isAdmin('artur@soma.com', '  artur@soma.com  ,outro@soma.com'), true)
})

test('retorna false para email fora da lista', () => {
  assert.equal(isAdmin('nao@empresa.com', 'artur@soma.com'), false)
})

test('retorna false se adminEmailsEnv é string vazia', () => {
  assert.equal(isAdmin('artur@soma.com', ''), false)
})

test('retorna false se adminEmailsEnv é undefined', () => {
  assert.equal(isAdmin('artur@soma.com', undefined), false)
})

test('retorna false se email é string vazia', () => {
  assert.equal(isAdmin('', 'artur@soma.com'), false)
})

test('ignora entradas vazias após split (vírgulas consecutivas)', () => {
  assert.equal(isAdmin('artur@soma.com', ',,artur@soma.com,,'), true)
})
```

- [ ] **Step 3: Rodar os testes**

```bash
cd portal && node --test api/_helpers/__tests__/adminAuth.test.js
```

Esperado: `✔ retorna true para email exato na lista` × 8 testes, todos passando.

- [ ] **Step 4: Commit**

```bash
git add portal/api/_helpers/adminAuth.js portal/api/_helpers/__tests__/adminAuth.test.js
git commit -m "feat(admin): helper isAdmin + testes unitários"
```

---

## Task 2: Roteamento e proteção da rota `/admin`

Dois problemas a resolver juntos: (a) Vercel não roteia `/admin` para `admin.html` sem rewrite explícito; (b) `middleware.js` não protege a rota — qualquer pessoa pode baixar o HTML sem cookie válido.

**Files:**
- Modify: `portal/vercel.json`
- Modify: `portal/middleware.js`

- [ ] **Step 1: Adicionar rewrite e maxDuration em `vercel.json`**

No arquivo `portal/vercel.json`, faça duas alterações:

1. Adicione o rewrite `/admin` → `/admin.html` no array `rewrites`:

```json
{ "source": "/admin", "destination": "/admin.html" }
```

2. Adicione `maxDuration` para os novos endpoints admin no objeto `functions`:

```json
"api/admin/analytics.js": { "maxDuration": 15 },
"api/admin/bq-stats-proxy.js": { "maxDuration": 15 }
```

O arquivo após as alterações deve ficar:

```json
{
  "version": 2,
  "outputDirectory": ".",
  "functions": {
    "api/auth.js": { "maxDuration": 10 },
    "api/share.js": { "maxDuration": 30 },
    "api/mcp/auth/[action].js": { "maxDuration": 15 },
    "api/admin/analytics.js": { "maxDuration": 15 },
    "api/admin/bq-stats-proxy.js": { "maxDuration": 15 }
  },
  "rewrites": [
    { "source": "/onboarding", "destination": "/onboarding.html" },
    { "source": "/admin", "destination": "/admin.html" },
    { "source": "/api/download-dxt", "destination": "/api/download?type=dxt" },
    { "source": "/api/download-skill", "destination": "/api/download?type=skill" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "SAMEORIGIN" },
        { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
        {
          "key": "Content-Security-Policy",
          "value": "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.plot.ly; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self' https://login.microsoftonline.com; form-action 'none'; frame-ancestors 'self'"
        }
      ]
    },
    {
      "source": "/api/analysis/(.*)",
      "headers": [
        { "key": "Cache-Control", "value": "private, no-store" },
        {
          "key": "Content-Security-Policy",
          "value": "sandbox allow-scripts allow-popups allow-modals allow-forms"
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Adicionar `/admin` ao middleware**

No arquivo `portal/middleware.js`, faça duas alterações:

1. Substitua o guard de pathname (linha 46):

```js
// antes:
if (pathname !== '/onboarding' && pathname !== '/onboarding/') return

// depois:
const PROTECTED = ['/onboarding', '/onboarding/', '/admin', '/admin/']
if (!PROTECTED.includes(pathname)) return
```

2. Substitua o `export const config` na última linha (linha 62):

```js
// antes:
export const config = { matcher: ['/onboarding'] }

// depois:
export const config = { matcher: ['/onboarding', '/admin'] }
```

- [ ] **Step 3: Commit**

```bash
git add portal/vercel.json portal/middleware.js
git commit -m "feat(admin): rewrite /admin + proteção server-side via middleware"
```

---

## Task 3: Endpoint `/api/admin/analytics` — agregados do `audit_log`

Retorna métricas dos últimos 30 dias do PostgreSQL `audit_log`. Inclui join com `analyses` para nomes das análises mais acessadas.

**Files:**
- Create: `portal/api/admin/analytics.js`

- [ ] **Step 1: Criar o endpoint**

Crie `portal/api/admin/analytics.js`:

```js
const { getSql } = require('../_helpers/db')
const { verifySession } = require('../_helpers/session')
const { parseCookie } = require('../_helpers/cookie')
const { isAdmin } = require('../_helpers/adminAuth')

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })
  if (!isAdmin(email, process.env.ADMIN_EMAILS)) return res.status(403).json({ error: 'forbidden' })

  const sql = getSql()

  // Run all queries in parallel; individual failures return null so the page
  // still renders partial data rather than a full 500.
  const [summary, byActionByDay, topUsers, topAnalyses, recentActivity] = await Promise.all([
    sql`
      SELECT
        COUNT(*) FILTER (WHERE action = 'publish')      AS total_publishes,
        COUNT(*) FILTER (WHERE action = 'refresh')      AS total_refreshes,
        COUNT(*) FILTER (WHERE action = 'share')        AS total_shares,
        COUNT(*) FILTER (WHERE action = 'archive')      AS total_archives,
        COUNT(*) FILTER (WHERE action = 'login_failed') AS total_login_failures,
        COUNT(DISTINCT actor_email)                      AS distinct_users,
        COUNT(*)                                         AS total_events
      FROM audit_log
      WHERE occurred_at >= NOW() - INTERVAL '30 days'
    `.catch(() => null),

    // Volume por ação por dia — últimos 14 dias para gráfico de tendência
    sql`
      SELECT
        DATE_TRUNC('day', occurred_at)::date AS day,
        action,
        COUNT(*) AS n
      FROM audit_log
      WHERE occurred_at >= NOW() - INTERVAL '14 days'
        AND action IN ('publish', 'refresh', 'share', 'archive')
      GROUP BY 1, 2
      ORDER BY 1 ASC, 2
    `.catch(() => null),

    // Usuários mais ativos (excluindo login_failed para não inflar quem tem problema de auth)
    sql`
      SELECT actor_email, COUNT(*) AS n
      FROM audit_log
      WHERE occurred_at >= NOW() - INTERVAL '30 days'
        AND action != 'login_failed'
      GROUP BY actor_email
      ORDER BY n DESC
      LIMIT 10
    `.catch(() => null),

    // Análises mais acessadas com título (join com analyses)
    sql`
      SELECT al.analysis_id, COUNT(*) AS n, a.title
      FROM audit_log al
      LEFT JOIN analyses a ON a.id = al.analysis_id
      WHERE al.occurred_at >= NOW() - INTERVAL '30 days'
        AND al.action IN ('refresh', 'share')
        AND al.analysis_id IS NOT NULL
      GROUP BY al.analysis_id, a.title
      ORDER BY n DESC
      LIMIT 10
    `.catch(() => null),

    // Feed de atividade recente — 50 eventos, sem metadata para não vazar dados de erro
    sql`
      SELECT occurred_at, actor_email, action, analysis_id
      FROM audit_log
      ORDER BY occurred_at DESC
      LIMIT 50
    `.catch(() => null),
  ])

  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json({
    summary: summary?.[0] ?? null,
    by_action_by_day: byActionByDay ?? [],
    top_users: topUsers ?? [],
    top_analyses: topAnalyses ?? [],
    recent_activity: recentActivity ?? [],
  })
}
```

- [ ] **Step 2: Testar manualmente o endpoint**

Com a sessão de admin ativa no browser, acesse:

```
GET /api/admin/analytics
```

Esperado: JSON com `summary`, `by_action_by_day`, `top_users`, `top_analyses`, `recent_activity`.

Com sessão de não-admin: status 403. Sem cookie: status 401.

- [ ] **Step 3: Commit**

```bash
git add portal/api/admin/analytics.js
git commit -m "feat(admin): endpoint /api/admin/analytics com agregados do audit_log"
```

---

## Task 4: Endpoint `GET /api/admin/bq-stats` no servidor MCP

Expõe stats do SQLite de queries BigQuery. Autenticado pelo mesmo Bearer JWT proxy já usado em `/api/refresh`.

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/api_routes.py`
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py`
- Create: `packages/mcp-core/tests/test_bq_stats_endpoint.py`

- [ ] **Step 1: Escrever os testes**

Crie `packages/mcp-core/tests/test_bq_stats_endpoint.py`:

```python
import sqlite3
import tempfile
import time
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_core.api_routes import register_api_routes
from mcp_core.auth_middleware import AuthContext


def _make_client(audit_db_path: str) -> TestClient:
    app = FastAPI()
    auth_ctx = MagicMock(spec=AuthContext)
    # extract_exec_email is called as a standalone function imported into api_routes.
    # We patch it at the import site, not as a method on auth_ctx.
    with patch(
        "mcp_core.api_routes.extract_exec_email",
        new_callable=AsyncMock,
        return_value="user@soma.com",
    ):
        register_api_routes(
            app,
            auth_ctx=auth_ctx,
            bq_factory=MagicMock(),
            blob_factory=MagicMock(),
            audit_db_path=audit_db_path,
        )
        return TestClient(app)


def _seed_db(path: str) -> None:
    now = time.time()
    with sqlite3.connect(path) as c:
        c.execute("""
            CREATE TABLE audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                exec_email TEXT NOT NULL,
                tool TEXT NOT NULL,
                sql TEXT,
                bytes_scanned INTEGER DEFAULT 0,
                row_count INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                result TEXT NOT NULL,
                error TEXT
            )
        """)
        c.executemany(
            "INSERT INTO audit (ts, exec_email, tool, sql, bytes_scanned, row_count, duration_ms, result, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (now - 3600, "a@soma.com", "consultar_bq", "SELECT 1", 1024, 1, 200, "success", None),
                (now - 1800, "a@soma.com", "consultar_bq", "SELECT 2", 2048, 5, 300, "success", None),
                (now - 900,  "b@soma.com", "consultar_bq", "SELECT 3", 512,  2, 150, "error",   "syntax error"),
                # Fora do janela de 30 dias — não deve aparecer nos totais
                (now - 31 * 86400, "a@soma.com", "consultar_bq", "SELECT 4", 9999, 0, 100, "success", None),
            ],
        )


def test_bq_stats_returns_aggregates():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _seed_db(db_path)
        client = _make_client(db_path)
        with patch("mcp_core.api_routes.extract_exec_email", new_callable=AsyncMock, return_value="user@soma.com"):
            resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert "by_user" in data
        assert "totals" in data
        assert "recent_errors" in data
        assert data["totals"]["total_calls"] == 3          # 4th row is outside 30d window
        assert data["totals"]["total_errors"] == 1
        assert data["totals"]["distinct_users"] == 2
    finally:
        os.unlink(db_path)


def test_bq_stats_by_user_sorted_desc():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _seed_db(db_path)
        client = _make_client(db_path)
        with patch("mcp_core.api_routes.extract_exec_email", new_callable=AsyncMock, return_value="user@soma.com"):
            resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
        users = resp.json()["by_user"]
        assert users[0]["exec_email"] == "a@soma.com"   # 2 calls, mais ativo
        assert users[0]["total_calls"] == 2
        assert users[1]["exec_email"] == "b@soma.com"
        assert users[1]["errors"] == 1
    finally:
        os.unlink(db_path)


def test_bq_stats_recent_errors_populated():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _seed_db(db_path)
        client = _make_client(db_path)
        with patch("mcp_core.api_routes.extract_exec_email", new_callable=AsyncMock, return_value="user@soma.com"):
            resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
        errors = resp.json()["recent_errors"]
        assert len(errors) == 1
        assert errors[0]["exec_email"] == "b@soma.com"
        assert "syntax error" in errors[0]["error"]
    finally:
        os.unlink(db_path)


def test_bq_stats_empty_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        # DB vazio — sem tabela, sem dados
        client = _make_client(db_path)
        with patch("mcp_core.api_routes.extract_exec_email", new_callable=AsyncMock, return_value="user@soma.com"):
            resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
        # Sem audit_db_path ou tabela inexistente → retorna zeros/listas vazias, não 500
        assert resp.status_code == 200
        data = resp.json()
        assert data["by_user"] == []
        assert data["recent_errors"] == []
    finally:
        os.unlink(db_path)


def test_bq_stats_missing_audit_db_path():
    """Quando audit_db_path=None, endpoint responde 200 com dados vazios."""
    app = FastAPI()
    auth_ctx = MagicMock(spec=AuthContext)
    with patch("mcp_core.api_routes.extract_exec_email", new_callable=AsyncMock, return_value="user@soma.com"):
        register_api_routes(
            app,
            auth_ctx=auth_ctx,
            bq_factory=MagicMock(),
            blob_factory=MagicMock(),
            audit_db_path=None,
        )
        client = TestClient(app)
        resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["by_user"] == []
    assert data["totals"] == {}
    assert data["recent_errors"] == []
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
cd packages/mcp-core && python -m pytest tests/test_bq_stats_endpoint.py -v
```

Esperado: `FAILED` com `TypeError: register_api_routes() got an unexpected keyword argument 'audit_db_path'`.

- [ ] **Step 3: Implementar o endpoint em `api_routes.py`**

Abra `packages/mcp-core/src/mcp_core/api_routes.py`. Faça as seguintes alterações:

**3a. Adicione imports no topo do arquivo (após os imports existentes):**

```python
import sqlite3
import time
```

**3b. Altere a assinatura de `register_api_routes` (linha 28) para aceitar `audit_db_path`:**

```python
def register_api_routes(
    app: FastAPI,
    *,
    auth_ctx: AuthContext,
    bq_factory,
    blob_factory,
    audit_db_path: str | None = None,
) -> None:
```

**3c. Adicione o endpoint ao final do corpo de `register_api_routes`, antes do fechamento da função:**

```python
    @app.get("/api/admin/bq-stats")
    async def bq_stats(authorization: str | None = Header(None)):
        token = _bearer_token(authorization)
        try:
            await extract_exec_email(token, auth_ctx)
        except AuthError as e:
            raise HTTPException(401, str(e))

        if not audit_db_path:
            return {"by_user": [], "totals": {}, "recent_errors": []}

        since = time.time() - 30 * 86400

        try:
            with sqlite3.connect(audit_db_path) as conn:
                conn.row_factory = sqlite3.Row

                by_user = [
                    dict(r) for r in conn.execute(
                        """
                        SELECT exec_email,
                               COUNT(*) AS total_calls,
                               SUM(CASE WHEN result='error' THEN 1 ELSE 0 END) AS errors,
                               SUM(bytes_scanned) AS total_bytes,
                               ROUND(AVG(duration_ms)) AS avg_duration_ms
                        FROM audit
                        WHERE ts >= ?
                        GROUP BY exec_email
                        ORDER BY total_calls DESC
                        """,
                        (since,),
                    )
                ]

                totals_row = conn.execute(
                    """
                    SELECT COUNT(*) AS total_calls,
                           SUM(CASE WHEN result='error' THEN 1 ELSE 0 END) AS total_errors,
                           SUM(bytes_scanned) AS total_bytes_scanned,
                           COUNT(DISTINCT exec_email) AS distinct_users
                    FROM audit WHERE ts >= ?
                    """,
                    (since,),
                ).fetchone()

                recent_errors = [
                    dict(r) for r in conn.execute(
                        """
                        SELECT ts, exec_email, tool, error, bytes_scanned
                        FROM audit
                        WHERE result = 'error' AND ts >= ?
                        ORDER BY ts DESC
                        LIMIT 20
                        """,
                        (since,),
                    )
                ]
        except sqlite3.OperationalError:
            # Tabela ainda não criada (DB vazio) — retorna zeros sem explodir
            return {"by_user": [], "totals": {}, "recent_errors": []}

        return {
            "by_user": by_user,
            "totals": dict(totals_row) if totals_row else {},
            "recent_errors": recent_errors,
        }
```

- [ ] **Step 4: Rodar testes para confirmar verde**

```bash
cd packages/mcp-core && python -m pytest tests/test_bq_stats_endpoint.py -v
```

Esperado: 5 testes passando.

- [ ] **Step 5: Confirmar que testes existentes continuam passando**

```bash
cd packages/mcp-core && python -m pytest tests/ -v
```

Esperado: todos em verde.

- [ ] **Step 6: Passar `audit_db_path` no `server_factory.py`**

Abra `packages/mcp-core/src/mcp_core/server_factory.py`, linhas 630–635. Altere a chamada de `register_api_routes`:

```python
# antes:
register_api_routes(
    auth_app,
    auth_ctx=api_auth_ctx,
    bq_factory=lambda: _load_cached_state().bq_client,
    blob_factory=lambda: BlobClient(),
)

# depois:
register_api_routes(
    auth_app,
    auth_ctx=api_auth_ctx,
    bq_factory=lambda: _load_cached_state().bq_client,
    blob_factory=lambda: BlobClient(),
    audit_db_path=settings.audit.db_path,
)
```

> **Nota:** `settings` já existe neste escopo — é o objeto retornado por `load_settings(...)` mais acima na mesma função. `settings.audit.db_path` é `str` (linha 38 de `settings.py`) e corresponde a `MCP_AUDIT_DB_PATH` (default `/var/mcp/audit.db`).

- [ ] **Step 7: Commit**

```bash
git add packages/mcp-core/src/mcp_core/api_routes.py \
        packages/mcp-core/src/mcp_core/server_factory.py \
        packages/mcp-core/tests/test_bq_stats_endpoint.py
git commit -m "feat(admin): endpoint GET /api/admin/bq-stats com stats do SQLite de queries BQ"
```

---

## Task 5: Proxy `/api/admin/bq-stats-proxy` no portal

O portal (Vercel) não tem acesso ao SQLite do Railway — precisa de um proxy que repassa a chamada com o JWT proxy já existente.

> **Atenção:** O email do admin precisa estar também na **allowlist do servidor MCP** (`MCP_ALLOWED_EMAILS` ou `config/allowed_execs.json`), caso contrário o Railway rejeitará o JWT proxy com 401.

**Files:**
- Create: `portal/api/admin/bq-stats-proxy.js`

- [ ] **Step 1: Criar o proxy**

Crie `portal/api/admin/bq-stats-proxy.js`:

```js
const { verifySession } = require('../_helpers/session')
const { parseCookie } = require('../_helpers/cookie')
const { isAdmin } = require('../_helpers/adminAuth')
const { mintProxyJwt } = require('../_helpers/proxy_jwt')

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })
  if (!isAdmin(email, process.env.ADMIN_EMAILS)) return res.status(403).json({ error: 'forbidden' })

  const mcpBase = process.env.MCP_BASE_URL
  if (!mcpBase) return res.status(503).json({ error: 'MCP_BASE_URL não configurado' })

  // mintProxyJwt lê MCP_PROXY_SIGNING_KEY do env automaticamente.
  // TTL de 60s é suficiente para uma chamada HTTP.
  let token
  try {
    token = mintProxyJwt(email)
  } catch (err) {
    return res.status(503).json({ error: `JWT proxy: ${err.message}` })
  }

  let upstream
  try {
    upstream = await fetch(`${mcpBase}/api/admin/bq-stats`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(10_000),
    })
  } catch (err) {
    return res.status(504).json({ error: `Railway indisponível: ${err.message}` })
  }

  if (!upstream.ok) {
    const text = await upstream.text().catch(() => upstream.statusText)
    return res.status(upstream.status).json({ error: text })
  }

  const data = await upstream.json()
  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json(data)
}
```

- [ ] **Step 2: Commit**

```bash
git add portal/api/admin/bq-stats-proxy.js
git commit -m "feat(admin): proxy /api/admin/bq-stats-proxy portal→Railway"
```

---

## Task 6: Enriquecer metadata do evento `refresh` com `duration_ms`

O `audit_log` já registra `period_start`, `period_end` e `queries_run` no evento `refresh`. Falta `duration_ms` para análise de performance. A alteração é mínima: um `time.monotonic()` antes da transação.

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/refresh_handler.py`

- [ ] **Step 1: Escrever o teste**

Abra `packages/mcp-core/tests/test_refresh_handler.py` e adicione ao final:

```python
@pytest.mark.asyncio
async def test_refresh_metadata_includes_duration_ms(db_pool):
    """audit_log deve conter duration_ms no metadata do evento refresh."""
    await _seed()
    bq = _bq_ok([{"x": 1}])
    blob = _blob_ok()

    await refresh_analysis(
        analysis_id="t1", actor_email="author@x.com",
        start=date(2026, 3, 1), end=date(2026, 3, 31),
        bq=bq, blob=blob,
    )

    async with db.transaction() as conn:
        row = await conn.fetchrow(
            "SELECT metadata FROM audit_log WHERE action='refresh' AND analysis_id='t1'"
        )
    assert row is not None
    meta = json.loads(row["metadata"])
    assert "duration_ms" in meta, "metadata deve conter duration_ms"
    assert isinstance(meta["duration_ms"], (int, float))
    assert meta["duration_ms"] >= 0
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
cd packages/mcp-core && python -m pytest tests/test_refresh_handler.py::test_refresh_metadata_includes_duration_ms -v
```

Esperado: `FAILED — AssertionError: metadata deve conter duration_ms`.

- [ ] **Step 3: Implementar em `refresh_handler.py`**

Abra `packages/mcp-core/src/mcp_core/refresh_handler.py`.

**3a. Adicione `import time` no topo (linha 19, após `from datetime import date`):**

```python
import time
```

**3b. Adicione `_t0 = time.monotonic()` na linha 79, imediatamente antes do `async with db.transaction()`:**

```python
    _t0 = time.monotonic()
    async with db.transaction() as conn:
```

**3c. No bloco `actions_audit.record` (linhas 129–137), adicione `duration_ms` ao dict `metadata`:**

```python
        await actions_audit.record(
            conn, action="refresh", actor_email=actor_email,
            analysis_id=analysis_id,
            metadata={
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "queries_run": len(spec.queries),
                "duration_ms": round((time.monotonic() - _t0) * 1000),
            },
        )
```

- [ ] **Step 4: Rodar testes**

```bash
cd packages/mcp-core && python -m pytest tests/test_refresh_handler.py -v
```

Esperado: todos os testes passando, incluindo o novo.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/refresh_handler.py \
        packages/mcp-core/tests/test_refresh_handler.py
git commit -m "feat(audit): adiciona duration_ms ao metadata do evento refresh"
```

---

## Task 7: Página `/admin` no portal — XSS-safe

A página renderiza dados do usuário via `innerHTML`. Todo output deve passar por `escHtml()` para prevenir XSS. O campo `by_action_by_day` (buscado na Task 3) é renderizado como tabela de tendência diária.

**Files:**
- Create: `portal/admin.html`

- [ ] **Step 1: Criar a página**

Crie `portal/admin.html`:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Admin · Azzas 2154</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f4f4f5; color: #18181b; min-height: 100vh; }
    header { background: #18181b; color: #fff; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
    header h1 { font-size: 1rem; font-weight: 600; letter-spacing: .02em; }
    .back { color: #a1a1aa; font-size: .875rem; text-decoration: none; }
    .back:hover { color: #fff; }
    main { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
    .section-title { font-size: .75rem; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #71717a; margin: 32px 0 12px; }
    .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 4px; }
    .card { background: #fff; border-radius: 8px; padding: 20px 16px; border: 1px solid #e4e4e7; }
    .card .label { font-size: .75rem; color: #71717a; margin-bottom: 8px; }
    .card .value { font-size: 2rem; font-weight: 700; line-height: 1; }
    .card .value.warn { color: #b91c1c; }
    table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; border: 1px solid #e4e4e7; }
    th, td { text-align: left; padding: 10px 14px; font-size: .875rem; }
    th { background: #fafafa; font-weight: 600; color: #52525b; font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; }
    tr:not(:last-child) td { border-bottom: 1px solid #f4f4f5; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: .75rem; font-weight: 500; }
    .badge.publish { background: #dcfce7; color: #15803d; }
    .badge.refresh { background: #dbeafe; color: #1d4ed8; }
    .badge.share { background: #fef9c3; color: #a16207; }
    .badge.archive { background: #f4f4f5; color: #52525b; }
    .badge.login_failed { background: #fee2e2; color: #b91c1c; }
    .err-text { color: #b91c1c; font-size: .8rem; }
    .msg { padding: 32px; text-align: center; color: #71717a; }
    .msg.error { color: #b91c1c; }
    code { font-family: ui-monospace, monospace; font-size: .8rem; background: #f4f4f5; padding: 1px 4px; border-radius: 3px; }
  </style>
</head>
<body>
<header>
  <a href="/" class="back">← Portal</a>
  <h1>Admin · Analytics de Uso</h1>
</header>
<main><div id="root"><p class="msg">Carregando…</p></div></main>
<script type="module">
  // XSS-safe: toda string de usuário passa por escHtml antes de ir ao innerHTML
  function escHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  function fmt(n) { return Number(n ?? 0).toLocaleString('pt-BR') }

  function fmtBytes(b) {
    b = Number(b ?? 0)
    if (b >= 1e12) return (b / 1e12).toFixed(1) + ' TB'
    if (b >= 1e9)  return (b / 1e9).toFixed(1) + ' GB'
    if (b >= 1e6)  return (b / 1e6).toFixed(1) + ' MB'
    return (b / 1e3).toFixed(1) + ' KB'
  }

  function fmtDate(ts) {
    const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) +
      ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  }

  function badge(action) {
    const safe = escHtml(action)
    const cls = ['publish','refresh','share','archive','login_failed'].includes(action) ? action : ''
    return `<span class="badge ${cls}">${safe}</span>`
  }

  async function fetchJson(url) {
    const res = await fetch(url, { credentials: 'include' })
    if (res.status === 401) { location.href = '/'; throw new Error('unauthorized') }
    if (res.status === 403) throw new Error('forbidden')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  }

  async function render() {
    const root = document.getElementById('root')

    const [analyticsResult, bqResult] = await Promise.allSettled([
      fetchJson('/api/admin/analytics'),
      fetchJson('/api/admin/bq-stats-proxy'),
    ])

    if (analyticsResult.status === 'rejected') {
      const msg = analyticsResult.reason.message
      if (msg === 'unauthorized') return
      if (msg === 'forbidden') {
        root.innerHTML = '<p class="msg error">⛔ Acesso restrito.</p>'
        return
      }
      root.innerHTML = `<p class="msg error">Erro ao carregar analytics: ${escHtml(msg)}</p>`
      return
    }

    const a = analyticsResult.value
    const bq = bqResult.status === 'fulfilled' ? bqResult.value : null
    let html = ''

    // ── Summary cards — portal ──────────────────────────────────────────────
    if (a.summary) {
      const s = a.summary
      html += `<p class="section-title">Últimos 30 dias — Portal</p><div class="cards">
        <div class="card"><div class="label">Publicações</div><div class="value">${fmt(s.total_publishes)}</div></div>
        <div class="card"><div class="label">Refreshes</div><div class="value">${fmt(s.total_refreshes)}</div></div>
        <div class="card"><div class="label">Compartilhamentos</div><div class="value">${fmt(s.total_shares)}</div></div>
        <div class="card"><div class="label">Arquivamentos</div><div class="value">${fmt(s.total_archives)}</div></div>
        <div class="card"><div class="label">Usuários únicos</div><div class="value">${fmt(s.distinct_users)}</div></div>
        <div class="card"><div class="label">Logins falhos</div>
          <div class="value${Number(s.total_login_failures) > 0 ? ' warn' : ''}">${fmt(s.total_login_failures)}</div>
        </div>
      </div>`
    }

    // ── Tendência diária (by_action_by_day) ─────────────────────────────────
    if (a.by_action_by_day?.length) {
      // Agrupar por dia para exibir linha por dia com contagens por ação
      const days = {}
      for (const row of a.by_action_by_day) {
        const day = row.day
        if (!days[day]) days[day] = { publish: 0, refresh: 0, share: 0, archive: 0 }
        days[day][row.action] = Number(row.n)
      }
      html += `<p class="section-title">Tendência — últimos 14 dias</p>
      <table><thead><tr>
        <th>Dia</th><th>Publicações</th><th>Refreshes</th><th>Compartilhamentos</th><th>Arquivamentos</th>
      </tr></thead><tbody>`
      for (const [day, counts] of Object.entries(days).sort().reverse()) {
        html += `<tr>
          <td>${escHtml(day)}</td>
          <td>${fmt(counts.publish)}</td>
          <td>${fmt(counts.refresh)}</td>
          <td>${fmt(counts.share)}</td>
          <td>${fmt(counts.archive)}</td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    // ── Summary cards — BigQuery ────────────────────────────────────────────
    if (bq?.totals && Object.keys(bq.totals).length) {
      const t = bq.totals
      html += `<p class="section-title">Últimos 30 dias — Queries BigQuery</p><div class="cards">
        <div class="card"><div class="label">Total de queries</div><div class="value">${fmt(t.total_calls)}</div></div>
        <div class="card"><div class="label">Erros</div>
          <div class="value${Number(t.total_errors) > 0 ? ' warn' : ''}">${fmt(t.total_errors)}</div>
        </div>
        <div class="card"><div class="label">Bytes escaneados</div>
          <div class="value" style="font-size:1.25rem">${fmtBytes(t.total_bytes_scanned)}</div>
        </div>
        <div class="card"><div class="label">Usuários ativos</div><div class="value">${fmt(t.distinct_users)}</div></div>
      </div>`
    } else if (bqResult.status === 'rejected') {
      html += `<p class="section-title">Queries BigQuery</p>
        <p class="msg" style="background:#fff;border-radius:8px;border:1px solid #e4e4e7">
          Stats do BigQuery indisponíveis: ${escHtml(bqResult.reason?.message ?? 'erro desconhecido')}
        </p>`
    }

    // ── Usuários mais ativos — portal ───────────────────────────────────────
    if (a.top_users?.length) {
      html += `<p class="section-title">Usuários mais ativos (portal, 30d)</p>
      <table><thead><tr><th>Email</th><th>Ações</th></tr></thead><tbody>`
      for (const u of a.top_users) {
        html += `<tr><td>${escHtml(u.actor_email)}</td><td>${fmt(u.n)}</td></tr>`
      }
      html += `</tbody></table>`
    }

    // ── Usuários com mais queries — BigQuery ────────────────────────────────
    if (bq?.by_user?.length) {
      html += `<p class="section-title">Usuários com mais queries (BigQuery, 30d)</p>
      <table><thead><tr><th>Email</th><th>Queries</th><th>Erros</th><th>Bytes</th><th>Avg ms</th></tr></thead><tbody>`
      for (const u of bq.by_user) {
        html += `<tr>
          <td>${escHtml(u.exec_email)}</td>
          <td>${fmt(u.total_calls)}</td>
          <td class="${u.errors > 0 ? 'err-text' : ''}">${fmt(u.errors)}</td>
          <td>${fmtBytes(u.total_bytes)}</td>
          <td>${fmt(u.avg_duration_ms)}</td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    // ── Análises mais acessadas ─────────────────────────────────────────────
    if (a.top_analyses?.length) {
      html += `<p class="section-title">Análises mais acessadas (refresh + share, 30d)</p>
      <table><thead><tr><th>Título</th><th>ID</th><th>Acessos</th></tr></thead><tbody>`
      for (const r of a.top_analyses) {
        html += `<tr>
          <td>${escHtml(r.title ?? '—')}</td>
          <td><code>${escHtml(r.analysis_id)}</code></td>
          <td>${fmt(r.n)}</td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    // ── Erros recentes de query BigQuery ────────────────────────────────────
    if (bq?.recent_errors?.length) {
      html += `<p class="section-title">Erros recentes de query (BigQuery)</p>
      <table><thead><tr><th>Quando</th><th>Usuário</th><th>Erro</th></tr></thead><tbody>`
      for (const e of bq.recent_errors) {
        html += `<tr>
          <td>${escHtml(fmtDate(e.ts))}</td>
          <td>${escHtml(e.exec_email)}</td>
          <td class="err-text">${escHtml(e.error ?? '—')}</td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    // ── Feed de atividade recente ───────────────────────────────────────────
    if (a.recent_activity?.length) {
      html += `<p class="section-title">Atividade recente</p>
      <table><thead><tr><th>Quando</th><th>Usuário</th><th>Ação</th><th>Analysis ID</th></tr></thead><tbody>`
      for (const ev of a.recent_activity) {
        html += `<tr>
          <td>${escHtml(fmtDate(ev.occurred_at))}</td>
          <td>${escHtml(ev.actor_email)}</td>
          <td>${badge(ev.action)}</td>
          <td><code>${escHtml(ev.analysis_id ?? '—')}</code></td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    root.innerHTML = html || '<p class="msg">Nenhum dado disponível.</p>'
  }

  render()
</script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add portal/admin.html
git commit -m "feat(admin): página /admin com analytics XSS-safe (portal + BigQuery)"
```

---

## Task 8: Configurar variáveis de ambiente e smoke test

**Files:** nenhum arquivo novo — configuração operacional.

- [ ] **Step 1: Adicionar `ADMIN_EMAILS` no Vercel**

```bash
cd portal && vercel env add ADMIN_EMAILS production
```

Quando solicitado, insira os emails separados por vírgula: `artur@somagrupo.com,outro@somagrupo.com`

- [ ] **Step 2: Confirmar que o email do admin está na allowlist do MCP**

O email do admin precisa existir em `config/allowed_execs.json` (ou em `MCP_ALLOWED_EMAILS` no Railway), caso contrário o proxy `/api/admin/bq-stats-proxy` receberá 401 do Railway.

```bash
cat config/allowed_execs.json | grep -i "seu-email"
```

Se não estiver, adicione seguindo o processo de allowlist já estabelecido (commit `chore(allowlist): ...`).

- [ ] **Step 3: Testar localmente com `.env.local`**

Edite (ou crie) `portal/.env.local` (já ignorado pelo git):

```
ADMIN_EMAILS=seu-email@empresa.com
SESSION_SECRET=<mesmo valor do Vercel>
DATABASE_URL=<string de conexão do Neon>
MCP_BASE_URL=https://seu-agente.railway.app
MCP_PROXY_SIGNING_KEY=<mesmo valor do Vercel>
```

```bash
cd portal && vercel dev
```

Acesse `http://localhost:3000/admin` e verifique:
- Sem cookie de sessão → redireciona para `/` (via middleware)
- Com cookie de não-admin → mostra "⛔ Acesso restrito"
- Com cookie de admin → carrega os cards de summary do portal
- Cards de BigQuery carregam (podem estar vazios se Railway não tiver dados ainda)

- [ ] **Step 4: Deploy para preview e validação**

```bash
cd portal && vercel
```

Abra a URL de preview e repita os cenários do Step 3.

- [ ] **Step 5: Rodar a suite de testes do portal**

```bash
cd portal && npm test
```

Esperado: testes existentes em `api/mcp/__tests__/` continuam passando.

- [ ] **Step 6: Rodar os testes do helper admin separadamente**

```bash
cd portal && node --test api/_helpers/__tests__/adminAuth.test.js
```

Esperado: 8 testes passando.

- [ ] **Step 7: Deploy para produção**

```bash
cd portal && vercel --prod
```

---

## Self-review

### Spec coverage

| Requisito | Task |
|-----------|------|
| Analytics do `audit_log` (PostgreSQL) | Task 3 |
| Stats de queries BQ (SQLite) | Task 4 |
| Proxy portal → Railway | Task 5 |
| Página admin no portal | Task 7 |
| Permissionamento por env var, sem schema novo | Task 1, Task 8 |
| Proteção server-side da rota `/admin` | Task 2 |
| Rewrite Vercel para `/admin` | Task 2 |
| Enriquecer metadata de refresh com `duration_ms` | Task 6 |
| Renderização XSS-safe | Task 7 (`escHtml`) |
| `by_action_by_day` renderizado (não desperdiçado) | Task 7 (tabela de tendência diária) |
| `top_analyses` com título (join `analyses`) | Task 3 + Task 7 |

### Bugs corrigidos em relação ao plano anterior

| Bug | Correção |
|-----|----------|
| `makeProxyJwt` (inexistente) | `mintProxyJwt` (correto, exportado por `proxy_jwt.js`) |
| `MCP_PROXY_JWT_SECRET` (env var errada) | `mintProxyJwt` lê `MCP_PROXY_SIGNING_KEY` automaticamente |
| Sintaxe Jest nos testes do portal | `node:test` + `node:assert/strict` (runner nativo do projeto) |
| `/admin` sem rewrite no `vercel.json` | Rewrite explícito adicionado (Task 2) |
| `middleware.js` não protegia `/admin` | PROTECTED array + matcher atualizado (Task 2) |
| XSS em `admin.html` via `innerHTML` | `escHtml()` em todo output de dado de usuário (Task 7) |
| `by_action_by_day` buscado mas não renderizado | Tabela de tendência diária adicionada (Task 7) |
| `top_analyses` sem título | `LEFT JOIN analyses` no SQL (Task 3) |
| Task 4 vaga ("encontre e adapte") | Linhas exatas do `refresh_handler.py` documentadas (Task 6) |
| Mock incorreto em test (`auth_ctx.extract_email`) | `patch('mcp_core.api_routes.extract_exec_email', ...)` (Task 4) |

### Placeholder scan

Nenhum "TBD", "TODO", "adapte conforme contexto" ou "similar ao anterior" no plano.

### Type consistency

- `isAdmin(email, adminEmailsEnv)` — definido Task 1, usado em Task 3 e Task 5. Consistente.
- `mintProxyJwt(email)` — importado de `proxy_jwt.js` como `{ mintProxyJwt }`. Consistente.
- `register_api_routes(..., audit_db_path)` — assinatura alterada Task 4, chamador atualizado Task 4 Step 6. Consistente.
- `escHtml(str)` — definida e usada dentro do mesmo `<script>` em `admin.html`. Consistente.
