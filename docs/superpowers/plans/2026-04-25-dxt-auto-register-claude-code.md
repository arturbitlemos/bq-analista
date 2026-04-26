# DXT Auto-Register Claude Code MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quando o usuário instala o DXT no Claude Desktop, a entrada `azzas-mcp` é escrita automaticamente em `~/.claude.json` usando o Node bundled do Desktop — sem terminal, sem passos extras.

**Architecture:** Nova função `selfRegisterClaudeCode()` em módulo isolado (`claude-code-register.ts`), chamada uma vez em `main()`. Usa `process.execPath` e `process.argv[1]` do processo em execução. Loga resultado em `~/.mcp/logs/claude-code-setup.log` via `logsDir()` já existente em `paths.ts`.

**Tech Stack:** TypeScript, Node.js built-ins (`fs`, `path`, `os`), vitest para testes.

**Worktree:** Trabalhe em `.worktrees/cowork-mcp` (branch `feat/cowork-mcp`). Todos os comandos assumem `cd packages/mcp-client-dxt` dentro da worktree.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `src/claude-code-register.ts` | **Criar** | `selfRegisterClaudeCode()` — lê/escreve `~/.claude.json`, loga |
| `tests/claude-code-register.test.ts` | **Criar** | Testes da função acima |
| `src/index.ts` | **Modificar** | Importar e chamar `selfRegisterClaudeCode()` em `main()` |

---

## Task 1: Criar `src/claude-code-register.ts` com TDD

**Files:**
- Create: `src/claude-code-register.ts`
- Create: `tests/claude-code-register.test.ts`

- [ ] **Step 1: Escrever o arquivo de testes**

Crie `tests/claude-code-register.test.ts` com o conteúdo abaixo. Os imports de `../src/claude-code-register` ainda não existem — os testes vão falhar na compilação, o que é esperado.

```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { selfRegisterClaudeCode } from '../src/claude-code-register';

const FAKE_EXEC = '/fake/node';
const FAKE_SCRIPT = '/fake/dist/index.js';

let tmpHome: string;
const origHome = process.env.HOME;

beforeEach(() => {
  tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'ccr-test-'));
  process.env.HOME = tmpHome;
  process.env.USERPROFILE = tmpHome;
});

afterEach(() => {
  process.env.HOME = origHome;
  process.env.USERPROFILE = origHome;
  fs.rmSync(tmpHome, { recursive: true, force: true });
});

function claudeJsonPath() {
  return path.join(tmpHome, '.claude.json');
}
function logPath() {
  return path.join(tmpHome, '.mcp', 'logs', 'claude-code-setup.log');
}
function readClaudeJson() {
  return JSON.parse(fs.readFileSync(claudeJsonPath(), 'utf8'));
}
function readLog() {
  return fs.readFileSync(logPath(), 'utf8');
}

describe('selfRegisterClaudeCode', () => {
  it('cria ~/.claude.json com entrada correta quando arquivo não existe', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);

    const cfg = readClaudeJson();
    expect(cfg.mcpServers['azzas-mcp']).toEqual({
      type: 'stdio',
      command: FAKE_EXEC,
      args: [FAKE_SCRIPT],
      env: {},
    });
  });

  it('loga "registered" após escrever', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readLog()).toContain(`registered: command=${FAKE_EXEC} args=${FAKE_SCRIPT}`);
  });

  it('não sobrescreve quando entrada já está correta', async () => {
    // Primeira chamada: escreve
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    const mtimeBefore = fs.statSync(claudeJsonPath()).mtimeMs;

    // Segunda chamada: não deve tocar no arquivo
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    const mtimeAfter = fs.statSync(claudeJsonPath()).mtimeMs;

    expect(mtimeAfter).toBe(mtimeBefore);
  });

  it('loga "skipped" quando entrada já está correta', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readLog()).toContain('skipped: already registered with correct path');
  });

  it('atualiza entrada quando execPath mudou', async () => {
    await selfRegisterClaudeCode('/old/node', FAKE_SCRIPT);
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);

    const cfg = readClaudeJson();
    expect(cfg.mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
  });

  it('preserva outras chaves existentes em ~/.claude.json', async () => {
    fs.writeFileSync(claudeJsonPath(), JSON.stringify({
      numStartups: 42,
      mcpServers: { feedz: { type: 'http', url: 'https://x.io' } },
    }));

    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);

    const cfg = readClaudeJson();
    expect(cfg.numStartups).toBe(42);
    expect(cfg.mcpServers.feedz).toEqual({ type: 'http', url: 'https://x.io' });
    expect(cfg.mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
  });

  it('reinicializa do {} e loga warn quando ~/.claude.json tem JSON inválido', async () => {
    fs.writeFileSync(claudeJsonPath(), 'not valid json {{');

    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);

    const cfg = readClaudeJson();
    expect(cfg.mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
    expect(readLog()).toContain('warn: invalid ~/.claude.json, reinitializing');
  });

  it('loga erro mas não lança quando não tem permissão de escrita', async () => {
    // Cria o arquivo como read-only
    fs.writeFileSync(claudeJsonPath(), '{}');
    fs.chmodSync(claudeJsonPath(), 0o444);

    await expect(selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT)).resolves.toBeUndefined();
    expect(readLog()).toContain('error writing ~/.claude.json:');

    // Restore para cleanup
    fs.chmodSync(claudeJsonPath(), 0o644);
  });
});
```

