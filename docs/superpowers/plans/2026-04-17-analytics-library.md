# Analytics Library — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploying uma biblioteca de análises hospedada no Vercel com Azure AD SSO, análises privadas por analista e compartilhamento público opt-in — sem backend persistente.

**Architecture:** Arquivos estáticos + Vercel Edge Middleware (`middleware.js`) protege `/analyses/*` validando um cookie de sessão assinado, criado após login OIDC no Azure AD. Cada analista publica em `analyses/{userOID}/`; análises públicas são espelhadas em `analyses/public/`. Um SPA em vanilla JS (`index.html`) exibe a biblioteca e abre análises inline via iframe.

**Tech Stack:** Vercel (Edge Middleware + Serverless Functions), Azure AD / MSAL.js v2 (CDN), Node.js `crypto` (serverless), Web Crypto API (edge), vanilla JS/CSS.

---

## File Map

| Caminho | Ação | Responsabilidade |
|---|---|---|
| `analyses/public/.gitkeep` | Create | Mantém o diretório de análises públicas no git |
| `library/public.json` | Create | Índice global de análises públicas (`[]` inicial) |
| `queries/venda_itens.sql` | Create (move) | Query padrão de vendas (vindo de `query_venda.sql`) |
| `vercel.json` | Create | Roteamento, Edge Middleware, headers de cache |
| `api/auth.js` | Create | Serverless Node.js: valida ID token Azure AD, seta cookie assinado |
| `middleware.js` | Create | Vercel Edge: valida cookie, enforça acesso por OID |
| `index.html` | Create | SPA: login MSAL, grid da biblioteca, viewer iframe |

**Já existe e não muda:** `SKILL.md` (workflow de publicação completo), `schema.md`, `business-rules.md`, `.gitignore` (`.env` já incluído).

---

## Task 1: Repo Scaffolding

**Files:**
- Create: `analyses/public/.gitkeep`
- Create: `library/public.json`
- Create: `queries/venda_itens.sql` (conteúdo copiado de `query_venda.sql`)

- [ ] **Step 1: Criar diretório de análises públicas**

```bash
mkdir -p analyses/public
touch analyses/public/.gitkeep
```

- [ ] **Step 2: Criar índice público vazio**

```bash
echo '[]' > library/public.json
```

- [ ] **Step 3: Mover query para diretório padrão**

```bash
mkdir -p queries
cp query_venda.sql queries/venda_itens.sql
git rm query_venda.sql
```

- [ ] **Step 4: Verificar estrutura**

```bash
ls analyses/public/ library/ queries/
```

Expected: `.gitkeep` em `analyses/public/`, `public.json` em `library/`, `venda_itens.sql` em `queries/`.

- [ ] **Step 5: Commit**

```bash
git add analyses/public/.gitkeep library/public.json queries/venda_itens.sql
git commit -m "scaffold: estrutura de diretórios da analytics library"
```

---

## Task 2: vercel.json

**Files:**
- Create: `vercel.json`

- [ ] **Step 1: Criar vercel.json**

Criar o arquivo `/vercel.json`:

```json
{
  "version": 2,
  "middleware": [{ "src": "/analyses/(.*)" }],
  "functions": {
    "api/auth.js": { "maxDuration": 10 }
  },
  "headers": [
    {
      "source": "/analyses/(.*)",
      "headers": [{ "key": "Cache-Control", "value": "private, no-store" }]
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add vercel.json
git commit -m "feat: vercel.json com Edge Middleware e headers de cache"
```

---

## Task 3: api/auth.js

Serverless Node.js que recebe o ID token do Azure AD (enviado pelo MSAL browser), valida a assinatura via JWKS, extrai o claim `oid` e seta um cookie de sessão assinado com HMAC-SHA256.

**Cookie format:** `{oid}~{expiry_unix}~{base64url_hmac}`  
**HMAC input:** `{oid}~{expiry_unix}` com chave `SESSION_SECRET`

**Files:**
- Create: `api/auth.js`

- [ ] **Step 1: Criar `api/auth.js`**

