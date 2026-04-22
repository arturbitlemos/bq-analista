---
name: querying-farm-sales
description: Use this skill whenever the user asks questions about sales, revenue, stores, products, brands, or retail KPIs using BigQuery. Covers venda líquida, venda bruta, CMV, markup, ticket médio, PA, and brand/store dimensions. Triggers on any analytics question about Azzas 2154 data.
---

# Azzas 2154 — BigQuery Sales Analytics

## Setup Check
Before any query, verify auth:
```bash
bq ls
```
If this fails, run `gcloud auth application-default login` first.

## Query Pattern (always use this)
```bash
# 1. Dry-run first — estimate cost
bq query --use_legacy_sql=false --dry_run '<SQL>'

# 2. Execute only after dry-run confirms cost is acceptable
bq query --use_legacy_sql=false --format=prettyjson '<SQL>'
```

> ⚠️ Never execute a query without dry-run first on unknown tables.

## Schema Discovery
```bash
# Inspect a table
bq show --schema --format=prettyjson PROJECT:DATASET.TABLE

# Sample data (always do this before writing complex SQL)
bq query --use_legacy_sql=false 'SELECT * FROM `PROJECT.DATASET.TABLE` LIMIT 20'

# List tables in dataset
bq ls PROJECT:DATASET
```

## Business Rules — Read business-rules.md for full detail

**Key fields:**
- `rede_lojas_mais_vendas` → brand code (INTEGER — see schema.md for mapping)
- `codigo_filial_mais_vendas` → store (point of sale)
- `valor_produto` → gross sales (before discount)
- `valor_pago_produto` → net sales (after discount) — **default metric**
- `cmv` → cost of goods sold
- `quantidade` → units sold

**Always use `valor_pago_produto` as the base metric unless explicitly told otherwise.**

**Standard filters (always apply):**
```sql
AND ultimo_status NOT IN ('CANCELADO', 'CANCELADO AUTOMATICO')
AND tipo_seller <> 'EXTERNO'
AND NOT (tipo_venda = 'FISICO' AND programa = 'franquia')
AND TIMESTAMP_TRUNC(data_evento, DAY) >= TIMESTAMP_TRUNC(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL N DAY), DAY)
```

**Core KPIs (see `business-rules.md` for canonical formulas with sign/key corrections):**
- Markup = `SUM(valor_pago_produto) / SUM(cmv_liquido)` — use `cmv_liquido` to avoid double-counting in returns
- Ticket Médio = `SUM(valor_pago_produto) / COUNT(DISTINCT chave_pedido)` — use treated `pacote` as `chave_pedido`
- PA = `SUM(quantidade) / COUNT(DISTINCT chave_pedido)`
- Margem Bruta = `(SUM(valor_pago_produto) - SUM(cmv_liquido)) / SUM(valor_pago_produto)`
- Taxa de Desconto = `(SUM(valor_produto) - SUM(valor_pago_produto)) / SUM(valor_produto)`

**Crítico — sempre consultar `business-rules.md`** antes de análises que envolvam:
- Canal (§2: mapeamento tipo_venda → Físico/Online)
- PA, ticket, contagem de atendimentos (§3: chave_pedido via pacote tratado)
- Markup ou margem (§4: correção de sinal do CMV)

For full schema context → read `schema.md`
For all business rules, canonical formulas, and analysis templates → read `business-rules.md`

## Workflow for Analytics Questions

### Passo 0 — Decidir o formato da resposta

Antes de executar qualquer query, classifique o pedido:

**Resposta inline** (responda direto no chat, sem dashboard):
- Pergunta pontual com uma métrica ou dimensão ("qual foi o ticket médio de ontem?")
- Verificação rápida ("quantos pedidos tivemos hoje?")
- Comparação simples entre dois valores
- Pedido explícito de resposta rápida

**Relatório analítico** (gera HTML e exibe inline no chat — não publicar, não salvar em lugar nenhum):
- Análise com múltiplos KPIs ou seções
- Pedido de "análise", "relatório", "dashboard", "comparativo completo"
- Análise histórica com mais de 2 dimensões

**Quando não for óbvio**, pergunte ao usuário:
> "Você quer uma resposta rápida aqui no chat ou um relatório HTML completo?"

---

1. **Understand the question** — identify dimensions (marca? loja? período?) and metrics (qual KPI?)
2. **Discover schema** if table is unknown (`bq show --schema`)
3. **Sample data** to verify column names and value formats
4. **Dry-run** the query
5. **Execute** and interpret results in business context
6. **Se relatório analítico**: Build HTML dashboard (mobile-first, dark green theme — see existing dashboards for reference) e exiba o HTML diretamente ao usuário no chat. **Não publicar, não persistir em arquivo, não rodar `publicar_dashboard`.**
7. **After corrections** → update `schema.md` with what you learned

## Output Format
- Always present numbers with Brazilian formatting (R$ 1.234,56)
- Percentages with 1 decimal (12,3%)
- When results are large, summarize top 10 and offer to export
- Contextualize results: "Ticket médio de R$320 está X% acima/abaixo da média"

---

## Exibindo um Relatório HTML

Quando o fluxo exigir um relatório analítico (ver Passo 0), **gere o HTML e exiba diretamente no chat**. Não persistir em arquivo, não commitar, não publicar em portal.

### Como entregar
- Monte o HTML completo (mobile-first, tema verde escuro, padrão visual dos dashboards existentes), inline — sem dependências externas além de CDN (Chart.js, fontes).
- Retorne o HTML inteiro em um único bloco de código ```html ...``` no chat, para o usuário copiar/colar e abrir localmente no navegador.
- Resuma os principais achados em texto logo após o bloco HTML (3–6 bullets), seguindo o padrão do `analyst principles.md` (número + tier + contexto).

### O que NÃO fazer
- ❌ Não rodar a ferramenta MCP `publicar_dashboard`.
- ❌ Não criar arquivos em `analyses/`, `library/` ou `public/`.
- ❌ Não fazer `git add/commit/push` de relatórios.
- ❌ Não pedir `USER_EMAIL` nem ler `.env` para fins de publicação.

Se o usuário pedir explicitamente para "publicar", "compartilhar" ou "salvar na biblioteca", responda que esse fluxo está desativado no momento e ofereça o HTML inline como alternativa.
