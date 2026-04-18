---
name: querying-farm-sales
description: Use this skill whenever the user asks questions about sales, revenue, stores, products, brands, or retail KPIs using BigQuery. Covers venda líquida, venda bruta, CMV, markup, ticket médio, PA, and brand/store dimensions. Triggers on any analytics question about Farm Group data. Also triggers when user asks to publish, save, or share an analysis.
---

# Farm Group — BigQuery Sales Analytics

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

**Core KPIs:**
- Markup = `venda_liquida / cmv`
- Ticket Médio = `valor_pago_produto / qtd_transacoes`
- PA = `qtd_pecas / qtd_transacoes`
- Margem Bruta = `(valor_pago_produto - cmv) / valor_pago_produto`
- Taxa de Desconto = `(valor_produto - valor_pago_produto) / valor_produto`

For full schema context → read `schema.md`
For KPI formulas and analysis patterns → read `business-rules.md`

## Workflow for Analytics Questions

1. **Understand the question** — identify dimensions (marca? loja? período?) and metrics (qual KPI?)
2. **Discover schema** if table is unknown (`bq show --schema`)
3. **Sample data** to verify column names and value formats
4. **Dry-run** the query
5. **Execute** and interpret results in business context
6. **Build HTML dashboard** (mobile-first, dark green theme — see existing dashboards for reference)
7. **Publish** the analysis (see Publishing section below)
8. **After corrections** → update `schema.md` with what you learned

## Output Format
- Always present numbers with Brazilian formatting (R$ 1.234,56)
- Percentages with 1 decimal (12,3%)
- When results are large, summarize top 10 and offer to export
- Contextualize results: "Ticket médio de R$320 está X% acima/abaixo da média"

---

## Publishing an Analysis

After building the HTML dashboard, always publish it to the analytics library.

### Step 1 — Load user config
```bash
# Load USER_OID from .env (must exist in project root)
source .env
echo "Publishing as OID: $USER_OID"
```

If `.env` doesn't exist or `USER_OID` is empty, stop and ask the user to run:
```bash
# User finds their OID at: https://portal.azure.com → Azure AD → Users → [your name] → Object ID
echo 'USER_OID=paste-your-oid-here' >> .env
```

### Step 2 — Save the analysis file
```bash
ANALYSIS_ID="{brand}-{topic}-{YYYY-MM-DD}"   # e.g. farm-produto-ecomm-2026-04-17
mkdir -p analyses/$USER_OID
# Write HTML to: analyses/$USER_OID/$ANALYSIS_ID.html
```

### Step 3 — Update personal library index
Read `library/$USER_OID.json` (create as `[]` if it doesn't exist), prepend new entry:

```json
{
  "id": "{ANALYSIS_ID}",
  "title": "{short title}",
  "brand": "{BRAND}",
  "period": "{human-readable period}",
  "date": "{YYYY-MM-DD}",
  "description": "{1-sentence summary}",
  "file": "analyses/{USER_OID}/{ANALYSIS_ID}.html",
  "public": false,
  "tags": ["{tag1}", "{tag2}"]
}
```

### Step 4 — Commit and push
```bash
git add analyses/$USER_OID/$ANALYSIS_ID.html library/$USER_OID.json
git commit -m "análise: $ANALYSIS_ID"
git push
```

Vercel rebuilds automatically (~60s). Analysis is live.

### Making an analysis public
When the user says "torna pública" or "compartilha":
```bash
# Copy to public folder
cp analyses/$USER_OID/$ANALYSIS_ID.html analyses/public/$ANALYSIS_ID.html

# Add entry to library/public.json (same structure, public: true)
# Update library/public.json

git add analyses/public/$ANALYSIS_ID.html library/public.json
git commit -m "publica análise: $ANALYSIS_ID"
git push
```
