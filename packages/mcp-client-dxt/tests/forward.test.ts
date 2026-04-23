import { describe, it, expect, beforeEach } from 'vitest';
import {
  forwardToolCall,
  ForwardError,
  _resetPoolForTesting,
  type ForwardSession,
  type ForwardSessionFactory,
} from '../src/forward';

function fakeSession(behavior: {
  onCall?: (name: string, args: Record<string, unknown>) => Promise<unknown>;
  onClose?: () => Promise<void>;
  callCount?: { n: number };
}): ForwardSession {
  return {
    async callTool(name, args) {
      if (behavior.callCount) behavior.callCount.n += 1;
      return behavior.onCall ? behavior.onCall(name, args) : { content: [] };
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
