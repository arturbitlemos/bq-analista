# @azzas/mcp-client-dxt

Cliente DXT do Azzas MCP — ponte stdio que Claude Desktop instala e que encaminha tool calls pros agentes Python (`agents/*`) hospedados na Railway.

## Arquitetura

```
Claude Desktop ──stdio──► DXT client ──HTTPS + Bearer JWT──► Railway agent (FastMCP)
                              │
                              └──► portal (bq-analista.vercel.app)
                                   • /api/mcp/agents — lista dinâmica de agentes
                                   • /api/mcp/version — última versão do DXT
                                   • /auth/start — OAuth Azure AD
```

- `src/index.ts` — registra tools no formato `<agent>__<tool>` e roteia.
- `src/forward.ts` — pool de sessões MCP por `agentUrl` + classificação de erro (`auth_invalid` / `forbidden` / `unavailable` / `network` / `malformed`). Sessão stale (ex: Railway redeployed) é descartada e reconectada transparente.
- `src/auth.ts` — loopback OAuth; credenciais em `~/.azzas-mcp/credentials.json`.
- `src/jwt.ts` — validação local de JWT e refresh.
- `src/errors.ts` — mensagens user-facing em PT.

## Rodar os testes

```bash
npm test          # vitest run
npm run typecheck # tsc --noEmit
```

## Release de uma versão nova

`.dxt` é gitignored globalmente; a única cópia rastreada vive em `portal/public/downloads/` e é servida via Vercel. Pular algum passo abaixo = usuários não recebem a atualização.

### 1. Bump version (2 arquivos)

- `packages/mcp-client-dxt/package.json` → `"version"`
- `packages/mcp-client-dxt/manifest.json` → `"version"`

Os dois têm que bater.

### 2. Build

```bash
cd packages/mcp-client-dxt
npm run build:dxt   # gera dist/index.js + azzas-mcp-<VERSION>.dxt local
```

### 3. Publicar no portal

```bash
cp azzas-mcp-<NEW>.dxt ../../portal/public/downloads/
rm ../../portal/public/downloads/azzas-mcp-<OLD>.dxt
```

### 4. Bump `VERSION.latest`

Em `portal/api/mcp/_helpers/manifest.js`:

```js
const VERSION = {
  latest: '1.0.2',  // ← nova
  min: '1.0.0',
};
```

`min` só sobe quando quer forçar users antigos a atualizar — mover com cautela, quebra quem está na versão mínima.

### 5. Commit + push

```bash
# .dxt é gitignored, força:
git add -f portal/public/downloads/azzas-mcp-<NEW>.dxt
git add portal/public/downloads/azzas-mcp-<OLD>.dxt   # delete
git add portal/api/mcp/_helpers/manifest.js
git add packages/mcp-client-dxt/{package,manifest}.json packages/mcp-client-dxt/src  # se mexeu em src
git commit -m "release(dxt): v<NEW>"
git push origin main
```

Vercel redeployed automaticamente. Após deploy:

- `https://bq-analista.vercel.app/downloads/azzas-mcp-<NEW>.dxt` baixável
- `https://bq-analista.vercel.app/api/mcp/version` retorna `{"latest":"<NEW>",...}`

### 6. Users reinstalam

Claude Desktop **não auto-atualiza DXT**. Usuários precisam:

1. Settings → Extensions → remover "Azzas MCP"
2. Baixar novo `.dxt` do portal
3. Instalar manualmente

O cliente avisa via `MSG.versionStale` (em `src/errors.ts`) quando detecta que tá desatualizado — mas só se `VERSION.min` subiu.

## Checklist rápido

- [ ] `package.json` version
- [ ] `manifest.json` version
- [ ] `npm run build:dxt`
- [ ] copiar .dxt pra `portal/public/downloads/`
- [ ] remover .dxt antigo
- [ ] `VERSION.latest` em `manifest.js`
- [ ] `git add -f` + commit + push
- [ ] avisar users pra reinstalar
