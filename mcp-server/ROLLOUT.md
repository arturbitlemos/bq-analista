# Exec MCP Dispatch — Rollout Checklist

Este documento é a ponte entre o **código mergeado em `main`** e o **serviço rodando no Mac mini atendendo execs reais**. Tudo aqui é operação, não código.

Docs canônicos relacionados:
- Arquitetura: `docs/superpowers/specs/2026-04-18-exec-mcp-dispatch-design.md`
- Plano de execução: `docs/superpowers/plans/2026-04-18-exec-mcp-dispatch.md`
- Runbook de integração E2E: `mcp-server/tests/integration/test_end_to_end.md`
- Setup Cloudflare Tunnel: `mcp-server/infra/cloudflare/README.md`
- Registro do connector Claude Team: `mcp-server/infra/claude-team/connector.md`

---

## 1. O que já existe no repo (pronto pra usar)

**Código**
- 4 MCP tools em Python 3.13: `get_context`, `consultar_bq`, `listar_analises`, `publicar_dashboard`
- Auth JWT com gate por allowlist + middleware de bearer token em todas as tools
- CLI `mcp-login` que faz o OAuth dance com Azure AD e grava `~/.mcp/credentials.json`
- Audit log SQLite, detector de anomalias horário, purga diária (90 dias)
- 57 testes unitários, todos verdes

**Infra**
- `mcp-server/Dockerfile` — Python 3.13-slim, user não-root, health check em `/health`
- 3 plists launchd em `mcp-server/infra/launchd/`:
  - `com.azzas.mcp.plist` — serviço principal, `KeepAlive=true`
  - `com.azzas.mcp.alerts.plist` — detector horário
  - `com.azzas.mcp.purge.plist` — purga diária 03:00
- `mcp-server/infra/deploy.sh` — rebuild imagem, renderiza plist com secrets do Keychain, `launchctl load`

---

## 2. Pré-produção — o que falta configurar no Mac mini

### 2.1. Keychain (6 secrets)

Rodar uma vez no Mac mini:

```bash
security add-generic-password -a mcp -s bq_sa_key          -w "$(cat path/to/bq-sa.json)"
security add-generic-password -a mcp -s github_pat         -w "<fine-grained PAT>"
security add-generic-password -a mcp -s azure_tenant_id    -w "<tenant uuid>"
security add-generic-password -a mcp -s azure_client_id    -w "<app uuid>"
security add-generic-password -a mcp -s azure_client_secret -w "<client secret>"
security add-generic-password -a mcp -s jwt_secret         -w "$(openssl rand -base64 48)"
```

`deploy.sh` falha com erro claro se algum deles estiver faltando.

### 2.2. Azure AD (Entra ID) app registration

1. Entra ID → App registrations → New registration.
2. Name: `Azzas MCP Dispatch`.
3. Supported account types: single tenant (Azzas).
4. Redirect URI: `http://localhost:8765/` (tipo "Public client/native", pro OAuth code grant do `mcp-login`).
5. Em "API permissions": adicionar `User.Read` (Microsoft Graph, delegated).
6. Em "Certificates & secrets": gerar client secret, anotar valor (só aparece uma vez).
7. Copiar tenant ID, client ID, client secret pro Keychain (passo 2.1).

### 2.3. BigQuery service account

1. No projeto GCP que hospeda `soma_online_refined`: criar SA `mcp-exec-reader@...`.
2. IAM: dar `roles/bigquery.jobUser` + `roles/bigquery.dataViewer` **apenas** no dataset `soma_online_refined` (não no projeto inteiro).
3. Gerar key JSON, colocar conteúdo no Keychain como `bq_sa_key`.
4. Rotação trimestral recomendada.

### 2.4. GitHub fine-grained PAT

1. GitHub → Settings → Developer settings → Fine-grained tokens.
2. Resource owner: sua conta. Repo access: apenas `bq-analista`.
3. Permissions: `Contents: Read and write`, `Metadata: Read-only`. Nada mais.
4. Copiar token pro Keychain como `github_pat`.

### 2.5. Diretórios no host

```bash
sudo mkdir -p /var/mcp /var/log/mcp /etc/mcp
sudo chown $(whoami) /var/mcp /var/log/mcp /etc/mcp
cp mcp-server/config/settings.example.toml /etc/mcp/settings.toml
cp mcp-server/config/allowed_execs.example.json /etc/mcp/allowed_execs.json
```

Editar `/etc/mcp/allowed_execs.json` com os emails dos execs aprovados.

### 2.6. Cloudflare Tunnel

Seguir `mcp-server/infra/cloudflare/README.md` (brew install cloudflared → login → create tunnel → DNS route → service install → WAF rule restringindo origin a `claude.ai`).

