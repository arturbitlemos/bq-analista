# Multi-Agent Monorepo — Design Spec

**Data:** 2026-04-21  
**Status:** Aprovado

---

## Contexto

O repositório `bq-analista` hoje tem um único MCP server (`mcp-server/`) que serve o domínio `vendas-linx` (dataset `silver_linx`). O objetivo é transformar o repo em uma plataforma multi-agente onde cada domínio analítico (ecommerce, atacado, compras, operações, etc.) tem deploy independente, regras de negócio específicas e acesso a tabelas específicas, compartilhando infraestrutura de segurança e contexto de dimensões comuns.

---

## Decisões de design

| Questão | Decisão |
|---|---|
| Eixo de separação | Domínios analíticos (não marcas) |
| Isolamento de deploy | Um Railway service por agente |
| Estrutura de repo | Monorepo com pacote compartilhado (`mcp-core`) |
| Compartilhamento de código | `packages/mcp-core/` via workspace `uv` |
| Compartilhamento de contexto | `shared/context/` — princípios, PII, dimensões |
| Template de novo agente | Script `scripts/new-agent.sh` (não cópia manual) |

---

## Estrutura de diretórios

```
bq-analista/
│
├── packages/
│   └── mcp-core/
│       ├── pyproject.toml
│       └── src/mcp_core/
│           ├── auth_middleware.py
│           ├── auth_routes.py
│           ├── azure_auth.py
│           ├── jwt_tokens.py
│           ├── allowlist.py
│           ├── audit.py
│           ├── bq_client.py        ← enforcement de allowed_datasets aqui
│           ├── sql_validator.py
│           ├── git_ops.py
│           ├── library.py
│           ├── sandbox.py
│           ├── settings.py         ← inclui campo domain em [server]
│           ├── context_loader.py   ← aceita shared_root + agent_root
│           └── server_factory.py   ← build_mcp_app() — novo
│
├── shared/
│   └── context/
│       ├── analyst-principles.md   ← movido da raiz
│       ├── pii-rules.md            ← extraído do CLAUDE.md
│       └── dimensions/
│           ├── produto.md
│           ├── filiais.md
│           └── colecao.md
│
├── agents/
│   ├── vendas-linx/                ← mcp-server/ migrado
│   │   ├── Dockerfile
│   │   ├── railway.toml
│   │   ├── pyproject.toml
│   │   ├── config/
│   │   │   ├── settings.toml
│   │   │   └── allowed_execs.json
│   │   ├── tests/
│   │   └── src/agent/
│   │       ├── server.py
│   │       └── context/
│   │           ├── schema.md
│   │           └── business-rules.md
│   ├── vendas-ecomm/
│   ├── atacado/
│   └── compras/
│
├── portal/                         ← raiz atual migrada
│   ├── index.html
│   ├── api/
│   ├── public/
│   ├── analyses/
│   │   └── <domain>/
│   │       └── <email>/
│   ├── library/
│   │   └── <domain>/
│   └── vercel.json
│
├── scripts/
│   └── new-agent.sh                ← gera agente a partir do estado atual
│
├── pyproject.toml                  ← workspace uv
└── CLAUDE.md                       ← inclui seção "Como criar um novo agente"
```

---

## `packages/mcp-core/`

Contém toda a infraestrutura compartilhada entre agentes. Nenhum agente reimplementa auth, audit, BQ client ou SQL validation — qualquer mudança nessa camada propaga automaticamente via workspace `uv`.

### `context_loader.py` — interface revisada

```python
def load_exec_context(agent_root: Path, shared_root: Path) -> ExecContext:
    """
    Merge de duas camadas:
    - shared_root/analyst-principles.md
    - shared_root/pii-rules.md
    - shared_root/dimensions/*.md
    - agent_root/context/schema.md
    - agent_root/context/business-rules.md
    """
```

### `bq_client.py` — enforcement de allowed_datasets

