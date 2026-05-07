# Release do DXT (`packages/mcp-client-dxt`)

O DXT é a extensão que os usuários instalam no Claude Desktop. Toda mudança no client do DXT, no `manifest.json`, ou no `manifest.js` do portal exige um release. Sem release, **as mudanças não chegam aos usuários**.

> ⚠️ **DXT 0.3 não aceita `prompt_for_model`.** Adicionar essa chave no `manifest.json` quebra o preview no Claude Desktop com `Unrecognized key(s) in object: 'prompt_for_model'`. O roteamento entre agentes acontece via prefixo de tool name + description do agente — ver README §8.

## Por que existe esse processo

- `.dxt` é gitignored globalmente. A única cópia rastreada do binário fica em `portal/public/downloads/`, servida via Vercel.
- O Claude Desktop **não auto-atualiza DXTs** — o usuário precisa reinstalar manualmente. O cliente só sabe que tem versão nova porque `/api/mcp/version` retorna um `latest` maior que o seu `DXT_VERSION` local.
- O `manifest.js` do portal é a fonte de verdade do `VERSION.latest`. Se você buildar o DXT mas não bumpar isso, ninguém é avisado.

## Os 4 passos

### 1. Bump de versão em três arquivos

Versões estão em sync entre:

| Arquivo | Onde |
|---|---|
| `packages/mcp-client-dxt/package.json` | `"version": "X.Y.Z"` |
| `packages/mcp-client-dxt/manifest.json` | `"version": "X.Y.Z"` (top-level, não confundir com `manifest_version`) |
| `packages/mcp-client-dxt/src/index.ts` | `const DXT_VERSION = 'X.Y.Z';` |

> **Observação**: o `DXT_VERSION` em `index.ts` é o que vai pro stale-check (`isStale(DXT_VERSION, manifest.min_dxt_version)`). Se você esquecer de bumpar esse, o build sai com versão errada e o cliente vai se reportar como a versão antiga mesmo após reinstalar.

**SemVer aplicado:**
- **Patch** (X.Y.Z → X.Y.Z+1): bug fix no client (auth, refresh, error handling).
- **Minor** (X.Y.0 → X.Y+1.0): adicionar agente, novo tool, mudar `prompt_for_model`.
- **Major** (X.0.0 → X+1.0.0): mudar contrato (ex: nome de tool, formato de auth) — exige bumpar `min_dxt_version` no portal manifest também.

### 2. Build

```bash
cd packages/mcp-client-dxt
npm run build:dxt
```

Isso roda `esbuild` (gera `dist/index.js`) e depois `scripts/build-dxt.mjs` (empacota em `azzas-mcp-X.Y.Z.dxt` na raiz do package). Saída esperada:

```
✔ DXT bundle built → dist/index.js
✔ Built azzas-mcp-X.Y.Z.dxt (~155 KB)
```

### 3. Distribuir via portal

```bash
# da raiz do repo:
cp packages/mcp-client-dxt/azzas-mcp-X.Y.Z.dxt portal/public/downloads/
rm portal/public/downloads/azzas-mcp-<VERSAO_ANTERIOR>.dxt
```

Manter só **uma** versão em `portal/public/downloads/` evita acúmulo de binários. As versões antigas continuam disponíveis no histórico do git via `git show HEAD~N:portal/public/downloads/...`.

### 4. Bumpar `VERSION.latest` no portal

Em `portal/api/mcp/_helpers/manifest.js`:

```js
const VERSION = {
  latest: 'X.Y.Z',  // ← novo
  min: '1.0.0',     // ← só mexer se a release for breaking
};
```

`min` só sobe se você fez uma release breaking (Major). Subir `min` força todos os usuários abaixo dessa versão a verem erro ao chamar qualquer tool, então use com cautela.

## Commit

O `.dxt` é gitignored, então força o add:

```bash
git add -f portal/public/downloads/azzas-mcp-X.Y.Z.dxt
git add packages/mcp-client-dxt/{package.json,manifest.json,src/index.ts}
git add -f packages/mcp-client-dxt/dist/index.js  # também é gitignored
git add portal/api/mcp/_helpers/manifest.js
git rm --cached portal/public/downloads/azzas-mcp-<VERSAO_ANTERIOR>.dxt
git commit -m "release(dxt): vX.Y.Z — <descrição curta>"
```

Push → Vercel faz deploy automático do portal → `https://bq-analista.vercel.app/downloads/azzas-mcp-X.Y.Z.dxt` fica disponível e `/api/mcp/version` passa a retornar a nova `latest`.

## Validação pós-deploy

```bash
# 1. Confirma que o portal tá servindo a versão nova
curl -s https://bq-analista.vercel.app/api/mcp/version | jq

# 2. Confirma que o download funciona
curl -sI https://bq-analista.vercel.app/downloads/azzas-mcp-X.Y.Z.dxt | head -1
# esperado: HTTP/2 200

# 3. Se mudou agentes, confirma o manifest
curl -s https://bq-analista.vercel.app/api/mcp/agents | jq '.agents[].name'
```

## Comunicação aos usuários

DXT não auto-atualiza. Usuários só descobrem que tem versão nova quando:

1. Chamam alguma tool — o DXT compara `DXT_VERSION` com `manifest.min_dxt_version` e mostra `MSG.versionStale` se estiverem abaixo do mínimo. Esse aviso só aparece em **major** releases (quando `min` sobe).
2. Você comunica explicitamente (Slack, email, link de onboarding).

Para releases minor/patch, mande um aviso manual com o link de download. O usuário precisa:
1. Baixar o novo `.dxt`.
2. No Claude Desktop, ir em **Settings → Extensions** e remover a versão antiga.
3. Arrastar o novo `.dxt` pra mesma janela.

Ver [`dxt-release-checklist.md`](dxt-release-checklist.md) para o checklist de QA antes de comunicar a release a todos os usuários.
