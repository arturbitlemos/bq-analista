# Portal de Análises — Azzas 2154

Biblioteca privada de dashboards de BI do grupo. Cada analista tem sua própria pasta de análises (só ele vê) e pode marcar uma análise como pública (todo mundo logado vê).

**Portal em produção:** https://bq-analista.vercel.app/

---

## 🚀 Quero usar o Azzas MCP no meu Claude Desktop

**Para todos os usuários corporativos.** Nenhuma instalação técnica no seu computador.

1. Acesse **[bq-analista.vercel.app/onboarding](https://bq-analista.vercel.app/onboarding)** e faça login com sua conta `@somagrupo.com.br`
2. Baixe o arquivo `azzas-mcp-*.dxt`
3. Abra o Claude Desktop (Mac ou Windows) e arraste o `.dxt` pra dentro da janela
4. Desktop pergunta *"Install Azzas MCP?"* — clique em Install
5. Peça uma análise no chat. Na primeira vez, um browser vai abrir pedindo login corporativo. Depois de logar, peça de novo e pronto.

A sessão dura 7 dias. Depois disso, vai pedir login de novo.

Para troubleshooting e arquitetura técnica, continue lendo este README.

---

## Para consultar análises

1. Abra https://bq-analista.vercel.app/
2. Faça login com sua conta `@somagrupo.com.br` (SSO Azure)
3. A biblioteca aparece com todas as análises públicas + suas análises privadas
4. Clique num card pra abrir o dashboard

Só isso. Se você só quer **ler** análises, pode parar aqui.

---

## Para publicar uma análise

> Requer acesso ao BigQuery do grupo (`bq` CLI autenticado) e uma instalação local do Claude Code.

### 1. Setup inicial (uma vez só)

```bash
# Clone
git clone https://github.com/somalabs/bq-analista.git
cd bq-analista

# Configure seu email (o mesmo que você usa pra logar no portal)
echo 'USER_EMAIL=seu.nome@somagrupo.com.br' > .env

# Autentique no BigQuery
gcloud auth application-default login
bq ls   # deve listar datasets sem erro
```

### 2. Gerar uma análise

Abra o Claude Code na raiz do projeto e peça a análise em linguagem natural:

> "Faça uma análise de ticket médio da FARM por categoria nos últimos 30 dias"

O Claude vai:
- Carregar `SKILL.md` + `analyst principles.md` + `business-rules.md`
- Fazer `dry-run` da query no BigQuery
- Executar e interpretar os resultados
- Gerar um dashboard HTML mobile-first
- **Publicar automaticamente** na sua biblioteca privada

### 3. Fluxo de publicação (o que o Claude faz por você)

1. Salva o HTML em `analyses/{USER_EMAIL}/{brand}-{topic}-{YYYY-MM-DD}.html`
2. Adiciona uma entrada em `library/{USER_EMAIL}.json` com metadata (título, período, tags…)
3. `git commit + push` → Vercel redeploya em ~60s
4. Análise aparece na sua biblioteca no próximo refresh do portal

### 4. Tornar uma análise pública

Peça ao Claude: "torna pública" ou "compartilha com o time". Ele copia o HTML pra `analyses/public/` e adiciona a entrada em `library/public.json`.

---

## Desenvolvimento local

Se você quer rodar o portal na sua máquina (pra testar mudanças no código, não pra publicar análises):

```bash
npm install
vercel link               # linka no projeto 'analysis-lib' (time Azzas)
vercel env pull .env.local   # puxa as variáveis do Azure
vercel dev                # http://localhost:3000
```

O login MSAL precisa que `http://localhost:3000/` esteja registrado como redirect URI no App Registration do Azure (plataforma **Single-page application**).

---

## Arquitetura

**Stateless, sem backend persistente.** Tudo mora no git e é servido pelo Vercel.

```
index.html                        → SPA da biblioteca (login + grid + iframe viewer)
api/auth.js                       → valida idToken Azure, seta cookie de sessão assinado (HMAC)
api/config.js                     → expõe AZURE_CLIENT_ID/TENANT_ID pro browser
middleware.js                     → Edge middleware: valida cookie, enforça ACL por email
analyses/public/                  → dashboards visíveis a todos autenticados
analyses/{email}/                 → dashboards privados de um analista
library/public.json               → índice público
library/{email}.json              → índice privado de um analista
```

**Fluxo de auth:**
1. Browser faz `loginRedirect` no MSAL (SPA flow)
2. Azure devolve `idToken` com claim `preferred_username` (email)
3. Browser POSTa o token em `/api/auth` → valida assinatura, seta cookie `session={email}~{exp}~{hmac}`
4. Middleware intercepta `/analyses/*` e `/library/*`, valida cookie, compara email da sessão com segmento da URL

**Como a biblioteca é montada** (`index.html`):
- Faz `fetch('library/public.json')` + `fetch('library/{meu-email}.json')` em paralelo
- Merge por `id` (privada tem prioridade)
- Ordena por `date` desc
- Renderiza como grid de cards; clique abre iframe com o `file` da entrada

---

## Configuração do Azure

App Registration no Azure AD do tenant do grupo, com:

- **Plataforma:** Single-page application
- **Redirect URIs:**
  - `https://bq-analista.vercel.app/`
  - `http://localhost:3000/` (pra dev local)
- **Scopes solicitados:** `openid profile`
- **Claim usado como identidade:** `preferred_username` (email corporativo)

Variáveis de ambiente no Vercel (`vercel env`):
- `AZURE_CLIENT_ID` — Application (client) ID do App Registration
- `AZURE_TENANT_ID` — Directory (tenant) ID
- `SESSION_SECRET` — chave aleatória usada pra assinar o cookie (HMAC-SHA256)

---

## Convenções

- **Análises** sempre seguem o padrão `{brand}-{topic}-{YYYY-MM-DD}` no ID
- **Data** em ISO (`2026-04-18`); **período** em texto humano (`"11–17 abr 2026"`)
- **Tags** em minúsculas, curtas (`"ecommerce"`, `"produto"`, `"mtd"`)
- **Valores monetários** em BRL (`R$ 1.234,56`); **percentuais** com vírgula e 1 casa (`12,3%`)
- **Número real vs benchmark vs estimativa** tem que estar rotulado — ver `analyst principles.md` (Prime Directive)

---

## Arquivos de referência no repo

| Arquivo | Pra que serve |
|---|---|
| `SKILL.md` | Workflow completo de análise + publicação (lido pelo Claude em toda pergunta analítica) |
| `analyst principles.md` | Framework epistêmico (como lidar com incerteza, tier de dado, padrão de resposta) |
| `business-rules.md` | Regras de negócio — filtros padrão, fórmulas de KPI, cuidados |
| `schema.md` | Schema da tabela principal de vendas (colunas, tipos, semântica) |
| `identidade-visual-azzas.md` | Guia de estilo dos dashboards (cores, tipografia, tom) |
| `queries/` | Queries SQL reutilizáveis (ex: `venda_itens.sql`) |

## Exec dispatch via MCP (beta)

This repo also hosts Python MCP servers (um por domínio, em `agents/`) that lets Azzas executives run BigQuery analyses and publish dashboards to this portal directly from Claude Team on mobile, gated by Azure AD SSO + allowlist.

- Architecture spec: `docs/superpowers/specs/2026-04-18-exec-mcp-dispatch-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-21-multi-agent-monorepo.md`
- Shared core: `packages/mcp-core/`
- Agentes: `agents/<domain>/`

---

## Configuração dos agentes MCP

Cada agente (`agents/<domain>/`) é um MCP server que opera num escopo de dados específico. A configuração é dividida em **dois níveis**:

### Princípio: governança no repo, deployment no env

| Camada | Onde fica | Pra quê serve | Quem edita |
|---|---|---|---|
| **`config/settings.toml`** | Repo, checado em PR | **Governança** do agente: domínio, datasets permitidos, limites de query, retenção, TTLs de auth. Define o que o agente pode fazer. | Via PR review |
| **Env vars** | Railway (ou plist local) | **Deployment**: segredos, projetos GCP (billing e dados), identidade do commit do GitHub. Define onde e com quem o agente roda. | Via dashboard da plataforma |

**Regra de ouro:** se o valor muda entre dev e prod (ou precisa ficar em cofre), vai em env var. Se é uma regra de negócio que precisa ser auditável, vai no `settings.toml`.

### Precedência

Env var > `settings.toml` > default no código.

### Convenção de nomes

Env vars seguem `MCP_<SECTION>_<FIELD>` em UPPER_SNAKE_CASE, espelhando a estrutura do toml:

| `settings.toml` | Env var equivalente |
|---|---|
| `[bigquery] project_id` | `MCP_BQ_PROJECT_ID` |
| `[bigquery] billing_project_id` | `MCP_BQ_BILLING_PROJECT_ID` |
| `[github] author_email` | `MCP_GITHUB_AUTHOR_EMAIL` |

(Seções longas são abreviadas: `bigquery` → `BQ`.) A tabela exata de quais campos são sobrescrevíveis vive em `packages/mcp-core/src/mcp_core/settings.py` (`_ENV_OVERRIDES`). Para adicionar um novo campo sobrescrevível, acrescente uma linha lá.

### Modelo de projeto BigQuery: billing vs. dados

Dois projetos GCP **distintos**:

- **`project_id`** (dados): onde os datasets vivem (ex: `soma-pipeline-prd`). Usado na validação `allowed_datasets` — o dry-run bloqueia qualquer tabela fora de `project_id.allowed_datasets`.
- **`billing_project_id`** (billing): onde os jobs rodam e o custo é cobrado (ex: `soma-pipeline-dev`). Se ausente, cai em `project_id`.

A Service Account precisa de:
- `roles/bigquery.jobUser` no **billing project** (para criar jobs).
- `roles/bigquery.dataViewer` nos datasets do **data project** (para ler dados).

Essa separação permite centralizar billing/cota numa conta de sandbox enquanto a fonte de verdade continua em produção.

### Segredos — nunca no toml

Esses **sempre** ficam em env var, nunca no `settings.toml`:

- `MCP_BQ_SA_KEY` — JSON da Service Account (inline) ou caminho para o arquivo
- `MCP_AZURE_TENANT_ID`, `MCP_AZURE_CLIENT_ID`, `MCP_AZURE_CLIENT_SECRET`
- `MCP_JWT_SECRET`
- `GITHUB_TOKEN`

---

## Criando um novo agente MCP

### 1. Scaffold (1 comando)

```bash
scripts/new-agent.sh vendas-ecomm
```

Isso cria `agents/vendas-ecomm/` copiado de `vendas-linx`, com o `domain` ajustado e `allowed_datasets` vazio.

### 2. Configurar governança (no repo)

Edite os arquivos em `agents/vendas-ecomm/`:

- `config/settings.toml` → preencha `allowed_datasets` com os datasets que esse agente pode tocar.
- `config/allowed_execs.json` → lista de emails corporativos autorizados a chamar esse MCP.
- `src/agent/context/schema.md` → documente as tabelas (rode o protocolo PII do `CLAUDE.md` antes!).
- `src/agent/context/business-rules.md` → documente as regras de negócio do domínio.

Depois, da raiz do repo:

```bash
uv lock
```

### 3. Deploy no Railway

Crie um novo serviço apontando para este repo com:

- **Dockerfile path**: `agents/vendas-ecomm/Dockerfile`
- **Build context**: raiz do repo (`.`)
- **Branch**: `main`

**Variáveis de ambiente obrigatórias:**

| Variável | Exemplo | Descrição |
|---|---|---|
| `MCP_DOMAIN` | `vendas-ecomm` | Igual ao `domain` do `settings.toml`. Usado no fallback quando o toml não existe. |
| `MCP_BQ_PROJECT_ID` | `soma-pipeline-prd` | Projeto onde os datasets vivem. |
| `MCP_BQ_BILLING_PROJECT_ID` | `soma-pipeline-dev` | Projeto onde os jobs rodam (billing). |
| `MCP_BQ_SA_KEY` | `{"type":"service_account",...}` | JSON inline da SA (ou caminho para arquivo dentro do container). |
| `MCP_AZURE_TENANT_ID` | `...` | Azure AD tenant do grupo. |
| `MCP_AZURE_CLIENT_ID` | `...` | App Registration client ID. |
| `MCP_AZURE_CLIENT_SECRET` | `...` | Client secret do App Registration. |
| `MCP_JWT_SECRET` | (randômico ≥32 bytes) | Assinatura dos JWTs internos. |
| `GITHUB_TOKEN` | `ghp_...` | PAT com permissão de push no repo. |
| `GITHUB_REPO` | `abitlemos/bq-analista` | `owner/repo` para o entrypoint clonar. |

**Opcionais (defaults do `settings.toml`):**

| Variável | Override de |
|---|---|
| `MCP_GITHUB_AUTHOR_EMAIL` | `[github] author_email` — precisa bater com o dono do `GITHUB_TOKEN` |
| `MCP_GITHUB_AUTHOR_NAME` | `[github] author_name` |
| `MCP_GITHUB_BRANCH` | `[github] branch` |

### 4. Validar acesso à SA antes do deploy

Rode no ambiente do Railway para garantir que a SA consegue criar jobs no billing project:

```bash
railway run python3 - <<'EOF'
import os, json
raw = os.environ.get("MCP_BQ_SA_KEY", "").strip()
if not raw:
    print("❌ MCP_BQ_SA_KEY vazio")
else:
    info = json.loads(raw) if raw.startswith("{") else json.load(open(raw))
    print(f"SA: {info['client_email']}")
    print(f"SA project: {info['project_id']}")
    print(f"Billing (MCP_BQ_BILLING_PROJECT_ID): {os.environ.get('MCP_BQ_BILLING_PROJECT_ID')}")
    print(f"Data (MCP_BQ_PROJECT_ID): {os.environ.get('MCP_BQ_PROJECT_ID')}")
EOF
```

Se `bigquery.jobs.create` falhar, peça ao admin do projeto de billing:

```bash
gcloud projects add-iam-policy-binding <BILLING_PROJECT> \
  --member="serviceAccount:<SA_EMAIL>" \
  --role="roles/bigquery.jobUser"
```

E para cada dataset no data project:

```bash
bq add-iam-policy-binding \
  --member="serviceAccount:<SA_EMAIL>" \
  --role="roles/bigquery.dataViewer" \
  <DATA_PROJECT>:<DATASET>
```

### 5. Healthcheck

Depois do deploy, `GET /health` deve retornar 200. Logs do Railway mostram `Processing request of type ListToolsRequest` quando o Claude Team conecta.
