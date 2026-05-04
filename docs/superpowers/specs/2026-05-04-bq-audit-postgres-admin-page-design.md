# BQ Audit — Migração para Postgres + Revisão da Página Admin

**Data:** 2026-05-04  
**Status:** Aprovado (revisado após critique — v2)

## Problema

Os logs de uso dos agentes MCP (queries BigQuery) são gravados em SQLite local em `/var/mcp/audit.db` dentro dos containers Railway. A cada redeploy (disparado por todo push para `main`), o container é recriado do zero e o arquivo SQLite é apagado. Por isso a página admin exibe dados de apenas 2 pessoas — são as sessões desde o último deploy.

Três bugs adicionais agravam o problema:
- `consultar_bq` não grava audit em nenhum dos 3 caminhos de erro (`SqlValidationError`, `DatasetNotAllowedError`, `Exception`)
- A página admin não tem destaque visual para BQ Stats, sendo que esses são os logs mais importantes
- O fan-out HTTP para cada agent é frágil: qualquer timeout silencia dados daquele agent

## Solução

Mover o audit de BQ para o Neon Postgres que os agents já acessam via `DATABASE_URL`. Isso elimina o fan-out, torna os logs duráveis e permite corrigir os paths de erro silenciosos.

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

- `agent`: nome do agent que executou (ex: `"ciclo-de-venda-atacado"`) — vem do argumento `agent_name` de `build_mcp_app`, não de settings
- `result`: `'ok'` ou `'error'`
- `sql`: texto completo da query (sem restrição de tamanho — estimativa < 70 MB/ano)
- Sem TTL automático por ora; purge manual > 90 dias pode ser adicionado depois

**Como aplicar:** usar o mesmo mecanismo já em uso para `0001_create_analyses_audit.sql`. A migration **deve ser aplicada antes do deploy dos agents** — se os agents subirem primeiro sem a tabela existir, o INSERT falhará silenciosamente (fire-and-forget captura o erro), mas nenhum dado será gravado até a migration rodar.

### `AuditSettings` (`settings.py`)

Novo campo `database_url: str | None = None` em `AuditSettings`:

```python
class AuditSettings(BaseModel):
    db_path: str
    retention_days: int = 90
    database_url: str | None = None
```

Novo entry em `_ENV_OVERRIDES` — **formato 3-tupla** `(env_var, section, field)`, igual ao padrão existente:

```python
("DATABASE_URL", "audit", "database_url"),
```

> **Nota:** o env var é `DATABASE_URL` (sem prefixo `MCP_`), porque Railway já o fornece com esse nome exato para a DATABASE_URL do Neon. Desvio intencional da convenção `MCP_*` do restante do arquivo.

`audit.db_path` continua existindo para fallback local (dev sem Postgres).

---

## 2. Módulo `audit.py`

Novo `PgAuditLog` ao lado do `AuditLog` (SQLite) existente.

**Design:**
- Construtor recebe `database_url: str` e `agent_name: str` — armazena apenas, não abre conexão
- `record()` vira `async def` — usa `db.get_pool().acquire()` (pool já inicializado no lifespan de `server_factory.py`), insere, libera a conexão de volta ao pool
- **Não** abre `asyncpg.connect()` por chamada — reusar o pool existente evita overhead de ~10 ms por conexão nova e não esgota o limite de conexões do Neon
- Erros de INSERT são logados com `logger.error` mas não propagados

```python
class PgAuditLog:
    def __init__(self, agent_name: str) -> None:
        # database_url não é necessário como argumento — usa o pool já
        # inicializado via mcp_core.db (que lê DATABASE_URL internamente)
        self._agent_name = agent_name

    async def record(
        self, *, exec_email: str, tool: str, sql: str | None,
        bytes_scanned: int, row_count: int, duration_ms: int,
        result: str, error: str | None,
    ) -> None:
        try:
            async with db.get_pool().acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO bq_audit
                      (exec_email, agent, tool, sql, bytes_scanned,
                       row_count, duration_ms, result, error)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    """,
                    exec_email, self._agent_name, tool, sql,
                    bytes_scanned, row_count, duration_ms, result, error,
                )
        except Exception:
            logger.error("bq_audit insert failed", exc_info=True)
```

**Seleção em runtime (`server_factory.py`):**
```python
if settings.audit.database_url:
    _audit = PgAuditLog(agent_name=agent_name)   # agent_name vem do closure de build_mcp_app
else:
    _audit = AuditLog(db_path=Path(settings.audit.db_path))  # fallback local
```

