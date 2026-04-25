// Manifest servido em /api/mcp/agents e constantes de versão /api/mcp/version.
// Adicionar/remover agente = editar aqui + deploy Vercel.
// URL do Railway tem que bater com o endpoint onde o agente Python está deployed.
// Agents: vendas-linx e devolucoes (agents/<name>/ no repo).

const MANIFEST = {
  min_dxt_version: '1.0.0',
  agents: [
    {
      name: 'vendas-linx',
      label: 'Vendas Linx',
      description: 'Vendas, produtos, lojas e canais — dados do sistema Linx (físico + e-commerce).',
      url: 'https://bq-analista-production.up.railway.app',
      tools: ['get_context', 'consultar_bq', 'publicar_dashboard', 'listar_analises'],
    },
    {
      name: 'devolucoes',
      label: 'Devoluções',
      description: 'Análise de devoluções, motivos e impacto na venda líquida por loja e marca.',
      url: 'https://analista-devolucoes-production.up.railway.app',
      tools: ['get_context', 'consultar_bq', 'publicar_dashboard', 'listar_analises'],
    },
  ],
};

const VERSION = {
  latest: '1.0.5',
  min: '1.0.0',
};

const SKILL_VERSION = {
  latest: '1.0.0',
};

module.exports = { MANIFEST, VERSION, SKILL_VERSION };
