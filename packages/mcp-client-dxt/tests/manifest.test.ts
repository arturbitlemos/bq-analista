import { describe, it, expect, beforeEach, vi } from 'vitest';
import { fetchManifest } from '../src/manifest';

describe('manifest', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('parse manifest válido', async () => {
    (globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        min_dxt_version: '1.0.0',
        agents: [{ name: 'vendas-linx', label: 'Vendas Linx', url: 'https://x', tools: ['consultar_bq'] }],
      }),
    });
    const m = await fetchManifest('https://portal');
    expect(m.agents).toHaveLength(1);
    expect(m.agents[0].name).toBe('vendas-linx');
  });

  it('throw on network error', async () => {
    (globalThis.fetch as any).mockRejectedValue(new Error('net'));
    await expect(fetchManifest('https://portal')).rejects.toThrow();
  });
});