- [ ] **Step 2: Rodar testes para confirmar falha de compilação**

```bash
cd /Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp/packages/mcp-client-dxt
npm test 2>&1 | tail -20
```

Esperado: erro de import `../src/claude-code-register` não encontrado.

- [ ] **Step 3: Criar `src/claude-code-register.ts`**

```typescript
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { logsDir } from './paths.js';

function claudeJsonPath(): string {
  return path.join(os.homedir(), '.claude.json');
}

function appendLog(line: string): void {
  try {
    const dir = logsDir();
    fs.mkdirSync(dir, { recursive: true });
    const logFile = path.join(dir, 'claude-code-setup.log');
    fs.appendFileSync(logFile, `[${new Date().toISOString()}] ${line}\n`);
  } catch {
    // não consegue logar o erro de log — silencioso
  }
}

export async function selfRegisterClaudeCode(
  execPath: string = process.execPath,
  scriptPath: string = process.argv[1],
): Promise<void> {
  try {
    let config: Record<string, unknown> = {};
    try {
      const raw = fs.readFileSync(claudeJsonPath(), 'utf8');
      config = JSON.parse(raw) as Record<string, unknown>;
    } catch (err: unknown) {
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') {
        appendLog('warn: invalid ~/.claude.json, reinitializing');
      }
      // ENOENT → arquivo não existe, config fica {}
    }

    const servers = (config.mcpServers ?? {}) as Record<string, unknown>;
    const existing = servers['azzas-mcp'] as { command?: string; args?: string[] } | undefined;
    if (existing?.command === execPath && existing?.args?.[0] === scriptPath) {
      appendLog('skipped: already registered with correct path');
      return;
    }

    config.mcpServers = {
      ...servers,
      'azzas-mcp': { type: 'stdio', command: execPath, args: [scriptPath], env: {} },
    };

    fs.writeFileSync(claudeJsonPath(), JSON.stringify(config, null, 2));
    appendLog(`registered: command=${execPath} args=${scriptPath}`);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    appendLog(`error writing ~/.claude.json: ${msg}`);
  }
}
```

- [ ] **Step 4: Rodar testes e confirmar que passam**

```bash
npm test 2>&1 | tail -20
```

Esperado: todos os testes de `claude-code-register.test.ts` passando (8 testes), sem regressão nos demais.

