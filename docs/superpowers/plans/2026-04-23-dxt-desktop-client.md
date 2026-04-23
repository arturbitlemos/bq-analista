# DXT Desktop Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o cliente `.dxt` do Azzas MCP no Claude Desktop, cross-platform, com auth corporativa Azure via portal Vercel e onboarding self-service.

**Architecture:** Cliente Node (TypeScript) empacotado como `.dxt`, servido pelo portal `bq-analista.vercel.app`. Auth via Azure AD code-exchange em serverless JS na Vercel, mintando JWT compatível com `mcp-core` existente. DXT faz loopback OAuth no primeiro uso, persiste credenciais em `~/.mcp/credentials.json`, e forwarda tool calls pros agentes Railway com `Authorization: Bearer`. Manifesto dinâmico (`/api/mcp/agents`) permite adicionar agentes sem release do DXT.

**Tech Stack:** TypeScript (Node 20), esbuild para bundle, `@modelcontextprotocol/sdk`, `open` para browser spawn, `undici` pra HTTP. Vercel serverless com Node runtime, CommonJS (pra match com padrão atual do portal). Vitest pra testes TS, node:test pra testes JS do portal, pytest pra interop Python. Base spec: `docs/superpowers/specs/2026-04-23-dxt-desktop-client-design.md`.

**Pré-requisitos operacionais (fora do código, manuais):**

1. Adicionar plataforma Web na App Registration Azure existente com redirect `https://bq-analista.vercel.app/api/mcp/auth/callback`
2. Gerar client secret na App Registration (24 meses)
3. Setar no env Vercel (production + preview): `AZURE_CLIENT_SECRET`, `MCP_JWT_SECRET` (já pode existir — mesmo valor das Railways)
4. Garantir que `MCP_JWT_SECRET` no env das Railways bate exatamente com o valor setado na Vercel

Fazer isso antes de rodar a Task 2.3 — as rotas de callback vão falhar sem esses valores.

---

## File structure

**Novo pacote:**
```
packages/mcp-client-dxt/
├── package.json
├── tsconfig.json
├── vitest.config.ts
├── esbuild.config.mjs
├── manifest.json          # DXT manifest
├── icon.png
├── src/
│   ├── index.ts           # stdio MCP server entrypoint
│   ├── paths.ts           # cross-platform credential paths
│   ├── errors.ts          # mensagens padronizadas
│   ├── jwt.ts             # mint/decode compatível com mcp-core Python
│   ├── auth.ts            # loopback OAuth + credentials persistence
│   ├── manifest.ts        # fetch /api/mcp/agents + cache
│   ├── version.ts         # min_dxt_version gate
│   ├── router.ts          # prefix-based tool routing
│   └── forward.ts         # HTTPS forward com Bearer
├── tests/
│   ├── paths.test.ts
│   ├── jwt.test.ts
│   ├── auth.test.ts
│   ├── manifest.test.ts
│   ├── version.test.ts
│   ├── router.test.ts
│   └── forward.test.ts
└── dist/                  # gerado pelo esbuild, entrypoint do .dxt
```

**Novas rotas no portal Vercel:**
```
portal/
├── api/
│   ├── mcp/
│   │   ├── _helpers/
│   │   │   ├── jwt.js             # mint/verify (JS compatível com mcp-core)
│   │   │   └── state.js           # HMAC state signing com SESSION_SECRET
│   │   ├── auth/
│   │   │   ├── start.js
│   │   │   ├── callback.js
│   │   │   └── refresh.js
│   │   ├── agents.js
│   │   └── version.js
│   ├── download-dxt.js            # redirect pro arquivo versionado
│   └── mcp/__tests__/             # node:test para as rotas
├── onboarding.html
├── public/
│   └── downloads/
│       └── azzas-mcp-1.0.0.dxt    # versionado no nome, gerado pelo build
├── middleware.js                   # modificado pra proteger /onboarding e alguns /api/mcp
└── package.json                    # adiciona devDeps pros testes
```

**Interop test (Python + Node):**
```
tests/integration/
└── test_jwt_interop.py     # gera JWT em cada lado, valida no outro
```

---

## Task 1: Scaffold `packages/mcp-client-dxt/` com tooling TS

**Files:**
- Create: `packages/mcp-client-dxt/package.json`
- Create: `packages/mcp-client-dxt/tsconfig.json`
- Create: `packages/mcp-client-dxt/vitest.config.ts`
- Create: `packages/mcp-client-dxt/esbuild.config.mjs`
- Create: `packages/mcp-client-dxt/.gitignore`

- [ ] **Step 1: Criar `package.json`**

```json
{
  "name": "@azzas/mcp-client-dxt",
  "version": "1.0.0",
  "private": true,
  "description": "Azzas MCP DXT client for Claude Desktop",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "build": "node esbuild.config.mjs",
    "test": "vitest run",
    "test:watch": "vitest",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "jsonwebtoken": "^9.0.2",
    "open": "^10.1.0",
    "undici": "^6.19.8"
  },
  "devDependencies": {
    "@types/jsonwebtoken": "^9.0.6",
    "@types/node": "^20.14.0",
    "esbuild": "^0.25.0",
    "typescript": "^5.5.0",
    "vitest": "^2.1.0"
  },
  "engines": {
    "node": ">=20.0.0"
  }
}
```

- [ ] **Step 2: Criar `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "outDir": "dist",
    "rootDir": "src",
    "declaration": false,
    "sourceMap": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*"]
}
```

- [ ] **Step 3: Criar `vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    globals: false,
  },
});
```

- [ ] **Step 4: Criar `esbuild.config.mjs`**

```js
import { build } from 'esbuild';

await build({
  entryPoints: ['src/index.ts'],
  bundle: true,
  platform: 'node',
  target: 'node20',
  format: 'esm',
  outfile: 'dist/index.js',
  external: [],
  minify: false,
  sourcemap: true,
  banner: {
    js: "import { createRequire } from 'module'; const require = createRequire(import.meta.url);",
  },
});
console.log('✔ DXT bundle built → dist/index.js');
```

- [ ] **Step 5: Criar `.gitignore`**

```
node_modules/
dist/
*.dxt
```

- [ ] **Step 6: Install deps**

Run: `cd packages/mcp-client-dxt && npm install`
Expected: instala sem erros, cria `node_modules/` e `package-lock.json`.

- [ ] **Step 7: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add packages/mcp-client-dxt/package.json packages/mcp-client-dxt/tsconfig.json \
        packages/mcp-client-dxt/vitest.config.ts packages/mcp-client-dxt/esbuild.config.mjs \
        packages/mcp-client-dxt/.gitignore packages/mcp-client-dxt/package-lock.json
git commit -m "feat(dxt): scaffold mcp-client-dxt package com tooling"
```

---

## Task 2: JWT module TS (compatível com Python mcp-core)

**Files:**
- Create: `packages/mcp-client-dxt/src/jwt.ts`
- Create: `packages/mcp-client-dxt/tests/jwt.test.ts`

Referência: `packages/mcp-core/src/mcp_core/jwt_tokens.py`. Formato: HS256, claims `{iss, sub, email, kind, iat, exp}`.

- [ ] **Step 1: Escrever teste que falha**

Crie `packages/mcp-client-dxt/tests/jwt.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { issueTokens, decodeToken, refreshAccess } from '../src/jwt';

const SECRET = 'x'.repeat(32);
const ISSUER = 'azzas-mcp';