```javascript
const crypto = require('crypto')

// Module-level JWKS cache (survives warm Lambda invocations)
let jwksCache = { keys: [], fetchedAt: 0 }
const JWKS_TTL_MS = 3_600_000

async function getJwks(tenantId) {
  if (Date.now() - jwksCache.fetchedAt < JWKS_TTL_MS) return jwksCache.keys
  const res = await fetch(
    `https://login.microsoftonline.com/${tenantId}/discovery/v2.0/keys`
  )
  const data = await res.json()
  jwksCache = { keys: data.keys, fetchedAt: Date.now() }
  return jwksCache.keys
}

function b64urlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/')
  while (str.length % 4) str += '='
  return Buffer.from(str, 'base64')
}

async function validateToken(token, clientId, tenantId) {
  const parts = token.split('.')
  if (parts.length !== 3) throw new Error('Formato de token inválido')

  const header = JSON.parse(b64urlDecode(parts[0]).toString())
  const payload = JSON.parse(b64urlDecode(parts[1]).toString())

  const now = Math.floor(Date.now() / 1000)
  if (payload.exp < now) throw new Error('Token expirado')
  if (payload.aud !== clientId) throw new Error('Audience inválido')
  const validIssuer = `https://login.microsoftonline.com/${tenantId}/v2.0`
  if (payload.iss !== validIssuer) throw new Error('Issuer inválido')
  if (!payload.oid) throw new Error('Claim OID ausente')

  const keys = await getJwks(tenantId)
  const jwk = keys.find(k => k.kid === header.kid)
  if (!jwk) throw new Error('Chave de assinatura desconhecida')

  const publicKey = crypto.createPublicKey({ key: jwk, format: 'jwk' })
  const data = Buffer.from(`${parts[0]}.${parts[1]}`)
  const signature = b64urlDecode(parts[2])
  const valid = crypto.verify('RSA-SHA256', data, publicKey, signature)
  if (!valid) throw new Error('Assinatura inválida')

  return payload.oid
}

function createSessionCookie(oid, secret) {
  const expiry = Math.floor(Date.now() / 1000) + 8 * 3600
  const payload = `${oid}~${expiry}`
  const hmac = crypto.createHmac('sha256', secret).update(payload).digest('base64url')
  return `${payload}~${hmac}`
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  const { idToken } = req.body ?? {}
  if (!idToken) return res.status(400).json({ error: 'idToken ausente' })

  const { AZURE_CLIENT_ID, AZURE_TENANT_ID, SESSION_SECRET } = process.env
  if (!AZURE_CLIENT_ID || !AZURE_TENANT_ID || !SESSION_SECRET) {
    return res.status(500).json({ error: 'Variáveis de ambiente não configuradas' })
  }

  try {
    const oid = await validateToken(idToken, AZURE_CLIENT_ID, AZURE_TENANT_ID)
    const cookieValue = createSessionCookie(oid, SESSION_SECRET)
    res.setHeader('Set-Cookie',
      `session=${cookieValue}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=28800`
    )
    res.status(200).json({ oid })
  } catch (err) {
    res.status(401).json({ error: err.message })
  }
}
```

- [ ] **Step 2: Testar localmente com vercel dev**

Requer Azure AD app registrado e variáveis de ambiente. Se não disponível ainda, pular para Task 5 e testar integrado.

```bash
# Simular chamada com token inválido (deve retornar 401)
curl -X POST http://localhost:3000/api/auth \
  -H "Content-Type: application/json" \
  -d '{"idToken":"invalid.token.here"}'
