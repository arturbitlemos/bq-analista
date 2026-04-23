# DXT Desktop Client — Design Spec

**Data:** 2026-04-23
**Status:** Em design — aguardando revisão
**Escopo:** Cliente Claude Desktop (`.dxt`) pra consumir os agentes MCP do grupo Azzas, com autenticação corporativa via Azure AD e distribuição pelo portal `analysis-lib.vercel.app`.

---

## 1. Motivação e requisitos

Hoje os agentes MCP vivem na Railway como servidores HTTP. A única forma confiável de um usuário final consumi-los com OAuth per-user é via Claude Code CLI, porque o cliente de connectors do `claude.ai` (web + mobile via Team) tem bug aberto (`anthropics/claude-ai-mcp#155`) que impede anexar o Bearer token após o OAuth — logo, não é opção pra rollout.

**Requisitos:**

1. Zero dependência técnica no PC do usuário (sem Python, sem CLI, sem `git clone`)
2. Cross-platform: macOS e Windows, com prioridade pra Windows
3. Autenticação per-user via Azure AD (tenant corporativo), não chave estática
4. Onboarding claro e auto-suficiente, hospedado no portal existente
5. Atualizações e troubleshooting sem envolver TI

**Não-requisitos (v1):**

- Não valida allowlist per-agente no DXT — cada agente na Railway continua fazendo seu próprio `allowed_execs` check
- Sem UI de gerenciamento (gerir usuários continua via PR no `allowed_execs.json` de cada agente)
- Sem métricas ou dashboards de uso embutidos

## 2. Arquitetura geral

```
Usuário (Mac / Windows)
 ├─ Browser → portal analysis-lib.vercel.app
 │    - /onboarding   (SPA, atrás do SSO)
 │    - /download/azzas-mcp-<version>.dxt
 │    - /api/mcp/auth/start + /callback + /refresh
 │    - /api/mcp/agents + /api/mcp/version
 │
 └─ Claude Desktop → azzas-mcp.dxt (stdio MCP server)
      - Fetch dinâmico do manifesto
      - OAuth loopback na primeira vez / após 7 dias de inatividade
      - Forward HTTPS com Bearer JWT pros agentes Railway

Agentes Railway (Python, mcp-core)
 ├─ vendas-linx   /mcp, verifica JWT + allowed_execs
 ├─ vendas-ecomm  (planejado)
 └─ (futuros)

Azure AD (tenant Azzas)
```

Todos os agentes Railway e o endpoint de auth no Vercel compartilham `MCP_JWT_SECRET`, de forma que um JWT emitido pelo portal é aceito por qualquer agente.

## 3. Componentes

### 3.1 `packages/mcp-client-dxt/` (novo)

Cliente TypeScript/Node, buildado como `.dxt` (zip com `manifest.json` + JS bundled + `node_modules`).

```
packages/mcp-client-dxt/
├── manifest.json           # manifest DXT (Anthropic spec)
├── package.json
├── tsconfig.json
├── icon.png
├── src/
│   ├── index.ts            # entry stdio MCP server
│   ├── auth.ts             # OAuth loopback + credentials.json
│   ├── manifest.ts         # fetch /api/mcp/agents + cache
│   ├── router.ts           # tool routing: prefixo → agent
│   ├── forward.ts          # HTTPS call com Bearer
│   ├── paths.ts            # cross-platform homedir
│   ├── version.ts          # check min_dxt_version
│   └── errors.ts           # mensagens padronizadas
└── tests/
    ├── auth.test.ts
    ├── router.test.ts
    ├── forward.test.ts
    └── version.test.ts
```

**Stack:** Node 20, `@modelcontextprotocol/sdk`, `open`, `undici`. Build com `esbuild` em bundle único.