Antes de executar qualquer query, o cliente extrai os datasets referenciados no SQL e valida contra `settings.bigquery.allowed_datasets`. Queries fora do escopo retornam erro sem atingir o BigQuery. Este enforcement é pré-requisito para criar novos agentes.

### `server_factory.py` — novo helper

```python
def build_mcp_app(agent_name: str) -> tuple[FastMCP, Callable]:
    """
    Lê MCP_PUBLIC_HOST, MCP_JWT_SECRET e settings.toml.
    Registra as 4 ferramentas base: get_context, consultar_bq,
    publicar_dashboard, listar_analises.
    Retorna (app, main) — app para registrar ferramentas extras,
    main para o entrypoint.
    """
```

### `settings.py` — campo `domain`

```toml
[server]
domain = "vendas-linx"   # novo campo obrigatório
```

Usado por `git_ops.py` e `sandbox.py` para rotear commits e arquivos para `analyses/<domain>/` e `library/<domain>/`.

---

## Anatomia de um agente

### Dependências (`pyproject.toml`)

```toml
[project]
name = "agent-<dominio>"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["mcp-core"]

[tool.uv.sources]
mcp-core = { workspace = true }
```

### Configuração (`config/settings.toml`)

Os únicos campos que variam por agente:

```toml
[server]
domain = "vendas-ecomm"

[bigquery]
allowed_datasets = ["silver_ecomm"]
```

### `server.py` — interface mínima

```python
from mcp_core.server_factory import build_mcp_app

app, main = build_mcp_app(agent_name="mcp-exec-<dominio>")

# ferramentas extras do domínio (opcional)

if __name__ == "__main__":
    main()
```

### Docker — build context é a raiz do repo

```dockerfile
FROM python:3.13-slim
COPY . /workspace
WORKDIR /workspace/agents/<dominio>
RUN pip install uv && uv sync --frozen
CMD ["uv", "run", "python", "-m", "agent.server"]
```

Railway configurado por service: Dockerfile path = `agents/<dominio>/Dockerfile`, build context = `.`.

---

## Isolamento de analyses e library

Cada agente escreve exclusivamente em:
- `portal/analyses/<domain>/<email>/`
- `portal/library/<domain>/<email>.json`

Sem sobreposição entre agentes. Colisão de git dentro do mesmo agente continua sequencial — igual ao comportamento atual.

---

## Workspace uv

```toml
# pyproject.toml raiz
[tool.uv.workspace]
members = ["packages/mcp-core", "agents/*"]
```

O glob `agents/*` inclui automaticamente novos agentes sem edição manual.

---

## Testes por camada

| Camada | Localização | O que cobre |
|---|---|---|
| `mcp-core` | `packages/mcp-core/tests/` | auth, sql_validator, bq_client, context_loader |
| Agente | `agents/<dominio>/tests/` | ferramentas específicas, schema, get_context do domínio |

Os 15+ testes atuais em `mcp-server/tests/` são migrados: a maioria vai para `mcp-core/tests/`, os específicos de vendas-linx ficam em `agents/vendas-linx/tests/`.

---

## Migração do agente atual

A migração de `mcp-server/` é o passo mais arriscado e precede tudo. Ordem:

1. Criar `packages/mcp-core/` e mover módulos (sem alterar imports ainda)
2. Atualizar todos os imports `mcp_exec` → `mcp_core` (15+ arquivos)
3. Mover `mcp-server/` → `agents/vendas-linx/`
4. Validar testes no novo path
5. Atualizar Railway service existente (Dockerfile path + build context)
6. Mover raiz Vercel → `portal/` e reconfigurar "Root Directory = portal" no painel Vercel
7. Validar deploy em produção antes de criar qualquer agente novo

---

## Vercel — reconfiguração necessária

Com `portal/` como subdiretório, o projeto Vercel precisa de:
- **Root Directory:** `portal`

Isso causa um redeploy. Planejar janela de manutenção ou garantir que a mudança seja atômica com o commit que move os arquivos.