```

Expected: `{"error":"Formato de token inválido"}` com status 401.

- [ ] **Step 3: Commit**

```bash
git add api/auth.js
git commit -m "feat: api/auth — valida ID token Azure AD e seta session cookie"
```

---

## Task 4: middleware.js

Vercel Edge Middleware que intercepta todas as requests para `/analyses/*`. Valida o cookie de sessão com Web Crypto API e enforça:
- `/analyses/public/*` → qualquer usuário autenticado pode acessar
- `/analyses/{oid}/*` → apenas o dono (`oid` do token == `oid` do path)

**Files:**
- Create: `middleware.js`

- [ ] **Step 1: Criar `middleware.js`**

```javascript
function parseCookie(header, name) {
  if (!header) return null
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (k === name) return v.join('=')
  }
  return null
}

function b64urlToBytes(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/')
  while (str.length % 4) str += '='
  return Uint8Array.from(atob(str), c => c.charCodeAt(0))
}

async function verifySession(cookieValue, secret) {
  const parts = cookieValue.split('~')
  if (parts.length !== 3) return null
  const [oid, expiry, signature] = parts

  if (parseInt(expiry) < Date.now() / 1000) return null

  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['verify']
  )
  const data = new TextEncoder().encode(`${oid}~${expiry}`)
  const sigBytes = b64urlToBytes(signature)
  const valid = await crypto.subtle.verify('HMAC', key, sigBytes, data)

  return valid ? oid : null
}

export default async function middleware(request) {
  const cookieHeader = request.headers.get('cookie')
  const sessionCookie = parseCookie(cookieHeader, 'session')

  if (!sessionCookie) {
    return new Response('Não autenticado', { status: 401 })
  }

  const sessionOid = await verifySession(sessionCookie, process.env.SESSION_SECRET)
  if (!sessionOid) {
    return new Response('Sessão inválida ou expirada', { status: 401 })
  }

  const url = new URL(request.url)
  // url.pathname = /analyses/public/... ou /analyses/{oid}/...
  const segment = url.pathname.split('/')[2]

  if (!segment) return new Response('Not Found', { status: 404 })
  if (segment === 'public') return // qualquer autenticado: deixa passar
  if (segment !== sessionOid) return new Response('Acesso negado', { status: 403 })
  // OID bate: deixa passar
}
```

- [ ] **Step 2: Verificar após deploy no Vercel**

```bash
# Sem cookie → 401
curl -I https://{seu-dominio-vercel}/analyses/public/qualquer.html

# Com cookie inválido → 401
curl -I -H "Cookie: session=fakevalue" https://{seu-dominio-vercel}/analyses/public/qualquer.html
```

- [ ] **Step 3: Commit**

```bash
git add middleware.js
git commit -m "feat: edge middleware — controle de acesso por OID"
```

---

## Task 5: index.html

SPA completo. Fluxo:
1. Carrega MSAL.js do CDN
2. Tenta login silencioso; se falhar → redirect Azure AD
3. Pós-login: chama `POST /api/auth` → recebe `oid` + cookie
4. Busca `library/public.json` + `library/{oid}.json` e une (deduplica por `id`)
5. Renderiza grid de cards com chips de filtro (marca / tag)
6. Click no card → abre iframe com barra de navegação

**Configuração Azure AD:** Os valores `AZURE_CLIENT_ID` e `AZURE_TENANT_ID` devem ser substituídos pelos valores reais antes do deploy. Eles não são segredos — aparecem em toda URL OAuth.

**Files:**
- Create: `index.html`

- [ ] **Step 1: Criar `index.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Farm Group Analytics</title>
  <script src="https://alcdn.msauth.net/browser/2.38.3/js/msal-browser.min.js"
          integrity="sha384-k2EoJZNfS9UcBvGVPBPQv0LMJPFZ5pFlU67KT2fWpS7GWxKQzX0m3lkDZDKpnOS"
          crossorigin="anonymous"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #0d1a0d;
      --surface: #152315;
      --border: #2a4a2a;
      --green: #3a8a3a;
      --green-light: #4caf50;
      --text: #e8f5e8;
      --text-muted: #8aaf8a;
      --accent: #66bb6a;
    }

    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      min-height: 100vh;
    }

    /* ── Loading ── */
    #loading {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      flex-direction: column;
      gap: 16px;
      color: var(--text-muted);
    }
    .spinner {
      width: 32px; height: 32px;
      border: 3px solid var(--border);
      border-top-color: var(--green-light);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ── Library view ── */
    #library-view { display: none; }

    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 16px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
    }
    header h1 {
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--accent);
      flex: 1;
    }
    #user-email { font-size: 0.8rem; color: var(--text-muted); }

    .filters {
      padding: 16px 24px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      border-bottom: 1px solid var(--border);
    }
    .chip {
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 0.8rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover, .chip.active {
      border-color: var(--green-light);
      color: var(--green-light);
      background: rgba(76, 175, 80, 0.08);
    }

    #grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
      padding: 24px;
    }

    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      cursor: pointer;
      transition: border-color 0.15s, transform 0.1s;
    }
    .card:hover {
      border-color: var(--green);
      transform: translateY(-2px);
    }
    .card-brand {
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.1em;
      color: var(--accent);
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    .card-title {
      font-size: 1rem;
      font-weight: 600;
      margin-bottom: 4px;
      color: var(--text);
    }
    .card-period {
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 8px;
    }
    .card-desc {
      font-size: 0.82rem;
      color: var(--text-muted);
      line-height: 1.4;
      margin-bottom: 10px;
    }
    .card-footer {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }
    .tag {
      background: rgba(58, 138, 58, 0.15);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 0.72rem;
    }
    .badge-public {
      margin-left: auto;
      font-size: 0.65rem;
      color: var(--green-light);
      border: 1px solid var(--green);
      border-radius: 4px;
      padding: 1px 6px;
    }

    #empty {
      grid-column: 1/-1;
      text-align: center;
      padding: 60px 0;
      color: var(--text-muted);
    }

    /* ── Analysis view ── */
    #analysis-view {
      display: none;
      flex-direction: column;
      height: 100vh;
    }
    .analysis-bar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 10px 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
    #back-btn {
      background: none;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.85rem;
      transition: all 0.15s;
    }
    #back-btn:hover { border-color: var(--green-light); color: var(--green-light); }
    #analysis-crumb { font-size: 0.9rem; color: var(--text-muted); }
    #analysis-iframe {
      flex: 1;
      border: none;
      background: var(--bg);
    }
  </style>
