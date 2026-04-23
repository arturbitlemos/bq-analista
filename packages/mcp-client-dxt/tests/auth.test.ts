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
