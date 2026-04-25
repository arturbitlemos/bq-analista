// Manifest servido em /api/mcp/agents e constantes de versão /api/mcp/version.
// Adicionar/remover agente = editar aqui + deploy Vercel.
// URL do Railway tem que bater com o endpoint onde o agente Python está deployed.
// Agents: vendas-linx e devolucoes (agents/<name>/ no repo).

const TOOL_SCHEMAS = {
  get_context: {
    type: 'object',
    properties: {},
  },
  consultar_bq: {
    type: 'object',
    properties: {
      sql: { type: 'string', description: 'SELECT ou WITH query a executar no BigQuery.' },
    },
    required: ['sql'],
  },
  publicar_dashboard: {
    type: 'object',
    properties: {
      title:        { type: 'string', description: "Título do dashboard (ex: 'Farm · Produtividade por Loja · Abril/2026')." },
      brand:        { type: 'string', description: "Marca (ex: 'Farm', 'Animale')." },
      period:       { type: 'string', description: "Período coberto (ex: '2026-04-01 a 2026-04-23')." },
      description:  { type: 'string', description: 'Descrição curta do conteúdo.' },
      html_content: { type: 'string', description: 'HTML completo do dashboard.' },
      tags:         { type: 'array', items: { type: 'string' }, description: "Tags para categorização (ex: ['farm', 'lojas'])." },
    },
    required: ['title', 'brand', 'period', 'description', 'html_content', 'tags'],
  },
  listar_analises: {
    type: 'object',
    properties: {
      escopo: { type: 'string', enum: ['mine', 'public'], description: "'mine' para sandbox próprio, 'public' para biblioteca compartilhada." },
    },
    required: ['escopo'],
  },
};

const BASE_TOOLS = ['get_context', 'consultar_bq', 'publicar_dashboard', 'listar_analises']
  .map((name) => ({ name, inputSchema: TOOL_SCHEMAS[name] }));

const MANIFEST = {
  min_dxt_version: '1.0.0',
  agents: [
    {
      name: 'vendas-linx',
      label: 'Vendas Linx',
      description: 'Vendas, produtos, lojas e canais — dados do sistema Linx (físico + e-commerce).',
      url: 'https://bq-analista-production.up.railway.app',
      tools: BASE_TOOLS,
    },
    {
      name: 'devolucoes',
      label: 'Devoluções',
      description: 'Análise de devoluções, motivos e impacto na venda líquida por loja e marca.',
      url: 'https://analista-devolucoes-production.up.railway.app',
      tools: BASE_TOOLS,
    },
  ],
};

const VERSION = {
  latest: '1.0.6',
  min: '1.0.0',
};

const SKILL_VERSION = {
  latest: '1.0.0',
};

module.exports = { MANIFEST, VERSION, SKILL_VERSION };
