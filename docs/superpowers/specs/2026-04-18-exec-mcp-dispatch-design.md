# Acesso executivo via MCP — arquitetura de consulta sob demanda pelo celular

**Data**: 2026-04-18
**Autor**: Artur Lemos (com assistência de Claude)
**Status**: Design aprovado, aguardando plano de execução
**Contexto anterior**: Brainstorming na sessão de 2026-04-18 (02:14 GMT-3)

---

## 1. Contexto e problema

Hoje o portal `bq-analista` (Azzas 2154) já está publicado na Vercel e serve como *viewer* de análises. Toda interação de **geração** de análise acontece via repositório: o analista roda Claude Code localmente, consulta o BigQuery, gera o HTML, commita, a Vercel redeploya.

Isso não escala quando a intenção passa a ser **executivos pedindo análises sob demanda pelo celular**:

- Executivos não têm (nem vão ter) conta GitHub. Criar licenças só pra eles vira passivo de governança.
- Interação via repo exige clone, setup, disciplina de branches — fricção inviável pro caso de uso.
- Executivos **já têm** conta no workspace Claude Team da Azzas — essa licença é o ponto de entrada natural.

A visão: exec no celular → mensagem em linguagem natural no Claude Team → análise gerada → link Vercel no chat. Sem eles abrirem nenhum repositório.

## 2. Goals e non-goals

### Goals

- Exec pergunta no Claude mobile → dashboard HTML publicado na Vercel em <60s → link no chat.
- Identidade do exec preservada em três lugares: no Claude (conta dele), no BigQuery (audit log por email), no Git (commit attribution via metadata).
- Custo recorrente = licenças Claude Team que já existem. Sem consumir API key da Anthropic.
- Analista (Artur) mantém fluxo atual: repo local + Claude Code + dispatch próprio, inalterado.
- Dados financeiros tratados com rigor — allowlist explícita de execs, query sandbox, least-privilege credentials.

### Non-goals

- Não substituir o portal Vercel. Viewer continua o mesmo.
- Não substituir o fluxo do analista. Mac mini atende ambos, mas repo local continua canônico.
- Não abrir pra toda a empresa. Escopo restrito à lista de executivos autorizados.
- Não suportar análises arbitrárias de SQL no MVP — apenas o escopo coberto pelas tools expostas.

## 3. Por que MCP e não "dispatch puro"

Considerado e descartado durante brainstorming:

| Alternativa | Por que não |
|---|---|
| Claude Code dispatch com cada exec tendo repo próprio | Exec sem GitHub → provisionamento inviável |
| Claude Agent SDK via API | Custo por token, não por licença — escala mal com N execs curiosos |
| Bot Teams/WhatsApp na frente de um Agent SDK | Ambiente não é "do exec" — perde identidade no Claude e duplica UX de chat |
| Conta Claude compartilhada entre execs | Quebra rastreabilidade, viola política de conta individual |

**Escolhido**: MCP server hospedado em um Mac mini no escritório, exposto via HTTPS público, registrado como *custom connector* no workspace Claude Team Azzas. Cada exec autentica (OAuth Azure AD) e usa as tools do MCP a partir do Claude dele.

## 4. Arquitetura

### 4.1 Componentes

1. **Mac mini (escritório)** — always-on. Roda o serviço MCP, guarda credenciais (BQ SA, GitHub PAT) no Keychain, tem clone local do repo `bq-analista`.
2. **MCP Server** — serviço Node ou Python, em container Docker, atrás de `launchd`. Expõe as tools enumeradas abaixo.
3. **Cloudflare Tunnel** — conecta o MCP a um DNS público HTTPS (ex: `mcp-azzas.dominio-corporativo`) sem expor porta no firewall do escritório. WAF e rate limit no edge.
4. **Claude Team workspace Azzas** — conector MCP custom publicado uma vez; todos execs autorizados herdam.
5. **BigQuery** — SA dedicada do MCP, escopo mínimo. Jobs marcados com `labels: {exec_email: ...}` para audit.
6. **Repo `bq-analista`** (GitHub) — MCP escreve apenas em `analyses/<exec_email>/` e `library/<exec_email>.json`. Docs canônicos (SKILL.md, business-rules.md, schema.md, código) são read-only via escopo do PAT.
7. **Vercel** — inalterado. Auto-deploy a cada push.

