# Portal — Fase B: refresh, compartilhamento granular e migração para DB

**Data:** 2026-04-26
**Pré-requisito:** Fase A em produção (portal SPA com tabs, marca aplicada, callback DXT brandado)

**Escopo:** transformar o portal de uma camada estática sobre git num produto com banco de dados — habilita refresh server-side de análises com novo período, ACL granular por email, e expõe o catálogo de análises como contexto pro próprio agente.

---

## 1. Visão geral

### 1.1 O que muda

Dois recursos novos no produto + uma migração de arquitetura que viabiliza ambos.

**Refresh server-side de análises**
- Autor pode re-executar a SQL original com novo período (presets ou datas customizadas)
- Backend re-roda no BigQuery, faz swap de "data islands" no HTML, sobrescreve in-place
- Apenas o autor consegue atualizar (público ou privado)
- Operação síncrona (~5-30s), sem polling, sem deploy do Vercel envolvido

**Compartilhamento granular por email**
- Autor adiciona emails específicos à ACL de um relatório privado
- Destinatários veem o relatório numa nova tab "Compartilhadas comigo"
- Lista é gerenciável (add/remove) via modal único
- Sem notificação por email (pode entrar como melhoria futura)
- Sem validação de domínio — email errado = pessoa nunca acessa, sem ônus pro autor

**Migração de git pra Postgres + Vercel Blob**
- Library e ACL deixam de viver em arquivos JSON commitados; passam pra Postgres (Neon)
- HTMLs deixam de viver no repo; passam pra Vercel Blob
- Git deixa de ser fonte da verdade pro conteúdo; mantido só pra código
- Refresh deixa de pagar latência de deploy do Vercel

### 1.2 Tabs do portal passam a ser

**Minhas / Público / Compartilhadas comigo / Arquivadas**

(Renomeia "Time" da Fase A pra "Público".)

### 1.3 Não-objetivos

- Notificação por email aos destinatários (futuro, exige SMTP/SendGrid)
- Histórico/versionamento de refreshes (sobrescreve in-place sem retenção)
- Refresh com parâmetros que não sejam período (filtros de marca, filial, etc.)
- Refresh por terceiros que não o autor
- Análises antigas (sem `refresh_spec`) ganharem refresh retroativamente
- Migração de dados existentes (descartam-se; usuários republicam o que importa)
- Retrocompat de URLs antigas (`/analyses/...` paths estáticos viram 404)
- pgvector / embeddings (futuro, quando FTS não bastar)
- `obter_html(id)` como ferramenta MCP (agente raramente precisa do markup; YAGNI)
- Auto-export periódico do DB pra git como backup (decisão futura)
- Versionamento formal de migrations via Alembic (MVP usa SQL numerado)

---

## 2. Arquitetura

### 2.1 Stack

- **Postgres** (Neon, via Vercel Marketplace) — fonte da verdade pra metadados, ACL, audit
- **Vercel Blob** — armazena os HTMLs das análises (private, signed URLs com TTL)
- **Vercel Functions** (portal) — leituras (library, view, share read) + mutations sem BQ (share/unshare, archive)
- **mcp-core** (Railway, FastAPI) — operações que tocam BigQuery: `publicar_dashboard` (publish) e `POST /api/refresh/<id>` (refresh). Conecta direto na DB e no Blob.
- **Git** — só código. Sem GitHub App auth, sem GitOps no mcp-core, sem commits por análise.

### 2.2 Quem faz o quê

| Operação | Quem executa | Toca BQ? | Toca DB? | Toca Blob? |
|----------|--------------|---------|---------|----------|
| `GET /api/library?agent=X` | Vercel function | — | read | — |
| `GET /api/analysis/<id>` | Vercel function | — | read (ACL) | 302 → signed URL |
| `POST /api/share` | Vercel function | — | write | — |
| `POST /api/archive` | Vercel function | — | write | — |
| `buscar_analises` (MCP tool) | mcp-core | — | read | — |
| `obter_analise` (MCP tool) | mcp-core | — | read | — |
| `publicar_dashboard` (MCP tool) | mcp-core | — | insert | upload |
| `POST /api/refresh/<id>` | mcp-core | ✅ | update | replace |

### 2.3 Por que essa divisão