**Credenciais persistidas** em `{homedir}/.mcp/credentials.json` (modo 0600 em Unix; Windows usa ACL padrão do `USERPROFILE`):

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt refresh>",
  "access_expires_at": "2026-04-23T14:30:00Z",
  "refresh_expires_at": "2026-04-30T14:00:00Z",
  "email": "fulano@somagrupo.com.br",
  "server": "https://analysis-lib.vercel.app"
}
```

### 3.2 Rotas Vercel em `portal/api/mcp/` (novo)

```
portal/api/mcp/
├── auth/
│   ├── start.js        # GET  → 302 Azure AD /authorize
│   ├── callback.js     # GET  → code exchange → mint JWT → 302 loopback
│   └── refresh.js      # POST → refresh JWT → novo access
├── agents.js           # GET  → manifesto JSON
└── version.js          # GET  → { latest, min }
```

**Azure App Registration:** reusa a App do portal, adicionando `AZURE_CLIENT_SECRET` no env Vercel (hoje é SPA public client; vira confidential client). Redirect URIs adicionados: `https://analysis-lib.vercel.app/api/mcp/auth/callback`.

**Validações no callback:**

- `tid` (tenant id) do id_token bate com `AZURE_TENANT_ID`
- `state` assinado via HMAC-SHA256 com `SESSION_SECRET` do portal (cookie `mcp_oauth_state`, HttpOnly, SameSite=Lax, TTL 10min)
- `redirect_uri` é loopback (`http://localhost:PORT/cb` com PORT ∈ [8765, 8799])

**Tratamento de erro no callback:** se qualquer validação falhar (tenant errado, state inválido, code rejeitado), Vercel redireciona pro loopback com `?error=<code>&error_description=<msg>` em vez de tokens. Lista de códigos: `wrong_tenant`, `invalid_state`, `invalid_code`, `azure_error`. DXT captura no loopback e traduz pra mensagem específica no chat.

**JWT claims emitidos:**

- Access (HS256, TTL 30min): `{ sub: email, email, tid, iat, exp, typ: "access" }`
- Refresh (HS256, TTL 7d): `{ sub: email, email, tid, iat, exp, typ: "refresh", jti: <uuid> }`

Refresh **não rotaciona** — a política é simplicidade. Pode ser revisada se aparecer requisito de segurança.

**`agents.js`** retorna constante TypeScript compilada:

```json
{
  "min_dxt_version": "1.0.0",
  "agents": [
    {
      "name": "vendas-linx",
      "label": "Vendas Linx",
      "url": "https://vendas-linx-prd.railway.app",
      "tools": ["get_context", "consultar_bq", "publicar_dashboard", "listar_analises"]
    }
  ]
}
```

Adicionar agente = PR editando essa constante = deploy Vercel.

**`version.js`** retorna `{ "latest": "1.3.0", "min": "1.0.0" }`, também constante versionada.

### 3.3 Página `/onboarding` e download

```
portal/
├── onboarding.html
├── public/downloads/
│   └── azzas-mcp-1.0.0.dxt
└── api/
    └── download-dxt.js      # redirect pra arquivo versionado
```

`middleware.js` é estendido pra proteger `/onboarding` e `/api/mcp/version` e `/api/mcp/agents` com SSO; `/api/mcp/auth/*` fica público (Azure precisa redirecionar pra lá sem cookie de sessão do portal).

### 3.4 Ajuste em `packages/mcp-core/` (mínimo)

Nenhuma mudança destrutiva. O Python continua emitindo e verificando JWTs com o mesmo formato. A garantia é testada via teste de interoperabilidade (ver §7).

Endpoints `/auth/start` e `/auth/callback` dos agentes Python ficam como **legacy** (para o `cli_login.py` existente) e podem ser removidos num release posterior.

## 4. Fluxos de autenticação

### 4.1 Primeiro uso (sem credenciais)

1. User pede tool no Claude Desktop (ex: `vendas_linx__consultar_bq`)
2. DXT tenta ler `~/.mcp/credentials.json` → arquivo não existe
3. DXT sobe HTTP loopback server em porta livre de [8765..8799], rota `/cb`
4. DXT abre browser em `https://analysis-lib.vercel.app/api/mcp/auth/start?redirect_uri=http://localhost:PORT/cb&state=<HMAC>`
5. Vercel `auth/start` valida, seta cookie `mcp_oauth_state`, 302 pra Azure AD `/authorize` (response_type=code, scope=openid+profile+email)
6. User loga (ou SSO click-through)
7. Azure 302 pra `/api/mcp/auth/callback?code=...`
8. Vercel `callback`: valida cookie/state, troca code por id_token (confidential client), valida `tid`, emite access+refresh JWT
   - Se qualquer validação falhar: 302 pra `http://localhost:PORT/cb?error=<code>&error_description=<msg>`
