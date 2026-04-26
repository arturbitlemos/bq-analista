from mcp_core.server_factory import build_mcp_app

_INSTRUCTIONS = """\
Agente de **Devoluções** do grupo Azzas 2154 — análise de trocas, devoluções,
estornos, motivos, SLA logístico e geografia das 9 marcas, via BigQuery
(`soma-crm-bi.dados_trusted.trusted_troque_devolucao`).

Comece toda sessão chamando `get_context` para carregar princípios analíticos e
índice de tabelas. Para schema completo use `describe_table`. Para regras de
negócio (tipos de reversa, filtros obrigatórios) use `get_business_rules`.

Exemplos rápidos do que o usuário pode perguntar:
• "Taxa de devolução da Farm em abril vs LY"
• "Top 10 motivos de devolução da Animale no último trimestre"
• "Quais lojas têm mais devolução por estado (SP)?"
• "SLA médio de reversa por marca na última semana"

Para um catálogo mais amplo de perguntas chame `exemplos_perguntas`.

Regras invioláveis:
- Nunca expor PII (CPF, e-mail, nome, telefone, ID individual de cliente).
- Sempre confirmar **marca** + **tipo de reversa** + **período** antes da 1ª query
  — só pular se já estiverem claros na pergunta.
- Toda métrica temporal deve trazer comparação vs Last Year (LY).
- Publicar dashboard só quando o usuário pedir explicitamente.
"""

_EXEMPLOS = """\
# Catálogo de perguntas — Devoluções

## Volume e taxa
- "Quantas devoluções da {marca} em {período}?"
- "Taxa de devolução (% sobre venda) por marca em {período} vs LY"
- "Curva diária / semanal de devoluções"

## Motivos
- "Top motivos de devolução da {marca} em {período}"
- "Motivos por categoria de produto"
- "Distribuição de motivos por canal de venda original"

## Geografia e logística
- "Devoluções por estado / cidade"
- "SLA médio de reversa por marca / centro de distribuição"
- "Quais lojas concentram mais devolução?"

## Produto
- "Top produtos com maior taxa de devolução em {período}"
- "Categorias com pior taxa de devolução"
- "Devolução por coleção"

## Tipos de reversa (ver business-rules.md §3)
- "Quanto foi estorno puro vs reversa total vs troca em {período}?"
- "Tempo médio entre venda e início da reversa"

## Dicas para boas perguntas
- Especifique **marca** e **tipo de reversa** quando possível — evita ida-e-volta.
- "Devolução" e "troca" têm regras distintas — se importar, diga qual.
- Para benchmarks comparativos, sempre interno (LY do próprio grupo); não há benchmark de mercado.
"""

# Herda as 7 ferramentas base (get_context, describe_table, get_business_rules,
# ping, consultar_bq, publicar_dashboard, listar_analises) + exemplos_perguntas.
app, main = build_mcp_app(
    agent_name="mcp-exec-devolucoes",
    instructions=_INSTRUCTIONS,
    exemplos=_EXEMPLOS,
)

# Adicione ferramentas específicas do domínio devolucoes aqui, se necessário.

if __name__ == "__main__":
    main()
