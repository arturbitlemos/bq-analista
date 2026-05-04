# BQ Audit — Migração para Postgres + Revisão da Página Admin

**Data:** 2026-05-04  
**Status:** Aprovado

## Problema

Os logs de uso dos agentes MCP (queries BigQuery) são gravados em SQLite local em `/var/mcp/audit.db` dentro dos containers Railway. A cada redeploy (disparado por todo push para `main`), o container é recriado do zero e o arquivo SQLite é apagado. Por isso a página admin exibe dados de apenas 2 pessoas — são as sessões desde o último deploy.

## Solução

Mover o audit de BQ para o Neon Postgres que os agents já acessam via `DATABASE_URL`. Isso elimina o fan-out da página admin e torna os logs duráveis.

---

## 1. Camada de Dados

### Nova tabela `bq_audit` (Postgres)

**Arquivo:** `packages/mcp-core/migrations/0002_create_bq_audit.sql`

```sql
CREATE TABLE IF NOT EXISTS bq_audit (
  id            BIGSERIAL PRIMARY KEY,
  ts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  exec_email    TEXT NOT NULL,
  agent         TEXT NOT NULL,
  tool          TEXT NOT NULL,
  sql           TEXT,
  bytes_scanned BIGINT  DEFAULT 0,
  row_count     INT     DEFAULT 0,
  duration_ms   INT     DEFAULT 0,
  result        TEXT    NOT NULL,
  error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_bq_audit_ts   ON bq_audit (ts);
CREATE INDEX IF NOT EXISTS idx_bq_audit_exec ON bq_audit (exec_email);
```

- `agent`: nome do agent que executou (ex: `"ciclo-de-venda-atacado"`)
- `result`: `'ok'` ou `'error'`
- `sql`: texto completo da query (sem restrição de tamanho — estimativa < 70 MB/ano)
- Sem TTL automático por ora; purge manual > 90 dias pode ser adicionado depois

### `AuditSettings` (`settings.py`)

Novo campo `database_url: str | None = None` em `AuditSettings`.  
Adicionado à tupla `_ENV_OVERRIDES`:
```python
("DATABASE_URL", "audit.database_url"),
```
`audit.db_path` continua existindo para fallback local (dev sem Postgres).

---

## 2. Módulo `audit.py`

Novo `PgAuditLog` ao lado do `AuditLog` (SQLite) existente:

- Construtor recebe `database_url: str` e `agent_name: str`
- `record()` vira `async def` — abre conexão asyncpg, insere, fecha
- Chamada em `server_factory.py` via `asyncio.create_task(record(...))` — fire-and-forget; falha de DB não bloqueia nem falha a resposta BQ
- Erros de INSERT são logados com `logger.error` mas não propagados

**Seleção em runtime (`server_factory.py`):**
```python
if settings.audit.database_url:
    _audit = PgAuditLog(settings.audit.database_url, settings.agent_name)
else:
    _audit = AuditLog(db_path=Path(settings.audit.db_path))  # fallback local
```

---

## 3. Mudanças nos Agents

### `server_factory.py`

- Instanciação do audit usa `PgAuditLog` se `DATABASE_URL` presente
- Chamada `_get_audit().record(...)` muda para:
  ```python
  asyncio.create_task(_get_audit().record(...))
  ```

### `api_routes.py`

- Endpoint `/api/admin/bq-stats` **removido** — dados agora vivem no Postgres, portal consulta direto
- Endpoint `/api/refresh/{analysis_id}` não muda

---

## 4. Portal — API Admin

**Arquivo:** `portal/api/admin/[action].js`

`handleBqStats` deixa de fazer fan-out para agents. Passa a consultar o Neon via `getSql()` (mesmo helper já usado em `handleAnalytics`).

Aceita query param `?days=` (padrão 30, máximo 90).

Queries:

```sql
-- totals
SELECT COUNT(*) AS total_calls,
       SUM(CASE WHEN result='error' THEN 1 ELSE 0 END) AS total_errors,
       SUM(bytes_scanned) AS total_bytes_scanned,
       COUNT(DISTINCT exec_email) AS distinct_users
FROM bq_audit WHERE ts >= NOW() - INTERVAL '$days days'

-- by_user (com agent mais usado)
SELECT exec_email,
       COUNT(*) AS total_calls,
       SUM(CASE WHEN result='error' THEN 1 ELSE 0 END) AS errors,
       SUM(bytes_scanned) AS total_bytes,
       ROUND(AVG(duration_ms)) AS avg_duration_ms,
       MODE() WITHIN GROUP (ORDER BY agent) AS top_agent
FROM bq_audit WHERE ts >= NOW() - INTERVAL '$days days'
GROUP BY exec_email ORDER BY total_calls DESC

-- by_day (por usuário, para o gráfico de linha)
SELECT DATE_TRUNC('day', ts)::date AS day,
       exec_email,
       COUNT(*) AS n
FROM bq_audit WHERE ts >= NOW() - INTERVAL '$days days'
GROUP BY 1, 2 ORDER BY 1

-- recent_errors
SELECT ts, exec_email, agent, tool,
       LEFT(sql, 120) AS sql_preview,
       error, bytes_scanned
FROM bq_audit
WHERE result = 'error' AND ts >= NOW() - INTERVAL '$days days'
ORDER BY ts DESC LIMIT 20
```

---

## 5. Portal — Admin UI (`admin.html`)

### Seletor de janela de tempo

Botões **7d / 30d / 90d** no topo da seção BQ Stats. Ao clicar, refaz o fetch com `?days=N` e re-renderiza.

### Gráfico de linha — Uso no Tempo

- Biblioteca: **Chart.js** (CDN, ~60 KB gzip)
- Dados: `by_day` retornado pela API
- Dropdown "Todos os usuários" + um item por `exec_email` distinto
- Modo "Todos": linha única com volume agregado por dia
- Modo usuário específico: linha única com volume daquele usuário
- Responde ao seletor 7d / 30d / 90d

### Tabela por usuário

- Coluna `agent` mostra o agent mais usado por aquele email (`top_agent`)
- Colunas: email · calls · erros · bytes · duração média · agent principal

### Erros recentes

- Coluna `sql_preview` (primeiros 120 chars da query) para facilitar debug
- Coluna `agent` para identificar qual serviço gerou o erro

### Status dos agents

- Bloco "Agent Status" (online/offline via fan-out) **removido** — sem fan-out, não faz mais sentido
- Substituído por linha de texto: "Último registro: `<timestamp do row mais recente>`" por agent

---

## 6. O que não muda

- Tabela `audit_log` (Postgres) — eventos de portal (publish, refresh, share, archive) não mudam
- `handleAnalytics` — sem alterações
- Auth/middleware da página admin — sem alterações
- Schema do toml de cada agent — `db_path` continua existindo (não é removido, apenas ignorado em produção)

---

## Arquivos modificados / criados

| Arquivo | Tipo |
|---|---|
| `packages/mcp-core/migrations/0002_create_bq_audit.sql` | Novo |
| `packages/mcp-core/src/mcp_core/audit.py` | Modificado |
| `packages/mcp-core/src/mcp_core/settings.py` | Modificado |
| `packages/mcp-core/src/mcp_core/server_factory.py` | Modificado |
| `packages/mcp-core/src/mcp_core/api_routes.py` | Modificado |
| `portal/api/admin/[action].js` | Modificado |
| `portal/admin.html` | Modificado |

---

## Fora de escopo

- Purge automático de registros antigos (pode ser adicionado depois via cron)
- Login success tracking em `audit_log`
- Alertas / notificações baseados em erros BQ
