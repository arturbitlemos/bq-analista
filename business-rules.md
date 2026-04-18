# Business Rules — Farm Group Sales Analytics

## Metric Definitions

### Revenue Metrics
| Metric | Formula | Notes |
|---|---|---|
| Venda Bruta | raw value | Pre-discount, pre-return |
| Venda Líquida | bruta - descontos - devoluções - cancelamentos | **Default metric** |
| CMV | cost of goods sold | Product cost only |
| Receita Líquida | venda_liquida (same) | Use interchangeably |

### Margin & Efficiency
| KPI | Formula | Direction |
|---|---|---|
| Markup | `venda_liquida / cmv` | Higher = better |
| Margem Bruta % | `(venda_liquida - cmv) / venda_liquida * 100` | Higher = better |
| Taxa de Desconto % | `(venda_bruta - venda_liquida) / venda_bruta * 100` | Lower = better |

### Traffic & Conversion
| KPI | Formula | Notes |
|---|---|---|
| Ticket Médio | `venda_liquida / qtd_transacoes` | Per transaction/receipt |
| PA (Peças/Atendimento) | `qtd_pecas / qtd_transacoes` | Items per transaction |
| Preço Médio por Peça | `venda_liquida / qtd_pecas` | Avg unit price sold |

## Dimension Hierarchy

```
rede_lojas (brand)
  └── filial (store)
        └── transaction
              └── SKU / product
```

**rede_lojas examples** (populate from real data):
- `[TO BE FILLED after sampling data]`

**filial** = physical store identifier. Always filter by `rede_lojas` first when comparing stores across brands.

## Period Analysis Patterns

```sql
-- Current month vs same month last year
WHERE DATE_TRUNC(data_venda, MONTH) = DATE_TRUNC(CURRENT_DATE(), MONTH)
   OR DATE_TRUNC(data_venda, MONTH) = DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR), MONTH)

-- Last 30 days rolling
WHERE data_venda >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)

-- Last complete month
WHERE DATE_TRUNC(data_venda, MONTH) = DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)
```

## Common Analysis Patterns

### Brand Ranking by Revenue
```sql
SELECT
  rede_lojas,
  SUM(venda_liquida) AS receita,
  SUM(qtd_pecas) AS pecas,
  SUM(venda_liquida) / NULLIF(SUM(qtd_transacoes), 0) AS ticket_medio,
  SUM(qtd_pecas) / NULLIF(SUM(qtd_transacoes), 0) AS pa,
  (SUM(venda_liquida) - SUM(cmv)) / NULLIF(SUM(venda_liquida), 0) AS margem_bruta
FROM `PROJECT.DATASET.TABLE`
WHERE [date_filter]
GROUP BY rede_lojas
ORDER BY receita DESC
```

### Store Performance
```sql
SELECT
  filial,
  rede_lojas,
  SUM(venda_liquida) AS receita,
  SUM(venda_liquida) / NULLIF(SUM(qtd_transacoes), 0) AS ticket_medio,
  SUM(qtd_pecas) / NULLIF(SUM(qtd_transacoes), 0) AS pa,
  (SUM(venda_bruta) - SUM(venda_liquida)) / NULLIF(SUM(venda_bruta), 0) AS taxa_desconto
FROM `PROJECT.DATASET.TABLE`
WHERE rede_lojas = '[BRAND]'
  AND [date_filter]
GROUP BY filial, rede_lojas
ORDER BY receita DESC
```

## Safety Rules
- Always use `NULLIF(..., 0)` in division to avoid divide-by-zero
- When comparing periods, always use the same date grain (day, week, month)
- Never assume column names — verify with `bq show --schema` first
- Devoluções/cancelamentos may be in separate tables — check before assuming they're embedded in venda_liquida
