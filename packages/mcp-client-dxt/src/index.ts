#!/usr/bin/env node
import crypto from 'node:crypto';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import open from 'open';
import { fetchManifest, type Manifest } from './manifest.js';
import { loadCredentials, saveCredentials, clearCredentials, type Credentials } from './auth.js';
import { resolveRoute, listPrefixedTools } from './router.js';
import { forwardToolCall, ForwardError } from './forward.js';
import { isStale } from './version.js';
import { MSG } from './errors.js';

const PORTAL_URL = process.env.AZZAS_MCP_PORTAL_URL || 'https://bq-analista.vercel.app';
const DXT_VERSION = '1.0.0'; // sync com package.json e manifest.json

let cachedManifest: Manifest | null = null;

// Guard: only one auth flow at a time
let authInProgress: Promise<void> | null = null;

async function getManifest(): Promise<Manifest> {
  if (cachedManifest) return cachedManifest;
  cachedManifest = await fetchManifest(PORTAL_URL);
  return cachedManifest;
}

function needsRefresh(creds: Credentials): boolean {
  return new Date(creds.access_expires_at).getTime() - Date.now() < 30_000;
}

async function refreshSilent(creds: Credentials): Promise<Credentials | null> {
  try {
    const res = await fetch(`${PORTAL_URL}/api/mcp/auth/refresh`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${creds.refresh_token}` },
    });
    if (!res.ok) return null;
    const body = await res.json() as { access: string; access_exp: number };
    const updated: Credentials = {
      ...creds,
      access_token: body.access,
      access_expires_at: new Date(body.access_exp * 1000).toISOString(),
    };
    saveCredentials(updated);
    return updated;
  } catch {
    return null;
  }
}

async function ensureAuth(): Promise<Credentials | 'auth_needed'> {
  const creds = loadCredentials();
  if (!creds) return authInteractive();
  if (new Date(creds.refresh_expires_at).getTime() < Date.now()) {
    clearCredentials();
    return authInteractive();
  }
  if (needsRefresh(creds)) {
    const refreshed = await refreshSilent(creds);
    if (refreshed) return refreshed;
    clearCredentials();
    return authInteractive();
  }
  return creds;
}

function timingEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  return crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b));
}

async function runAuthFlow(expectedNonce: string): Promise<void> {
  try {
    const http = await import('node:http');
    let port = -1;
    let server: import('node:http').Server | null = null;
    for (let p = 8765; p <= 8799; p++) {
      try {
        server = await new Promise<import('node:http').Server>((resolve, reject) => {
          const s = http.createServer();
          s.once('error', reject);
          s.listen(p, '127.0.0.1', () => resolve(s));
        });
        port = p;
        break;
      } catch { /* próxima */ }
    }
    if (!server || port < 0) {
      console.error('[azzas-mcp]', MSG.authLoopbackPortsBusy);
      return;
    }

    const startUrl = new URL(`${PORTAL_URL}/api/mcp/auth/start`);
    startUrl.searchParams.set('redirect_uri', `http://localhost:${port}/cb`);
    startUrl.searchParams.set('nonce', expectedNonce);
    await open(startUrl.toString());

    const params = await new Promise<Record<string, string>>((resolve, reject) => {
      const timer = setTimeout(() => { server!.close(); reject(new Error('timeout')); }, 120_000);
      server!.on('request', (req, res) => {
        const url = new URL(req.url ?? '/', `http://localhost:${port}`);
        if (url.pathname !== '/cb') { res.statusCode = 404; res.end(); return; }
        const p: Record<string, string> = {};
        for (const [k, v] of url.searchParams) p[k] = v;
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end('<h1>Pronto!</h1><p>Você pode fechar esta aba.</p>');
        clearTimeout(timer);
        server!.close();
        resolve(p);
      });
    });

    if (params.error) {
      console.error('[azzas-mcp] auth error:', params.error, params.error_description);
      return;
    }

    // Validate nonce before trusting any credential data
    if (!params.error) {
      const got = params.nonce ?? '';
      if (!timingEqual(got, expectedNonce)) {
        console.error('[azzas-mcp] nonce mismatch — abortando');
        return;
      }
    }

    if (!params.access || !params.refresh) return;

    const creds: Credentials = {
      access_token: params.access,
      refresh_token: params.refresh,
      access_expires_at: new Date(parseInt(params.access_exp, 10) * 1000).toISOString(),
      refresh_expires_at: new Date(parseInt(params.refresh_exp, 10) * 1000).toISOString(),
      email: params.email ?? '',
      server: PORTAL_URL,
    };
    saveCredentials(creds);
  } catch (err) {
    console.error('[azzas-mcp] auth flow error:', err);
  }
}

async function authInteractive(): Promise<'auth_needed'> {
  // If a flow is already in progress, don't start another one.
  if (authInProgress) return 'auth_needed';
  const nonce = crypto.randomBytes(16).toString('base64url');
  authInProgress = runAuthFlow(nonce).finally(() => { authInProgress = null; });
  return 'auth_needed';
}

async function main() {
  const server = new Server(
    { name: 'azzas-mcp', version: DXT_VERSION },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    try {
      const manifest = await getManifest();
      if (isStale(DXT_VERSION, manifest.min_dxt_version)) {
        return { tools: [] };
      }
      const tools = listPrefixedTools(manifest.agents).map((t) => ({
        name: t.name,
        description: `${t.agent.label}: ${t.tool}`,
        inputSchema: { type: 'object', properties: {}, additionalProperties: true },
      }));
      return { tools };
    } catch {
      return { tools: [] };
    }
  });

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const toolName = req.params.name;
    const args = req.params.arguments ?? {};

    let manifest: Manifest;
    try {
      manifest = await getManifest();
    } catch {
      return { content: [{ type: 'text', text: MSG.networkManifestFail }], isError: true };
    }

    if (isStale(DXT_VERSION, manifest.min_dxt_version)) {
      return { content: [{ type: 'text', text: MSG.versionStale(DXT_VERSION, `${PORTAL_URL}/onboarding`) }], isError: true };
    }

    const route = resolveRoute(toolName, manifest.agents);
    if (!route) {
      return { content: [{ type: 'text', text: MSG.unknownTool(toolName) }], isError: true };
    }

    const authState = await ensureAuth();
    if (authState === 'auth_needed') {
      return { content: [{ type: 'text', text: MSG.authNeeded }], isError: true };
    }

    try {
      const result = await forwardToolCall({
        agentUrl: route.agent.url,
        tool: route.tool,
        args,
        getAccessToken: () => authState.access_token,
      });
      // forward retorna o CallToolResult do agente Python (já no formato MCP).
      // Passar direto pro Claude Desktop sem re-serializar.
      return result as { content: unknown[]; isError?: boolean };
    } catch (err) {
      if (err instanceof ForwardError) {
        if (err.kind === 'auth_invalid') {
          clearCredentials();
          await authInteractive();
          return { content: [{ type: 'text', text: MSG.authSessionInvalid }], isError: true };
        }
        if (err.kind === 'forbidden') {
          return { content: [{ type: 'text', text: MSG.agentForbidden(route.agent.name) }], isError: true };
        }
        if (err.kind === 'unavailable' || err.kind === 'network') {
          return { content: [{ type: 'text', text: MSG.agentUnavailable(route.agent.name) }], isError: true };
        }
        return { content: [{ type: 'text', text: MSG.malformedAgentResponse(route.agent.name) }], isError: true };
      }
      throw err;
    }
  });

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error('[azzas-mcp] fatal:', err);
  process.exit(1);
});
