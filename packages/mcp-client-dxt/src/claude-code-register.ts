import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { logsDir } from './paths.js';

function claudeJsonPath(): string {
  return path.join(os.homedir(), '.claude.json');
}

function claudeDesktopConfigPath(): string {
  if (process.platform === 'win32') {
    const appData = process.env.APPDATA ?? path.join(os.homedir(), 'AppData', 'Roaming');
    return path.join(appData, 'Claude', 'claude_desktop_config.json');
  }
  return path.join(os.homedir(), 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
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

function registerInFile(filePath: string, execPath: string, scriptPath: string, label: string): void {
  try {
    let config: Record<string, unknown> = {};
    try {
      const raw = fs.readFileSync(filePath, 'utf8');
      config = JSON.parse(raw) as Record<string, unknown>;
    } catch (err: unknown) {
      if ((err as NodeJS.ErrnoException).code !== 'ENOENT') {
        appendLog(`warn: invalid ${label}, reinitializing`);
      }
    }

    const servers = (config.mcpServers ?? {}) as Record<string, unknown>;
    const existing = servers['azzas-mcp'] as { command?: string; args?: string[] } | undefined;
    if (existing?.command === execPath && existing?.args?.[0] === scriptPath) {
      appendLog(`skipped ${label}: already registered with correct path`);
      return;
    }

    config.mcpServers = {
      ...servers,
      'azzas-mcp': { type: 'stdio', command: execPath, args: [scriptPath], env: {} },
    };

    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, JSON.stringify(config, null, 2));
    appendLog(`registered ${label}: command=${execPath} args=${scriptPath}`);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    appendLog(`error writing ${label}: ${msg}`);
  }
}

export async function selfRegisterClaudeCode(
  execPath: string = process.execPath,
  scriptPath: string = process.argv[1],
): Promise<void> {
  registerInFile(claudeJsonPath(), execPath, scriptPath, 'claude-code');
  registerInFile(claudeDesktopConfigPath(), execPath, scriptPath, 'desktop-config');
}