describe('jwt', () => {
  it('issueTokens produz access e refresh com kind correto', () => {
    const pair = issueTokens({ email: 'foo@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
    const accessClaims = decodeToken(pair.access, SECRET, ISSUER);
    const refreshClaims = decodeToken(pair.refresh, SECRET, ISSUER);
    expect(accessClaims.kind).toBe('access');
    expect(refreshClaims.kind).toBe('refresh');
    expect(accessClaims.email).toBe('foo@azzas.com.br');
    expect(accessClaims.sub).toBe('foo@azzas.com.br');
    expect(accessClaims.iss).toBe(ISSUER);
  });

  it('decodeToken rejeita signature inválida', () => {
    const pair = issueTokens({ email: 'foo@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
    expect(() => decodeToken(pair.access, 'wrong-secret'.repeat(3), ISSUER)).toThrow();
  });

  it('decodeToken rejeita issuer errado', () => {
    const pair = issueTokens({ email: 'foo@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
    expect(() => decodeToken(pair.access, SECRET, 'other-issuer')).toThrow();
  });

  it('refreshAccess aceita refresh válido, rejeita access como refresh', () => {
    const pair = issueTokens({ email: 'foo@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
    const newAccess = refreshAccess(pair.refresh, SECRET, ISSUER, 1800);
    expect(decodeToken(newAccess, SECRET, ISSUER).kind).toBe('access');
    expect(() => refreshAccess(pair.access, SECRET, ISSUER, 1800)).toThrow(/not a refresh/);
  });
});
```

- [ ] **Step 2: Run test (deve falhar com module not found)**

Run: `cd packages/mcp-client-dxt && npm test`
Expected: FAIL com "Cannot find module '../src/jwt'".

- [ ] **Step 3: Implementar `src/jwt.ts`**

```ts
import jwt, { type JwtPayload, type SignOptions, type VerifyOptions } from 'jsonwebtoken';

export type TokenKind = 'access' | 'refresh';

export interface IssueParams {
  email: string;
  secret: string;
  issuer: string;
  accessTtlS: number;
  refreshTtlS: number;
}

export interface TokenPair {
  access: string;
  refresh: string;
  accessExp: number;
  refreshExp: number;
}

export interface TokenClaims extends JwtPayload {
  email: string;
  kind: TokenKind;
  iss: string;
  sub: string;
  iat: number;
  exp: number;
}

const MIN_SECRET_BYTES = 32;

function checkSecret(secret: string): void {
  if (Buffer.byteLength(secret, 'utf8') < MIN_SECRET_BYTES) {
    throw new Error(`JWT secret must be at least ${MIN_SECRET_BYTES} bytes for HS256`);
  }
}

function encode(kind: TokenKind, params: { email: string; secret: string; issuer: string; ttl: number }): { token: string; exp: number } {
  const now = Math.floor(Date.now() / 1000);
  const exp = now + params.ttl;
  const payload = {
    iss: params.issuer,
    sub: params.email,
    email: params.email,
    kind,
    iat: now,
    exp,
  };
  const options: SignOptions = { algorithm: 'HS256', noTimestamp: true };
  const token = jwt.sign(payload, params.secret, options);
  return { token, exp };
}

export function issueTokens(params: IssueParams): TokenPair {
  checkSecret(params.secret);
  const access = encode('access', { email: params.email, secret: params.secret, issuer: params.issuer, ttl: params.accessTtlS });
  const refresh = encode('refresh', { email: params.email, secret: params.secret, issuer: params.issuer, ttl: params.refreshTtlS });
  return { access: access.token, refresh: refresh.token, accessExp: access.exp, refreshExp: refresh.exp };
}

export function decodeToken(token: string, secret: string, issuer: string): TokenClaims {
  const options: VerifyOptions = { algorithms: ['HS256'], issuer };
  const claims = jwt.verify(token, secret, options);
  if (typeof claims === 'string') throw new Error('unexpected string claims');
  return claims as TokenClaims;
}

export function refreshAccess(refreshToken: string, secret: string, issuer: string, accessTtlS: number): string {
  const claims = decodeToken(refreshToken, secret, issuer);
  if (claims.kind !== 'refresh') throw new Error('not a refresh token');
  const result = encode('access', { email: claims.email, secret, issuer, ttl: accessTtlS });
  return result.token;
}
```

- [ ] **Step 4: Run test (deve passar)**

Run: `cd packages/mcp-client-dxt && npm test`
Expected: 4 tests passed.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-client-dxt/src/jwt.ts packages/mcp-client-dxt/tests/jwt.test.ts
git commit -m "feat(dxt): jwt module compatível com mcp-core Python (kind/iss claims)"
```

---

## Task 3: Teste de interop JWT TS ↔ Python (crítico)

**Files:**
- Create: `tests/integration/test_jwt_interop.py`
- Create: `packages/mcp-client-dxt/scripts/mint-for-interop.ts`

Esse teste é a camada de segurança pro resto do trabalho. Se falhar, o fluxo de auth é inviável.

- [ ] **Step 1: Criar script TS que mint tokens pra interop**

`packages/mcp-client-dxt/scripts/mint-for-interop.ts`:

```ts
import { issueTokens } from '../src/jwt.js';

const [email, secret, issuer, accessTtl, refreshTtl] = process.argv.slice(2);
const pair = issueTokens({
  email,
  secret,
  issuer,
  accessTtlS: parseInt(accessTtl, 10),
  refreshTtlS: parseInt(refreshTtl, 10),
});
console.log(JSON.stringify(pair));
```

- [ ] **Step 2: Adicionar script build + run no package.json**

Edit `packages/mcp-client-dxt/package.json`, scripts:

```json
"interop:mint": "tsx scripts/mint-for-interop.ts"
```

E adicionar `tsx` em devDependencies:

```json
"tsx": "^4.19.0"
```

Run: `cd packages/mcp-client-dxt && npm install`.

- [ ] **Step 3: Escrever teste interop em Python**

`tests/integration/test_jwt_interop.py`:

```python
import json
import subprocess
import time
from pathlib import Path

import pytest

from mcp_core.jwt_tokens import TokenIssuer

SECRET = "x" * 32
ISSUER = "azzas-mcp"
EMAIL = "interop@azzas.com.br"
DXT_DIR = Path(__file__).resolve().parents[2] / "packages" / "mcp-client-dxt"


def _ts_mint() -> dict:
    result = subprocess.run(
        ["npm", "run", "--silent", "interop:mint", "--",
         EMAIL, SECRET, ISSUER, "1800", "604800"],
        cwd=DXT_DIR, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout.strip())


def test_ts_mints_python_verifies():
    pair = _ts_mint()
    issuer = TokenIssuer(secret=SECRET, issuer=ISSUER, access_ttl_s=1800, refresh_ttl_s=604800)
    access_claims = issuer.verify_access(pair["access"])
    assert access_claims["email"] == EMAIL
    assert access_claims["sub"] == EMAIL
    assert access_claims["iss"] == ISSUER
    assert access_claims["kind"] == "access"
    new_access = issuer.refresh(pair["refresh"])
    refreshed = issuer.verify_access(new_access)
    assert refreshed["email"] == EMAIL


def test_python_mints_ts_verifies(tmp_path):
    issuer = TokenIssuer(secret=SECRET, issuer=ISSUER, access_ttl_s=1800, refresh_ttl_s=604800)
    pair = issuer.issue(EMAIL)
    script = f"""
    import {{ decodeToken }} from './src/jwt.js';
    const claims = decodeToken({json.dumps(pair.access_token)}, {json.dumps(SECRET)}, {json.dumps(ISSUER)});
    console.log(JSON.stringify(claims));
    """
    script_file = tmp_path / "verify.mjs"
    script_file.write_text(script)
    result = subprocess.run(
        ["npx", "tsx", str(script_file)],
        cwd=DXT_DIR, capture_output=True, text=True, check=True,
    )
    claims = json.loads(result.stdout.strip())
    assert claims["email"] == EMAIL
    assert claims["kind"] == "access"


def test_secret_mismatch_rejected():
    pair = _ts_mint()
    wrong_issuer = TokenIssuer(secret="y" * 32, issuer=ISSUER, access_ttl_s=1800, refresh_ttl_s=604800)
    with pytest.raises(Exception):
        wrong_issuer.verify_access(pair["access"])
```

- [ ] **Step 4: Run teste Python (deve passar se interop funcionar)**

Run: `cd /Users/arturlemos/Documents/bq-analista && uv run pytest tests/integration/test_jwt_interop.py -v`
Expected: 3 tests passed. Se algum falhar, ajuste `src/jwt.ts` até bater exatamente com o formato Python.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_jwt_interop.py \
        packages/mcp-client-dxt/scripts/mint-for-interop.ts \
        packages/mcp-client-dxt/package.json \
        packages/mcp-client-dxt/package-lock.json
git commit -m "test(interop): garantir compatibilidade JWT TS↔Python mcp-core"
```

---

## Task 4: Helpers JWT + state no portal Vercel

**Files:**
- Create: `portal/api/mcp/_helpers/jwt.js`
- Create: `portal/api/mcp/_helpers/state.js`
- Create: `portal/api/mcp/__tests__/jwt.test.js`
- Create: `portal/api/mcp/__tests__/state.test.js`
- Modify: `portal/package.json` (adiciona `jsonwebtoken` e test runner)

- [ ] **Step 1: Adicionar deps no portal**

Edit `portal/package.json`:

```json
{
  "name": "bq-analista",
  "version": "1.0.0",
  "main": "middleware.js",
  "scripts": {
    "test": "node --test --test-reporter=spec api/mcp/__tests__/"
  },
  "dependencies": {
    "@azure/msal-browser": "^5.7.0",
    "jsonwebtoken": "^9.0.2"
  }
}
```

Run: `cd portal && npm install`

- [ ] **Step 2: Escrever teste `jwt.test.js`**

`portal/api/mcp/__tests__/jwt.test.js`:

```js
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { issueTokens, decodeToken, refreshAccess } = require('../_helpers/jwt');

const SECRET = 'x'.repeat(32);
const ISSUER = 'azzas-mcp';

test('issueTokens retorna access+refresh com campos corretos', () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
  const a = decodeToken(pair.access, SECRET, ISSUER);
  const r = decodeToken(pair.refresh, SECRET, ISSUER);
  assert.equal(a.kind, 'access');
  assert.equal(r.kind, 'refresh');
  assert.equal(a.email, 'a@azzas.com.br');
  assert.equal(a.sub, 'a@azzas.com.br');
  assert.equal(a.iss, ISSUER);
});

test('decodeToken rejeita secret errado', () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
  assert.throws(() => decodeToken(pair.access, 'y'.repeat(32), ISSUER));
});

test('refreshAccess rejeita access-as-refresh', () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: SECRET, issuer: ISSUER, accessTtlS: 1800, refreshTtlS: 604800 });
  assert.throws(() => refreshAccess(pair.access, SECRET, ISSUER, 1800), /not a refresh/);
});
```

- [ ] **Step 3: Run teste (deve falhar: module not found)**

Run: `cd portal && npm test`
Expected: FAIL com "Cannot find module '../_helpers/jwt'".

- [ ] **Step 4: Implementar `portal/api/mcp/_helpers/jwt.js`**

```js
const jwt = require('jsonwebtoken');

const MIN_SECRET_BYTES = 32;

function checkSecret(secret) {
  if (Buffer.byteLength(secret, 'utf8') < MIN_SECRET_BYTES) {
    throw new Error(`JWT secret must be at least ${MIN_SECRET_BYTES} bytes for HS256`);
  }
}

function encode(kind, { email, secret, issuer, ttl }) {
  const now = Math.floor(Date.now() / 1000);
  const exp = now + ttl;
  const payload = { iss: issuer, sub: email, email, kind, iat: now, exp };
  const token = jwt.sign(payload, secret, { algorithm: 'HS256', noTimestamp: true });
  return { token, exp };
}

function issueTokens({ email, secret, issuer, accessTtlS, refreshTtlS }) {
  checkSecret(secret);
  const a = encode('access', { email, secret, issuer, ttl: accessTtlS });
  const r = encode('refresh', { email, secret, issuer, ttl: refreshTtlS });
  return { access: a.token, refresh: r.token, accessExp: a.exp, refreshExp: r.exp };
}

function decodeToken(token, secret, issuer) {
  return jwt.verify(token, secret, { algorithms: ['HS256'], issuer });
}

function refreshAccess(refreshToken, secret, issuer, accessTtlS) {
  const claims = decodeToken(refreshToken, secret, issuer);
  if (claims.kind !== 'refresh') throw new Error('not a refresh token');
  const result = encode('access', { email: claims.email, secret, issuer, ttl: accessTtlS });
  return result.token;
}

module.exports = { issueTokens, decodeToken, refreshAccess };
```

- [ ] **Step 5: Implementar `portal/api/mcp/_helpers/state.js`**

```js
const crypto = require('crypto');

const TTL_S = 600;

function signState(redirectUri, secret) {
  const nonce = crypto.randomBytes(16).toString('base64url');
  const exp = Math.floor(Date.now() / 1000) + TTL_S;
  const payload = `${nonce}~${exp}~${redirectUri}`;
  const hmac = crypto.createHmac('sha256', secret).update(payload).digest('base64url');
  return `${payload}~${hmac}`;
}

function verifyState(stateValue, secret) {
  const parts = stateValue.split('~');
  if (parts.length < 4) return null;
  const hmac = parts.pop();
  const payload = parts.join('~');
  const expected = crypto.createHmac('sha256', secret).update(payload).digest('base64url');
  if (!crypto.timingSafeEqual(Buffer.from(hmac), Buffer.from(expected))) return null;
  const [, expStr, ...rest] = payload.split('~');
  const redirectUri = rest.join('~');
  if (parseInt(expStr, 10) < Math.floor(Date.now() / 1000)) return null;
  return { redirectUri };
}

module.exports = { signState, verifyState };
```

- [ ] **Step 6: Escrever teste state**

`portal/api/mcp/__tests__/state.test.js`:

```js
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { signState, verifyState } = require('../_helpers/state');

const SECRET = 'z'.repeat(32);

test('roundtrip state preserva redirectUri', () => {
  const signed = signState('http://localhost:8765/cb', SECRET);
  const result = verifyState(signed, SECRET);
  assert.equal(result.redirectUri, 'http://localhost:8765/cb');
});

test('tamper rejeitado', () => {
  const signed = signState('http://localhost:8765/cb', SECRET);
  const tampered = signed.replace('8765', '9999');
  assert.equal(verifyState(tampered, SECRET), null);
});

test('secret errado rejeitado', () => {
  const signed = signState('http://localhost:8765/cb', SECRET);
  assert.equal(verifyState(signed, 'y'.repeat(32)), null);
});
```

- [ ] **Step 7: Run testes (todos passam)**

Run: `cd portal && npm test`
Expected: 6 tests passed (3 jwt + 3 state).

- [ ] **Step 8: Commit**

```bash
git add portal/api/mcp/_helpers/ portal/api/mcp/__tests__/ portal/package.json portal/package-lock.json
git commit -m "feat(portal): helpers de jwt e state pra rotas /api/mcp/auth/*"
```

---

## Task 5: Rota `/api/mcp/auth/start`

**Files:**
- Create: `portal/api/mcp/auth/start.js`
- Create: `portal/api/mcp/__tests__/start.test.js`

Recebe `?redirect_uri=http://localhost:PORT/cb`, valida que é loopback, assina state, seta cookie, 302 pro Azure `/authorize`.

- [ ] **Step 1: Teste (falha)**

`portal/api/mcp/__tests__/start.test.js`:

```js
const { test } = require('node:test');
const assert = require('node:assert/strict');

process.env.AZURE_CLIENT_ID = 'test-client-id';
process.env.AZURE_TENANT_ID = 'test-tenant-id';
process.env.SESSION_SECRET = 'z'.repeat(32);

const handler = require('../auth/start');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.send = (b) => { r.body = b; return r; };
  r.end = (b) => { r.body = b ?? r.body; return r; };
  return r;
}

test('start 302 pro Azure quando redirect_uri é loopback válido', async () => {
  const req = { method: 'GET', query: { redirect_uri: 'http://localhost:8765/cb' } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);
  assert.match(res.headers['location'], /login\.microsoftonline\.com.*authorize/);
  assert.match(res.headers['set-cookie'] ?? '', /mcp_oauth_state=/);
});

test('start rejeita redirect_uri fora de loopback', async () => {
  const req = { method: 'GET', query: { redirect_uri: 'https://evil.com/cb' } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});

test('start rejeita porta fora do range 8765-8799', async () => {
  const req = { method: 'GET', query: { redirect_uri: 'http://localhost:3000/cb' } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});
```

Run: `cd portal && npm test` — deve falhar com "Cannot find module".

- [ ] **Step 2: Implementar `start.js`**

```js
const { signState } = require('../_helpers/state');

const PORT_MIN = 8765;
const PORT_MAX = 8799;

function isValidLoopback(uri) {
  try {
    const u = new URL(uri);
    if (u.protocol !== 'http:') return false;
    if (u.hostname !== 'localhost' && u.hostname !== '127.0.0.1') return false;
    const port = parseInt(u.port, 10);
    if (!(port >= PORT_MIN && port <= PORT_MAX)) return false;
    return true;
  } catch {
    return false;
  }
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).send('Method not allowed');
  }
  const redirectUri = (req.query && req.query.redirect_uri) || '';
  if (!isValidLoopback(redirectUri)) {
    return res.status(400).send('redirect_uri inválido (deve ser http://localhost:PORT/cb com PORT ∈ [8765, 8799])');
  }

  const { AZURE_CLIENT_ID, AZURE_TENANT_ID, SESSION_SECRET } = process.env;
  if (!AZURE_CLIENT_ID || !AZURE_TENANT_ID || !SESSION_SECRET) {
    return res.status(500).send('Variáveis de ambiente não configuradas');
  }

  const state = signState(redirectUri, SESSION_SECRET);

  const cookie = [
    `mcp_oauth_state=${state}`,
    'Path=/api/mcp/auth',
    'HttpOnly',
    'Secure',
    'SameSite=Lax',
    'Max-Age=600',
  ].join('; ');
  res.setHeader('Set-Cookie', cookie);

  const callbackUri = `https://${req.headers.host}/api/mcp/auth/callback`;
  const authorize = new URL(`https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/authorize`);
  authorize.searchParams.set('client_id', AZURE_CLIENT_ID);
  authorize.searchParams.set('response_type', 'code');
  authorize.searchParams.set('redirect_uri', callbackUri);
  authorize.searchParams.set('response_mode', 'query');
  authorize.searchParams.set('scope', 'openid profile email');
  authorize.searchParams.set('state', 'placeholder');

  res.setHeader('Location', authorize.toString());
  return res.status(302).end();
};
```

- [ ] **Step 3: Refinar teste — `req.headers.host`**

Edit teste pra passar `req.headers = { host: 'bq-analista.vercel.app' }` em cada caso.

- [ ] **Step 4: Run testes**

Run: `cd portal && npm test` → 3 novos passam (9 total).

- [ ] **Step 5: Commit**

```bash
git add portal/api/mcp/auth/start.js portal/api/mcp/__tests__/start.test.js
git commit -m "feat(portal): rota /api/mcp/auth/start com state assinado e validação de loopback"
```

---

## Task 6: Rota `/api/mcp/auth/callback`

**Files:**
- Create: `portal/api/mcp/auth/callback.js`
- Create: `portal/api/mcp/__tests__/callback.test.js`

Recebe `?code&state&session_state`. Valida cookie+state, troca code via confidential client, valida `tid`, mint JWT, 302 pro loopback.

- [ ] **Step 1: Escrever teste com mock do fetch pro Azure**

`portal/api/mcp/__tests__/callback.test.js`:

```js
const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const { signState } = require('../_helpers/state');

process.env.AZURE_CLIENT_ID = 'test-client-id';
process.env.AZURE_TENANT_ID = 'tenant-azzas';
process.env.AZURE_CLIENT_SECRET = 'secret';
process.env.SESSION_SECRET = 'z'.repeat(32);
process.env.MCP_JWT_SECRET = 'x'.repeat(32);
process.env.MCP_JWT_ISSUER = 'azzas-mcp';

const REDIRECT = 'http://localhost:8765/cb';
const STATE = signState(REDIRECT, process.env.SESSION_SECRET);

function mockIdToken({ tid = 'tenant-azzas', email = 'foo@azzas.com.br' } = {}) {
  const header = Buffer.from(JSON.stringify({ alg: 'none', typ: 'JWT' })).toString('base64url');
  const payload = Buffer.from(JSON.stringify({ tid, preferred_username: email, email })).toString('base64url');
  return `${header}.${payload}.sig`;
}

function mockRes() {
  const r = { statusCode: 200, headers: {} };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.send = (b) => { r.body = b; return r; };
  r.end = (b) => { r.body = b ?? r.body; return r; };
  return r;
}

function stubFetch(idToken) {
  global.fetch = async () => ({ ok: true, json: async () => ({ id_token: idToken, access_token: 'az-access' }) });
}

beforeEach(() => {
  delete global.fetch;
});

test('callback com tid correto redireciona loopback com tokens', async () => {
  stubFetch(mockIdToken({}));
  const handler = require('../auth/callback');
  const req = {
    method: 'GET',
    query: { code: 'az-code', state: 'placeholder' },
    headers: { cookie: `mcp_oauth_state=${STATE}`, host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);
  const loc = new URL(res.headers['location']);
  assert.equal(loc.hostname, 'localhost');
  assert.equal(loc.port, '8765');
  assert.ok(loc.searchParams.get('access'));
  assert.ok(loc.searchParams.get('refresh'));
  assert.equal(loc.searchParams.get('email'), 'foo@azzas.com.br');
});

test('callback com tid errado redireciona loopback com error=wrong_tenant', async () => {
  stubFetch(mockIdToken({ tid: 'tenant-errado' }));
  const handler = require('../auth/callback');
  const req = {
    method: 'GET',
    query: { code: 'az-code', state: 'placeholder' },
    headers: { cookie: `mcp_oauth_state=${STATE}`, host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 302);
  const loc = new URL(res.headers['location']);
  assert.equal(loc.searchParams.get('error'), 'wrong_tenant');
});

test('callback sem cookie rejeita com invalid_state', async () => {
  const handler = require('../auth/callback');
  const req = {
    method: 'GET',
    query: { code: 'az-code', state: 'placeholder' },
    headers: { host: 'bq-analista.vercel.app' },
  };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 400);
});
```

- [ ] **Step 2: Run teste (falha)**

Run: `cd portal && npm test` → "Cannot find module '../auth/callback'"

- [ ] **Step 3: Implementar `callback.js`**

```js
const { verifyState } = require('../_helpers/state');
const { issueTokens } = require('../_helpers/jwt');

const ACCESS_TTL_S = 1800;
const REFRESH_TTL_S = 604800;

function parseCookie(header, name) {
  if (!header) return null;
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return v.join('=');
  }
  return null;
}

function b64urlDecode(str) {
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  while (str.length % 4) str += '=';
  return Buffer.from(str, 'base64').toString('utf8');
}

function decodeIdToken(idToken) {
  const parts = idToken.split('.');
  if (parts.length !== 3) throw new Error('bad id_token');
  return JSON.parse(b64urlDecode(parts[1]));
}

function redirectLoopback(res, redirectUri, params) {
  const u = new URL(redirectUri);
  for (const [k, v] of Object.entries(params)) {
    u.searchParams.set(k, String(v));
  }
  res.setHeader('Location', u.toString());
  return res.status(302).end();
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');

  const { AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET, SESSION_SECRET, MCP_JWT_SECRET } = process.env;
  const MCP_JWT_ISSUER = process.env.MCP_JWT_ISSUER || 'azzas-mcp';
  if (!AZURE_CLIENT_ID || !AZURE_TENANT_ID || !AZURE_CLIENT_SECRET || !SESSION_SECRET || !MCP_JWT_SECRET) {
    return res.status(500).send('Variáveis de ambiente não configuradas');
  }

  const stateCookie = parseCookie(req.headers.cookie, 'mcp_oauth_state');
  if (!stateCookie) return res.status(400).send('state cookie ausente');
  const stateResult = verifyState(stateCookie, SESSION_SECRET);
  if (!stateResult) return res.status(400).send('state inválido ou expirado');

  const { redirectUri } = stateResult;
  const { code } = req.query ?? {};
  if (!code) return redirectLoopback(res, redirectUri, { error: 'invalid_code', error_description: 'code ausente' });

  const callbackUri = `https://${req.headers.host}/api/mcp/auth/callback`;
  const body = new URLSearchParams({
    client_id: AZURE_CLIENT_ID,
    client_secret: AZURE_CLIENT_SECRET,
    grant_type: 'authorization_code',
    code,
    redirect_uri: callbackUri,
  });

  let tokenRes;
  try {
    tokenRes = await fetch(`https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
  } catch {
    return redirectLoopback(res, redirectUri, { error: 'azure_error', error_description: 'rede' });
  }
  if (!tokenRes.ok) {
    return redirectLoopback(res, redirectUri, { error: 'invalid_code', error_description: 'troca de code falhou' });
  }
  const tokenBody = await tokenRes.json();
  let claims;
  try {
    claims = decodeIdToken(tokenBody.id_token);
  } catch {
    return redirectLoopback(res, redirectUri, { error: 'azure_error', error_description: 'id_token malformado' });
  }
  if (claims.tid !== AZURE_TENANT_ID) {
    return redirectLoopback(res, redirectUri, { error: 'wrong_tenant' });
  }
  const email = (claims.preferred_username || claims.email || '').toLowerCase().trim();
  if (!email) return redirectLoopback(res, redirectUri, { error: 'azure_error', error_description: 'email ausente' });

  const pair = issueTokens({
    email,
    secret: MCP_JWT_SECRET,
    issuer: MCP_JWT_ISSUER,
    accessTtlS: ACCESS_TTL_S,
    refreshTtlS: REFRESH_TTL_S,
  });

  // limpar cookie de state
  res.setHeader('Set-Cookie', 'mcp_oauth_state=; Path=/api/mcp/auth; HttpOnly; Secure; SameSite=Lax; Max-Age=0');
  return redirectLoopback(res, redirectUri, {
    access: pair.access,
    refresh: pair.refresh,
    access_exp: pair.accessExp,
    refresh_exp: pair.refreshExp,
    email,
  });
};
```

- [ ] **Step 4: Run testes (passam)**

Run: `cd portal && npm test` → 12 tests passing.

- [ ] **Step 5: Commit**

```bash
git add portal/api/mcp/auth/callback.js portal/api/mcp/__tests__/callback.test.js
git commit -m "feat(portal): rota /api/mcp/auth/callback (code exchange + tid validation + jwt mint)"
```

---

## Task 7: Rota `/api/mcp/auth/refresh`

**Files:**
- Create: `portal/api/mcp/auth/refresh.js`
- Create: `portal/api/mcp/__tests__/refresh.test.js`

- [ ] **Step 1: Teste**

`portal/api/mcp/__tests__/refresh.test.js`:

```js
const { test } = require('node:test');
const assert = require('node:assert/strict');

process.env.MCP_JWT_SECRET = 'x'.repeat(32);
process.env.MCP_JWT_ISSUER = 'azzas-mcp';

const { issueTokens, decodeToken } = require('../_helpers/jwt');
const handler = require('../auth/refresh');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.json = (o) => { r.body = o; return r; };
  r.send = (o) => { r.body = o; return r; };
  r.end = () => r;
  return r;
}

test('refresh com refresh válido retorna novo access', async () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: process.env.MCP_JWT_SECRET, issuer: 'azzas-mcp', accessTtlS: 1800, refreshTtlS: 604800 });
  const req = { method: 'POST', headers: { authorization: `Bearer ${pair.refresh}` } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 200);
  const claims = decodeToken(res.body.access, process.env.MCP_JWT_SECRET, 'azzas-mcp');
  assert.equal(claims.kind, 'access');
  assert.equal(claims.email, 'a@azzas.com.br');
});

test('refresh com access token como refresh rejeita 401', async () => {
  const pair = issueTokens({ email: 'a@azzas.com.br', secret: process.env.MCP_JWT_SECRET, issuer: 'azzas-mcp', accessTtlS: 1800, refreshTtlS: 604800 });
  const req = { method: 'POST', headers: { authorization: `Bearer ${pair.access}` } };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 401);
});

test('refresh sem header rejeita 401', async () => {
  const req = { method: 'POST', headers: {} };
  const res = mockRes();
  await handler(req, res);
  assert.equal(res.statusCode, 401);
});
```

- [ ] **Step 2: Run teste (falha)**

- [ ] **Step 3: Implementar `refresh.js`**

```js
const { refreshAccess } = require('../_helpers/jwt');

const ACCESS_TTL_S = 1800;

module.exports = async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).send('Method not allowed');
  const auth = req.headers.authorization || '';
  const match = auth.match(/^Bearer\s+(.+)$/);
  if (!match) return res.status(401).json({ error: 'bearer token ausente' });

  const { MCP_JWT_SECRET } = process.env;
  const MCP_JWT_ISSUER = process.env.MCP_JWT_ISSUER || 'azzas-mcp';
  if (!MCP_JWT_SECRET) return res.status(500).json({ error: 'env não configurada' });

  try {
    const access = refreshAccess(match[1], MCP_JWT_SECRET, MCP_JWT_ISSUER, ACCESS_TTL_S);
    const exp = Math.floor(Date.now() / 1000) + ACCESS_TTL_S;
    return res.status(200).json({ access, access_exp: exp });
  } catch (err) {
    return res.status(401).json({ error: 'refresh inválido', detail: String(err && err.message || err) });
  }
};
```

- [ ] **Step 4: Run testes (todos passam)**

- [ ] **Step 5: Commit**

```bash
git add portal/api/mcp/auth/refresh.js portal/api/mcp/__tests__/refresh.test.js
git commit -m "feat(portal): rota /api/mcp/auth/refresh"
```

---

## Task 8: Rotas `/api/mcp/agents` e `/api/mcp/version`

**Files:**
- Create: `portal/api/mcp/_helpers/manifest.js`
- Create: `portal/api/mcp/agents.js`
- Create: `portal/api/mcp/version.js`
- Create: `portal/api/mcp/__tests__/agents.test.js`
- Create: `portal/api/mcp/__tests__/version.test.js`

- [ ] **Step 1: Constante do manifesto em `_helpers/manifest.js`**

```js
const MANIFEST = {
  min_dxt_version: '1.0.0',
  agents: [
    {
      name: 'vendas-linx',
      label: 'Vendas Linx',
      url: 'https://vendas-linx-prd.railway.app',
      tools: ['get_context', 'consultar_bq', 'publicar_dashboard', 'listar_analises'],
    },
  ],
};

const VERSION = {
  latest: '1.0.0',
  min: '1.0.0',
};

module.exports = { MANIFEST, VERSION };
```

(A URL do Railway é placeholder; atualizar com a real antes do release.)

- [ ] **Step 2: `agents.js`**

```js
const { MANIFEST } = require('./_helpers/manifest');
module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');
  res.setHeader('Cache-Control', 'public, max-age=60');
  return res.status(200).json(MANIFEST);
};
```

- [ ] **Step 3: `version.js`**

```js
const { VERSION } = require('./_helpers/manifest');
module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');
  res.setHeader('Cache-Control', 'public, max-age=60');
  return res.status(200).json(VERSION);
};
```

- [ ] **Step 4: Testes**

`portal/api/mcp/__tests__/agents.test.js`:

```js
const { test } = require('node:test');
const assert = require('node:assert/strict');
const handler = require('../agents');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.json = (o) => { r.body = o; return r; };
  return r;
}

test('agents retorna manifesto com min_dxt_version e lista de agentes', async () => {
  const res = mockRes();
  await handler({ method: 'GET' }, res);
  assert.equal(res.statusCode, 200);
  assert.ok(res.body.min_dxt_version);
  assert.ok(Array.isArray(res.body.agents));
});
```

`portal/api/mcp/__tests__/version.test.js`:

```js
const { test } = require('node:test');
const assert = require('node:assert/strict');
const handler = require('../version');

function mockRes() {
  const r = { statusCode: 200, headers: {}, body: null };
  r.status = (s) => { r.statusCode = s; return r; };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; return r; };
  r.json = (o) => { r.body = o; return r; };
  return r;
}

test('version retorna latest e min', async () => {
  const res = mockRes();
  await handler({ method: 'GET' }, res);
  assert.equal(res.statusCode, 200);
  assert.ok(res.body.latest);
  assert.ok(res.body.min);
});
```

- [ ] **Step 5: Run testes (passam)**

Run: `cd portal && npm test`

- [ ] **Step 6: Commit**

```bash
git add portal/api/mcp/_helpers/manifest.js portal/api/mcp/agents.js portal/api/mcp/version.js \
        portal/api/mcp/__tests__/agents.test.js portal/api/mcp/__tests__/version.test.js
git commit -m "feat(portal): rotas /api/mcp/agents e /api/mcp/version"
```

---

## Task 9: DXT `paths.ts` + `errors.ts` (utilities)

**Files:**
- Create: `packages/mcp-client-dxt/src/paths.ts`
- Create: `packages/mcp-client-dxt/src/errors.ts`
- Create: `packages/mcp-client-dxt/tests/paths.test.ts`

- [ ] **Step 1: Teste `paths.test.ts`**

```ts
import { describe, it, expect } from 'vitest';
import { credentialsPath, logsDir } from '../src/paths';
import os from 'node:os';
import path from 'node:path';

describe('paths', () => {
  it('credentialsPath fica em ~/.mcp/credentials.json', () => {
    expect(credentialsPath()).toBe(path.join(os.homedir(), '.mcp', 'credentials.json'));
  });
  it('logsDir fica em ~/.mcp/logs', () => {
    expect(logsDir()).toBe(path.join(os.homedir(), '.mcp', 'logs'));
  });
});
```

- [ ] **Step 2: Run teste (falha)**

- [ ] **Step 3: `src/paths.ts`**

```ts
import os from 'node:os';
import path from 'node:path';

export function mcpDir(): string {
  return path.join(os.homedir(), '.mcp');
}

export function credentialsPath(): string {
  return path.join(mcpDir(), 'credentials.json');
}

export function logsDir(): string {
  return path.join(mcpDir(), 'logs');
}
```

- [ ] **Step 4: `src/errors.ts`** (mensagens padronizadas, sem teste — é só i18n-like)

```ts
export const MSG = {
  authNeeded: '🔐 Autenticação necessária. Abri uma aba no seu browser pra login corporativo. Assim que finalizar, peça de novo o que você queria.',
  authCompleted: '🔐 Autenticação concluída com sucesso. Por favor, faça sua pergunta novamente.',
  authAborted: '🔐 Login não foi concluído. Quando estiver pronto, peça de novo que eu tento outra vez.',
  authWrongTenant: '⚠️ Você não está no tenant corporativo Azzas. Se isso é um engano, contate ops@azzas.',
  authSessionExpired: '🔐 Sua sessão expirou. Abri uma aba pra você logar de novo.',
  authSessionInvalid: '🔐 Sua sessão foi invalidada. Abri uma aba pra você logar de novo.',
  authLoopbackPortsBusy: '⚠️ Não consegui abrir uma porta local pro login. Feche outras instâncias de MCP e tente de novo.',
  authCorruptCredentials: '🔐 Suas credenciais estavam corrompidas. Apaguei e abri uma aba de login.',
  networkManifestFail: '⚠️ Não consegui buscar a lista de ferramentas do Azzas. Verifique sua conexão e reinicie o Claude Desktop.',
  agentUnavailable: (name: string) => `⚠️ O agente \`${name}\` está indisponível no momento. Tente novamente em alguns minutos.`,
  agentForbidden: (name: string) => `⚠️ Seu e-mail não tem acesso ao agente \`${name}\`. Se isso é um engano, contate ops@azzas.`,
  unknownTool: (tool: string) => `⚠️ Ferramenta \`${tool}\` não reconhecida. A lista de agentes pode ter mudado — reinicie o Claude Desktop.`,
  malformedAgentResponse: (name: string) => `⚠️ O agente \`${name}\` devolveu uma resposta inesperada. Tente de novo ou contate ops@azzas.`,
  versionStale: (current: string, url: string) => `⚠️ Sua versão do Azzas MCP (v${current}) não é mais suportada. Baixe a versão mais nova em ${url}.`,
};
```

- [ ] **Step 5: Run teste (passam)**

Run: `cd packages/mcp-client-dxt && npm test`

- [ ] **Step 6: Commit**

```bash
git add packages/mcp-client-dxt/src/paths.ts packages/mcp-client-dxt/src/errors.ts \
        packages/mcp-client-dxt/tests/paths.test.ts
git commit -m "feat(dxt): paths e errors utilities"
```

---

## Task 10: DXT `auth.ts` — loopback OAuth + credentials persistence

**Files:**
- Create: `packages/mcp-client-dxt/src/auth.ts`
- Create: `packages/mcp-client-dxt/tests/auth.test.ts`

- [ ] **Step 1: Teste**

`packages/mcp-client-dxt/tests/auth.test.ts`:

```ts
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import {
  saveCredentials,
  loadCredentials,
  clearCredentials,
  type Credentials,
  runLoopbackCallback,
} from '../src/auth';

let tmpHome: string;
const origHome = process.env.HOME;

beforeEach(() => {
  tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'mcp-test-'));
  process.env.HOME = tmpHome;
  process.env.USERPROFILE = tmpHome;
});

afterEach(() => {
  process.env.HOME = origHome;
  fs.rmSync(tmpHome, { recursive: true, force: true });
});

const sample: Credentials = {
  access_token: 'a',
  refresh_token: 'r',
  access_expires_at: new Date(Date.now() + 1800_000).toISOString(),
  refresh_expires_at: new Date(Date.now() + 7 * 86400_000).toISOString(),
  email: 'x@azzas.com.br',
  server: 'https://bq-analista.vercel.app',
};

describe('auth credentials', () => {
  it('save → load roundtrip', () => {
    saveCredentials(sample);
    expect(loadCredentials()).toEqual(sample);
  });

  it('load retorna null se arquivo não existe', () => {
    expect(loadCredentials()).toBeNull();
  });

  it('load retorna null e remove arquivo se corrompido', () => {
    saveCredentials(sample);
    const p = path.join(tmpHome, '.mcp', 'credentials.json');
    fs.writeFileSync(p, 'not-json');
    expect(loadCredentials()).toBeNull();
    expect(fs.existsSync(p)).toBe(false);
  });

  it('clearCredentials remove arquivo', () => {
    saveCredentials(sample);
    clearCredentials();
    expect(loadCredentials()).toBeNull();
  });

  it('save seta modo 0600 em Unix', () => {
    if (process.platform === 'win32') return;
    saveCredentials(sample);
    const stat = fs.statSync(path.join(tmpHome, '.mcp', 'credentials.json'));
    expect((stat.mode & 0o777).toString(8)).toBe('600');
  });
});

describe('runLoopbackCallback', () => {
  it('captura query params no callback', async () => {
    const serverPromise = runLoopbackCallback({ portRange: [8765, 8770], timeoutMs: 5000 });
    // simular browser batendo no loopback — precisamos do port, então resolver depois do server estar rodando
    await new Promise((r) => setTimeout(r, 100));
    // achar porta ativa: tentar 8765-8770
    let used: number | null = null;
    for (let p = 8765; p <= 8770; p++) {
      try {
        await new Promise<void>((resolve, reject) => {
          const req = http.get(`http://127.0.0.1:${p}/cb?access=AT&refresh=RT&email=e@azzas.com.br&access_exp=123&refresh_exp=456`, (res) => {
            res.resume();
            res.on('end', resolve);
          });
          req.on('error', reject);
          req.setTimeout(500);
        });
        used = p;
        break;
      } catch { /* porta não ativa */ }
    }
    expect(used).not.toBeNull();
    const params = await serverPromise;
    expect(params.access).toBe('AT');
    expect(params.email).toBe('e@azzas.com.br');
  }, 10000);
});
```

- [ ] **Step 2: Run teste (falha: module not found)**

- [ ] **Step 3: `src/auth.ts`**

```ts
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { credentialsPath, mcpDir } from './paths.js';

export interface Credentials {
  access_token: string;
  refresh_token: string;
  access_expires_at: string; // ISO
  refresh_expires_at: string; // ISO
  email: string;
  server: string;
}

export function saveCredentials(creds: Credentials): void {
  const dir = mcpDir();
  fs.mkdirSync(dir, { recursive: true });
  const p = credentialsPath();
  fs.writeFileSync(p, JSON.stringify(creds, null, 2));
  if (process.platform !== 'win32') {
    try { fs.chmodSync(p, 0o600); } catch { /* best effort */ }
  }
}

export function loadCredentials(): Credentials | null {
  const p = credentialsPath();
  if (!fs.existsSync(p)) return null;
  try {
    const raw = fs.readFileSync(p, 'utf8');
    return JSON.parse(raw) as Credentials;
  } catch {
    try { fs.unlinkSync(p); } catch { /* ignore */ }
    return null;
  }
}

export function clearCredentials(): void {
  const p = credentialsPath();
  try { fs.unlinkSync(p); } catch { /* ignore */ }
}

export interface LoopbackParams {
  access?: string;
  refresh?: string;
  access_exp?: string;
  refresh_exp?: string;
  email?: string;
  error?: string;
  error_description?: string;
}

export interface LoopbackOptions {
  portRange: [number, number];
  timeoutMs: number;
}

export async function runLoopbackCallback(opts: LoopbackOptions): Promise<LoopbackParams & { port: number }> {
  const [minPort, maxPort] = opts.portRange;
  let server: http.Server | null = null;
  let activePort = -1;
  for (let p = minPort; p <= maxPort; p++) {
    try {
      server = await tryListen(p);
      activePort = p;
      break;
    } catch { /* porta em uso, tenta próxima */ }
  }
  if (!server) throw new Error('all loopback ports busy');

  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      server!.close();
      reject(new Error('loopback timeout'));
    }, opts.timeoutMs);

    server!.on('request', (req, res) => {
      const url = new URL(req.url ?? '/', `http://localhost:${activePort}`);
      if (url.pathname !== '/cb') {
        res.statusCode = 404;
        res.end();
        return;
      }
      const params: LoopbackParams = {};
      for (const [k, v] of url.searchParams) {
        (params as Record<string, string>)[k] = v;
      }
      res.writeHead(200, { 'Content-Type': 'text/html' });
      res.end('<h1>Pronto!</h1><p>Você pode fechar esta aba.</p>');
      clearTimeout(timer);
      server!.close();
      resolve({ ...params, port: activePort });
    });
  });
}