### 4.2 Fluxo de uma pergunta

```
Exec (celular)
  │  "me dá venda da FARM ontem"
  ▼
Claude Team (app mobile)
  │  Claude mostra "analisando..." imediatamente
  │  Claude seleciona tools, gera SQL contextualizado
  ▼
MCP Server (via Cloudflare Tunnel → Mac mini)
  │  1. Valida token OAuth → resolve email do exec
  │  2. Checa allowlist → autoriza ou rejeita
  │  3. consultar_bq(sql): valida SELECT-only, max 5GB, timeout 60s, label com email
  │     └─ Envia progress: "querying BigQuery..."
  │  4. publicar_dashboard(...): grava HTML em analyses/<email>/, atualiza library/<email>.json
  │     └─ Envia progress: "rendering dashboard..."
  │  5. git add + commit (author = mcp-bot, message = "analise dispatched para <exec>") + push
  │     └─ Envia progress: "publishing to Vercel..."
  ▼
Vercel (auto-deploy)
  ▼
MCP retorna { link: "https://bq-analista.vercel.app/#analise-xyz", resumo: "...", duration_s: 180 }
  ▼
Claude responde no chat com resumo + link (total: ~3-5 min com feedback contínuo)
```

### 4.3 Tools expostas pelo MCP (contrato)

| Tool | Input | Output | Observação |
|---|---|---|---|
| `get_context` | — | conteúdo de `schema.md` + `business-rules.md` + lista de tabelas permitidas | Chamada uma vez no início da conversa pra priming |
| `consultar_bq` | `sql: string` | `{ rows, row_count, bytes_scanned, duration_ms }` ou progress stream | Valida: só `SELECT`/`WITH`, sem multi-statement, `maximum_bytes_billed=5GB`, timeout 60s, labels com exec_email. Pode retornar updates de progresso durante execução. |
| `listar_analises` | `escopo: "mine" \| "public"` | array de `{id, title, brand, date, link}` | Lê `library/<email>.json` ou `library/public.json` |
| `publicar_dashboard` | `{title, brand, period, description, html_content, tags}` | `{id, link, published_at}` ou progress | Grava em sandbox do exec, não toca docs nem código. Retorna progresso durante build e deploy. |

Claude do exec decide, em cada turno, quais tools chamar — baseado no system prompt do conector (que inclui uma versão enxuta do SKILL.md focada em executivos).

## 5. Segurança — 7 camadas

### 5.1 Autenticação

**Fluxo one-time**:

1. Exec roda `mcp-login` (CLI) localmente no seu device.
2. CLI abre browser → Azure AD login (SSO Azzas, MFA se configurado).
3. Azure AD retorna authorization code → CLI troca por token JWT via endpoint `/auth/token` do MCP.
4. Token é salvo em `~/.mcp/credentials.json` (permissão 600, owner only).
5. Claude chama MCP com token no header `Authorization: Bearer <token>`.

**Token lifecycle**:
- **TTL**: 30 minutos (curto, pra limitar window de compromise).
- **Refresh**: automático. Quando token próximo de expirar (5 min antes), MCP envia `refresh_token` no response. Claude ou exec client usa refresh endpoint (`/auth/refresh`) pra renovar sem re-autenticar.
- **Quando expira**: MCP retorna 401 com mensagem `"token expired, run: mcp-login"`. Claude orienta exec com clareza.

**Autenticação forte em tudo**:
- Azure AD é a fonte de verdade. Quando exec é demitido e removido do Entra ID, seu token continua válido por até 30 min (eventual consistency — aceitável pra analytics, não pra payment).
- MCP valida token via JWKS do Azure AD em **toda chamada** (não per-request, mas na autenticação inicial do token).

**Armazenamento local**:
- `~/.mcp/credentials.json` contém: `{ access_token, refresh_token, expires_at, user_email }`.
- Arquivo é lido apenas por Claude quando chama MCP (não exposto na web).
- Se device do exec é comprometido, attacker ganha acesso até token expirar. Mitigação: TTL curto + audit log rastreia IP + email.