9. Em caso de sucesso: 302 pra `http://localhost:PORT/cb?access=...&refresh=...&access_exp=...&refresh_exp=...&email=...`
10. Loopback DXT captura, salva `credentials.json` (0600), encerra
11. DXT devolve ao tool call original **erro amigável**: "🔐 Autenticação concluída. Por favor, faça sua pergunta novamente."
12. User repete, DXT executa tool normalmente

### 4.2 Uso recorrente (access expirado, refresh válido)

1. DXT detecta `access_expires_at < now`
2. POST `https://analysis-lib.vercel.app/api/mcp/auth/refresh` com header `Authorization: Bearer <refresh_jwt>`
3. Vercel valida signature, `typ=refresh`, `exp`, `tid`
4. Vercel emite novo access JWT (refresh não rotaciona)
5. DXT atualiza `credentials.json`, prossegue com tool call
6. **Invisível pro usuário**

### 4.3 Refresh expirado (>7d inativo)

Equivalente a "primeiro uso" — DXT limpa credenciais e repete fluxo 4.1.

## 5. Página `/onboarding`

### 5.1 Estrutura (landing linear, top → bottom)

1. **Header** — logo Azzas + email da sessão + logout (reusa componente de `index.html`)
2. **Hero + CTA** — título, sub-título, botão grande "Baixar Azzas MCP v1.3.0 .dxt", data da última atualização
3. **Instalação em 5 passos numerados** — com mini-screenshots. Quinto passo avisa do primeiro login no browser.
4. **Lista de agentes** — fetch de `/api/mcp/agents`, renderiza `label` + descrição curta. `coming soon` aparece em cinza.
5. **Fallback "não tem Claude Desktop"** — link pra `claude.ai/download`
6. **Troubleshooting** — 4 cenários pré-mapeados (reauth 7d, tools não aparecem, 403 de allowlist, versão desatualizada)
7. **Link pro README técnico** — github.com/somalabs/bq-analista

### 5.2 Comportamento dinâmico

- `GET /api/mcp/version` no load → compara com `localStorage.last_known_dxt_version`. Se há versão mais nova, mostra ribbon de update.
- `GET /api/mcp/agents` no load → renderiza seção 4.
- Sem sessão SSO → middleware redireciona pro login do portal.
- Responsivo: mobile empilha em coluna, botão de download full-width.

### 5.3 Visual e tom

Reusa estilo do portal (guia em `identidade-visual-azzas.md`). HTML+JS estático, sem framework. Copy em segunda pessoa, curto, sem jargão. Emojis apenas em mensagens de erro do DXT (nunca na página).

## 6. Tratamento de erros

### 6.1 Auth

| Caso | User vê | DXT faz |
|---|---|---|
| Sem credenciais | 🔐 Autenticação necessária. Abri uma aba de login. | Abre browser, inicia loopback, salva JWT no retorno |
| User fechou browser sem logar | 🔐 Login não foi concluído. Peça de novo quando estiver pronto. | Loopback timeout 120s → encerra sem estado |
| Azure AD rejeita (fora do tenant) | ⚠️ Você não está no tenant Azzas. Contate ops@azzas. | Vercel redireciona loopback com `?error=wrong_tenant`, DXT traduz a mensagem, nada salvo |
| `state` HMAC inválido ou code inválido | ⚠️ Erro na autenticação. Tente de novo. | Vercel redireciona com `?error=invalid_state` ou `invalid_code`, DXT traduz |
| Refresh expirou | 🔐 Sua sessão expirou. Abri aba pra re-login. | Limpa credenciais, dispara fluxo §4.1 |
| Refresh inválido (secret rotacionado) | 🔐 Sua sessão foi invalidada. Abri aba pra re-login. | Limpa credenciais, dispara §4.1 |
| Loopback: portas ocupadas | ⚠️ Não consegui abrir porta local pro login. Feche outras instâncias de MCP e tente de novo. | Tentativa em [8765..8799], todas falham |
| `credentials.json` corrompido | 🔐 Credenciais corrompidas. Apaguei e abri aba de login. | Try/catch no parse, apaga, dispara §4.1 |

