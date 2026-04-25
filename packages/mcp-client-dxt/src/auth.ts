import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { credentialsPath, mcpDir } from './paths.js';
import { renderCallbackPage } from './callback-page.js';

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
  nonce?: string;
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
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(renderCallbackPage(params));
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