- [ ] **Step 5: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp
git add packages/mcp-client-dxt/src/claude-code-register.ts packages/mcp-client-dxt/tests/claude-code-register.test.ts
git commit -m "feat(dxt): selfRegisterClaudeCode — escreve ~/.claude.json no startup"
```

---

## Task 2: Wiring em `index.ts`

**Files:**
- Modify: `packages/mcp-client-dxt/src/index.ts` — adicionar import + call em `main()`

- [ ] **Step 1: Adicionar import no topo de `src/index.ts`**

Após a linha `import { MSG } from './errors.js';` (linha ~11), adicionar:

```typescript
import { selfRegisterClaudeCode } from './claude-code-register.js';
```

- [ ] **Step 2: Chamar `selfRegisterClaudeCode()` no início de `main()`**

`main()` começa na linha 182. Adicionar a chamada como **primeira linha** dentro da função, antes de criar o `Server`:

```typescript
async function main() {
  await selfRegisterClaudeCode();

  const server = new Server(
  // ... resto do código inalterado
```

- [ ] **Step 3: Rodar typecheck**

```bash
cd /Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp/packages/mcp-client-dxt
npm run typecheck 2>&1
```

Esperado: zero erros de TypeScript.

- [ ] **Step 4: Rodar todos os testes**

```bash
npm test 2>&1 | tail -10
```

Esperado: todos os testes passando sem regressão.

- [ ] **Step 5: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp
git add packages/mcp-client-dxt/src/index.ts
git commit -m "feat(dxt): chamar selfRegisterClaudeCode() no startup do MCP"
```

---

## Task 3: Corrigir `~/.claude.json` local (worktree → DXT instalado)

O setup atual aponta para a worktree (`/Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp/...`). Isso só funciona nessa máquina de dev. Após a Task 2, o próprio DXT instalado vai corrigir isso — mas precisamos acionar a correção manualmente antes de testar.

- [ ] **Step 1: Remover a entrada worktree**

```bash
claude mcp remove azzas-mcp 2>&1
```

Esperado: `Removed MCP server "azzas-mcp" from user config`

- [ ] **Step 2: Verificar que foi removido**

```bash
claude mcp list 2>&1 | grep azzas
```

Esperado: nenhuma linha com `azzas-mcp`.

- [ ] **Step 3: Acionar o DXT instalado para auto-registrar**

Execute o DXT instalado por 3 segundos para disparar `selfRegisterClaudeCode()`:

```bash
python3 -c "
import subprocess, json, time
proc = subprocess.Popen(
  ['node', '/Users/arturlemos/Library/Application Support/Claude/Claude Extensions/local.dxt.azzas-2154.azzas-mcp/dist/index.js'],
  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)
proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':0,'method':'initialize','params':{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'test','version':'0.1'}}}) + '\n')
proc.stdin.flush()
time.sleep(3)
proc.terminate()
proc.communicate(timeout=2)
print('done')
"
```

**Nota:** O DXT instalado ainda é a versão 1.0.3 (sem `selfRegisterClaudeCode`). Este step só vai funcionar DEPOIS que a nova versão for publicada (Task 4). Por ora, registre manualmente:

```bash
DXT_PATH="$HOME/Library/Application Support/Claude/Claude Extensions/local.dxt.azzas-2154.azzas-mcp/dist/index.js"
DXT_NODE="$(node -e 'console.log(process.execPath)')"
claude mcp add --scope user azzas-mcp -- node "$DXT_PATH" 2>&1
```

- [ ] **Step 4: Verificar que aponta para o DXT instalado**

```bash
claude mcp list 2>&1 | grep azzas
```

Esperado: `azzas-mcp: node /Users/.../Claude Extensions/local.dxt.azzas-2154.azzas-mcp/dist/index.js - ✓ Connected`

---

## Task 4: Build, bump de versão e release

Seguir o processo de release documentado (4 passos):

- [ ] **Step 1: Bump de versão para 1.0.4 em 3 arquivos**

Em `packages/mcp-client-dxt/package.json`:
```json
"version": "1.0.4"
```

Em `packages/mcp-client-dxt/src/index.ts` (linha com `DXT_VERSION`):
```typescript
const DXT_VERSION = '1.0.4'; // sync com package.json e manifest.json
```

Em `packages/mcp-client-dxt/manifest.json`:
```json
"version": "1.0.4"
```

- [ ] **Step 2: Build do DXT**

```bash
cd /Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp/packages/mcp-client-dxt
npm run build:dxt 2>&1 | tail -5
```

Esperado: `✔ DXT bundle built → dist/index.js` e geração de `azzas-mcp-1.0.4.dxt`.

- [ ] **Step 3: Copiar para portal/public/downloads**

```bash
cp -f /Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp/packages/mcp-client-dxt/azzas-mcp-1.0.4.dxt \
      /Users/arturlemos/Documents/bq-analista/portal/public/downloads/azzas-mcp-1.0.4.dxt
```

- [ ] **Step 4: Atualizar versão no manifest.js do portal**

Em `portal/api/mcp/_helpers/manifest.js`, atualizar:

```javascript
const VERSION = {
  latest: '1.0.4',
  min: '1.0.0',
};
```

- [ ] **Step 5: Rodar testes finais**

```bash
cd /Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp/packages/mcp-client-dxt
npm test 2>&1 | tail -5
```

Esperado: todos os testes passando.

- [ ] **Step 6: Commit e push**

```bash
cd /Users/arturlemos/Documents/bq-analista/.worktrees/cowork-mcp
git add packages/mcp-client-dxt/package.json \
        packages/mcp-client-dxt/src/index.ts \
        packages/mcp-client-dxt/manifest.json \
        portal/public/downloads/azzas-mcp-1.0.4.dxt \
        portal/api/mcp/_helpers/manifest.js
git commit -m "feat(dxt): v1.0.4 — auto-registra Claude Code MCP no startup"
git push origin feat/cowork-mcp
```

- [ ] **Step 7: Abrir PR para main**

```bash
gh pr create \
  --title "feat(dxt): v1.0.4 — auto-registra Claude Code MCP no startup" \
  --body "$(cat <<'EOF'
## O que muda

Quando o usuário instala o DXT e abre o Claude Desktop pela primeira vez, o MCP é registrado automaticamente em `~/.claude.json`. Isso habilita o acesso aos tools do Azzas no cowork (agente background) **sem terminal e sem passos extras**.

## Como funciona

- `selfRegisterClaudeCode()` é chamado em `main()` no startup do DXT
- Usa `process.execPath` (Node bundled do Claude Desktop) e `process.argv[1]` (path do DXT instalado)
- Idempotente: não toca no arquivo se já estiver correto
- Loga em `~/.mcp/logs/claude-code-setup.log`
- Nunca lança exceção para o processo principal

## Testes

8 novos testes em `tests/claude-code-register.test.ts` cobrindo: criação, idempotência, atualização, JSON inválido, erro de permissão, preservação de outras chaves.
EOF
)"
```