- Vercel functions bastam pra reads/ACL — query SQL simples + auth via cookie de sessão. Mesma origem do portal, zero CORS, latência baixa.
- mcp-core fica focado no que justifica sua existência: BqClient + allowlist + audit. Sem clone de repo, sem GitOps, sem GitHub App.
- DB é contrato compartilhado. Vercel e Railway têm credenciais pra ela. Schema versionado com SQL plano em `packages/mcp-core/migrations/`.
- Blob serve HTML via Vercel CDN (edge cache). Leitura tão rápida quanto git+Vercel atual, sem deploy.

### 2.4 Bônus inesperado da migração

**Arquivamento per-user vira server-side** — campo `archived_by: TEXT[]` na tabela. Hoje vive em localStorage (per-browser). Depois da migração, arquivar num laptop reflete no celular do mesmo usuário.

---

## 3. Modelo de dados (Postgres)

### 3.1 Tabela `analyses`

```sql
CREATE TABLE analyses (
    id              TEXT PRIMARY KEY,
    agent_slug      TEXT NOT NULL,
    author_email    TEXT NOT NULL,
    title           TEXT NOT NULL,
    brand           TEXT,
    period_label    TEXT,
    period_start    DATE,
    period_end      DATE,
    description     TEXT,
    tags            TEXT[]    NOT NULL DEFAULT '{}',
    public          BOOLEAN   NOT NULL DEFAULT FALSE,
    shared_with     TEXT[]    NOT NULL DEFAULT '{}',
    archived_by     TEXT[]    NOT NULL DEFAULT '{}',
    blob_pathname   TEXT      NOT NULL,
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

CREATE INDEX analyses_agent_author_idx  ON analyses(agent_slug, author_email);
CREATE INDEX analyses_agent_public_idx  ON analyses(agent_slug) WHERE public = TRUE;
CREATE INDEX analyses_shared_with_gin   ON analyses USING GIN(shared_with);
CREATE INDEX analyses_archived_by_gin   ON analyses USING GIN(archived_by);
CREATE INDEX analyses_period_idx        ON analyses(agent_slug, period_end DESC);
CREATE INDEX analyses_search_idx        ON analyses USING GIN(search_doc);
```

**Decisões:**
- Sem tabela ACL separada — `shared_with` e `archived_by` como `TEXT[]` com GIN. Funciona até dezenas de milhares de análises sem dor.
- Sem FK pra tabela de agentes — `agent_slug` é string (lista canônica vive em config).
- `refresh_spec` em JSONB — schema flexível, validação em Pydantic no mcp-core.
- `blob_pathname` em vez de `blob_url` — pathname é estável, signed URL gerada na hora.
- `search_doc` é tsvector gerado automaticamente; pesos: title (A) > desc/tags (B) > brand (C).

**Schema do `refresh_spec`:**

```jsonc
{
  "queries": [
    {
      "id": "top_lojas",
      "sql": "SELECT ... WHERE data_venda BETWEEN '{{start_date}}' AND '{{end_date}}' ..."
    },
    { "id": "top_produtos", "sql": "..." }
  ],
  "data_blocks": [
    { "block_id": "data_top_lojas",    "query_id": "top_lojas" },
    { "block_id": "data_top_produtos", "query_id": "top_produtos" }
  ],
  "original_period": { "start": "2026-04-01", "end": "2026-04-23" }
}
```

**Convenções obrigatórias:**
- Placeholders fixos `{{start_date}}` e `{{end_date}}` — substituídos por strings ISO `YYYY-MM-DD`. Aspas vão **fora** do placeholder (na SQL), nunca dentro.
- Cada `query.id` é único dentro de uma análise.
- Cada `data_blocks[i].block_id` corresponde a um `<script id="<block_id>" type="application/json">…</script>` no HTML.
- O conteúdo de cada `<script>` é JSON serializado da query result (lista de objetos). HTML resultante deve ser auto-suficiente: o JS de render (Plotly/Chart/tabela) lê de `JSON.parse(document.getElementById('<block_id>').textContent)`.
- Validação no `publicar_dashboard`: pra cada `data_blocks[i].block_id`, o HTML precisa ter o `<script id>` correspondente — senão erro educativo.