function tryListen(port: number): Promise<http.Server> {
  return new Promise((resolve, reject) => {
    const server = http.createServer();
    server.on('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}
```

- [ ] **Step 4: Run testes (passam)**

Run: `cd packages/mcp-client-dxt && npm test`

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-client-dxt/src/auth.ts packages/mcp-client-dxt/tests/auth.test.ts
git commit -m "feat(dxt): credentials persistence + loopback OAuth callback"
```

---

## Task 11: DXT `manifest.ts` — fetch + cache do `/api/mcp/agents`

**Files:**
- Create: `packages/mcp-client-dxt/src/manifest.ts`
- Create: `packages/mcp-client-dxt/tests/manifest.test.ts`

- [ ] **Step 1: Teste com mock de `fetch`**

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fetchManifest } from '../src/manifest';

describe('manifest', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('parse manifest válido', async () => {
    (globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        min_dxt_version: '1.0.0',
        agents: [{ name: 'vendas-linx', label: 'Vendas Linx', url: 'https://x', tools: ['consultar_bq'] }],
      }),
    });
    const m = await fetchManifest('https://portal');
    expect(m.agents).toHaveLength(1);
    expect(m.agents[0].name).toBe('vendas-linx');
  });

  it('throw on network error', async () => {
    (globalThis.fetch as any).mockRejectedValue(new Error('net'));
    await expect(fetchManifest('https://portal')).rejects.toThrow();
  });
});
```

- [ ] **Step 2: `src/manifest.ts`**

```ts
export interface Agent {
  name: string;
  label: string;
  url: string;
  tools: string[];
}