### 6.2 Rede

| Caso | User vê | DXT faz |
|---|---|---|
| Sem internet no startup | ⚠️ Não consegui buscar ferramentas. Verifique conexão e reinicie Claude Desktop. | `tools/list` vazio com aviso |
| Vercel fora do ar | Mesmo | Mesmo |
| Agente Railway fora do ar | ⚠️ O agente `vendas-linx` está indisponível. Tente em alguns minutos. | Timeout/5xx traduzido; outros agentes não afetados |
| Latência alta | (running tool...) | Timeout 60s no forward |

### 6.3 Autorização pós-auth

| Caso | User vê | DXT faz |
|---|---|---|
| Email fora de `allowed_execs` | ⚠️ Seu e-mail não tem acesso ao agente `vendas-linx`. Contate ops@azzas. | Traduz 403 do agente |
| JWT signature inválida no agente | ⚠️ Sua sessão não foi aceita. Abri aba pra re-login. | Trata 401 como re-auth |

### 6.4 Versão

| Caso | User vê | DXT faz |
|---|---|---|
| DXT < `min_dxt_version` | ⚠️ Sua versão do Azzas MCP (v1.0.0) não é mais suportada. Baixe a nova em analysis-lib.vercel.app/onboarding. | Hard gate: todo tool call retorna esse erro |
| Nova versão disponível (>= min) | (silencioso no chat) | Portal mostra ribbon na próxima visita |

### 6.5 Protocolo

| Caso | User vê | DXT faz |
|---|---|---|
| Tool com prefixo desconhecido | ⚠️ Ferramenta não reconhecida. Reinicie Claude Desktop. | Router retorna erro |
| Payload malformado do agente | ⚠️ Resposta inesperada do agente. | Log local detalhado, mensagem curta |
| Múltiplas janelas Claude Desktop | (sem problema) | Processos independentes leem o mesmo `credentials.json`; last-write-wins em auth concorrente (aceitável) |

### 6.6 Logging local

`~/.mcp/logs/azzas-mcp-YYYY-MM-DD.log`:

- Eventos de auth (sem tokens em claro)
- Tool calls (nome + duração, sem payload)
- Forward failures com status code
- Mudanças de manifesto/versão

Rotação: um arquivo por dia. Zero envio remoto.

### 6.7 Operacional

- **Rotação de `MCP_JWT_SECRET`**: invalida todas as sessões; DXT trata via 401 = re-auth. Política: só em emergência de segurança.
- **Rotação de `AZURE_CLIENT_SECRET`**: silenciosa, só Vercel afetado.
- **Mudança de `AZURE_CLIENT_ID` ou `AZURE_TENANT_ID`**: breaking change; novo release do DXT.

## 7. Testes

### 7.1 Automatizados

**DXT (TS):**

- `auth.test.ts`: roundtrip credentials, arquivo corrompido, permissões, loopback callback, timeout, range de portas
- `router.test.ts`: prefix matching, tool desconhecido, manifesto vazio
- `forward.test.ts`: Bearer header, tradução de 401/403/5xx, refresh silencioso
- `version.test.ts`: comparação semver, hard gate de min_version

**Vercel (TS):**

- `auth-start.test.ts`: HMAC state, redirect URL Azure, rejeita redirect não-loopback
- `auth-callback.test.ts`: mock code exchange, validação tid, mint de JWT, rejeição de tenant errado
- `auth-refresh.test.ts`: aceita refresh válido, rejeita expirado/tipo errado
- `agents.test.ts`, `version.test.ts`: retornos estáticos corretos