### 3.2 Tabela `audit_log`

```sql
CREATE TABLE audit_log (
    id            BIGSERIAL PRIMARY KEY,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_email   TEXT NOT NULL,
    action        TEXT NOT NULL,
    analysis_id   TEXT REFERENCES analyses(id) ON DELETE SET NULL,
    metadata      JSONB
);

CREATE INDEX audit_actor_time_idx  ON audit_log(actor_email, occurred_at DESC);
CREATE INDEX audit_analysis_idx    ON audit_log(analysis_id, occurred_at DESC);
```

**Actions reconhecidas:** `publish` | `refresh` | `share` | `unshare` | `make_public` | `make_private` | `archive` | `unarchive`. Append-only por convenção.

### 3.3 Vercel Blob

- Pathname: `analyses/<agent_slug>/<analysis_id>.html`
- Privacidade: **private** (signed URLs com TTL 5 min)
- HTML nunca é servido diretamente — sempre via `GET /api/analysis/<id>` que checa ACL antes
- Após refresh, pathname é o mesmo mas conteúdo muda; cache invalidado via `?v=<last_refreshed_at>` no URL do iframe

### 3.4 Conexão e credenciais

- Neon: `DATABASE_URL` (versão `-pooler`) em ambos Vercel e Railway
- Blob: `BLOB_READ_WRITE_TOKEN` em ambos
- Migrations: SQL plano em `packages/mcp-core/migrations/000N_*.sql`, aplicado manualmente no rollout

---

## 4. Cutover

Sem migração de dados — descarta-se o que existe.

1. Provisionar Neon + Vercel Blob via Marketplace (gera env vars)
2. Aplicar migrations SQL no Neon (cria tabelas + indexes)
3. Deploy do código novo (mcp-core + portal) — modo limpo, zero fallback
4. Mover `portal/library/` e `portal/analyses/` pra `legacy/` (fora do build do Vercel)
5. Anunciar pros usuários: links antigos descontinuados; republicar análises ainda relevantes

---

## 5. Fluxos passo-a-passo

### 5.1 Publicar

1. Agente Claude gera HTML + `refresh_spec` + chama `publicar_dashboard(title, brand, period, description, html_content, tags, refresh_spec)`
2. mcp-core valida: cada `query_id` em `refresh_spec.data_blocks` tem `<script id="data_<query_id>" type="application/json">…</script>` no HTML
3. Gera `analysis_id` (slug + short_hash, mesma regra atual)
4. Upload do HTML pro Blob em `analyses/<agent_slug>/<analysis_id>.html`
5. INSERT em `analyses` (com `period_start`/`period_end` extraídos do `refresh_spec.original_period`)
6. INSERT em `audit_log` (`action='publish'`)
7. Retorna `{id, url: "/api/analysis/<id>"}` — agente compartilha com o usuário no chat

**Latência:** ~1-2s. Usuário vê no portal imediatamente.

### 5.2 Listar library

1. Browser carrega `index.html` (Vercel CDN)
2. JS chama `GET /api/agents` (já existe), depois pra cada agente em paralelo: `GET /api/library?agent=<slug>`
3. Vercel function `library.js`:
   - Lê cookie de sessão → email do usuário
   - Query: `SELECT * FROM analyses WHERE agent_slug = $1 AND (author_email = $2 OR public = TRUE OR $2 = ANY(shared_with)) ORDER BY COALESCE(last_refreshed_at, created_at) DESC`
   - Retorna JSON com `is_mine`, `is_shared_with_me`, `is_archived` calculados
4. Frontend agrega resultado dos N agentes, classifica em tabs, renderiza

**Latência:** ~200-500ms.

### 5.3 Abrir análise

1. Frontend abre iframe com `src="/api/analysis/<id>?v=<last_refreshed_at>"`
2. Vercel function `analysis.js`:
   - Lê cookie → email
   - `SELECT blob_pathname, author_email, public, shared_with FROM analyses WHERE id = $1`
   - Checa ACL: `email == author_email OR public OR email IN shared_with` — senão 403
   - Gera signed URL do Blob com TTL 5 min
   - 302 → signed URL
3. Browser segue redirect, baixa HTML, renderiza

### 5.4 Atualizar período