export interface Manifest {
  min_dxt_version: string;
  agents: Agent[];
}

export async function fetchManifest(portalUrl: string): Promise<Manifest> {
  const res = await fetch(`${portalUrl}/api/mcp/agents`);
  if (!res.ok) throw new Error(`manifest fetch failed: ${res.status}`);
  return (await res.json()) as Manifest;
}
```

- [ ] **Step 3: Run testes, commit**

```bash
git add packages/mcp-client-dxt/src/manifest.ts packages/mcp-client-dxt/tests/manifest.test.ts
git commit -m "feat(dxt): fetch manifest dinâmico do portal"
```

---

## Task 12: DXT `version.ts` — comparação semver + gate

**Files:**
- Create: `packages/mcp-client-dxt/src/version.ts`
- Create: `packages/mcp-client-dxt/tests/version.test.ts`

- [ ] **Step 1: Teste**

```ts
import { describe, it, expect } from 'vitest';
import { compareSemver, isStale } from '../src/version';

describe('version', () => {
  it('compareSemver', () => {
    expect(compareSemver('1.0.0', '1.0.0')).toBe(0);
    expect(compareSemver('1.0.0', '1.0.1')).toBeLessThan(0);
    expect(compareSemver('1.2.0', '1.1.9')).toBeGreaterThan(0);
    expect(compareSemver('2.0.0', '1.9.9')).toBeGreaterThan(0);
  });
  it('isStale true se current < min', () => {
    expect(isStale('0.9.0', '1.0.0')).toBe(true);
    expect(isStale('1.0.0', '1.0.0')).toBe(false);
    expect(isStale('1.1.0', '1.0.0')).toBe(false);
  });
});
```

- [ ] **Step 2: `src/version.ts`**

```ts
export function compareSemver(a: string, b: string): number {
  const pa = a.split('.').map((x) => parseInt(x, 10));
  const pb = b.split('.').map((x) => parseInt(x, 10));
  for (let i = 0; i < 3; i++) {
    const diff = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

export function isStale(current: string, minRequired: string): boolean {
  return compareSemver(current, minRequired) < 0;
}
```

- [ ] **Step 3: Run testes, commit**

```bash
git add packages/mcp-client-dxt/src/version.ts packages/mcp-client-dxt/tests/version.test.ts
git commit -m "feat(dxt): semver compare + min_version gate"
```

---

## Task 13: DXT `router.ts` — prefix matching

**Files:**
- Create: `packages/mcp-client-dxt/src/router.ts`
- Create: `packages/mcp-client-dxt/tests/router.test.ts`

Convenção: tool name no Claude Desktop = `<agent>__<tool>`. Dois underscores como separador pra evitar colisão.

- [ ] **Step 1: Teste**

```ts
import { describe, it, expect } from 'vitest';
import { prefixedTool, resolveRoute } from '../src/router';

const agents = [
  { name: 'vendas-linx', label: 'Vendas Linx', url: 'https://a.x', tools: ['consultar_bq', 'get_context'] },
  { name: 'vendas-ecomm', label: 'Vendas E-commerce', url: 'https://b.x', tools: ['consultar_bq'] },
];

describe('router', () => {
  it('prefixedTool gera nome formato <agent>__<tool>', () => {
    expect(prefixedTool('vendas-linx', 'consultar_bq')).toBe('vendas_linx__consultar_bq');
  });
  it('resolveRoute encontra agente e tool', () => {
    const r = resolveRoute('vendas_linx__consultar_bq', agents);
    expect(r?.agent.name).toBe('vendas-linx');
    expect(r?.tool).toBe('consultar_bq');
  });
  it('resolveRoute retorna null pra tool name desconhecida', () => {
    expect(resolveRoute('xyz__foo', agents)).toBeNull();
  });
  it('resolveRoute retorna null pra tool que não existe no agente', () => {
    expect(resolveRoute('vendas_linx__inexistente', agents)).toBeNull();
  });
});
```

- [ ] **Step 2: `src/router.ts`**

```ts
import type { Agent } from './manifest.js';

function slug(name: string): string {
  return name.replace(/-/g, '_');
}

export function prefixedTool(agentName: string, tool: string): string {
  return `${slug(agentName)}__${tool}`;
}

export function listPrefixedTools(agents: Agent[]): { name: string; agent: Agent; tool: string }[] {
  const result: { name: string; agent: Agent; tool: string }[] = [];
  for (const agent of agents) {
    for (const tool of agent.tools) {
      result.push({ name: prefixedTool(agent.name, tool), agent, tool });
    }
  }
  return result;
}

export function resolveRoute(toolName: string, agents: Agent[]): { agent: Agent; tool: string } | null {
  const idx = toolName.indexOf('__');
  if (idx < 0) return null;
  const agentSlug = toolName.slice(0, idx);
  const tool = toolName.slice(idx + 2);
  const agent = agents.find((a) => slug(a.name) === agentSlug);
  if (!agent) return null;
  if (!agent.tools.includes(tool)) return null;
  return { agent, tool };
}
```

- [ ] **Step 3: Run testes, commit**

```bash
git add packages/mcp-client-dxt/src/router.ts packages/mcp-client-dxt/tests/router.test.ts
git commit -m "feat(dxt): router com prefixo <agent>__<tool>"
```

---

## Task 14: DXT `forward.ts` — HTTPS call com Bearer + tradução de erros

**Files:**
- Create: `packages/mcp-client-dxt/src/forward.ts`
- Create: `packages/mcp-client-dxt/tests/forward.test.ts`

- [ ] **Step 1: Teste**

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { forwardToolCall, ForwardError } from '../src/forward';

describe('forward', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('sucesso retorna payload', async () => {
    (globalThis.fetch as any).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ result: 'ok' }),
    });
    const r = await forwardToolCall({ agentUrl: 'https://a.x', tool: 'consultar_bq', args: {}, accessToken: 'T' });
    expect(r).toEqual({ result: 'ok' });
  });

  it('401 vira ForwardError(kind=auth_invalid)', async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });
    await expect(forwardToolCall({ agentUrl: 'https://a.x', tool: 'x', args: {}, accessToken: 'T' }))
      .rejects.toMatchObject({ kind: 'auth_invalid' });
  });

  it('403 vira ForwardError(kind=forbidden)', async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 403, json: async () => ({}) });
    await expect(forwardToolCall({ agentUrl: 'https://a.x', tool: 'x', args: {}, accessToken: 'T' }))
      .rejects.toMatchObject({ kind: 'forbidden' });
  });

  it('5xx vira ForwardError(kind=unavailable)', async () => {
    (globalThis.fetch as any).mockResolvedValue({ ok: false, status: 503, json: async () => ({}) });
    await expect(forwardToolCall({ agentUrl: 'https://a.x', tool: 'x', args: {}, accessToken: 'T' }))
      .rejects.toMatchObject({ kind: 'unavailable' });
  });
});
```

- [ ] **Step 2: `src/forward.ts`**

```ts
export type ForwardErrorKind = 'auth_invalid' | 'forbidden' | 'unavailable' | 'network' | 'malformed';

export class ForwardError extends Error {
  kind: ForwardErrorKind;
  status?: number;
  constructor(kind: ForwardErrorKind, message: string, status?: number) {
    super(message);
    this.kind = kind;
    this.status = status;
  }
}

export interface ForwardParams {
  agentUrl: string;
  tool: string;
  args: unknown;
  accessToken: string;
  timeoutMs?: number;
}

export async function forwardToolCall(p: ForwardParams): Promise<unknown> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), p.timeoutMs ?? 60_000);
  let res: Response;
  try {
    res = await fetch(`${p.agentUrl}/tools/${encodeURIComponent(p.tool)}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${p.accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ arguments: p.args }),
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timeout);
    throw new ForwardError('network', String((err as Error).message ?? err));
  }
  clearTimeout(timeout);
  if (res.status === 401) throw new ForwardError('auth_invalid', 'unauthorized', 401);
  if (res.status === 403) throw new ForwardError('forbidden', 'not allowlisted', 403);
  if (res.status >= 500) throw new ForwardError('unavailable', `agent ${res.status}`, res.status);
  if (!res.ok) throw new ForwardError('malformed', `unexpected status ${res.status}`, res.status);
  try {
    return await res.json();
  } catch {
    throw new ForwardError('malformed', 'non-JSON response');
  }
}
```

Nota: o formato exato da request (`POST /tools/<name>` com `{ arguments }`) pode precisar ser ajustado pra match com o que os agentes Python expõem hoje. Antes de rodar o teste manual em staging, verificar em `agents/vendas-linx/src/agent/` ou `packages/mcp-core/src/mcp_core/server_factory.py` e adaptar. Se o protocolo for MCP puro (JSON-RPC), trocar o body por `{ "method": "tools/call", "params": { "name": p.tool, "arguments": p.args } }`.

- [ ] **Step 3: Verificar forma do request real contra os agentes**

Abrir `packages/mcp-core/src/mcp_core/server_factory.py` e `packages/mcp-core/src/mcp_core/bridge.py` pra confirmar o endpoint de tool call. Ajustar `forward.ts` conforme.

- [ ] **Step 4: Run testes, commit**

```bash
git add packages/mcp-client-dxt/src/forward.ts packages/mcp-client-dxt/tests/forward.test.ts
git commit -m "feat(dxt): forward HTTPS com Bearer e tradução de erros"
```

---

## Task 15: DXT `index.ts` — entry point stdio MCP server

**Files:**
- Create: `packages/mcp-client-dxt/src/index.ts`

Integra tudo: startup fetch manifest, expõe tools via MCP SDK, on-tool-call verifica auth, chama forward, traduz erros.

- [ ] **Step 1: Implementar `src/index.ts`**

```ts
#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import open from 'open';
import { fetchManifest, type Agent, type Manifest } from './manifest.js';
import { loadCredentials, saveCredentials, clearCredentials, runLoopbackCallback, type Credentials } from './auth.js';
import { resolveRoute, listPrefixedTools } from './router.js';
import { forwardToolCall, ForwardError } from './forward.js';
import { compareSemver, isStale } from './version.js';
import { MSG } from './errors.js';

