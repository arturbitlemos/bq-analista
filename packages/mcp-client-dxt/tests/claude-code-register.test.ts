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
    await selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT);
    const mtimeBefore = fs.statSync(claudeJsonPath()).mtimeMs;

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
    // Pre-create log dir so appendLog still works after tmpHome becomes non-writable
    fs.mkdirSync(path.join(tmpHome, '.mcp', 'logs'), { recursive: true });
    fs.writeFileSync(claudeJsonPath(), '{}');
    // Atomic write creates a tmp file in tmpHome, so making the directory non-writable
    // is what triggers the permission error (not just the target file).
    fs.chmodSync(tmpHome, 0o555);

    await expect(selfRegisterClaudeCode(FAKE_EXEC, FAKE_SCRIPT)).resolves.toBeUndefined();
    expect(readLog()).toContain('error writing ~/.claude.json:');

    fs.chmodSync(tmpHome, 0o755);
  });
});