</head>
<body>

<div id="loading">
  <div class="spinner"></div>
  <span>Autenticando…</span>
</div>

<div id="library-view">
  <header>
    <h1>Farm Group Analytics</h1>
    <span id="user-email"></span>
  </header>
  <div class="filters" id="filters">
    <button class="chip active" data-filter="all">Todas</button>
  </div>
  <div id="grid"></div>
</div>

<div id="analysis-view">
  <div class="analysis-bar">
    <button id="back-btn">← Biblioteca</button>
    <span id="analysis-crumb"></span>
  </div>
  <iframe id="analysis-iframe" src="" allow="same-origin"></iframe>
</div>

<script>
// ── Config (substitua antes do deploy) ──────────────────────────────────────
const AZURE_CLIENT_ID = 'REPLACE_WITH_AZURE_CLIENT_ID'
const AZURE_TENANT_ID = 'REPLACE_WITH_AZURE_TENANT_ID'
// ────────────────────────────────────────────────────────────────────────────

const msalInstance = new msal.PublicClientApplication({
  auth: {
    clientId: AZURE_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${AZURE_TENANT_ID}`,
    redirectUri: window.location.origin
  },
  cache: { cacheLocation: 'sessionStorage' }
})

let userOid = null
let allAnalyses = []
let activeFilter = 'all'

async function init() {
  try {
    await msalInstance.initialize()
    const redirectResult = await msalInstance.handleRedirectPromise()

    let idToken = null
    if (redirectResult) {
      idToken = redirectResult.idToken
    } else {
      const accounts = msalInstance.getAllAccounts()
      if (accounts.length === 0) {
        await msalInstance.loginRedirect({ scopes: ['openid', 'profile'] })
        return
      }
      try {
        const silent = await msalInstance.acquireTokenSilent({
          account: accounts[0],
          scopes: ['openid', 'profile']
        })
        idToken = silent.idToken
      } catch (e) {
        if (e instanceof msal.InteractionRequiredAuthError) {
          await msalInstance.loginRedirect({ scopes: ['openid', 'profile'] })
          return
        }
        throw e
      }
    }

    const authResult = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken }),
      credentials: 'include'
    })
    if (!authResult.ok) throw new Error('Falha na autenticação com o servidor')
    const { oid } = await authResult.json()
    userOid = oid

    const accounts = msalInstance.getAllAccounts()
    if (accounts[0]?.username) {
      document.getElementById('user-email').textContent = accounts[0].username
    }

    await loadLibrary()
  } catch (err) {
    document.getElementById('loading').innerHTML =
      `<p style="color:#ef5350">Erro: ${err.message}</p>`
  }
}

async function loadLibrary() {
  const [publicRes, privateRes] = await Promise.allSettled([
    fetch('library/public.json').then(r => r.json()),
    fetch(`library/${userOid}.json`).then(r => r.json())
  ])

  const publicList = publicRes.status === 'fulfilled' ? publicRes.value : []
  const privateList = privateRes.status === 'fulfilled' ? privateRes.value : []

  // Merge: private has priority (owns the entry); deduplicate by id
  const byId = new Map()
  publicList.forEach(a => byId.set(a.id, a))
  privateList.forEach(a => byId.set(a.id, a))
  allAnalyses = [...byId.values()].sort((a, b) => b.date.localeCompare(a.date))

  buildFilters()
  renderGrid()

  document.getElementById('loading').style.display = 'none'
  document.getElementById('library-view').style.display = 'block'
}

function buildFilters() {
  const brands = [...new Set(allAnalyses.map(a => a.brand).filter(Boolean))]
  const tags = [...new Set(allAnalyses.flatMap(a => a.tags ?? []))]
  const filtersEl = document.getElementById('filters')
  filtersEl.innerHTML = '<button class="chip active" data-filter="all">Todas</button>'

  brands.forEach(b => {
    const btn = document.createElement('button')
    btn.className = 'chip'
    btn.dataset.filter = `brand:${b}`
    btn.textContent = b
    filtersEl.appendChild(btn)
  })

  tags.slice(0, 8).forEach(t => {
    const btn = document.createElement('button')
    btn.className = 'chip'
    btn.dataset.filter = `tag:${t}`
    btn.textContent = `#${t}`
    filtersEl.appendChild(btn)
  })

  filtersEl.addEventListener('click', e => {
    const chip = e.target.closest('.chip')
    if (!chip) return
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'))
    chip.classList.add('active')
    activeFilter = chip.dataset.filter
    renderGrid()
  })
}

