import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';

export type ForwardErrorKind = 'auth_invalid' | 'forbidden' | 'unavailable' | 'network' | 'malformed';

export class ForwardError extends Error {
  kind: ForwardErrorKind;
  status?: number;
  constructor(kind: ForwardErrorKind, message: string, status?: number) {
    super(message);
    this.kind = kind;
    this.status = status;
  }
}

export interface ForwardParams {
  agentUrl: string;
  tool: string;
  args: unknown;
  getAccessToken: () => string;
  timeoutMs?: number;
}

export interface ForwardSession {
  callTool(
    name: string,
    args: Record<string, unknown>,
    getAccessToken: () => string,
  ): Promise<unknown>;
  close(): Promise<void>;
}

export type ForwardSessionFactory = (
  agentUrl: string,
  initialGetter: () => string,
) => Promise<ForwardSession>;

const pool = new Map<string, ForwardSession>();

export function _resetPoolForTesting(): void {
  for (const s of pool.values()) {
    void s.close().catch(() => undefined);
  }
  pool.clear();
}

export async function forwardToolCall(
  p: ForwardParams,
  factory: ForwardSessionFactory = defaultFactory,
): Promise<unknown> {
  const args = (p.args ?? {}) as Record<string, unknown>;
  const cached = pool.get(p.agentUrl);
  if (cached) {
    try {
      const result = await cached.callTool(p.tool, args, p.getAccessToken);
      throwIfAuthErrorInPayload(result);
      return result;
    } catch (err) {
      const translated = translateCallError(err);
      // auth_invalid/forbidden are about credentials, not stale sessions —
      // retrying with a fresh session won't help; surface to the caller.
      if (translated.kind === 'auth_invalid') {
        pool.delete(p.agentUrl);
        await cached.close().catch(() => undefined);
        throw translated;
      }
      if (translated.kind === 'forbidden') {
        throw translated;
      }
      // malformed/unavailable/network on a cached session usually means the
      // server redeployed and the session id is stale. Drop it and fall
      // through to reconnect + retry once.
      pool.delete(p.agentUrl);
      await cached.close().catch(() => undefined);
    }
  }
  let session: ForwardSession;
  try {
    session = await factory(p.agentUrl, p.getAccessToken);
  } catch (err) {
    const e = err as { message?: string };
    throw new ForwardError('unavailable', String(e.message ?? err));
  }
  pool.set(p.agentUrl, session);
  try {
    const result = await session.callTool(p.tool, args, p.getAccessToken);
    throwIfAuthErrorInPayload(result);
    return result;
  } catch (err) {
    const translated = translateCallError(err);
    if (translated.kind !== 'forbidden') {
      pool.delete(p.agentUrl);
      await session.close().catch(() => undefined);
    }
    throw translated;
  }
}

// Tool-level auth errors surface as JSON-RPC tool results with isError:true
// (HTTP 200), not as HTTP 401. Detect the canonical OAuth "invalid_token" /
// "token expired" message in the payload so the upstream reactive-refresh
// path in index.ts can fire.
function throwIfAuthErrorInPayload(result: unknown): void {
  const r = result as { content?: Array<{ type?: string; text?: string }>; isError?: boolean };
  if (!r?.isError) return;
  const text = (r.content ?? []).map((c) => c?.text ?? '').join(' ');
  if (/invalid_token|token expired/i.test(text)) {
    const err = new Error('invalid_token') as Error & { code: number };
    err.code = 401;
    throw err;
  }
}

function translateCallError(err: unknown): ForwardError {
  if (err instanceof ForwardError) return err;
  const e = err as { code?: number; message?: string };
  if (typeof e.code === 'number') {
    if (e.code === 401) return new ForwardError('auth_invalid', 'unauthorized', 401);
    if (e.code === 403) return new ForwardError('forbidden', 'not allowlisted', 403);
    if (e.code >= 500) return new ForwardError('unavailable', `agent ${e.code}`, e.code);
    return new ForwardError('malformed', `unexpected status ${e.code}`, e.code);
  }
  return new ForwardError('network', String(e.message ?? err));
}

async function defaultFactory(
  agentUrl: string,
  initialGetter: () => string,
): Promise<ForwardSession> {
  // The pool caches one ForwardSession per agentUrl across calls. Each call
  // arrives with its own getAccessToken closure (over the call's credsRef),
  // so we route the Authorization header through a mutable ref that each
  // callTool updates — otherwise the cached session would forever send the
  // Bearer token captured at session creation, even after silent refresh
  // rotated the access token on disk.
  let currentGetter = initialGetter;
  const transport = new StreamableHTTPClientTransport(new URL(`${agentUrl.replace(/\/$/, '')}/mcp`), {
    fetch: async (input, init) => {
      const headers = new Headers(init?.headers);
      headers.set('Authorization', `Bearer ${currentGetter()}`);
      return fetch(input, { ...init, headers });
    },
  });
  const client = new Client({ name: 'mcp-client-dxt', version: '1.0.0' });
  await client.connect(transport);
  return {
    async callTool(name, args, getAccessToken) {
      currentGetter = getAccessToken;
      return await client.callTool({ name, arguments: args });
    },
    async close() {
      try {
        await client.close();
      } catch {
        /* ignore */
      }
    },
  };
}
