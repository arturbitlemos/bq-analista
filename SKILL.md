---
name: querying-farm-sales
description: Use this skill whenever the user asks questions about sales, revenue, stores, products, brands, or retail KPIs using BigQuery. Covers venda líquida, venda bruta, CMV, markup, ticket médio, PA, and brand/store dimensions. Triggers on any analytics question about Farm Group data.
---

# Farm Group — BigQuery Sales Analytics

## Setup Check
Before any query, verify auth:
```bash
bq ls
```
If this fails, run `gcloud auth login` first.

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

## Business Rules — Read references/business-rules.md for full detail

**Key fields:**
- `rede_lojas` → brand (Farm, Fábula, Foxton, etc.)
- `filial` → store (point of sale)
- `venda_bruta` → gross sales (before discount)
- `venda_liquida` → net sales (after discount, returns, cancellations)
- `cmv` → cost of goods sold

**Always use `venda_liquida` as the base metric unless explicitly told otherwise.**

**Core KPIs:**
- Markup = `venda_liquida / cmv`
- Ticket Médio = `venda_liquida / qtd_transacoes`
- PA = `qtd_pecas / qtd_transacoes`
- Margem Bruta = `(venda_liquida - cmv) / venda_liquida`
- Taxa de Desconto = `(venda_bruta - venda_liquida) / venda_bruta`

For full schema context and column value definitions → read `references/schema.md`
For KPI formulas and analysis patterns → read `references/business-rules.md`

## Workflow for Analytics Questions

1. **Understand the question** — identify dimensions (marca? loja? período?) and metrics (qual KPI?)
2. **Discover schema** if table is unknown (`bq show --schema`)
3. **Sample data** to verify column names and value formats
4. **Dry-run** the query
5. **Execute** and interpret results in business context
6. **After corrections** → update `references/schema.md` with what you learned

## Output Format
- Always present numbers with Brazilian formatting (R$ 1.234,56)
- Percentages with 1 decimal (12,3%)
- When results are large, summarize top 10 and offer to export
- Contextualize results: "Ticket médio de R$320 está X% acima/abaixo da média"
