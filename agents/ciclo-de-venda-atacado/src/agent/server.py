from mcp_core.server_factory import build_mcp_app

_INSTRUCTIONS = """\
Agente de **Ciclo de Venda Atacado** do grupo Azzas 2154 — análise de vendas,
cancelamentos, embalados, faturamento, devoluções, metas e carteira de clientes
do canal Atacado da BU Fashion & Lifestyle via BigQuery
(`soma-dl-refined-online.atacado_processed`).

Comece toda sessão chamando `get_context` para carregar princípios analíticos e
índice de tabelas. Para schema completo de uma tabela use `describe_table`. Para
regras de negócio (aliases de marca/representante, filtros de TIPO_VENDA,
agrupamento de STATUS_CAIXA, capilaridade, cluster, markup) use `get_business_rules`.

Exemplos rápidos do que o usuário pode perguntar:
• "Qual foi a venda de FARM FUTURA no Inverno 2026?"
• "Quais representantes não bateram meta na AJ no INV26?"
• "Quais clientes da Farm estão com faturamento liberado?"
• "Qual o prazo médio de pagamento do ano de 2025?"
• "Quais foram os produtos mais cancelados no Verão 2026?"

Para um catálogo mais amplo de perguntas chame `exemplos_perguntas`.

Regras invioláveis:
- Nunca expor PII (e-mail, telefone, endereço, WhatsApp — colunas 🔴 de dim_clientes_v2, ver schema.md §7).
- Filtro padrão em toda análise: TIPO_VENDA IN ('VENDA', 'PRE VENDA') e VENDA_ORIGINAL > 0.
- Análises de venda, cancelamento e embalado filtradas por COLECAO — nunca por intervalo de datas.
- Devoluções analisadas por DATA_RECEBIMENTO (não por coleção).
- TIPO_VENDA só existe em info_venda — tabelas derivadas sempre fazem JOIN (ver business-rules §2).
- Excluir ATENDIMENTO INTERNO e FACEX de rankings e comparativos de representantes.
- Publicar dashboard só quando o usuário pedir explicitamente.
"""

_EXEMPLOS = """\
# Catálogo de perguntas — Ciclo de Venda Atacado

## Venda e markup
- "Venda de {marca} na coleção {coleção}"
- "Qual foi o crescimento no número de atendimentos de {marca} em {coleção}?"
- "Quais clientes decresceram em {marca} em {coleção} e ganharam mkp acima de {valor}?"
- "Qual o markup realizado da {marca} no {coleção}?"
- "Qual o prazo médio de pagamento do {ano}?"
- "Qual a representatividade de Farm Futura na venda de Fábula no {coleção}?"
- "Quais clientes compraram {marca} no {coleção}?"
- "Quantos clientes a coleção {coleção} teve?"
- "Em qual coleção vendeu o produto '{DESC_PRODUTO}'?"
- "Quantos produtos de {linha/material} foram vendidos na {coleção} da {marca}?"
- "Tinham quantos produtos de cada linha na {coleção} da {marca}?"
- "Qual representante vendeu menos em {coleção}?"

## Atingimento de meta
- "Quais representantes não bateram meta em {marca} no {coleção}?"
- "Qual o atingimento do representante {nome} no {coleção} da {marca}?"

## Clientes: segmentação e carteira
- "Clientes novos na {marca} no {coleção} — quantos continuam comprando?"
- "Quais são os clientes novos na {marca} no {coleção}?"
- "Clientes de {marca} que ainda não fizeram Prateleira Infinita em {coleção}"
- "Clientes que compraram {marca} na coleção e também compraram Prateleira Infinita {ano}"
- "Quantos clientes (cliente-marca) tivemos em {coleção1} + {coleção2}? Quantos receberam mais de 80% do faturamento?"

## Capilaridade
- "Qual a capilaridade do representante {nome} no {coleção}?" (fluxo obrigatório de 4 passos — ver business-rules §15)
- "Qual a capilaridade da {marca} no {representante} no {coleção}?"

## Cancelamento e quebra
- "Quais foram os produtos mais cancelados no {coleção}?"
- "Qual foi o cancelamento comercial da {marca} no {coleção}?"
- "Principal ofensor de quebra na {marca} no {coleção}?"

## Faturamento
- "Me dê a curva de faturamento da {marca} em {ano}"
- "Quanto temos faturado da coleção {coleção} para o clifor '{CLIFOR}'?"
- "Faturamento no trimestre?"
- "Quantos clientes receberam mais de 80% do faturamento em {coleção}?"

## Embalados
- "Quais clientes da {representante} na {marca} estão com faturamento liberado e quanto cada um tem?"
- "Quanto temos embalado de {tipo_produto} da {marca}?"
- "Valor embalado para o cliente '{CLIENTE}' na {marca}"
- "Quanto temos liberado para faturamento da {marca}?"

## Devolução
- "Representante com mais devolução na {marca} em {ano}"
- "Curva de faturamento líquido da {marca} em {ano} (faturamento - devolução)"

## Prateleira Infinita
- "Venda de Prateleira Infinita por marca e mês em {ano}"
- "Pedido médio de Prateleira Infinita por marca e mês"
- "Venda de Prateleira Infinita da {marca} — estoque externo vs estoque Azzas"
- "Qual a venda e venda líquida de cancelamento de Prateleira Infinita por mês, marca e ano?"

## Orientação de coleção
- "Qual a coleção atual?"
- "Quais são as últimas 4 coleções?"

## Financeiro
- "Quanto de faturamento que ainda não foi entregue está em clientes bloqueados?"
- "Qual o % de clientes M, G e GG que estão bloqueados?"
- "O clifor '507892' está com bloqueio financeiro?"

## Somaplace
- "Quantos clientes se cadastraram no Somaplace por marca em 2026?"
- "Qual a venda por cliente e marca no Somaplace em 2026?"
- "Quantos clientes que venderam no Somaplace esse ano não venderam no programa todas as marcas que compraram nas últimas 4 coleções?"

## Afiliados
- "Quantas multimarcas e vendedores afiliados tiveram venda por ano no Programa Afiliados?"
- "Qual a venda líquida de cancelamento do Programa Afiliados por mês em 2026?"
- "Qual é a venda média por vendedor afiliado da FARM (líquida de cancelamento), por mês, em 2026?"
- "Quantos vendedores têm cadastro ativo no Afiliados?"
- "Qual o status de cadastro do vendedor afiliado de código 7A3848?"
- "Me dê o ranking das 10 top vendedoras afiliadas em 2026, de FARM Etc, com a multimarca, o coordenador e o representante associado"

## Dicas para boas perguntas
- Especifique **marca** e **coleção** (ex: INV26, VERAO 2026) sempre que possível.
- Para representante, o nome Wise ou alias reconhecido (business-rules §1.1) acelera a busca.
- Para Prateleira Infinita e devoluções, especifique o **período** (ano/mês) — não são filtradas por coleção.
"""

# Herda as 7 ferramentas base (get_context, describe_table, get_business_rules,
# ping, consultar_bq, publicar_dashboard, listar_analises) + exemplos_perguntas.
app, main = build_mcp_app(
    agent_name="mcp-exec-ciclo-de-venda-atacado",
    instructions=_INSTRUCTIONS,
    exemplos=_EXEMPLOS,
)

# Adicione ferramentas específicas do domínio ciclo-de-venda-atacado aqui, se necessário.

if __name__ == "__main__":
    main()