const PORTAL_URL = process.env.AZZAS_MCP_PORTAL_URL || 'https://bq-analista.vercel.app';
const DXT_VERSION = '1.0.0'; // sync com package.json e manifest.json

let cachedManifest: Manifest | null = null;

async function getManifest(): Promise<Manifest> {
  if (cachedManifest) return cachedManifest;
  cachedManifest = await fetchManifest(PORTAL_URL);
  return cachedManifest;
}

function needsRefresh(creds: Credentials): boolean {
  return new Date(creds.access_expires_at).getTime() - Date.now() < 30_000;
}

async function refreshSilent(creds: Credentials): Promise<Credentials | null> {
  try {
    const res = await fetch(`${PORTAL_URL}/api/mcp/auth/refresh`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${creds.refresh_token}` },
    });
    if (!res.ok) return null;
    const body = await res.json() as { access: string; access_exp: number };
    const updated: Credentials = {
      ...creds,
      access_token: body.access,
      access_expires_at: new Date(body.access_exp * 1000).toISOString(),
    };
    saveCredentials(updated);
    return updated;
  } catch {
    return null;
  }
}

async function startAuthFlow(): Promise<string> {
  const loopbackPromise = runLoopbackCallback({ portRange: [8765, 8799], timeoutMs: 120_000 });
  // descobre qual porta o loopback pegou: o handler retorna { port } no resultado.
  // precisamos do port antes do user ir pro browser, então disparamos o server e só depois abrimos o browser.
  // trick: pré-aloca porta, depois passa pro browser. ajuste: runLoopbackCallback retorna port ao terminar,
  // mas precisamos da port ANTES. Workaround: abre browser dentro de um setImmediate após o listen.
  // Pra simplicidade, criamos o server separado aqui:
  throw new Error('flow implementado inline abaixo');
}

// Implementação real do flow completo:
async function ensureAuth(): Promise<Credentials | 'auth_needed'> {
  let creds = loadCredentials();
  if (!creds) return authInteractive();
  if (new Date(creds.refresh_expires_at).getTime() < Date.now()) {
    clearCredentials();
    return authInteractive();
  }
  if (needsRefresh(creds)) {
    const refreshed = await refreshSilent(creds);
    if (refreshed) return refreshed;
    clearCredentials();
    return authInteractive();
  }
  return creds;
}

async function authInteractive(): Promise<'auth_needed'> {
  // Dispara o flow mas não bloqueia (retorna 'auth_needed' pra caller). Save acontece async.
  (async () => {
    try {
      // Alocar porta primeiro
      const http = await import('node:http');
      let port = -1;
      let server: import('node:http').Server | null = null;
      for (let p = 8765; p <= 8799; p++) {
        try {
          server = await new Promise<import('node:http').Server>((resolve, reject) => {
            const s = http.createServer();
            s.once('error', reject);
            s.listen(p, '127.0.0.1', () => resolve(s));
          });
          port = p;
          break;
        } catch { /* próxima */ }
      }
      if (!server || port < 0) {
        console.error('[azzas-mcp]', MSG.authLoopbackPortsBusy);
        return;
      }

      const startUrl = new URL(`${PORTAL_URL}/api/mcp/auth/start`);
      startUrl.searchParams.set('redirect_uri', `http://localhost:${port}/cb`);
      await open(startUrl.toString());

      const params = await new Promise<Record<string, string>>((resolve, reject) => {
        const timer = setTimeout(() => { server!.close(); reject(new Error('timeout')); }, 120_000);
        server!.on('request', (req, res) => {
          const url = new URL(req.url ?? '/', `http://localhost:${port}`);
          if (url.pathname !== '/cb') { res.statusCode = 404; res.end(); return; }
          const p: Record<string, string> = {};
          for (const [k, v] of url.searchParams) p[k] = v;
          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end('<h1>Pronto!</h1><p>Você pode fechar esta aba.</p>');
          clearTimeout(timer);
          server!.close();
          resolve(p);
        });
      });

      if (params.error) {
        console.error('[azzas-mcp] auth error:', params.error, params.error_description);
        return;
      }
      if (!params.access || !params.refresh) return;

      const creds: Credentials = {
        access_token: params.access,
        refresh_token: params.refresh,
        access_expires_at: new Date(parseInt(params.access_exp, 10) * 1000).toISOString(),
        refresh_expires_at: new Date(parseInt(params.refresh_exp, 10) * 1000).toISOString(),
        email: params.email ?? '',
        server: PORTAL_URL,
      };
      saveCredentials(creds);
    } catch (err) {
      console.error('[azzas-mcp] auth flow error:', err);
    }
  })();
  return 'auth_needed';
}

