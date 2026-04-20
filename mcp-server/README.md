# mcp-exec

MCP server que permite executivos da Azzas rodarem análises no BigQuery e publicarem dashboards via Claude.

## Dois caminhos de uso

| | Claude Team (web) | Claude Desktop |
|---|---|---|
| **Quem usa** | ~90% dos usuários | Devs / power users |
| **Onde roda** | Railway (cloud) | Mac mini (local) |
| **Transporte** | SSE via HTTPS | stdio (bridge local) |
| **Auth** | Azure AD SSO | Mesmo SSO via bridge |
| **Setup do usuário** | Nenhum — já está no Claude Team | Instalar bridge localmente |

---

## Caminho A — Claude Team via Railway

### 1. Pré-requisitos

- Conta no Railway linkada a este repo GitHub
- Azure AD app registration (single-tenant)
- BigQuery service account JSON com `roles/bigquery.jobUser` + `roles/bigquery.dataViewer`
- GitHub fine-grained PAT com permissão Contents R/W no repo `bq-analista`

### 2. Variáveis de ambiente no Railway

Configure no dashboard Railway → **Variables**:

| Variável | Descrição |
|---|---|
| `MCP_AZURE_TENANT_ID` | UUID do tenant Azure AD |
| `MCP_AZURE_CLIENT_ID` | UUID do app Azure AD |
| `MCP_AZURE_CLIENT_SECRET` | Client secret do app Azure AD |
| `MCP_JWT_SECRET` | Chave JWT — gere com `openssl rand -hex 32` |
| `MCP_BQ_PROJECT_ID` | GCP project ID (ex: `soma-online-refined`) |
| `MCP_BQ_SA_KEY` | Conteúdo completo do JSON da service account BQ |
| `MCP_ALLOWED_EMAILS` | Emails autorizados, separados por vírgula |
| `MCP_GITHUB_PAT` | Fine-grained PAT do GitHub |
| `MCP_AZURE_REDIRECT_URI` | `https://<seu-railway-url>/auth/callback` |

Opcionais (com defaults):

| Variável | Default | Descrição |
|---|---|---|
| `MCP_BQ_MAX_BYTES_BILLED` | `5000000000` | Limite de scan (5 GB) |
| `MCP_BQ_QUERY_TIMEOUT_S` | `60` | Timeout de query em segundos |
| `MCP_BQ_MAX_ROWS` | `100000` | Máximo de linhas retornadas |
| `MCP_GITHUB_AUTHOR_EMAIL` | `mcp@azzas.com.br` | Email do autor nos commits |
| `MCP_AUDIT_DB_PATH` | `/var/mcp/audit.db` | Caminho do SQLite de auditoria |

> `PORT` é injetado automaticamente pelo Railway — não precisa configurar.

### 3. Deploy

Railway detecta o `Dockerfile` e faz deploy automático a cada push na `main`.

Após o primeiro deploy:

```bash
# Verificar saúde
curl https://<seu-railway-url>/health
# → {"status":"ok"}
```

### 4. Azure AD — configuração do app

No Azure Portal → App Registrations:

- **Tipo**: Single-tenant
- **Redirect URI**: `https://<seu-railway-url>/auth/callback`
- **Permissão**: `User.Read` (Microsoft Graph, delegated)

### 5. Registrar no Claude Team

1. Claude Team → **Settings** → **Integrations** → **Add MCP server**
2. URL: `https://<seu-railway-url>/mcp`
3. Auth: **OAuth** — usuários serão redirecionados ao Azure AD no primeiro uso

Pronto. Os executivos só precisam aceitar o login Azure AD uma vez; o token é renovado automaticamente.

### 6. Cron jobs (Railway)

O Railway não roda múltiplos processos por serviço. Configure como **Railway Cron Jobs** separados apontando para a mesma imagem:

| Schedule | Comando | Finalidade |
|---|---|---|
| `0 * * * *` | `python -m mcp_exec.alerts` | Detecção de anomalias (exit 1 = alerta) |
| `0 3 * * *` | `python scripts/purge_audit.py` | Limpeza de auditoria (retenção 90 dias) |

---

## Caminho B — Claude Desktop (bridge local)

Para quem quer usar o servidor remoto via Claude Desktop (app de desktop), há um bridge stdio que faz o SSO automaticamente.

### 1. Instalar o bridge

```bash
cd mcp-server
uv sync --all-extras
```

Ou instalar o pacote direto:

```bash
pip install -e .
```

### 2. Configurar o Claude Desktop

Edite `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-exec-azzas": {
      "command": "mcp-exec-bridge",
      "env": {
        "MCP_SERVER_URL": "https://<seu-railway-url>"
      }
    }
  }
}
```

Se o servidor ainda estiver rodando local (Mac mini + Cloudflare Tunnel), troque a URL pelo domínio do túnel.

### 3. Primeiro login

Na primeira vez que Claude Desktop tentar usar uma ferramenta MCP:

1. O bridge abre o browser em `https://<seu-railway-url>/auth/start`
2. Usuário faz login com conta Azure AD corporativa
3. Tokens são salvos em `~/.mcp/credentials.json` (modo 0600)
4. Sessão é renovada automaticamente (refresh a cada 30 min, válido por 30 dias)

---

## Desenvolvimento local

```bash
cd mcp-server
uv sync --all-extras

# Configs locais
cp config/settings.example.toml config/settings.toml
cp config/allowed_execs.example.json config/allowed_execs.json
# Edite allowed_execs.json com seu email

# Rodar sem Azure AD (dev)
export MCP_REPO_ROOT=/caminho/para/bq-analista
uv run mcp-exec-dev

# Health check
curl http://localhost:3000/health

# Token de dev (endpoint só existe no dev server)
TOKEN=$(curl -s "http://localhost:3000/auth/issue-token?email=seu@email.com" | jq -r .access_token)

# Chamar uma ferramenta
curl -H "Authorization: Bearer $TOKEN" http://localhost:3000/mcp/tools/get_context
```

### Testes

```bash
uv run pytest          # 57 testes unitários
```

Para o runbook de testes de integração end-to-end, veja `tests/integration/test_end_to_end.md`.

---

## Segurança

- **Allowlist de emails**: só emails em `allowed_execs.json` (prod) ou `MCP_ALLOWED_EMAILS` (Railway) podem chamar ferramentas
- **SQL read-only**: todas as queries passam por validação antes de ir ao BigQuery
- **Auditoria**: cada chamada de ferramenta é registrada em SQLite com email, SQL, bytes e duração
- **JWT**: tokens com TTL de 30 min, refresh de 30 dias, assinados com HS256

## Arquitetura

```
Claude (web/desktop)
    │
    ├── [Team] HTTPS SSE → Railway → FastAPI (server.py)
    │                                    ├── /auth/*  (Azure AD OAuth)
    │                                    ├── /mcp/*   (MCP tools via SSE)
    │                                    └── /health
    │
    └── [Desktop] stdio → bridge.py → HTTPS SSE → mesmo servidor
```

Para a arquitetura completa, veja `docs/superpowers/specs/2026-04-18-exec-mcp-dispatch-design.md`.