1. Autor abre menu do card, clica "Atualizar período…"
2. Modal abre com presets (últimos 7d / 30d / 90d / MTD / YTD / Personalizar) + datepickers; mostra período atual e último refresh
3. Autor escolhe período, clica "Atualizar"
4. Frontend POST `/api/refresh-proxy` (Vercel function fina) com `{agent, id, start, end}` — proxy descobre URL Railway do agente e repassa com JWT
5. mcp-core endpoint `POST /api/refresh/<id>`:
   - Auth via JWT, lê email do requester
   - `SELECT refresh_spec, author_email, blob_pathname FROM analyses WHERE id = $1`
   - 404 se não existe; 422 se `refresh_spec` é NULL; 403 se `requester != author_email`
   - Pra cada query em `refresh_spec.queries`: substitui placeholders `{{start_date}}`/`{{end_date}}` pela nova janela e roda via `BqClient.run_query` (passa pelo allowlist e audit existente — label `exec_email` no job)
   - Coleta resultados como list-of-dicts
   - Faz GET no Blob pra baixar HTML atual
   - Pra cada `data_block` no spec, faz string replace dentro do `<script id="data_<id>" type="application/json">…</script>` pelo JSON dos resultados
   - Upload do HTML novo pro mesmo `blob_pathname` (sobrescreve)
   - UPDATE `analyses SET period_start=$start, period_end=$end, last_refreshed_at=NOW(), last_refreshed_by=email, last_refresh_error=NULL, updated_at=NOW() WHERE id=$1`
   - INSERT em `audit_log` (`action='refresh'`, metadata com período + bq_job_ids)
   - Retorna `{ok: true, last_refreshed_at}`
6. Frontend recebe imediatamente (operação síncrona ~5-30s), modal fecha, toast "Atualizado!", card refresh: meta line nova + iframe `?v=` novo

**Erro:** se BQ falha, mcp-core captura, faz UPDATE só do `last_refresh_error`, retorna 502 com mensagem; frontend mostra toast vermelho.

### 5.5 Compartilhar

1. Autor clica "Compartilhar com pessoas..."
2. Modal mostra emails atuais (lidos da entry no DB) + input
3. Autor adiciona/remove (parsing por enter ou vírgula), clica "Salvar"
4. Frontend POST `/api/share` com `{id, shared_with: [emails], public: bool}`
5. Vercel function:
   - Lê email da sessão, valida que é `author_email` da entry
   - UPDATE `analyses SET shared_with=$1, public=$2, updated_at=NOW() WHERE id=$3`
   - INSERT audit (`action='share'`, metadata: diff de quem foi adicionado/removido)
6. Retorna entry atualizada; modal fecha, toast "Lista atualizada"

### 5.6 Arquivar

1. Usuário clica "Arquivar"
2. Frontend POST `/api/archive` com `{id, archive: bool}`
3. Vercel function: `UPDATE analyses SET archived_by = array_append(archived_by, $email)` (ou `array_remove` pra desarquivar) — idempotente via `array_append` precedido de `array_remove` na mesma operação
4. Retorna ok; frontend move o card pra tab "Arquivadas"

---

## 6. Catálogo como contexto do agente

### 6.1 Ideia

Expor `analyses` como ferramentas MCP. Quanto mais análises o portal acumula, mais inteligente o agente fica em reaproveitar trabalho prévio. ACL é preservada por construção (agente roda em nome do usuário, mesmo email no JWT).

### 6.2 Ferramentas novas no mcp-core

**`buscar_analises(query: str, brand: str | None = None, agent: str | None = None, days_back: int = 90, limit: int = 10)`**

- Filtra por ACL (igual ao endpoint `/api/library`)
- FTS via `search_doc @@ plainto_tsquery('portuguese', $query)`, ranked por `ts_rank` × decay de recência
- Retorna lista com `{id, title, description, brand, author_email, agent_slug, period_label, last_refreshed_at, tags, has_refresh_spec}` — sem HTML, sem SQL

**`obter_analise(id: str)`**

- Checa ACL antes de devolver (403 se usuário não pode ver)
- Retorna `{… metadados …, refresh_spec, blob_pathname}` — incluindo SQLs do refresh_spec
- Não retorna HTML inteiro (custo de contexto alto)