### 2.7. Deploy

```bash
cd ~/bq-analista/mcp-server
bash infra/deploy.sh
```

O script: rebuild imagem `mcp-azzas:latest` → lê Keychain → renderiza plist com secrets inline → `launchctl load`. Logs em `/var/log/mcp/stderr.log`.

Smoke test:
```bash
curl https://mcp-azzas.<corp-domain>/health
# → {"status":"ok"}
```

### 2.8. Registrar o connector no Claude Team

Seguir `mcp-server/infra/claude-team/connector.md`. URL do conector: `https://mcp-azzas.<corp-domain>/mcp`. Scope: grupo "Execs", não workspace inteiro.

### 2.9. Integration test manual

Rodar o runbook de 10 passos em `mcp-server/tests/integration/test_end_to_end.md`. Não liberar pra execs reais antes de todos os 10 passarem.

---

## 3. Onboarding de exec novo

1. PR adicionando email em `/etc/mcp/allowed_execs.json` (ou editar direto + reload se não quiser fricção).
2. Enviar PDF/instrução de uma página com:
   - Link pra baixar `mcp-login` (ou `uv run --directory mcp-server mcp-login` se tiver clone).
   - Rodar `mcp-login`, passar pelo SSO Azzas no browser.
   - "Token expira em 30 min; rodar `mcp-login` de novo se ver `token expired`."
3. Mandar queries de exemplo: `"venda da FARM ontem"`, `"resumo YTD por canal"`, `"lista minhas análises"`.

---

## 4. Operação rotineira

**Onde olhar:**
- Logs do serviço: `/var/log/mcp/stdout.log`, `stderr.log`.
- Audit SQLite: `sqlite3 /var/mcp/audit.db "SELECT * FROM audit ORDER BY ts DESC LIMIT 50"`.
- Alertas: `/var/log/mcp/alerts.log` (roda de hora em hora via launchd).
- BQ audit: `INFORMATION_SCHEMA.JOBS_BY_PROJECT` filtrando `labels.source = 'mcp_dispatch'`.

**Quando investigar:**
- Alert "huge_query" (>10 GiB) → olhar o SQL no audit, falar com o exec.
- Alert "high_call_rate" (>50/hora por exec) → possível loop ou abuso.
- Alert "high_error_rate" (>5% na última hora) → provavelmente bug ou dados quebrados.

**Deploy de mudança:**
- `git pull` no clone do Mac mini.
- `bash mcp-server/infra/deploy.sh` rebuilda imagem e reinicia serviço.

**Rotação de secret:**
- `security add-generic-password -U -a mcp -s <nome> -w "<novo valor>"` (`-U` atualiza).
- Rodar `deploy.sh` de novo pra injetar no plist.

---

## 5. Backlog explícito (fora do MVP)

Do spec §11, adiar pra pós-MVP:
- Branch review pré-publicação (exec-dispatched/<exec> → analista aprova → merge).
- SIEM externo (shipping de audit pra Grafana/Splunk).
- Per-exec BigQuery credentials em vez de SA compartilhada + labels.
- Notificações push/email (execs só recebem link no chat por enquanto).
- UI de admin pra gerenciar allowlist sem PR.
- Dashboard de observabilidade do próprio MCP (latência, custo BQ, erro rate).
- Suporte a outros workspaces Claude Team do grupo Azzas.
- Templates de análise ("relatório semanal FARM" sem digitar SQL).

---

## 6. Decisões intencionalmente adiadas que viram dívida técnica

Coisas flagadas nos code reviews que não foram corrigidas mas ficam registradas:

- **`allowed_datasets` em settings é documentário**, não código. Se quiser enforcement no Python (defesa em profundidade além do IAM), adicionar parser de SQL pra checar referências de tabela.
- **Sem validação de OAuth state** no `/auth/callback` — Azure AD já vincula code ao redirect_uri registrado, então o risco prático é pequeno, mas é boa prática adicionar.
- **Progress bar do `publicar_dashboard`** pula de 0% → 50% → 100% em sequência rápida (impl sync). UX correta exige refatorar o impl pra async ou streamar progresso de dentro.
- **`_build_bq_client`** e `load_settings` rodam a cada invocação de tool. Pra o volume esperado (execs curiosos, não alto throughput) isso não importa. Se virar gargalo, `functools.lru_cache`.

---

## 7. Como reverter / desligar

Emergência — parar de atender execs:

```bash
launchctl unload ~/Library/LaunchAgents/com.azzas.mcp.plist
```

O `/health` passa a falhar, Claude Team mostra "connector offline". Audit log e credenciais continuam intactos.

Rollback de versão:
```bash
cd ~/bq-analista && git checkout <commit-anterior>
bash mcp-server/infra/deploy.sh
```
