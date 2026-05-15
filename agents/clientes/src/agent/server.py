from mcp_core.server_factory import build_mcp_app

_INSTRUCTIONS = """\
Agente de **Clientes** do grupo Azzas 2154 — análise de base de clientes, segmentação
Novo/Retido/Reativado, receita, VA, MACO, Markup, Ticket Médio, Frequência, PA e PM
via BigQuery.

Comece toda sessão chamando `get_context` para carregar princípios analíticos e índice
de tabelas. Para schema completo use `describe_table`. Para fórmulas canônicas use
`get_business_rules`.

**ROTEAMENTO — quando usar este agente vs vendas-linx:**
- Para qualquer indicador de negócio (receita, ticket, volume, etc.) o **default é o
  agente vendas-linx**. Este agente só deve ser usado quando o pedido for explícito
  sob ótica de clientes (base ativa, novo/retido/reativado, LTV, recência, frequência,
  segmentação de base, etc.).
- A receita aqui **NÃO bate** com a do agente de vendas — e isso é por desenho:
  marketplaces (ex.: Mercado Livre) geram receita do Azzas 2154 mas o cliente final
  pertence ao marketplace, então não entram no universo deste agente. Se o usuário
  estranhar a divergência, **explique esse motivo**.

**PERSPECTIVA DE ANÁLISE — sempre declarar:**
- Os indicadores podem ser vistos sob **duas perspectivas distintas, com fontes de
  dados diferentes**:
  - **Ano de competência** — janelas fechadas por ano calendário (fonte:
    `soma-crm-bi.dashboards_corp.acomp_clientes_base`)
  - **Janela móvel 12m** — últimos 12 meses corridos da data de referência (fonte
    a ser confirmada)
- A mesma compra pode classificar o cliente em status diferentes em cada perspectiva.
  Exemplo: cliente compra 30/dez/2026 + 01/jan/2027 → Retido no ano de competência
  2027, ainda Novo na janela móvel até 31/dez/2027.
- **Sempre declare na resposta qual perspectiva está sendo usada.** Se o pedido não
  especificar, **pergunte** antes de calcular.

Exemplos rápidos do que o usuário pode perguntar:
• "Quantos clientes novos a FARM teve em 2026?"
• "Qual o VA dos clientes retidos da Animale?"
• "Decompõe a árvore lógica: Receita = Qtde Clientes × VA"
• "Comparar PM e PA por canal de entrada"

Para um catálogo mais amplo de perguntas chame `exemplos_perguntas`.

Regras invioláveis:
- Nunca expor PII (CPF, e-mail, nome, telefone, ID individual de cliente).
- Toda métrica temporal deve trazer comparação vs Last Year (LY) — sem proxy.
- Declarar canal (default = `tipo_canal = 'canal entrada'`) e perspectiva (ano de
  competência ou janela móvel) em toda resposta.
- Excluir linhas com `marca IS NULL` por padrão (replica filtro do dashboard
  gabarito).
"""

_EXEMPLOS = """\
# Catálogo de perguntas — Clientes

## Volume da base
- "Quantos clientes a {marca} teve em {período}? (ano de competência ou janela móvel?)"
- "Decompõe a quantidade de clientes em Novo / Retido / Reativado"
- "Qual a participação de cada marca na base total de clientes?"

## Segmentação por status
- "Qual o VA dos clientes Novos vs Retidos da {marca}?"
- "Receita por status de cliente — visão consolidada do grupo"
- "Qual a marca com maior taxa de reativação no {período}?"

## Árvore lógica
- "Decompõe Receita = Qtde Clientes × VA para a {marca}"
- "Decompõe VA = Ticket Médio × Frequência"
- "Decompõe Ticket Médio = PA × PM"

## Rentabilidade
- "MACO e Markup por status de cliente"
- "Comparar Markup entre canais de entrada"

## Canal
- "Receita por Canal de Entrada vs Canal de Cliente"
- "Distribuição de clientes Multicanal por marca"

## Dicas para boas perguntas
- Sempre especifique a **perspectiva** (ano de competência ou janela móvel). Se
  não souber, peça orientação ao agente.
- Especifique **marca** e **período** — economiza ida-e-volta.
- Para análise por canal, lembre que filtrar por canal muda a base agregada (de
  `tipo_canal = 'canal entrada'` para `'canal'`).
"""

# Herda as 7 ferramentas base (get_context, describe_table, get_business_rules,
# ping, consultar_bq, publicar_dashboard, listar_analises) + exemplos_perguntas.
app, main = build_mcp_app(
    agent_name="mcp-exec-clientes",
    instructions=_INSTRUCTIONS,
    exemplos=_EXEMPLOS,
)

# Adicione ferramentas específicas do domínio clientes aqui, se necessário.

if __name__ == "__main__":
    main()
