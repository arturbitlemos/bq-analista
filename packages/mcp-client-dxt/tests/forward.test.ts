import { describe, it, expect, beforeEach } from 'vitest';
import {
  forwardToolCall,
  ForwardError,
  _resetPoolForTesting,
  type ForwardSession,
  type ForwardSessionFactory,
} from '../src/forward';

function fakeSession(behavior: {
  onCall?: (
    name: string,
    args: Record<string, unknown>,
    getAccessToken: () => string,
  ) => Promise<unknown>;
  onClose?: () => Promise<void>;
  callCount?: { n: number };
}): ForwardSession {
  return {
    async callTool(name, args, getAccessToken) {
      if (behavior.callCount) behavior.callCount.n += 1;
      return behavior.onCall ? behavior.onCall(name, args, getAccessToken) : { content: [] };
    },
    async close() {
      if (behavior.onClose) await behavior.onClose();
    },
  };
}

describe('forwardToolCall', () => {
  beforeEach(() => _resetPoolForTesting());

  it('sucesso retorna payload do agente', async () => {
    const factory: ForwardSessionFactory = async () =>
      fakeSession({ onCall: async () => ({ content: [{ type: 'text', text: 'ok' }] }) });
    const r = await forwardToolCall(
      { agentUrl: 'https://a.x', tool: 'consultar_bq', args: { q: 1 }, getAccessToken: () => 'T' },
      factory,
    );
    expect(r).toEqual({ content: [{ type: 'text', text: 'ok' }] });
  });

  it('reusa sessão do pool entre chamadas no mesmo agentUrl', async () => {
    let created = 0;
    const counter = { n: 0 };
    const factory: ForwardSessionFactory = async () => {
      created += 1;
      return fakeSession({ callCount: counter });
    };
    await forwardToolCall({ agentUrl: 'https://a.x', tool: 'x', args: {}, getAccessToken: () => 'T' }, factory);
    await forwardToolCall({ agentUrl: 'https://a.x', tool: 'y', args: {}, getAccessToken: () => 'T' }, factory);
    expect(created).toBe(1);
    expect(counter.n).toBe(2);
  });

  it('sessão cached recebe o getAccessToken da chamada ATUAL (não da que criou a sessão)', async () => {
    // Reproduz o bug do token velho preso na pool: a primeira call cria a sessão
    // com getter Token-A; a segunda call passa getter Token-B. A sessão precisa
    // usar Token-B na segunda chamada para que tokens refrescados sejam aplicados.
    const seenTokens: string[] = [];
    const factory: ForwardSessionFactory = async () =>
      fakeSession({
        onCall: async (_name, _args, getAccessToken) => {
          seenTokens.push(getAccessToken());
          return { content: [{ type: 'text', text: 'ok' }] };
        },
      });
    await forwardToolCall(
      { agentUrl: 'https://a.x', tool: 'x', args: {}, getAccessToken: () => 'Token-A' },
      factory,
    );
    await forwardToolCall(
      { agentUrl: 'https://a.x', tool: 'x', args: {}, getAccessToken: () => 'Token-B' },
      factory,
    );
    expect(seenTokens).toEqual(['Token-A', 'Token-B']);
  });

  it('payload com "invalid_token: token expired" → ForwardError(auth_invalid) e remove sessão', async () => {
    // O servidor mcp-core levanta AuthError de dentro da tool, então o erro chega
    // como tool result (HTTP 200 + isError:true), não como HTTP 401. forward.ts
    // precisa detectar isso para acionar o refresh reativo em index.ts.
    const factory: ForwardSessionFactory = async () =>
      fakeSession({
        onCall: async () => ({
          content: [{ type: 'text', text: 'Error executing tool ping: invalid_token: token expired' }],
          isError: true,
        }),
      });
    await expect(
      forwardToolCall({ agentUrl: 'https://a.x', tool: 'ping', args: {}, getAccessToken: () => 'T' }, factory),
    ).rejects.toMatchObject({ kind: 'auth_invalid', status: 401 });
    // pool deve estar limpo após auth_invalid — próxima call cria sessão nova
    let created = 0;
    const factory2: ForwardSessionFactory = async () => {
      created += 1;
      return fakeSession({});
    };
    await forwardToolCall(
      { agentUrl: 'https://a.x', tool: 'ping', args: {}, getAccessToken: () => 'T' },
      factory2,
    );
    expect(created).toBe(1);
  });

  it('payload isError:true sem texto de auth → propaga sem virar auth_invalid', async () => {
    const factory: ForwardSessionFactory = async () =>
      fakeSession({
        onCall: async () => ({
          content: [{ type: 'text', text: 'dataset_not_allowed: foo' }],
          isError: true,
        }),
      });
    // erros de tool normais (com isError) devem vir como result, não como exception
    const r = await forwardToolCall(
      { agentUrl: 'https://a.x', tool: 'x', args: {}, getAccessToken: () => 'T' },
      factory,
    );
    expect(r).toMatchObject({ isError: true });
  });

  it('401 → ForwardError(auth_invalid) e remove sessão do pool', async () => {
    const factory: ForwardSessionFactory = async () =>
      fakeSession({
        onCall: async () => {
          const err: any = new Error('unauthorized');
          err.code = 401;
          throw err;
        },
      });
    await expect(
      forwardToolCall({ agentUrl: 'https://a.x', tool: 'x', args: {}, getAccessToken: () => 'T' }, factory),
    ).rejects.toMatchObject({ kind: 'auth_invalid', status: 401 });
    // próxima chamada deve forçar factory nova (pool limpo)
    let created = 0;
    const factory2: ForwardSessionFactory = async () => {
      created += 1;
      return fakeSession({});
    };
    await forwardToolCall({ agentUrl: 'https://a.x', tool: 'x', args: {}, getAccessToken: () => 'T' }, factory2);
    expect(created).toBe(1);
  });

  it('403 → ForwardError(forbidden)', async () => {
    const factory: ForwardSessionFactory = async () =>
      fakeSession({
        onCall: async () => {
          const err: any = new Error('forbidden');
          err.code = 403;
          throw err;
        },
      });
    await expect(
      forwardToolCall({ agentUrl: 'https://b.x', tool: 'x', args: {}, getAccessToken: () => 'T' }, factory),
    ).rejects.toMatchObject({ kind: 'forbidden', status: 403 });
  });

  it('5xx → ForwardError(unavailable)', async () => {
    const factory: ForwardSessionFactory = async () =>
      fakeSession({
        onCall: async () => {
          const err: any = new Error('bad gateway');
          err.code = 502;
          throw err;
        },
      });
    await expect(
      forwardToolCall({ agentUrl: 'https://c.x', tool: 'x', args: {}, getAccessToken: () => 'T' }, factory),
    ).rejects.toMatchObject({ kind: 'unavailable', status: 502 });
  });

  it('erro de rede (sem código HTTP) → ForwardError(network)', async () => {
    const factory: ForwardSessionFactory = async () =>
      fakeSession({
        onCall: async () => {
          throw new Error('ECONNRESET');
        },
      });
    await expect(
      forwardToolCall({ agentUrl: 'https://d.x', tool: 'x', args: {}, getAccessToken: () => 'T' }, factory),
    ).rejects.toMatchObject({ kind: 'network' });
  });

  it('sessão cached stale (server redeployed) → auto-retry com sessão nova e devolve ok', async () => {
    let created = 0;
    const factory: ForwardSessionFactory = async () => {
      created += 1;
      if (created === 1) {
        // Session A: ok no primeiro callTool, 404 nas chamadas seguintes
        // (simula Railway redeploy invalidando o session id entre calls).
        let calls = 0;
        return fakeSession({
          onCall: async () => {
            calls += 1;
            if (calls === 1) return { content: [{ type: 'text', text: 'ok-1' }] };
            const err: any = new Error('session not found');
            err.code = 404;
            throw err;
          },
        });
      }
      return fakeSession({ onCall: async () => ({ content: [{ type: 'text', text: 'ok-2' }] }) });
    };
    // Call 1: pool empty, cria A, callTool OK.
    await forwardToolCall(
      { agentUrl: 'https://s.x', tool: 'x', args: {}, getAccessToken: () => 'T' },
      factory,
    );
    // Call 2: cached A throws 404 → evict + reconnect B → retry succeeds, usuário nunca vê erro.
    const r = await forwardToolCall(
      { agentUrl: 'https://s.x', tool: 'x', args: {}, getAccessToken: () => 'T' },
      factory,
    );
    expect(r).toEqual({ content: [{ type: 'text', text: 'ok-2' }] });
    expect(created).toBe(2);
  });

  it('factory failure (connect falhou) → ForwardError(unavailable) e NÃO cacheia', async () => {
    let attempts = 0;
    const factory: ForwardSessionFactory = async () => {
      attempts += 1;
      throw new Error('connect refused');
    };
    await expect(
      forwardToolCall({ agentUrl: 'https://e.x', tool: 'x', args: {}, getAccessToken: () => 'T' }, factory),
    ).rejects.toMatchObject({ kind: 'unavailable' });
    await expect(
      forwardToolCall({ agentUrl: 'https://e.x', tool: 'x', args: {}, getAccessToken: () => 'T' }, factory),
    ).rejects.toMatchObject({ kind: 'unavailable' });
    expect(attempts).toBe(2);
  });
});