### 5.2 Blast radius no BigQuery

- SA dedicada `mcp-exec-reader@...`, separada da SA do analista.
- IAM: `bigquery.jobUser` + `bigquery.dataViewer` **apenas** nos datasets `soma_online_refined.*` (ou o escopo mínimo necessário). Zero admin, zero billing, zero acesso a `raw_*`.
- `maximum_bytes_billed=5GB` setado em toda query. Previne "me dá tudo" de gerar custo inesperado.
- Validator de SQL: aceita só `SELECT` e CTEs (`WITH`). Rejeita DDL, DML, multi-statement, session variables, scripting.
- Timeout de query: 60s. Max rows retornadas: 100k (previne resposta absurda).
- Todo job marcado com `labels: {exec_email: "fulano@somagrupo.com.br", source: "mcp_dispatch"}` → audit log do BigQuery mostra quem perguntou o quê, mesmo com SA compartilhada.

### 5.3 Blast radius no repositório

- MCP escreve apenas em dois caminhos: `analyses/<exec_email>/` e `library/<exec_email>.json`. Qualquer tentativa de escrever fora é rejeitada antes do commit.
- GitHub PAT fine-grained, escopo restrito ao repo `bq-analista`, com permissão apenas de `contents: write`.
- Commit author configurado como `mcp-exec-bot <mcp@azzas.com.br>`, com commit message padronizado incluindo o email do exec — audit via `git log`.
- **Diferido ao MVP**: branch review (`exec-dispatched/<exec>` → analista aprova → merge em `main`). Liga se houver incidente de qualidade. Começa direto no `main`.

### 5.4 Audit & anomalias

- Log estruturado por chamada em SQLite local (`/var/mcp/audit.db`): `timestamp, exec_email, tool, sql, bytes_scanned, row_count, duration_ms, result, error`.
- Rotação: 90 dias local, backup diário criptografado pra Blob (Vercel Blob ou similar).
- Alertas simples (via script de verificação horária):
  - query única > 10GB
  - > 50 chamadas/hora por exec
  - email fora do allowlist tentou conectar
  - erro 5xx em > 5% das chamadas da última hora

### 5.5 Host (Mac mini)

- FileVault on. Atualizações automáticas de macOS.
- MCP em container Docker, user não-root, mount read-only exceto `analyses/` e `library/`.
- Secrets no Keychain do macOS, injetados no container via `launchd` no boot.
- `launchd` gerencia restart automático + health check.
- Sem acesso SSH público — administração via Tailscale no dispositivo pessoal do analista.

### 5.6 Edge

- Cloudflare Tunnel entre Mac mini e DNS público → WAF grátis, DDoS protection, rate limit no edge (100 req/min por IP).
- TLS automático via Cloudflare.
- Access Policy: só aceita chamadas do domínio `claude.ai` (CF Access rule por hostname ou header).

### 5.7 Allowlist

- Lista hardcoded de emails autorizados em `config/allowed_execs.json`, versionada no repo.
- Exec novo = PR no config + deploy. Fricção deliberada — impede que alguém "descubra" o conector.

## 6. Latência e feedback de progresso

Uma análise complexa pode levar 5+ minutos (BQ processing, rendering, deploy). Isso é **aceitável** se houver feedback contínuo:
- Claude mostra "analisando..." imediatamente após chamar MCP.
- MPC retorna progresso (`progress: "querying BigQuery..."`, `progress: "rendering dashboard..."`) durante a execução.
- Exec vê o trabalho acontecendo em real-time.

O critério de sucesso (seção 9) reflete isso: **latência observável com feedback claro**, não latência de resposta pura.

---

## 7. Decisões tomadas

| Decisão | Escolha |
|---|---|
| Primitivo de interação | MCP server (não dispatch puro, não Agent SDK) |
| Plano Claude | Claude Team Azzas (já existe) |
| Canal de retorno | Link no chat (sem push/email) |
| Exposição de rede | DNS público + Cloudflare Tunnel |
| Auth primária | One-time CLI login via Azure AD (OAuth code-grant) |
| Auth token | TTL 30 min + refresh automático, armazenado em `~/.mcp/credentials.json` |
| BQ auth | SA compartilhada + labels com exec_email (não per-exec credentials) |
| Escopo de escrita | `analyses/<exec>/` + `library/<exec>.json` apenas |
| Branch review pré-publicação | **Não** no MVP. Commit direto em main. |
| Observabilidade | Local (SQLite) no MVP. SIEM depois, se TI exigir. |