function getFiltered() {
  if (activeFilter === 'all') return allAnalyses
  const [type, value] = activeFilter.split(':')
  if (type === 'brand') return allAnalyses.filter(a => a.brand === value)
  if (type === 'tag') return allAnalyses.filter(a => a.tags?.includes(value))
  return allAnalyses
}

function renderGrid() {
  const grid = document.getElementById('grid')
  const filtered = getFiltered()
  if (filtered.length === 0) {
    grid.innerHTML = '<div id="empty">Nenhuma análise encontrada.</div>'
    return
  }

  grid.innerHTML = ''
  filtered.forEach(a => {
    const card = document.createElement('div')
    card.className = 'card'
    card.innerHTML = `
      <div class="card-brand">${a.brand ?? ''}</div>
      <div class="card-title">${a.title}</div>
      <div class="card-period">${a.period ?? a.date}</div>
      <div class="card-desc">${a.description ?? ''}</div>
      <div class="card-footer">
        ${(a.tags ?? []).map(t => `<span class="tag">#${t}</span>`).join('')}
        ${a.public ? '<span class="badge-public">público</span>' : ''}
      </div>
    `
    card.addEventListener('click', () => openAnalysis(a))
    grid.appendChild(card)
  })
}

function openAnalysis(analysis) {
  document.getElementById('library-view').style.display = 'none'
  const view = document.getElementById('analysis-view')
  view.style.display = 'flex'
  document.getElementById('analysis-crumb').textContent =
    `${analysis.brand ?? ''} · ${analysis.title}`
  document.getElementById('analysis-iframe').src = analysis.file
}

document.getElementById('back-btn').addEventListener('click', () => {
  document.getElementById('analysis-view').style.display = 'none'
  document.getElementById('analysis-iframe').src = ''
  document.getElementById('library-view').style.display = 'block'
})

init()
</script>
</body>
</html>
```

- [ ] **Step 2: Substituir placeholders da config**

Abrir `index.html` e substituir:
- `REPLACE_WITH_AZURE_CLIENT_ID` → o `client_id` da app registrada no Azure AD
- `REPLACE_WITH_AZURE_TENANT_ID` → o `tenant_id` da organização

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "feat: index.html — SPA com MSAL, grid de análises e viewer iframe"
```

---

## Task 6: Publicar a primeira análise

Validação end-to-end: publica o `dashboard_farm_ecomm.html` existente como a primeira análise real.

**Pré-requisito:** `.env` com `USER_OID=` preenchido.

- [ ] **Step 1: Configurar USER_OID**

```bash
# Encontre seu OID em: https://portal.azure.com → Azure AD → Usuários → [seu nome] → Object ID
echo 'USER_OID=cole-seu-oid-aqui' > .env
source .env
echo "OID: $USER_OID"
```

- [ ] **Step 2: Criar diretório e copiar análise**

```bash
source .env
ANALYSIS_ID="farm-produto-ecomm-2026-04-17"
mkdir -p analyses/$USER_OID
cp dashboard_farm_ecomm.html analyses/$USER_OID/$ANALYSIS_ID.html
```

- [ ] **Step 3: Criar índice pessoal**

Criar `library/${USER_OID}.json` (substituir `{USER_OID}` pelo valor real):

```json
[
  {
    "id": "farm-produto-ecomm-2026-04-17",
    "title": "Top Produtos · Ecommerce",
    "brand": "FARM",
    "period": "11–17 Abr 2026",
    "date": "2026-04-17",
    "description": "Top 10 produtos, categorias e tendência diária de venda líquida.",
    "file": "analyses/{USER_OID}/farm-produto-ecomm-2026-04-17.html",
    "public": false,
    "tags": ["produto", "ecommerce", "ranking"]
  }
]
```

**Atenção:** o campo `file` deve ter o valor real do `USER_OID`, não o placeholder.

- [ ] **Step 4: Commit e push**

```bash
source .env
git add analyses/$USER_OID/farm-produto-ecomm-2026-04-17.html library/$USER_OID.json
git commit -m "análise: farm-produto-ecomm-2026-04-17"
git push
```

- [ ] **Step 5: Verificar no Vercel (~60s)**

Após o rebuild automático do Vercel:
1. Abrir o domínio Vercel → redireciona para Azure AD login
2. Fazer login → card da análise deve aparecer no grid
3. Clicar no card → análise abre em iframe
4. Testar URL direta `https://{dominio}/analyses/{oid}/farm-produto-ecomm-2026-04-17.html` → deve funcionar com cookie válido
5. Abrir em aba anônima (sem cookie) → deve retornar 401

---

## Checklist de Cobertura da Spec

| Requisito da Spec | Task |
|---|---|
| `queries/` com SQL padrão | Task 1 |
| `analyses/public/` e `library/public.json` | Task 1 |
| `vercel.json` exato | Task 2 |
| Validação de ID token Azure AD (JWKS, RSA, claims) | Task 3 |
| Cookie de sessão assinado com HMAC-SHA256 | Task 3 |
| Edge Middleware: `/analyses/public/*` → qualquer autenticado | Task 4 |
| Edge Middleware: `/analyses/{oid}/*` → somente dono | Task 4 |
| MSAL browser login redirect | Task 5 |
| Grid com cards, filtros por marca/tag | Task 5 |
| Iframe viewer com barra de navegação | Task 5 |
| Workflow de publicação (SKILL.md) | Já existe |
| Tornar análise pública (SKILL.md) | Já existe |
| Variáveis de ambiente documentadas | Task 3 (código) |
| `schema.md` e `business-rules.md` | Já existem |
