# Portal de Análises — Azzas 2154

Biblioteca privada de dashboards de BI do grupo. Cada analista tem sua própria pasta de análises (só ele vê) e pode marcar uma análise como pública (todo mundo logado vê).

**Portal em produção:** https://analysis-lib.vercel.app/

---

## Para consultar análises

1. Abra https://analysis-lib.vercel.app/
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
git clone https://github.com/arturbitlemos/bq-analista.git
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
  - `https://analysis-lib.vercel.app/`
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