> `agent_name` é o argumento de `build_mcp_app(agent_name: str, ...)`. `_get_audit()` vive dentro desse closure e pode referenciá-lo diretamente, sem precisar de um campo `settings.agent_name`.

---

## 3. Mudanças nos Agents

### `server_factory.py`

**Mudança 1 — instanciação do audit:**
```python
# antes
_audit = AuditLog(db_path=Path(settings.audit.db_path))

# depois
if settings.audit.database_url:
    _audit = PgAuditLog(agent_name=agent_name)
else:
    _audit = AuditLog(db_path=Path(settings.audit.db_path))
```

**Mudança 2 — `consultar_bq`: adicionar audit em TODOS os caminhos.**

Atualmente apenas o caminho de sucesso grava audit. Os três caminhos de erro retornam sem registrar nada — isso é o bug central desta feature. A correção:

```python
async def consultar_bq(sql: str, ctx: Context) -> dict[str, object]:
    exec_email = _current_email(ctx)
    start = _time.time()
    await ctx.report_progress(progress=0.0, total=1.0, message="validating query...")

    try:
        validate_readonly_sql(sql)
    except SqlValidationError as e:
        asyncio.create_task(_get_audit().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=f"sql_validation: {e}",
        ))
        return {"error": f"sql_validation: {e}"}

    await ctx.report_progress(progress=0.2, total=1.0, message="checking dataset access...")
    client = _load_cached_state().bq_client

    try:
        result = client.run_query(sql=sql, exec_email=exec_email)
    except DatasetNotAllowedError as e:
        asyncio.create_task(_get_audit().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=f"dataset_not_allowed: {e}",
        ))
        return {"error": f"dataset_not_allowed: {e}"}
    except Exception as e:
        asyncio.create_task(_get_audit().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=f"bq_execution: {e}",
        ))
        return {"error": f"bq_execution: {e}"}

    duration_ms = int((_time.time() - start) * 1000)
    await ctx.report_progress(progress=1.0, total=1.0, message="query complete")
    asyncio.create_task(_get_audit().record(
        exec_email=exec_email, tool="consultar_bq", sql=sql,
        bytes_scanned=cast(int, result.bytes_processed or 0),
        row_count=result.row_count,
        duration_ms=duration_ms,
        result="ok", error=None,
    ))
    return { ... }  # unchanged
```

`asyncio.create_task()` funciona porque `consultar_bq` já é `async def`. Fire-and-forget: falha de DB não bloqueia nem falha a resposta BQ.

### `api_routes.py`

- Endpoint `/api/admin/bq-stats` **removido** — dados agora vivem no Postgres, portal consulta direto
- Endpoint `/api/refresh/{analysis_id}` não muda
- Parâmetro `audit_db_path` em `register_api_routes` pode ser removido

---

## 4. Portal — API Admin

**Arquivo:** `portal/api/admin/[action].js`

### Validação de `days`

```js
const days = Math.max(1, Math.min(90, parseInt(req.query.days, 10) || 30))
```

Aplicar antes de qualquer query. Clampa silenciosamente valores fora do range; `parseInt` de string inválida retorna `NaN`, o `|| 30` garante o default.

### Queries

`handleBqStats` deixa de fazer fan-out para agents. Passa a consultar o Neon via `getSql()` com queries parametrizadas — usar `make_interval` para interpolar `days` sem risco de SQL injection:

```js
-- totals
SELECT COUNT(*)                                                      AS total_calls,
       SUM(CASE WHEN result='error' THEN 1 ELSE 0 END)              AS total_errors,
       SUM(bytes_scanned)                                            AS total_bytes_scanned,
       COUNT(DISTINCT exec_email)                                    AS distinct_users
FROM bq_audit
WHERE ts >= NOW() - make_interval(days => ${days})

-- by_user (com agent mais usado)
SELECT exec_email,
       COUNT(*)                                              AS total_calls,
       SUM(CASE WHEN result='error' THEN 1 ELSE 0 END)      AS errors,
       SUM(bytes_scanned)                                    AS total_bytes,
       ROUND(AVG(duration_ms))                              AS avg_duration_ms,
       MODE() WITHIN GROUP (ORDER BY agent)                 AS top_agent
FROM bq_audit
WHERE ts >= NOW() - make_interval(days => ${days})
GROUP BY exec_email
ORDER BY total_calls DESC

-- by_day (por usuário, para o gráfico de linha)
SELECT DATE_TRUNC('day', ts)::date AS day,
       exec_email,
       COUNT(*)                    AS n
FROM bq_audit
WHERE ts >= NOW() - make_interval(days => ${days})
GROUP BY 1, 2
ORDER BY 1

-- recent_errors
SELECT ts, exec_email, agent, tool,
       LEFT(sql, 200)   AS sql_preview,
       error, bytes_scanned
FROM bq_audit
WHERE result = 'error'
  AND ts >= NOW() - make_interval(days => ${days})
ORDER BY ts DESC
LIMIT 20

-- last_seen_by_agent (para o bloco de status)
SELECT agent, MAX(ts) AS last_seen
FROM bq_audit
GROUP BY agent
ORDER BY agent
```