---

## Fora do escopo deste plano

O portal (`portal/index.html`) lê `library/<email>.json` (estrutura atual). Com múltiplos domínios em `library/<domain>/`, o frontend precisará de navegação por domínio. Isso é trabalho independente, não bloqueante para criar novos agentes, mas registrado como pendente.

---

## Guia: como criar um novo agente

> **Pré-requisito:** a migração inicial (`mcp-server/` → `mcp-core` + `agents/vendas-linx/`) deve estar concluída.

**Passo 0 — Gere o agente com o script**

```bash
scripts/new-agent.sh <seu-dominio>
```

Não use `cp -r` — o script garante que a cópia parte do estado atual do repo.

**Passo 1 — Edite os 6 arquivos obrigatórios**

| Arquivo | O que mudar |
|---|---|
| `pyproject.toml` | `name` (já atualizado pelo script) |
| `config/settings.toml` | `domain`, `allowed_datasets` |
| `config/allowed_execs.json` | Emails autorizados |
| `src/agent/context/schema.md` | Tabelas, colunas, PKs, joins |
| `src/agent/context/business-rules.md` | Regras de negócio |
| `src/agent/server.py` | Ferramentas extras (pode ficar vazio) |

Dimensões compartilhadas (produto, filial, coleção): referencie `shared/context/dimensions/`, não duplique.  
PII: classifique cada coluna antes de escrever o schema. Colunas PII não entram.

**Passo 2 — Teste localmente**

```bash
gcloud auth application-default login   # obrigatório

cd agents/<seu-dominio>
uv sync
MCP_DEV_EXEC_EMAIL=seu@somagrupo.com.br \
MCP_JWT_SECRET=dev-secret \
MCP_REPO_ROOT=../../portal \
uv run python -m agent.server
```

Verifique:
1. `get_context` retorna schema do domínio + princípios compartilhados
2. Query válida em `allowed_datasets` executa
3. Query fora do `allowed_datasets` retorna erro **sem** `billed_bytes` nos logs

**Passo 3 — Escreva testes**

- Bug no core → `packages/mcp-core/tests/`
- Comportamento específico do agente → `agents/<dominio>/tests/`

**Passo 4 — Configure o Railway service**

1. Novo service apontando para este repo
2. Build: Dockerfile path = `agents/<dominio>/Dockerfile`, build context = `.`
3. Variáveis de ambiente:

| Variável | Instrução |
|---|---|
| `MCP_JWT_SECRET` | `openssl rand -hex 32` — nunca reutilize |
| `MCP_PUBLIC_HOST` | URL do Railway após primeiro deploy |
| `MCP_AZURE_TENANT_ID` | Mesmo do agente existente |
| `MCP_AZURE_CLIENT_ID` | Mesmo do agente existente |
| `MCP_AZURE_CLIENT_SECRET` | Mesmo do agente existente |
| `MCP_GIT_PUSH` | `1` |
| `MCP_SETTINGS` | `/app/config/settings.toml` |
| `MCP_ALLOWLIST` | `/app/config/allowed_execs.json` |

4. Após Railway gerar a URL, atualize `MCP_PUBLIC_HOST` e redeploy.

**Passo 5 — Emita token para o usuário**

```bash
cd agents/<seu-dominio>
uv run python scripts/issue_long_lived_token.py --email usuario@somagrupo.com.br
```

**Passo 6 — Registre no Claude.ai**

- URL: `https://<MCP_PUBLIC_HOST>/mcp`
- Header: `Authorization: Bearer <token>`
- Teste com `get_context` para confirmar contexto do domínio.

**O que NÃO fazer**

- Não use `cp -r` — use `scripts/new-agent.sh`
- Não reimplemente auth, audit ou SQL validation no agente
- Não duplique dimensões compartilhadas
- Não reutilize `MCP_JWT_SECRET`
- Não suba sem validar enforcement de `allowed_datasets` (Passo 2, item 3)