### 6.3 Como o agente usa (instruções no SKILL.md de cada agente)

Adicionar seção:

> **Antes de gerar uma análise nova:**
>
> 1. Chame `buscar_analises(query=<resumo da pergunta>, brand=<marca se houver>, agent="<este agente>")`.
> 2. Se houver match recente (últimos 30 dias) com mesma marca + tema:
>    - Mostre pro usuário: "Já existe uma análise parecida: '<título>' (publicada há 3 dias). Quer atualizar com o novo período em vez de criar uma nova?"
>    - Se sim → instrua o usuário a clicar "Atualizar período" no card; se não → siga.
> 3. Para análises não-triviais, chame `obter_analise(id)` em 1-2 análises mais relevantes do search e use as SQLs do `refresh_spec` como ponto de partida (não copiar cego — adaptar pro pedido atual).
> 4. Inclua nos rascunhos: "reaproveitando estrutura de [título da análise prévia]" pra dar transparência.

### 6.4 Trade-offs

- **Contexto:** cada `buscar_analises` traz ~10 entries × ~300 tokens = ~3k tokens. Aceitável.
- **Risco de atalho ruim:** agente pode reusar SQL parecida que vira aplica errado. Mitigação: instrução enfatiza "adaptar"; `analyst principles.md` força revisão da SQL.
- **Tags viram coordenadas reais** — convenções padronizadas (mtd, ytd, ranking, comparativo, produto, loja) entram no SKILL.md; agente passa a respeitar.

---

## 7. Testes

### 7.1 Automáticos

**`packages/mcp-core/`:**
- `tests/test_analyses_repository.py` — CRUD contra Postgres efêmero (testcontainers ou Postgres local): insert, ACL filter, update refresh state, archive add/remove, audit append
- `tests/test_publish_dashboard.py` — `publicar_dashboard` insere no DB + faz upload no Blob (mock); valida que `data_blocks` requer `<script id="data_X">` correspondente no HTML
- `tests/test_refresh.py` — `POST /api/refresh/<id>` com BqClient mockado: queries rodam, data_blocks são swapped, blob é re-uploaded, audit row criado; testa caminhos de erro (não-autor → 403, refresh_spec ausente → 422, BQ falha → 502 + UPDATE de last_refresh_error)
- `tests/test_search.py` — `buscar_analises` retorna só análises acessíveis (ACL); ranking de FTS respeitado; `obter_analise` retorna 403 pra não-autorizados

**`portal/api/`:**
- `tests/library.test.js` — endpoint filtra por sessão; classifica `is_mine` / `is_shared_with_me` / `is_archived` corretamente
- `tests/analysis.test.js` — checa ACL antes do 302; signed URL com TTL apropriado; 403 pra não-autorizado
- `tests/share.test.js` — só autor muda shared_with/public; audit gravado; diff de emails computado
- `tests/archive.test.js` — adiciona/remove email do array; idempotente

**Frontend (vitest existente):**
- Classificação de tabs dado payload de `/api/library`
- Modal de refresh: presets calculam datas corretas; "Personalizar" expande inputs; validação de ordem
- Modal de share: parsing de emails (vírgula, enter); remove com X; salvar dispara POST correto

### 7.2 QA manual (golden path)

Setup: 2 usuários (`a@somagrupo.com.br`, `b@somagrupo.com.br`) num staging com Neon + Blob isolados.

1. **Publicar:** A pede análise no Claude Desktop (vendas-linx). Agente gera com `refresh_spec`. Confirma no portal: aparece em "Minhas" pra A, sem aparecer pra B.
2. **Compartilhar 1:1:** A clica "Compartilhar com pessoas...", adiciona `b@somagrupo`, salva. B abre portal: análise aparece em "Compartilhadas comigo". B clica → abre.
3. **Tornar pública:** A clica "Tornar pública". B vê em "Público" (não mais em "Compartilhadas comigo"). Email no `shared_with` segue salvo (verificar via SQL direta).
4. **Atualizar período:** A abre menu da própria análise, clica "Atualizar período → últimos 7d". Modal mostra spinner ~10-20s, fecha com toast, card mostra período novo. Iframe re-aberto mostra dados novos.
5. **Não-autor não atualiza:** B abre menu da análise pública: opção "Atualizar período" não aparece (UI esconde) e POST direto retorna 403 (verificar via DevTools).
6. **Refresh com erro:** A altera `refresh_spec` da análise via SQL pra apontar pra dataset não-autorizado. Clica refresh: toast vermelho com mensagem "dataset não permitido"; `last_refresh_error` no DB.
7. **Arquivar:** B arquiva a análise pública. Some da tab Público pra B. A continua vendo em "Minhas" (archive é per-user).
8. **Search no agente:** A pergunta no chat algo similar à análise X já publicada. Agente chama `buscar_analises`, mostra match, sugere atualizar.
9. **ACL leak:** A publica análise privada. Tenta abrir como B (mesmo URL): 403. Tenta `GET /api/library?agent=vendas-linx` como B: análise não aparece.