**Interop JWT TS ⇄ Python (crítico):** teste integrado em `tests/integration/jwt_interop_test.py` que gera JWT de um lado e valida do outro (e vice-versa). Esse teste falhando = fluxo de auth inteiro quebrado.

### 7.2 End-to-end scripted

`scripts/e2e-dxt-auth.sh`:

- Mock de Azure AD local (token + userinfo)
- Vercel dev apontado pro mock
- Subprocess Node com DXT bundled
- Simula tool call → captura URL de browser → responde no loopback → valida credenciais salvas → segundo tool call sem nova auth → expira access → verifica refresh silencioso

### 7.3 QA manual por release

Checklist em `docs/dxt-release-checklist.md`:

- macOS (Apple Silicon + Intel): install, primeiro auth, segunda chamada sem re-auth, permissões do `credentials.json`, 403 de allowlist
- Windows 10 + 11: mesmos + dotdir funciona, browser padrão (Edge, Chrome), SmartScreen não bloqueia
- Ambos: remoção manual do credentials.json, corrupção manual, expiração simulada de access/refresh, bump de min_dxt_version, Vercel offline

### 7.4 Staging

Deploy em preview Vercel `analysis-lib-preview.vercel.app`, DXT apontando pra preview, testers: autor + 1 exec, 3 dias, zero tickets de auth = promoção.

### 7.5 Fora de escopo

- Teste de Azure AD
- Teste de Claude Desktop
- Performance sob carga (reavaliar com >50 usuários)

## 8. Decisões registradas

| # | Decisão | Motivo |
|---|---|---|
| D1 | DXT único multi-agente (router) | Evitar release por agente novo; atrito operacional menor |
| D2 | DXT valida só identidade corporativa; allowlist fica nos agentes | Separação de responsabilidades; mantém código Python atual |
| D3 | Landing page linear hub permanente | Serve onboarding + reauth + update + troubleshooting |
| D4 | Auth endpoint no portal Vercel (TS) | Unifica SSO do download com OAuth do DXT; zero infra nova |
| D5 | Manifesto dinâmico via `/api/mcp/agents` | Novo agente entra sem DXT release |
| D6 | UX de primeiro login: reativo com mensagem explícita | Evita timeout de tool; deixa o contrato claro |
| D7 | Refresh token não rotaciona (v1) | Simplicidade; allowlist per-agente mitiga |
| D8 | `min_dxt_version` como hard gate | Força upgrade em mudança breaking |
| D9 | Reusar Azure App Registration do portal, adicionando client_secret | Zero nova configuração Azure |
| D10 | JWT em `~/.mcp/credentials.json` cross-platform, mode 0600 em Unix | Padrão; Windows usa ACL do USERPROFILE |

## 9. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| JWT TS e Python divergem em algum campo | Média | Alto — auth inteira quebra | Teste de interop dedicado em CI |
| DXT spec evolui e quebra compatibilidade | Baixa | Médio — rebuild release novo | `min_dxt_version` + banner; documentar versão mínima de Desktop testada |
| Usuário corporativo bloqueado pelo tenant Azure fora de horário | Baixa | Baixo | Refresh 7d amortece; mensagem clara no erro |
| Port 8765-8799 todos bloqueados por corp firewall | Muito baixa | Alto pro user afetado | Expandir range; opção de porta custom via env var no próximo release |
| Vercel `/api/mcp/auth/callback` fica lento e Azure timeouta redirect | Baixa | Médio | Serverless warmup; monitoring |
| Rotação de `MCP_JWT_SECRET` por acidente | Baixa | Alto — invalida todos | Documento operacional; secret não auto-rotated |

## 10. Próximos passos após aprovação

1. Plano de implementação detalhado via `writing-plans` skill
2. Scaffold de `packages/mcp-client-dxt/` e `portal/api/mcp/`
3. Teste de interop JWT primeiro (antes de qualquer outra integração)
4. Staging em preview Vercel
5. Release v1.0.0 com checklist de QA manual
