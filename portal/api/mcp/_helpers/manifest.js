// Manifest servido em /api/mcp/agents e constantes de versão /api/mcp/version.
// Adicionar/remover agente = editar aqui + deploy Vercel.
// URL do Railway tem que bater com o endpoint onde o agente Python está deployed.
// Agents: vendas-linx e devolucoes (agents/<name>/ no repo).
// NOTA: URLs abaixo são placeholders do Railway — confirmar antes do merge pra main.

const MANIFEST = {
  min_dxt_version: '1.0.0',
  agents: [
    {
      name: 'vendas-linx',
      label: 'Vendas Linx',
      url: 'https://vendas-linx-production.up.railway.app',
      tools: ['get_context', 'consultar_bq', 'publicar_dashboard', 'listar_analises'],
    },
    {
      name: 'devolucoes',
      label: 'Devoluções',
      url: 'https://devolucoes-production.up.railway.app',
      tools: ['get_context', 'consultar_bq', 'publicar_dashboard', 'listar_analises'],
    },
  ],
};

const VERSION = {
  latest: '1.0.0',
  min: '1.0.0',
};

module.exports = { MANIFEST, VERSION };