---

## 8. Rollout

1. Provisionar Neon (free tier) e Vercel Blob via Vercel Marketplace — gera `DATABASE_URL` e `BLOB_READ_WRITE_TOKEN` automaticamente nas envs do projeto Vercel
2. Adicionar manualmente as mesmas envs nos services Railway (vendas-linx, devolucoes) — `DATABASE_URL` precisa ser a versão `-pooler` pra Neon aguentar conexões serverless
3. Rodar SQL de migrations no Neon (script ou painel)
4. Deploy do `packages/mcp-core` (Railway) com código novo — sem GitHub App auth, sem clone de repo, sem GitOps
5. Deploy do `portal/` (Vercel) com endpoints novos
6. Mover `portal/library/` e `portal/analyses/` pra `legacy/` — fora do build do Vercel
7. Smoke test do golden path em staging
8. Anunciar pros usuários: links antigos foram desativados

### 8.1 Riscos e mitigações

- **Connection pool exhaustion no Neon:** uso do pooler endpoint resolve no nível Neon. Conexões short-lived em ambos lados; sem idle abusivo.
- **Blob signed URL vazando:** TTL 5 min limita janela. Análises públicas não estendem TTL — quem é público acessa sempre via portal (que checa ACL na hora).
- **Quota do Blob:** análises ~500KB cada. Mil análises = ~500MB. Vercel Blob free tier é 1GB. Confortável; quando passar, paga.
- **Migrations sem versionamento formal:** MVP usa scripts SQL numerados. Pra Fase C, considerar Alembic.
- **Perda de retrocompat de URLs:** decisão consciente — usuários republicam o que importa, anuncio antecipado, links velhos viram 404 limpo.

---

## 9. Detalhes operacionais e de segurança

Decisões que ficaram implícitas e precisam ser explícitas pra implementação não derivar.

### 9.1 Contrato de auth entre camadas

**Sessão atual do portal (não muda):** cookie `session` é uma string HMAC custom no formato `<identity>~<expiry>~<base64url(hmac_sha256(SESSION_SECRET, identity~expiry))>`. Verificada em `portal/middleware.js` e em qualquer Vercel function via helper `verifySession(cookie, SESSION_SECRET) → identity | null`. **Não** é JWT — é cookie de sessão simétrico assinado com `SESSION_SECRET`.

- **Vercel function ↔ DB:** Vercel function lê cookie `session`, chama `verifySession`, extrai `identity` (email já lowercased pelo auth.js no momento da emissão). Se inválido/expirado → 401. Query no DB usa `identity` como filtro de ACL.
- **Vercel function (proxy) ↔ Railway (mcp-core):** Vercel não pode repassar o cookie (cross-origin) nem o ID token original (não fica armazenado em lugar nenhum após o login). Solução: Vercel **mint** um JWT curto (HS256, TTL 60s) assinado com `MCP_PROXY_SIGNING_KEY` (env var em ambos lados), claims `{email, aud: "mcp-core-proxy", exp}`. Railway valida via novo path no `auth_middleware`: além do MSAL JWT existente (DXT clients), aceita JWT HS256 com `aud=mcp-core-proxy` assinado com `MCP_PROXY_SIGNING_KEY`. Os dois paths são exclusivos — payload do MSAL não tem `aud=mcp-core-proxy`, e proxy JWT não tem assinatura RSA.
- **DXT client ↔ mcp-core:** fluxo MSAL existente (JWT do Azure AD com JWKS RSA). Inalterado.
- **Lista de allowlist (`allowed_execs.json`):** o `email` extraído (de qualquer um dos dois paths) precisa estar na allowlist do agente — vale para chamadas MCP, para `POST /api/refresh`, e para qualquer endpoint Railway novo. Removido da allowlist = não consegue refresh nem publish.