## 8. Decisões pendentes (abordar no plano de execução)

1. **Template de HTML**: criar `exec-template` novo mais enxuto (menos overlays técnicos, mais KPIs na cara) ou reaproveitar base dos dashboards atuais?
2. **Lista inicial de execs no allowlist**: a definir quando aproximar do rollout.
3. **Runtime MCP**: Node (mais maduro em MCP SDKs, mais conhecido do time) vs Python (mais próximo do ferramental BQ — `google-cloud-bigquery` é nativo). Recomendação preliminar: Python.
4. **Retention de audit log local**: 90 dias é suficiente ou precisa alinhar com política Azzas?
5. **SIEM/SOC**: se TI Azzas tem SOC centralizado, precisamos shippar logs pra lá? (pode ser fase 2)
6. **Progress streaming**: Como Claude recebe updates de progresso durante a execução (Server-Sent Events? Polling? LLM calls com conteúdo de log)? Define no plano.

## 9. Riscos

| Risco | Mitigação |
|---|---|
| Device do exec comprometido (malware rouба `~/.mcp/credentials.json`) | TTL 30 min limita window. Refresh automático + audit log rastreia IP anômalo. Entra ID desprovê exec quando demitido. |
| Token expirado e exec tira conclusão errada (acha que tá seguro operando) | Mensagem clara de erro (`"token expired, run: mcp-login"`). Documentar no onboarding que tokens expiram. |
| Multi-device: exec usa iPhone + Macbook, cada um precisa de `mcp-login` | Aceitável no MVP. Device novo = 2 min de setup. Sync de credentials é feature futura (OAuth + cloud storage). |
| Prompt injection (conteúdo adversarial em docs chegando ao Claude do exec) faz query maliciosa | Validator de SQL no MCP é última linha de defesa — bloqueia DDL/DML independente do que o Claude peça |
| SA do BQ comprometida via Mac mini | Keychain + rotação trimestral + alertas de volume anômalo. Escopo mínimo (read-only) limita impacto |
| Mac mini cai (queda de energia, update travado) | `launchd` auto-restart + UPS. Degradação é "exec vê erro", não "dado vazou" |
| Exec removido do Entra ID mas token local ainda válido | Eventual consistency — continua acessando por 30 min máximo. Aceitável pra analytics (não é payment). Monitor alertas no BigQuery por email fora do allowlist. |

## 10. Critérios de sucesso

MVP considerado pronto quando:

- 2 execs do allowlist usam em produção por 1 semana consecutiva sem intervenção do analista.
- Zero incidentes de autorização (sem exec não-autorizado conseguir chamar tools).
- Exec vê feedback claro de progresso ("analisando...") durante a execução.
- Análise é completada e link é publicado em < 5 min (com feedback em tempo real).
- Audit log do BigQuery mostra `exec_email` em 100% dos jobs originados do MCP.
- Portal Vercel renderiza dashboards dispatched sem mudança no frontend atual.
- Expiração de token é clara: exec vê mensagem de erro, sabe rodar `mcp-login` novamente.

## 11. O que fica de fora do MVP (backlog explícito)

- Branch review / aprovação humana antes de publicar.
- SIEM externo.
- Per-exec BigQuery credentials (em vez de SA + labels).
- Notificações push/email.
- UI de admin pra gerenciar allowlist sem deploy.
- Dashboard de observabilidade do próprio MCP (tempo de resposta, custos, taxa de erro).
- Suporte a mais workspaces Claude Team (outras empresas do grupo).
- Templates de análise (o exec escolhe "relatório semanal FARM" sem digitar nada).

---

## Próximo passo

Esse design vira um **plano de execução fase-a-fase** via skill `writing-plans`, com entregáveis, ordem de implementação, pontos de validação, e owner por tarefa. Execução futura — não agora.
