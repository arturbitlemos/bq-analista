import { describe, it, expect } from 'vitest';
import { prefixedTool, resolveRoute } from '../src/router';

const agents = [
  { name: 'vendas-linx', label: 'Vendas Linx', url: 'https://a.x', tools: ['consultar_bq', 'get_context'] },
  { name: 'vendas-ecomm', label: 'Vendas E-commerce', url: 'https://b.x', tools: ['consultar_bq'] },
];

describe('router', () => {
  it('prefixedTool gera nome formato <agent>__<tool>', () => {
    expect(prefixedTool('vendas-linx', 'consultar_bq')).toBe('vendas_linx__consultar_bq');
  });
  it('resolveRoute encontra agente e tool', () => {
    const r = resolveRoute('vendas_linx__consultar_bq', agents);
    expect(r?.agent.name).toBe('vendas-linx');
    expect(r?.tool).toBe('consultar_bq');
  });
  it('resolveRoute retorna null pra tool name desconhecida', () => {
    expect(resolveRoute('xyz__foo', agents)).toBeNull();
  });
  it('resolveRoute retorna null pra tool que não existe no agente', () => {
    expect(resolveRoute('vendas_linx__inexistente', agents)).toBeNull();
  });
});
