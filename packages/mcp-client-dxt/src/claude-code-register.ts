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

// Registers azzas-mcp in ~/.claude.json so Claude Code (cowork) can use it.
// Claude Desktop's extension system handles its own registration separately.
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