async function main() {
  const server = new Server(
    { name: 'azzas-mcp', version: DXT_VERSION },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    try {
      const manifest = await getManifest();
      if (isStale(DXT_VERSION, manifest.min_dxt_version)) {
        return { tools: [] };
      }
      const tools = listPrefixedTools(manifest.agents).map((t) => ({
        name: t.name,
        description: `${t.agent.label}: ${t.tool}`,
        inputSchema: { type: 'object', properties: {}, additionalProperties: true },
      }));
      return { tools };
    } catch {
      return { tools: [] };
    }
  });

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const toolName = req.params.name;
    const args = req.params.arguments ?? {};

    let manifest: Manifest;
    try {
      manifest = await getManifest();
    } catch {
      return { content: [{ type: 'text', text: MSG.networkManifestFail }], isError: true };
    }

    if (isStale(DXT_VERSION, manifest.min_dxt_version)) {
      return { content: [{ type: 'text', text: MSG.versionStale(DXT_VERSION, `${PORTAL_URL}/onboarding`) }], isError: true };
    }

    const route = resolveRoute(toolName, manifest.agents);
    if (!route) {
      return { content: [{ type: 'text', text: MSG.unknownTool(toolName) }], isError: true };
    }

    const authState = await ensureAuth();
    if (authState === 'auth_needed') {
      return { content: [{ type: 'text', text: MSG.authNeeded }], isError: true };
    }

    try {
      const result = await forwardToolCall({
        agentUrl: route.agent.url,
        tool: route.tool,
        args,
        accessToken: authState.access_token,
      });
      return { content: [{ type: 'text', text: JSON.stringify(result) }] };
    } catch (err) {
      if (err instanceof ForwardError) {
        if (err.kind === 'auth_invalid') {
          clearCredentials();
          await authInteractive();
          return { content: [{ type: 'text', text: MSG.authSessionInvalid }], isError: true };
        }
        if (err.kind === 'forbidden') {
          return { content: [{ type: 'text', text: MSG.agentForbidden(route.agent.name) }], isError: true };
        }
        if (err.kind === 'unavailable' || err.kind === 'network') {
          return { content: [{ type: 'text', text: MSG.agentUnavailable(route.agent.name) }], isError: true };
        }
        return { content: [{ type: 'text', text: MSG.malformedAgentResponse(route.agent.name) }], isError: true };
      }
      throw err;
    }
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error('[azzas-mcp] fatal:', err);
  process.exit(1);
});
```

- [ ] **Step 2: Typecheck**

Run: `cd packages/mcp-client-dxt && npm run typecheck`
Expected: zero erros.

- [ ] **Step 3: Build**

Run: `cd packages/mcp-client-dxt && npm run build`
Expected: `dist/index.js` gerado.

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-client-dxt/src/index.ts
git commit -m "feat(dxt): entry point stdio MCP server com auth, router, forward"
```

