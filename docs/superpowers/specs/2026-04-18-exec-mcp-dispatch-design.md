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
  │  Claude seleciona tool, gera SQL contextualizado
  ▼
MCP Server (via Cloudflare Tunnel → Mac mini)
  │  1. Valida OAuth → resolve email do exec
  │  2. Checa allowlist → autoriza ou rejeita
  │  3. consultar_bq(sql): valida SELECT-only, max 5GB, timeout 60s, label com email
  │  4. publicar_dashboard(...): grava HTML em analyses/<email>/, atualiza library/<email>.json
  │  5. git add + commit (author = mcp-bot, message = "analise dispatched para <exec>") + push
  ▼
Vercel (auto-deploy)
  ▼
MCP retorna { link: "https://bq-analista.vercel.app/#analise-xyz", resumo: "..." }
  ▼
Claude responde no chat com resumo + link
```

### 4.3 Tools expostas pelo MCP (contrato)

| Tool | Input | Output | Observação |
|---|---|---|---|
| `get_context` | — | conteúdo de `schema.md` + `business-rules.md` + lista de tabelas permitidas | Chamada uma vez no início da conversa pra priming |
| `consultar_bq` | `sql: string` | `{ rows, row_count, bytes_scanned, duration_ms }` | Valida: só `SELECT`/`WITH`, sem multi-statement, `maximum_bytes_billed=5GB`, timeout 60s, labels com exec_email |
| `listar_analises` | `escopo: "mine" \| "public"` | array de `{id, title, brand, date, link}` | Lê `library/<email>.json` ou `library/public.json` |
| `publicar_dashboard` | `{title, brand, period, description, html_content, tags}` | `{id, link, published_at}` | Grava em sandbox do exec, não toca docs nem código |

Claude do exec decide, em cada turno, quais tools chamar — baseado no system prompt do conector (que inclui uma versão enxuta do SKILL.md focada em executivos).

## 5. Segurança — 7 camadas

### 5.1 Autenticação

- **OAuth 2.0 via Azure AD**. Claude Team MCP custom connector suporta OAuth no fluxo de conexão. Exec clica "conectar", autentica SSO Azzas, token chega no MCP. MCP valida via JWKS do Azure AD e extrai `email` / `upn`.
- **Se OAuth com Azure AD não for suportado** no momento da implementação, fallback: API key por exec, emitida pelo analista, armazenada no secret store do conector. Rotação trimestral obrigatória. Menos robusto (sem desprovisionamento quando alguém sai), mas aceitável como interim.

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

## 6. Decisões tomadas

| Decisão | Escolha |
|---|---|
| Primitivo de interação | MCP server (não dispatch puro, não Agent SDK) |
| Plano Claude | Claude Team Azzas (já existe) |
| Canal de retorno | Link no chat (sem push/email) |
| Exposição de rede | DNS público + Cloudflare Tunnel |
| Auth primária | OAuth Azure AD; fallback API key per exec |
| BQ auth | SA compartilhada + labels com exec_email (não per-exec credentials) |
| Escopo de escrita | `analyses/<exec>/` + `library/<exec>.json` apenas |
| Branch review pré-publicação | **Não** no MVP. Commit direto em main. |
| Observabilidade | Local (SQLite) no MVP. SIEM depois, se TI exigir. |

## 7. Decisões pendentes (abordar no plano de execução)

1. **Template de HTML**: reaproveitar template base dos dashboards atuais ou criar `exec-template` mais enxuto (menos overlays técnicos, mais KPIs na cara)?
2. **Lista inicial de execs no allowlist**: a definir quando aproximar do rollout.
3. **Runtime MCP**: Node (mais maduro em MCP SDKs, mais conhecido do time) vs Python (mais próximo do ferramental BQ — `google-cloud-bigquery` é nativo). Recomendação preliminar: Python.
4. **Retention de audit log local**: 90 dias é suficiente ou precisa alinhar com política Azzas?
5. **SIEM/SOC**: se TI Azzas tem SOC centralizado, precisamos shippar logs pra lá? (pode ser fase 2)

## 8. Riscos

| Risco | Mitigação |
|---|---|
| Claude Team MCP custom connector pode não suportar OAuth com Azure AD em abril/2026 | Verificar como primeiro passo do plano. Se não suportar, fallback API key + plano B de provisionamento |
| Prompt injection (conteúdo adversarial em docs chegando ao Claude do exec) faz query maliciosa | Validator de SQL no MCP é última linha de defesa — bloqueia DDL/DML independente do que o Claude peça |
| SA do BQ comprometida via Mac mini | Keychain + rotação trimestral + alertas de volume anômalo. Escopo mínimo (read-only) limita impacto |
| Mac mini cai (queda de energia, update travado) | `launchd` auto-restart + UPS. Degradação é "exec vê erro", não "dado vazou" |
| Exec "expulsa" da empresa continua acessando | OAuth Azure AD → desprovisionamento imediato. Com API key, depende do analista revogar — daí a preferência por OAuth |

## 9. Critérios de sucesso

MVP considerado pronto quando:

- 2 execs do allowlist usam em produção por 1 semana consecutiva sem intervenção do analista.
- Zero incidentes de autorização (sem exec não-autorizado conseguir chamar tools).
- Latência p95 (mensagem → link no chat) ≤ 60s.
- Audit log do BigQuery mostra `exec_email` em 100% dos jobs originados do MCP.
- Portal Vercel renderiza dashboards dispatched sem mudança no frontend atual.

## 10. O que fica de fora do MVP (backlog explícito)

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