> `sql_preview` aumentado de 120 para 200 chars — 120 é raramente suficiente para ver a tabela relevante numa query WITH.

### Ordem de deploy

**Agents (Railway) devem ser deployados antes do portal (Vercel).** Durante a janela entre os dois deploys, o portal antigo ainda tenta fan-out para o endpoint `/api/admin/bq-stats` que ainda existe nos agents (pré-remoção) — sem quebra visível. Após o portal atualizar, ele passa a ler do Postgres diretamente.

---

## 5. Portal — Admin UI (`admin.html`)

### Hierarquia da página

**BQ Stats sobe para a primeira seção da página** (antes de "Analytics do Portal"). O usuário declarou que esses são os logs mais importantes da página — a hierarquia visual deve refletir isso.

### Seletor de janela de tempo

Botões **7d / 30d / 90d** no topo da seção BQ Stats. O botão 30d começa selecionado. Ao clicar, refaz o fetch com `?days=N` e re-renderiza. Estado ativo destacado visualmente (ex: borda/background diferente).

### Gráfico de linha — Uso no Tempo

- Biblioteca: **Chart.js 4.4.3** (`cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js`)
- Dados: `by_day` retornado pela API — array de `{day, exec_email, n}`
- Dropdown "Todos os usuários" + um item por `exec_email` distinto presente nos dados
- **Modo "Todos":** frontend agrega `by_day` client-side — `reduce` agrupando por `day`, somando `n` de todos os emails → dataset único de `{x: day, y: total}` para o chart
- **Modo usuário específico:** filtra `by_day` pelo email selecionado → dataset único
- Responde ao seletor 7d / 30d / 90d (novo fetch a cada mudança)
- Eixo X: datas; eixo Y: número de queries; tooltip mostra data + contagem

### Formatação de bytes

Em toda exibição de `bytes_scanned` / `total_bytes` / `total_bytes_scanned`:

```js
function formatBytes(n) {
  if (n == null || n === 0) return '—'
  if (n < 1024) return n + ' B'
  if (n < 1024 ** 2) return (n / 1024).toFixed(1) + ' KB'
  if (n < 1024 ** 3) return (n / 1024 ** 2).toFixed(1) + ' MB'
  return (n / 1024 ** 3).toFixed(2) + ' GB'
}
```

### Tabela por usuário

- Colunas: email · calls · erros · bytes (formatado) · duração média (ms) · agent principal
- `top_agent`: agent mais frequente daquele usuário no período (`MODE()` da query)

### Erros recentes

- Coluna `sql_preview` (primeiros 200 chars) para facilitar debug
- Coluna `agent` para identificar qual serviço gerou o erro
- Bytes exibidos formatados

### Bloco de status por agent

Substitui o "Agent Status" (online/offline via fan-out) — não faz mais sentido sem fan-out.

Mostra uma linha por agent presente em `bq_audit`:
- `{agent_name}` · último registro: `{timestamp formatado}` (ex: "há 2 horas" ou data se > 24h)
- Se `bq_audit` estiver vazia ou o agent nunca tiver registrado: exibir "Sem registros"

Query usada: `last_seen_by_agent` (seção 4 acima).

### Estados de loading / erro / vazio

- **Loading:** skeleton ou spinner enquanto o fetch está em andamento; botões de seleção de período ficam desabilitados
- **Erro de API:** banner de erro não intrusivo ("Erro ao carregar dados de BQ — tente novamente") com botão de retry; não apaga dados anteriores se já havia algo renderizado
- **Vazio (sem dados no período):** mensagem "Sem queries registradas nos últimos Xd" no lugar da tabela/gráfico; o gráfico exibe eixos vazios com essa legenda

---

## 6. O que não muda

- Tabela `audit_log` (Postgres) — eventos de portal (publish, refresh, share, archive) não mudam
- `handleAnalytics` — sem alterações
- Auth/middleware da página admin — sem alterações
- Schema do toml de cada agent — `db_path` continua existindo (não é removido, apenas ignorado em produção quando `DATABASE_URL` presente)

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
- Paginação da tabela por usuário (se crescer muito, adicionar depois)