**Env vars novas:**
- `MCP_PROXY_SIGNING_KEY` — gerada com `openssl rand -base64 64`, configurada em **Vercel** (acessível pelas functions) e em **cada agente Railway** (lida no boot pelo `auth_middleware`). Rotação manual: gerar nova, atualizar nos dois lados em janela de manutenção curta (TTL do JWT é 60s, então clientes renovam imediatamente).

### 9.2 Normalização de email

- **Em todo lugar onde email é armazenado ou comparado, é lowercased**: `analyses.author_email`, `shared_with[]`, `archived_by[]`, `audit_log.actor_email`, JWT claim antes de ir pra query.
- Função utilitária `_normalize_email(s) = s.strip().lower()` aplicada em:
  - mcp-core ao escrever (publish, share, archive)
  - Vercel ao escrever
  - Toda comparação de ACL antes da query SQL
- Não fazemos normalização Unicode (NFC) — emails corporativos só usam ASCII.

### 9.3 Concorrência no refresh

- Risco: autor clica "Atualizar" duas vezes em sequência rápida, dois jobs BQ rodam, dois UPDATE concorrentes no DB.
- Solução: **lock advisory por entry_id** no Postgres, dentro da transação do refresh:
  ```sql
  SELECT pg_try_advisory_xact_lock(hashtext('refresh:' || $entry_id));
  ```
  Se `false` → 409 Conflict com mensagem "Atualização já em andamento; aguarde".
- O lock é segurado pela duração da transação (que dura o refresh inteiro: BQ + blob upload + UPDATE). Auto-libera ao COMMIT/ROLLBACK.
- Frontend desabilita o botão "Atualizar" enquanto a request está pendente (camada extra de proteção, mas não substitui o lock server-side).

### 9.4 Swap de data islands no HTML

- **Algoritmo:** regex canônica que casa **exatamente** o padrão emitido pelo agente:
  ```
  <script id="<block_id>" type="application/json">(.*?)</script>
  ```
  com flag `re.DOTALL`. Substitui o conteúdo entre as tags pelo JSON novo.
- **Escape obrigatório:** ao serializar a query result em JSON pra inserir, **substituir `<` por `\u003c`** (também `>`, `&`, `'`, `\u2028`, `\u2029` por suas formas escapadas Unicode). Isso impede que dados (ex: nomes de produto contendo `</script>`) escapem da `<script>` e injetem markup. Implementação: `json.dumps(result, ensure_ascii=False).translate(_HTML_SCRIPT_ESCAPES)`.
- **Validação pós-swap:** após o replace, o mcp-core re-roda um regex pra confirmar que cada `<script id="<block_id>">` ainda está balanceado (abre+fecha 1:1). Se falhar → ROLLBACK, retorna 500 com `last_refresh_error="html_swap_invalid"`.
- **CSP preservada:** o swap só toca o conteúdo de `<script type="application/json">`. A meta CSP fica no `<head>`, intocada. Sanity check: regex match do `<meta http-equiv="Content-Security-Policy"` antes e depois — se sumiu, ROLLBACK.

### 9.5 Resultado vazio

- Query pode retornar 0 linhas (ex: período sem vendas). Mantém o `<script>` com `[]`.
- O JS de render do HTML é responsabilidade do agente — instrução no SKILL.md: "tabelas e gráficos devem renderizar estado vazio gracefully (mensagem 'sem dados no período')".
- Não bloqueia o refresh. `last_refresh_error` permanece NULL.

### 9.6 Estado de visibilidade no card e ações disponíveis