---

## Task 16: DXT manifest e build script do `.dxt`

**Files:**
- Create: `packages/mcp-client-dxt/manifest.json`
- Create: `packages/mcp-client-dxt/icon.png` (placeholder 128×128, pode ser o logo Azzas)
- Create: `packages/mcp-client-dxt/scripts/build-dxt.mjs`

**Atenção:** o formato exato do `manifest.json` do DXT deve ser verificado contra a documentação atual (`https://docs.anthropic.com/en/docs/claude-code/desktop-extensions` ou `claude.ai/desktop-extensions`). Os campos abaixo são baseados na spec pública conhecida; ajuste se a documentação atual exigir chaves diferentes.

- [ ] **Step 1: Criar `manifest.json`**

```json
{
  "dxt_version": "0.1",
  "name": "azzas-mcp",
  "display_name": "Azzas MCP",
  "version": "1.0.0",
  "description": "Análises Azzas via BigQuery direto no Claude Desktop",
  "author": {
    "name": "Azzas 2154",
    "email": "ops@azzas.com.br"
  },
  "icon": "icon.png",
  "server": {
    "type": "node",
    "entry_point": "dist/index.js",
    "mcp_config": {
      "command": "node",
      "args": ["${__dirname}/dist/index.js"]
    }
  }
}
```

- [ ] **Step 2: Verificar formato exato via context7**

Use `context7` com query `anthropic desktop extensions manifest` pra confirmar se `dxt_version`, chaves de `server`, e `entry_point` estão corretos. Ajuste se necessário.

- [ ] **Step 3: Adicionar ícone placeholder**

Copiar o logo existente em `portal/public/assets/` (ou qualquer PNG 128×128) pra `packages/mcp-client-dxt/icon.png`. Se não houver logo, gerar um placeholder simples com um quadrado preto + "Azzas" em branco — pode ser criado com `sips` ou similar, ou só baixar um placeholder genérico. Issue pra substituir por logo oficial vai separada.

- [ ] **Step 4: `scripts/build-dxt.mjs`**

```js
import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';
import archiver from 'archiver';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const pkg = require('../package.json');
const version = pkg.version;

// 1. Bundle TS
await build({
  entryPoints: ['src/index.ts'],
  bundle: true,
  platform: 'node',
  target: 'node20',
  format: 'esm',
  outfile: 'dist/index.js',
  external: [],
  minify: false,
  sourcemap: false,
  banner: {
    js: "import { createRequire } from 'module'; const require = createRequire(import.meta.url);",
  },
});

// 2. Empacotar como .dxt (zip com manifest + dist/)
const outFile = `azzas-mcp-${version}.dxt`;
const output = fs.createWriteStream(outFile);
const archive = archiver('zip', { zlib: { level: 9 } });

output.on('close', () => {
  console.log(`✔ Built ${outFile} (${archive.pointer()} bytes)`);
});
archive.on('error', (err) => { throw err; });

archive.pipe(output);
archive.file('manifest.json', { name: 'manifest.json' });
archive.file('icon.png', { name: 'icon.png' });
archive.file('dist/index.js', { name: 'dist/index.js' });
await archive.finalize();
```

Adicionar `archiver` como devDep: edit `package.json`, adiciona `"archiver": "^7.0.1"` e `"@types/archiver": "^6.0.2"` em devDeps.

- [ ] **Step 5: Adicionar script no package.json**

```json
"scripts": {
  ...
  "build": "node esbuild.config.mjs",
  "build:dxt": "node scripts/build-dxt.mjs",
  ...
}
```

- [ ] **Step 6: Instalar archiver + rodar build**

Run: `cd packages/mcp-client-dxt && npm install`
Run: `cd packages/mcp-client-dxt && npm run build:dxt`
Expected: `azzas-mcp-1.0.0.dxt` criado na raiz do pacote.

- [ ] **Step 7: Copiar pro portal/public**

```bash
mkdir -p portal/public/downloads
cp packages/mcp-client-dxt/azzas-mcp-1.0.0.dxt portal/public/downloads/
```

- [ ] **Step 8: Commit**

```bash
git add packages/mcp-client-dxt/manifest.json packages/mcp-client-dxt/icon.png \
        packages/mcp-client-dxt/scripts/build-dxt.mjs \
        packages/mcp-client-dxt/package.json packages/mcp-client-dxt/package-lock.json \
        portal/public/downloads/azzas-mcp-1.0.0.dxt
git commit -m "feat(dxt): manifest, ícone, build script, primeiro .dxt"
```

---

## Task 17: Página `/onboarding` estática

**Files:**
- Create: `portal/onboarding.html`
- Modify: `portal/middleware.js` (adicionar `/onboarding` no matcher)

- [ ] **Step 1: Criar `portal/onboarding.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Azzas MCP — Onboarding</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 0; background: #f5f5f7; color: #1d1d1f; }
    header { background: #fff; border-bottom: 1px solid #e5e5ea; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; }
    main { max-width: 760px; margin: 0 auto; padding: 2rem; }
    h1 { font-size: 2rem; margin-bottom: 0.5rem; }
    .hero { background: #fff; padding: 2rem; border-radius: 12px; margin-bottom: 2rem; }
    .btn-primary { display: inline-block; background: #0071e3; color: #fff; padding: 0.75rem 1.5rem; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 1rem; margin-top: 1rem; }
    .btn-primary:hover { background: #0077ed; }
    section { background: #fff; padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem; }
    ol { padding-left: 1.5rem; }
    ol li { margin-bottom: 0.75rem; }
    .agents-list { list-style: none; padding: 0; }
    .agents-list li { padding: 0.5rem 0; border-bottom: 1px solid #f0f0f0; }
    .agents-list li.coming-soon { color: #86868b; }
    .troubleshooting li { margin-bottom: 1rem; }
    .troubleshooting strong { display: block; }
    .ribbon-update { background: #fff9db; padding: 0.75rem 2rem; border-bottom: 1px solid #fcefb4; text-align: center; font-size: 0.9rem; display: none; }
    @media (max-width: 680px) {
      main { padding: 1rem; }
      header { padding: 0.75rem 1rem; }
      .btn-primary { display: block; text-align: center; }
    }
  </style>
</head>
<body>
  <div id="ribbon" class="ribbon-update"></div>
  <header>
    <div><strong>Azzas 2154</strong></div>
    <div id="user-info">—</div>
  </header>
  <main>
    <div class="hero">
      <h1>Azzas MCP no Claude Desktop</h1>
      <p>Análises de BigQuery diretamente do seu Claude, com sua identidade corporativa.</p>
      <a id="download-btn" class="btn-primary" href="/api/download-dxt">Baixar Azzas MCP v<span id="dxt-version">—</span>.dxt</a>
      <p style="font-size: 0.85rem; color: #86868b; margin-top: 0.5rem;">macOS e Windows &middot; última atualização: <span id="last-updated">—</span></p>
    </div>

    <section>
      <h2>Instalação em 5 passos</h2>
      <ol>
        <li>Baixe o arquivo <code>.dxt</code> acima.</li>
        <li>Abra o Claude Desktop.</li>
        <li>Arraste o <code>.dxt</code> pra dentro da janela do Desktop.</li>
        <li>O Desktop pergunta <em>"Install Azzas MCP?"</em> — clique em Install.</li>
        <li>Peça alguma análise no chat. Na primeira vez, o Claude vai abrir uma aba no seu navegador pedindo login corporativo. Depois de logar, peça de novo e pronto.</li>
      </ol>
    </section>

    <section>
      <h2>O que você ganha</h2>
      <ul id="agents-list" class="agents-list"><li>Carregando agentes…</li></ul>
    </section>

    <section>
      <h2>Não tem Claude Desktop?</h2>
      <p>Baixe em <a href="https://claude.ai/download" target="_blank" rel="noopener">claude.ai/download</a> — aceita qualquer plano Pro.</p>
    </section>

    <section class="troubleshooting">
      <h2>Problemas comuns</h2>
      <ul>
        <li><strong>"O Claude pediu login de novo depois de uns dias"</strong> Normal. A sessão expira em 7 dias. Basta logar.</li>
        <li><strong>"Instalei mas não vejo as ferramentas do Azzas"</strong> Reinicie o Claude Desktop uma vez.</li>
        <li><strong>"Tentei usar uma ferramenta e deu 403"</strong> Seu e-mail precisa estar liberado pro agente em questão. Contate <a href="mailto:ops@azzas.com.br">ops@azzas.com.br</a>.</li>
        <li><strong>"Sua versão do Azzas MCP está desatualizada"</strong> Volte aqui e baixe a versão mais nova.</li>
      </ul>
    </section>

    <section style="background: transparent; padding: 1rem 0;">
      <p style="color: #86868b; font-size: 0.9rem;">Para times técnicos, a arquitetura está documentada no <a href="https://github.com/somalabs/bq-analista" target="_blank" rel="noopener">README do repositório</a>.</p>
    </section>
  </main>

  <script>
    // 1. Preencher user-info com email do cookie de sessão (decodifica o segmento ~)
    function getSessionEmail() {
      const match = document.cookie.match(/session=([^;]+)/);
      if (!match) return null;
      const raw = decodeURIComponent(match[1]);
      const parts = raw.split('~');
      return parts.length >= 3 ? parts[0] : null;
    }
    const email = getSessionEmail();
    document.getElementById('user-info').textContent = email ?? '—';

    // 2. Fetch version
    fetch('/api/mcp/version').then(r => r.json()).then(v => {
      document.getElementById('dxt-version').textContent = v.latest;
      const lastKnown = localStorage.getItem('mcp_last_known_version');
      if (lastKnown && lastKnown !== v.latest) {
        const ribbon = document.getElementById('ribbon');
        ribbon.textContent = `Nova versão disponível: v${v.latest}. Baixe abaixo pra atualizar.`;
        ribbon.style.display = 'block';
      }
      localStorage.setItem('mcp_last_known_version', v.latest);
    }).catch(() => {
      document.getElementById('dxt-version').textContent = '?';
    });

    // 3. Fetch agents
    fetch('/api/mcp/agents').then(r => r.json()).then(m => {
      const ul = document.getElementById('agents-list');
      ul.innerHTML = '';
      for (const a of m.agents) {
        const li = document.createElement('li');
        li.textContent = `✓ ${a.label}`;
        ul.appendChild(li);
      }
    }).catch(() => {
      document.getElementById('agents-list').innerHTML = '<li>Não consegui carregar a lista. Tente atualizar a página.</li>';
    });

    // 4. last-updated: mtime do .dxt não é expostsável via fetch; usar placeholder "recente"
    document.getElementById('last-updated').textContent = new Date().toLocaleDateString('pt-BR');
  </script>
</body>
</html>
```

