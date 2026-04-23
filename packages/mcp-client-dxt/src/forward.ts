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
  callTool(name: string, args: Record<string, unknown>): Promise<unknown>;
  close(): Promise<void>;
}

export type ForwardSessionFactory = (
  agentUrl: string,
  getAccessToken: () => string,
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
  let session = pool.get(p.agentUrl);
  if (!session) {
    try {
      session = await factory(p.agentUrl, p.getAccessToken);
    } catch (err) {
      // Factory failures = connect/transport level: classify as unavailable, don't cache.
      const e = err as { message?: string };
      throw new ForwardError('unavailable', String(e.message ?? err));
    }
    pool.set(p.agentUrl, session);
  }
  try {
    return await session.callTool(p.tool, (p.args ?? {}) as Record<string, unknown>);
  } catch (err) {
    const translated = translateCallError(err);
    if (translated.kind === 'auth_invalid' || translated.kind === 'network') {
      pool.delete(p.agentUrl);
      await session.close().catch(() => undefined);
    }
    throw translated;
  }
}

function translateCallError(err: unknown): ForwardError {
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
  getAccessToken: () => string,
): Promise<ForwardSession> {
  const transport = new StreamableHTTPClientTransport(new URL(`${agentUrl.replace(/\/$/, '')}/mcp`), {
    fetch: async (input, init) => {
      const headers = new Headers(init?.headers);
      headers.set('Authorization', `Bearer ${getAccessToken()}`);
      return fetch(input, { ...init, headers });
    },
  });
  const client = new Client({ name: 'mcp-client-dxt', version: '1.0.0' });
  await client.connect(transport);
  return {
    async callTool(name, args) {
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
