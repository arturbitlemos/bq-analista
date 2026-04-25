import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { selfRegisterClaudeCode } from '../src/claude-code-register';

const FAKE_EXEC = '/fake/node';
const FAKE_SCRIPT = '/fake/dist/index.js';

let tmpHome: string;
const origHome = process.env.HOME;
const origAppData = process.env.APPDATA;

beforeEach(() => {
  tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'ccr-test-'));
  process.env.HOME = tmpHome;
  process.env.USERPROFILE = tmpHome;
  // Windows: apontar APPDATA para tmpHome também
  process.env.APPDATA = path.join(tmpHome, 'AppData', 'Roaming');
});

afterEach(() => {
  process.env.HOME = origHome;
  process.env.USERPROFILE = origHome;
  process.env.APPDATA = origAppData;
  fs.rmSync(tmpHome, { recursive: true, force: true });
});

function claudeJsonPath() {
  return path.join(tmpHome, '.claude.json');
}
function desktopConfigPath() {
  if (process.platform === 'win32') {
    return path.join(tmpHome, 'AppData', 'Roaming', 'Claude', 'claude_desktop_config.json');
  }
  return path.join(tmpHome, 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
}
function logPath() {
  return path.join(tmpHome, '.mcp', 'logs', 'claude-code-setup.log');
}
function readJson(p: string) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}
function readLog() {
  return fs.readFileSync(logPath(), 'utf8');
}

const AZZAS_ENTRY = { type: 'stdio', command: FAKE_EXEC, args: [FAKE_SCRIPT], env: {} };

describe('selfRegisterClaudeCode', () => {
  it('cria ~/.claude.json com entrada correta quando arquivo não existe', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readJson(claudeJsonPath()).mcpServers['azzas-mcp']).toEqual(AZZAS_ENTRY);
  });

  it('cria claude_desktop_config.json com entrada correta quando arquivo não existe', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readJson(desktopConfigPath()).mcpServers['azzas-mcp']).toEqual(AZZAS_ENTRY);
  });

  it('loga "registered claude-code" após escrever ~/.claude.json', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readLog()).toContain(`registered claude-code: command=${FAKE_EXEC} args=${FAKE_SCRIPT}`);
  });

  it('loga "registered desktop-config" após escrever claude_desktop_config.json', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readLog()).toContain(`registered desktop-config: command=${FAKE_EXEC} args=${FAKE_SCRIPT}`);
  });

  it('não sobrescreve ~/.claude.json quando entrada já está correta', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    const mtimeBefore = fs.statSync(claudeJsonPath()).mtimeMs;
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(fs.statSync(claudeJsonPath()).mtimeMs).toBe(mtimeBefore);
  });

  it('não sobrescreve desktop-config quando entrada já está correta', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    const mtimeBefore = fs.statSync(desktopConfigPath()).mtimeMs;
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(fs.statSync(desktopConfigPath()).mtimeMs).toBe(mtimeBefore);
  });

  it('loga "skipped claude-code" quando ~/.claude.json já está correto', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readLog()).toContain('skipped claude-code: already registered with correct path');
  });

  it('loga "skipped desktop-config" quando desktop-config já está correto', async () => {
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readLog()).toContain('skipped desktop-config: already registered with correct path');
  });

  it('atualiza entrada quando execPath mudou', async () => {
    await selfRegisterClaudeCode('/old/node', FAKE_SCRIPT);
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    expect(readJson(claudeJsonPath()).mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
    expect(readJson(desktopConfigPath()).mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
  });

  it('preserva outras chaves existentes em ~/.claude.json', async () => {
    fs.writeFileSync(claudeJsonPath(), JSON.stringify({
      numStartups: 42,
      mcpServers: { feedz: { type: 'http', url: 'https://x.io' } },
    }));

    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);

    const cfg = readJson(claudeJsonPath());
    expect(cfg.numStartups).toBe(42);
    expect(cfg.mcpServers.feedz).toEqual({ type: 'http', url: 'https://x.io' });
    expect(cfg.mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
  });

  it('preserva outras chaves existentes em desktop-config', async () => {
    const dcPath = desktopConfigPath();
    fs.mkdirSync(path.dirname(dcPath), { recursive: true });
    fs.writeFileSync(dcPath, JSON.stringify({
      mcpServers: { 'n8n-mcp': { type: 'stdio', command: '/usr/bin/node', args: ['/n8n/index.js'], env: {} } },
    }));

    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);

    const cfg = readJson(dcPath);
    expect(cfg.mcpServers['n8n-mcp']).toBeDefined();
    expect(cfg.mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
  });

  it('reinicializa do {} e loga warn quando ~/.claude.json tem JSON inválido', async () => {
    fs.writeFileSync(claudeJsonPath(), 'not valid json {{');

    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);

    expect(readJson(claudeJsonPath()).mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
    expect(readLog()).toContain('warn: invalid claude-code, reinitializing');
  });

  it('loga erro mas não lança quando não tem permissão de escrita em ~/.claude.json', async () => {
    fs.writeFileSync(claudeJsonPath(), '{}');
    fs.chmodSync(claudeJsonPath(), 0o444);

    await expect(selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT)).resolves.toBeUndefined();
    expect(readLog()).toContain('error writing claude-code:');

    fs.chmodSync(claudeJsonPath(), 0o644);
  });

  it('falha em um arquivo não impede o registro no outro', async () => {
    // ~/.claude.json read-only → erro nele, mas desktop-config deve ser escrito
    fs.writeFileSync(claudeJsonPath(), '{}');
    fs.chmodSync(claudeJsonPath(), 0o444);

    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);

    expect(readJson(desktopConfigPath()).mcpServers['azzas-mcp'].command).toBe(FAKE_EXEC);
    expect(readLog()).toContain('error writing claude-code:');
    expect(readLog()).toContain('registered desktop-config:');

    fs.chmodSync(claudeJsonPath(), 0o644);
  });
});
