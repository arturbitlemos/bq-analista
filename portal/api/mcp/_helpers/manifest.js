// Manifest servido em /api/mcp/agents e constantes de versão /api/mcp/version.
// Adicionar/remover agente = editar aqui + deploy Vercel.
// URL do Railway tem que bater com o endpoint onde o agente Python está deployed.
// Agents: vendas-linx e devolucoes (agents/<name>/ no repo).

const TOOL_SCHEMAS = {
  get_context: {
    type: 'object',
    properties: {},
  },
  describe_table: {
    type: 'object',
    properties: {
      table_name: {
        type: 'string',
        description: 'Nome exato da tabela em UPPER_CASE (ex: "TB_WANMTP_VENDAS_LOJA_CAPTADO"). Use get_context para listar as tabelas disponíveis.',
      },
    },
    required: ['table_name'],
  },
  get_business_rules: {
    type: 'object',
    properties: {},
  },
  ping: {
    type: 'object',
    properties: {},
  },
  consultar_bq: {
    type: 'object',
    properties: {
      sql: {
        type: 'string',
        description: 'SELECT ou WITH query. Sempre inclua filtro de data (DATA_VENDA, DATA). Nunca SELECT *. Marca em UPPER_CASE. Datas no formato YYYY-MM-DD.',
      },
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
      html_content: { type: 'string', description: 'HTML do dashboard. Construa com data islands (<script id="data_X" type="application/json">) — use html_data_block.' },
      tags:         { type: 'array', items: { type: 'string' }, description: "Tags para categorização (ex: ['farm', 'lojas'])." },
      refresh_spec: {
        type: 'object',
        description: 'OBRIGATÓRIO. Permite que o usuário clique "Atualizar período" no portal. Sem ele a tool rejeita com refresh_spec_required.',
        properties: {
          queries: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id:  { type: 'string' },
                sql: { type: 'string', description: "SELECT/WITH com placeholders literais '{{start_date}}' e '{{end_date}}' (com aspas simples)." },
              },
              required: ['id', 'sql'],
            },
          },
          data_blocks: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                block_id: { type: 'string', description: 'Id do <script id="..."> que recebe o JSON da query.' },
                query_id: { type: 'string', description: 'Id da query em queries[].' },
              },
              required: ['block_id', 'query_id'],
            },
          },
          original_period: {
            type: 'object',
            properties: {
              start: { type: 'string', description: 'YYYY-MM-DD' },
              end:   { type: 'string', description: 'YYYY-MM-DD' },
            },
            required: ['start', 'end'],
          },
        },
        required: ['queries', 'data_blocks', 'original_period'],
      },
    },
    required: ['title', 'brand', 'period', 'description', 'html_content', 'tags', 'refresh_spec'],
  },
  listar_analises: {
    type: 'object',
    properties: {
      escopo: { type: 'string', enum: ['mine', 'public'], description: "'mine' para sandbox próprio, 'public' para biblioteca compartilhada." },
    },
    required: ['escopo'],
  },
};

const TOOL_DESCRIPTIONS = {
  get_context:        'Contexto leve: princípios analíticos, regras de PII e índice de tabelas disponíveis. Chame uma vez no início da sessão.',
  describe_table:     'Schema completo de uma tabela: colunas, tipos, flags de PII, padrões de join. Chame antes de escrever SQL para essa tabela.',
  get_business_rules: 'Regras de negócio: definições de KPIs, SQL canônico, pitfalls conhecidos. Consulte ao calcular venda líquida, LY, giro ou cobertura.',
  ping:               'Health-check: status do servidor, projeto BigQuery e datasets visíveis. Use antes de qualquer query para verificar conectividade.',
  consultar_bq:       'Executa SQL SELECT/WITH no BigQuery. Requer get_context + describe_table antes. Sempre filtre por data. Nunca SELECT *.',
  publicar_dashboard: 'Publica HTML de análise na biblioteca compartilhada do portal Azzas. refresh_spec é obrigatório (permite "Atualizar período").',
  listar_analises:    'Lista análises publicadas: mine (sandbox próprio) ou public (biblioteca compartilhada).',
};

const BASE_TOOLS = [
  'get_context',
  'describe_table',
  'get_business_rules',
  'ping',
  'consultar_bq',
  'publicar_dashboard',
  'listar_analises',
].map((name) => ({ name, description: TOOL_DESCRIPTIONS[name], inputSchema: TOOL_SCHEMAS[name] }));

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
  latest: '1.0.9',
  min: '1.0.0',
};

const SKILL_VERSION = {
  latest: '1.0.1',
};

module.exports = { MANIFEST, VERSION, SKILL_VERSION };
