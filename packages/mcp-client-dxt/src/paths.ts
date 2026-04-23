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
