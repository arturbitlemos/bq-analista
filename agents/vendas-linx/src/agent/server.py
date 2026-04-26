from mcp_core.server_factory import build_mcp_app

_INSTRUCTIONS = """\
Agente de **Vendas (Linx)** do grupo Azzas 2154 — análise de venda, ticket, markup, PA,
margem e devoluções por marca/loja/produto/coleção via BigQuery.

Comece toda sessão chamando `get_context` para carregar princípios analíticos e
índice de tabelas. Para schema completo de uma tabela use `describe_table`. Para
fórmulas canônicas (markup, ticket, PA, etc.) use `get_business_rules`.

Exemplos rápidos do que o usuário pode perguntar:
• "Qual a venda líquida da Farm em abril vs LY?"
• "Top 10 produtos da Animale no último mês"
• "Ticket médio e PA por filial da Farm na semana passada"
• "Markup da Cris Barros vs LY no 1º trimestre"

Para um catálogo mais amplo de perguntas chame `exemplos_perguntas`.

Regras invioláveis:
- Nunca expor PII (CPF, e-mail, nome, telefone, ID individual de cliente).
- Toda métrica temporal deve trazer comparação vs Last Year (LY) — sem proxy.
- Devoluções entram por padrão em venda líquida; não filtrar sem pedido explícito.
- Filial/rede default = DESTINO (`CODIGO_FILIAL_DESTINO`, `RL_DESTINO`).
- Publicar dashboard só quando o usuário pedir explicitamente — padrão é renderizar inline.
"""

_EXEMPLOS = """\
# Catálogo de perguntas — Vendas (Linx)

## Volume e receita
- "Venda líquida da {marca} em {período} vs LY"
- "Top N produtos / lojas / coleções de {marca}"
- "Quebra de receita por canal (Físico vs Online) — quando a regra de canal estiver definida"
- "Curva diária de venda em {período}"

## Eficiência operacional
- "Ticket médio e PA por filial em {período}"
- "PA por marca / coleção"
- "Taxa de desconto por marca em {período}"

## Rentabilidade
- "Markup e margem bruta por marca / coleção"
- "Margem por produto (top giradores e piores giradores)"
- "Sell-through por coleção"

## Estoque e cobertura
- "Giro por loja em {horizonte}"
- "Cobertura média por filial em {horizonte}"
- "Produtos em ruptura por filial"

## Comparativos
- "{marca} A vs marca B em {período}"
- "Performance da loja X vs média da rede"
- "Coleção atual vs coleção equivalente LY"

## Dicas para boas perguntas
- Sempre que possível, especifique **marca** e **período** — economiza ida-e-volta.
- Para análise de produto, peça grão `produto × cor` para ver ranking com fotos.
- Para canal, hoje a regra Físico×Online ainda não está definida no Linx — perguntas envolvendo canal podem retornar análise em aberto.
"""

# Herda as 7 ferramentas base (get_context, describe_table, get_business_rules,
# ping, consultar_bq, publicar_dashboard, listar_analises) + exemplos_perguntas.
app, main = build_mcp_app(
    agent_name="mcp-exec-vendas-linx",
    instructions=_INSTRUCTIONS,
    exemplos=_EXEMPLOS,
)

# Adicione ferramentas específicas do domínio vendas-linx aqui, se necessário.

if __name__ == "__main__":
    main()