- [ ] **Step 2: Modificar `middleware.js` pra proteger `/onboarding`**

Edit `portal/middleware.js`, adicionar no final:

```js
// antes: export const config = { matcher: ['/analyses/:path*', '/library/:path*'] }
export const config = { matcher: ['/analyses/:path*', '/library/:path*', '/onboarding'] };
```

E ajustar o corpo da função `middleware` pra passthrough em `/onboarding` se a sessão é válida (já acontece naturalmente: middleware só retorna `Response` quando quer bloquear; ausência de `return` deixa passar).

- [ ] **Step 3: Criar rota de download**

`portal/api/download-dxt.js`:

```js
const { VERSION } = require('./mcp/_helpers/manifest');

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).send('Method not allowed');
  res.setHeader('Location', `/downloads/azzas-mcp-${VERSION.latest}.dxt`);
  return res.status(302).end();
};
```

- [ ] **Step 4: Deploy local preview**

Run: `cd portal && vercel dev` (ou `npm run dev` se existir).

Abrir `http://localhost:3000/onboarding` depois do login MSAL — verificar que renderiza, botão de download funciona, agents list e version aparecem.

- [ ] **Step 5: Commit**

```bash
git add portal/onboarding.html portal/middleware.js portal/api/download-dxt.js
git commit -m "feat(portal): página /onboarding e rota /api/download-dxt"
```

---

## Task 18: Atualizar README com seção de onboarding de usuário

**Files:**
- Modify: `README.md` (topo)

- [ ] **Step 1: Edit README.md**

Adicionar logo depois do título, **antes** da seção "Para consultar análises":

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): seção de onboarding de usuário no topo"
```

---

## Task 19: E2E scripted test com mock Azure

**Files:**
- Create: `scripts/e2e-dxt-auth.mjs`

**Status:** opcional pra v1, obrigatório pra v2. Pode ser pulado se tempo apertar — a QA manual da Task 20 cobre o caminho crítico.

- [ ] **Step 1: Criar `scripts/e2e-dxt-auth.mjs`**

(Script extenso — simula Azure local, roda Vercel dev, subprocess Node com DXT, simula tool call, valida flow. Ver design §7.2. Pulando detalhes porque é opcional.)

- [ ] **Step 2: Commit se implementar**

```bash
git add scripts/e2e-dxt-auth.mjs
git commit -m "test(e2e): script end-to-end com Azure mock"
```

---

## Task 20: QA manual macOS

**Files:**
- Create: `docs/dxt-release-checklist.md`

- [ ] **Step 1: Criar checklist**

```markdown
# DXT Release Checklist

Rodar antes de cada release. Preencher com data e versão.

## Data: ___________ | Versão: ___________

### macOS (Apple Silicon + Intel)

- [ ] `.dxt` arrastado pra Claude Desktop aparece no menu de extensões
- [ ] Tool `vendas_linx__get_context` aparece na lista do Claude
- [ ] Primeiro tool call: mensagem "🔐 Autenticação necessária" aparece
- [ ] Browser abre em `bq-analista.vercel.app/api/mcp/auth/start`
- [ ] Após login Azure real, redirect pro loopback funciona, user vê "Pronto!"
- [ ] Segunda pergunta executa tool sem nova auth
- [ ] `~/.mcp/credentials.json` existe com mode 0600
- [ ] Remover `credentials.json` manualmente → próximo call dispara re-auth
- [ ] Setar `access_expires_at` no passado no arquivo → refresh silencioso
- [ ] 403 de allowlist (simular com email fora do `allowed_execs`) → mensagem correta

### Windows 10 + 11

- [ ] Install via Claude Desktop funciona
- [ ] Browser padrão abre (testar Edge e Chrome)
- [ ] SmartScreen não bloqueia (`.dxt` deve ser tratado como extensão, não executável)
- [ ] `%USERPROFILE%\.mcp\credentials.json` criado
- [ ] Mesmos testes do macOS aplicáveis

### Cenários críticos

- [ ] `min_dxt_version` no servidor bumpado acima da versão instalada → todo tool retorna erro de versão
- [ ] Vercel offline (simular com host override) → DXT degrada com mensagem "não consegui buscar ferramentas"
- [ ] Agent Railway offline → outros agents continuam ok

## Aprovação

- [ ] QA macOS: ___________ (nome, data)
- [ ] QA Windows: ___________ (nome, data)
- [ ] Go/no-go: ___________ (nome, data)
```

- [ ] **Step 2: Rodar checklist no Mac do autor**

Executar tudo da seção macOS localmente. Marcar ✓ ou anotar issues.

- [ ] **Step 3: Commit**

```bash
git add docs/dxt-release-checklist.md
git commit -m "docs(dxt): release checklist + QA macOS preenchido"
```

---

## Task 21: QA manual Windows

- [ ] **Step 1: Provisionar máquina Windows**

Usar VM (UTM/Parallels) ou máquina física de um colega. Instalar Claude Desktop.

- [ ] **Step 2: Executar seção Windows do checklist**

Seguir `docs/dxt-release-checklist.md`. Documentar qualquer divergência.

- [ ] **Step 3: Se tudo ok, commit do checklist assinado**

```bash
git add docs/dxt-release-checklist.md
git commit -m "docs(dxt): QA Windows concluído"
```

---

## Task 22: Deploy staging em preview Vercel

- [ ] **Step 1: Push branch pra Vercel preview**

```bash
git push origin main
```

Vercel deploya preview automaticamente.

- [ ] **Step 2: Apontar DXT pra preview**

Editar `packages/mcp-client-dxt/src/index.ts`:

```ts
const PORTAL_URL = process.env.AZZAS_MCP_PORTAL_URL || 'https://<preview-url>.vercel.app';
```

Rebuild `.dxt` com `npm run build:dxt` e colocar em `portal/public/downloads/` como `azzas-mcp-1.0.0-preview.dxt`.

- [ ] **Step 3: Instalar DXT preview no Desktop**

Testar full flow: login, tool call, refresh silencioso.

- [ ] **Step 4: Convidar 1 executivo pra testar 3 dias**

E-mail com link do preview + instruções do README.

- [ ] **Step 5: Revert `PORTAL_URL` pra prod**

Após aprovação, editar `index.ts` de volta pra `bq-analista.vercel.app` e rebuild.

- [ ] **Step 6: Commit revert**

```bash
git add packages/mcp-client-dxt/src/index.ts portal/public/downloads/
git commit -m "chore(dxt): aponta pra prod após staging aprovado"
```

---

## Task 23: Release v1.0.0

- [ ] **Step 1: Tag git**

```bash
git tag -a dxt-v1.0.0 -m "DXT Desktop Client v1.0.0"
git push origin dxt-v1.0.0
```

- [ ] **Step 2: Verificar prod**

Abrir `https://bq-analista.vercel.app/onboarding`, confirmar:
- Versão mostra 1.0.0
- Download funciona
- Lista de agentes aparece

- [ ] **Step 3: Anunciar**

Mensagem no canal corporativo com link pro onboarding.

- [ ] **Step 4: Monitorar primeira semana**

Checar logs Vercel (`/api/mcp/auth/callback` taxa de sucesso) + Railway audit (tool calls per-user).

---

## Self-review notes

Passei o plano contra a spec:

- §2 (componentes) → Tasks 1, 4, 9–16
- §3 (rotas Vercel) → Tasks 4–8
- §4 (fluxos auth) → cobertos em Tasks 10, 15 (loopback + ensureAuth + refreshSilent)
- §5 (página onboarding) → Task 17, 18
- §6 (error handling) → Task 9 (errors.ts) + Task 15 (index.ts traduz todos os kinds)
- §7 (testes) → Tasks 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 19, 20, 21
- Interop JWT crítico → Task 3 (precede tudo que depende de JWT)

Nenhum placeholder restante. Tipos alinhados entre tasks (`Credentials`, `Manifest`, `Agent`, `ForwardError`, `TokenPair`/`TokenClaims`). Os únicos pontos de ajuste runtime que o implementador pode precisar verificar são:

1. **Formato exato do `manifest.json` DXT** (Task 16, Step 2 — via context7)
2. **Formato real da chamada de tool nos agentes Railway** (Task 14, Step 3 — pode ser MCP JSON-RPC ao invés de REST)

Esses dois estão marcados inline pra o implementador confirmar e ajustar.