| Ação no card menu | Autor (private) | Autor (shared) | Autor (public) | Não-autor (visualiza) |
|--------------------|-----------------|----------------|----------------|------------------------|
| Atualizar período  | ✓ (se tem `refresh_spec`) | ✓ | ✓ | — |
| Compartilhar com pessoas | ✓ (abre modal) | ✓ (modal mostra emails atuais) | — (já é público) | — |
| Tornar pública     | ✓ | ✓ | — | — |
| Tornar privada     | — | — | ✓ (zera o `public`, mantém `shared_with` se existia) | — |
| Copiar link        | — | ✓ | ✓ | ✓ |
| Arquivar/Restaurar | ✓ | ✓ | ✓ | ✓ |

- Meta line do card mostra `Atualizado em <last_refreshed_at>` pra qualquer um que enxergue, mesmo sem direito de atualizar.
- `Tornar privada` aparece quando `public=true` — útil pra desfazer um "Tornar pública" acidental.

### 9.7 Pagination e limites de `buscar_analises`

- Limite hard de 25 entries por chamada (default 10). Sem cursor de pagination — agente refina via `query`/`brand`/`agent` pra estreitar.
- Se o agente quiser ranqueamento mais largo, chama de novo com query mais específica.
- Aceitável pra MVP — escala 1k-10k análises confortavelmente sem o agente "perder" itens relevantes (FTS já ranqueia por relevância × recência).

### 9.8 Tags e canonicalização

- Tags são gravadas case-sensitive como o agente passa, mas FTS (`to_tsvector`) lowercased automaticamente — busca não diferencia maiúscula.
- Convenções recomendadas no SKILL.md: `mtd`, `ytd`, `ranking`, `comparativo`, `produto`, `loja`, `marca`, `canal`, `7d`, `30d`, `90d`. Slug-cased, sem acentos.
- Sem normalização forçada — o agente é instruído a respeitar; se desviar, FTS ainda casa pelo título/descrição.

### 9.9 Não-objetivos adicionais

- **DELETE de análise:** sem operação de hard-delete no MVP. Arquivar é a única ação de "esconder". Se precisar deletar de fato (LGPD, vazamento), fazer manual via SQL — operação rara.
- **Edição de metadata** (renomear título, mudar tags, mudar descrição depois de publicar): não. Republicar.
- **Mover análise entre agentes:** não. `agent_slug` é imutável após insert.

### 9.10 Atomicidade do refresh

A operação inteira (BQ queries + swap de data islands + upload do Blob + UPDATE no DB + INSERT no audit) precisa ser atômica do ponto de vista do usuário: ou tudo dá certo, ou o estado anterior persiste.

**Sequência recomendada:**

1. `BEGIN` transação no Postgres
2. Lock advisory (9.3)
3. SELECT do estado atual (`refresh_spec`, `blob_pathname`, etc.)
4. Validações (autor, refresh_spec presente)
5. **Roda todas as queries no BQ.** Se qualquer uma falhar → ROLLBACK + UPDATE só do `last_refresh_error` em transação separada + retorna 502. Não toca no Blob.
6. Faz GET do HTML atual no Blob
7. Aplica swap em memória, valida (CSP intacta, blocks balanceados — 9.4). Se falhar → ROLLBACK + retorna 500.
8. Upload do HTML novo pro mesmo `blob_pathname` (Blob não tem transação, mas é idempotente; falha aqui → ROLLBACK e o Blob fica com a versão velha porque o upload nem completou)
9. UPDATE `analyses` + INSERT `audit_log`
10. `COMMIT`

**Window de inconsistência:** entre upload do Blob (passo 8) e COMMIT do DB (passo 10), Blob tem versão nova mas DB tem `last_refreshed_at` antigo. Janela é <100ms. Se crash durante essa janela, próximo refresh sobrescreve o Blob de novo — não é estado inválido, só desincronia mínima.

### 9.11 Env vars que ficam obsoletos

Removidos na Fase B (cleanup do mcp-core durante a implementação):

- `MCP_FORCE_PUBLIC` — não faz mais sentido. Granularidade vem do flag `public` por análise + `shared_with`.
- `MCP_GIT_PUSH` — sem mais GitOps.
- `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY` — sem mais commits programáticos.

Mantidos: `MCP_BQ_PROJECT_ID`, `MCP_BQ_BILLING_PROJECT_ID`, `MCP_BQ_SA_KEY`, `JWT_SECRET` (MSAL path), `SESSION_SECRET` (portal). **Novos:** `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`, `MCP_PROXY_SIGNING_KEY`.
