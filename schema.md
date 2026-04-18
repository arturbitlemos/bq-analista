# Schema Reference — Farm Group BigQuery

> ⚠️ This file is a living document. After each session where you discover new tables, columns, or column values, update this file.

---

## Main Sales Table

**Full path:** `soma-dl-refined-online.soma_online_refined.refined_captacao`

**Partitioning:** NOT partitioned by a partition column (uses `data_evento` TIMESTAMP for filtering — always filter with TIMESTAMP_TRUNC to reduce scan cost)

**Date range:** 2019-12-28 to present (2303+ days of history as of 2026-04-17)

### Schema

| Column | Type | Description | Notes |
|---|---|---|---|
| `data_evento` | TIMESTAMP | Event date (capture/status change) | Use this for filtering — `TIMESTAMP_TRUNC(data_evento, DAY)` |
| `data_faturamento` | TIMESTAMP | Invoice/billing date | NULL for non-invoiced (cancelled, etc.) |
| `data_pagamento` | DATETIME | Payment date | |
| `data_venda_original` | TIMESTAMP | Original sale date (for returns/exchanges) | |
| `data_insercao_status` | TIMESTAMP | Status insertion date | |
| `rede_lojas_mais_vendas` | INTEGER | Brand identifier (numeric code) | See brand mapping below |
| `rede_lojas_evento` | INTEGER | Brand at time of event | |
| `rede_lojas_faturamento` | INTEGER | Brand at time of invoicing | |
| `rede_lojas_produto` | INTEGER | Brand of the product | |
| `codigo_filial_mais_vendas` | STRING | Store code (point of sale) | e.g. `"000261"` |
| `codigo_filial_evento` | STRING | Store at time of event | |
| `codigo_filial_faturamento` | STRING | Store at time of invoicing | |
| `pacote` | STRING | Order/package identifier | |
| `id_pacote` | INTEGER | Package ID | |
| `id_item` | INTEGER | Item ID within package | |
| `id_mais_carrinho` | STRING | Cart ID | |
| `status_evento` | STRING | Status of this event row | e.g. `CAPTURADO`, `CANCELADO` |
| `ultimo_status` | STRING | Final/latest status of the order | Filter on this to get current state |
| `id_status` | INTEGER | Status ID | |
| `tipo_venda` | STRING | Sale channel type | `FISICO`, `ECOMMERCE`, etc. |
| `tipo_seller` | STRING | Seller type | `NÃO DEFINIDO`, `EXTERNO`, etc. |
| `programa` | STRING | Program/franchise type | `próprio`, `franquia` |
| `ferramenta` | STRING | Tool/platform used | |
| `modalidade` | STRING | Sale modality | |
| `vendedor` | STRING | Salesperson identifier | |
| `cpf_cliente` | STRING | Customer CPF (hashed/masked) | |
| `produto` | STRING | Product code | |
| `produto_cor` | STRING | Product + color code | |
| `grade_produto` | STRING | Product grid | |
| `tamanho` | STRING | Size | |
| `colecao` | STRING | Collection | |
| `status_colecao` | STRING | Collection status | |
| `quantidade` | INTEGER | Units | |
| `valor_produto` | FLOAT | Gross product value (pre-discount) | = `venda_bruta` |
| `valor_desconto` | FLOAT | Discount value (negative number) | |
| `valor_pago_produto` | FLOAT | Net value paid (post-discount) | = `venda_liquida` — **default metric** |
| `cmv` | FLOAT | Cost of goods sold | Often 0.0 for FISICO/non-invoiced |
| `maco` | FLOAT | Contribution margin (margem de contribuição) | |
| `valor_frete_produto` | FLOAT | Shipping value | |
| `seller_fulfillment` | STRING | Fulfillment seller | |
| `tipo_transacao` | STRING | Transaction type | |
| `venda_original` | STRING | Original sale reference (for returns) | |
| `chave_atendimento` | STRING | Service key | |
| `chave_nota_entrada` | STRING | Entry invoice key | |
| `chave_nota_saida` | STRING | Exit invoice key | |
| `tipo_chave_entrada` | STRING | Entry key type | |
| `tipo_chave_saida` | STRING | Exit key type | |
| `data_autorizacao_nota_entrada` | DATETIME | Entry invoice authorization date | |
| `data_autorizacao_nota_saida` | DATETIME | Exit invoice authorization date | |
| `codigo_periodo_afastamento` | STRING | Leave period code | |
| `fl_venda_agenda` | BOOLEAN | Scheduled sale flag | |

---

## Brand Mapping (rede_lojas_mais_vendas)

| Code | Brand |
|---|---|
| 1 | ANIMALE |
| 2 | FARM |
| 5 | FÁBULA |
| 6 | OFF PREMIUM |
| 7 | FOXTON |
| 9 | CRIS BARROS |
| 15 | MARIA FILO |
| 16 | NV |
| 26 | FARM ETC |
| 30 | CAROL BASSI |

**Revenue rank (last 60 days, non-cancelled):**
1. FARM (2) — R$164M, 238 stores
2. ANIMALE (1) — R$85M, 84 stores
3. NV (16) — R$80M, 28 stores
4. CRIS BARROS (9) — R$43M, 16 stores
5. MARIA FILO (15) — R$34M, 60 stores
6. CAROL BASSI (30) — R$17M, 13 stores
7. FOXTON (7) — R$17M, 37 stores
8. OFF PREMIUM (6) — R$16M, 51 stores
9. FARM ETC (26) — R$9M, 66 stores
10. FÁBULA (5) — R$5M, 34 stores

---

## Key Metric Mappings

| Business concept | Column in table |
|---|---|
| Venda Bruta | `valor_produto` |
| Desconto | `valor_desconto` (negative) |
| Venda Líquida | `valor_pago_produto` ← **use this** |
| CMV | `cmv` |
| Margem de Contribuição | `maco` |
| Qtd Peças | `quantidade` |
| Marca | `rede_lojas_mais_vendas` (INTEGER) |
| Loja | `codigo_filial_mais_vendas` |
| Data venda | `data_evento` (TIMESTAMP) |

---

## Critical Filters (always apply)

```sql
-- Exclude cancelled orders
WHERE ultimo_status NOT IN ('CANCELADO', 'CANCELADO AUTOMATICO')

-- Exclude external sellers (marketplace)
AND tipo_seller <> 'EXTERNO'

-- Exclude physical franchise
AND NOT (tipo_venda = 'FISICO' AND programa = 'franquia')

-- Partition-style filter to reduce scan cost
AND TIMESTAMP_TRUNC(data_evento, DAY) >= TIMESTAMP_TRUNC(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL N DAY), DAY)
```

---

## Gotchas & Learned Rules

- `cmv` is often 0.0 for FISICO/non-invoiced rows — margin calculations may be unreliable for physical retail
- **`cmv` is ALWAYS stored positive, even on DEVOLUCAO and internal exchange rows.** Sign must be flipped by `quantidade` to avoid double-counting when aggregating with returns. See `business-rules.md` §4. Pattern: `IF(quantidade < 0, -ABS(cmv), ABS(cmv)) AS cmv_liquido`.
- `valor_desconto` is stored as a **negative** number (e.g. -20.0)
- `rede_lojas_mais_vendas` is INTEGER, not STRING — use numeric codes in WHERE/CASE
- Table has no native partition column — always filter on `data_evento` with TIMESTAMP_TRUNC to control scan size
- `ultimo_status` is the definitive field for order state; `status_evento` captures intermediate states
- For physical stores: use `data_faturamento` for invoiced revenue; for ecommerce: `data_pagamento` or `data_evento`
- `quantidade` = 0 for cancelled rows (even with valor_produto > 0); also appears on zero-value freebie/trial lines
- `quantidade` can be **negative** in FISICO rows (internal exchange within same atendimento) and in DEVOLUCAO (standalone returns)

### `pacote` vs `chave_atendimento` — transaction key

- `pacote` is the canonical transaction identifier — **but it's not globally unique for physical sales**. For FISICO/ESTOQUE PROPRIO/VITRINE/DEVOLUCAO, `pacote` is sequential per filial/day, so the same string repeats across stores/dates.
- For ecommerce (ONLINE, SOMASTORE), `pacote` has a `-NN` shipment suffix (e.g. `v1035019crb-01`, `-02`, `-03`) representing sub-shipments of the same logical order. Strip the suffix to get the pedido.
- `chave_atendimento` is a derived key (`YYYYMMDD + filial + pacote` for physical; `pacote` stripped for ecom). Works, but the canonical rule uses `pacote` directly — see `business-rules.md` §3.

### `tipo_venda` values

Observed values (2026-01 to present):

| `tipo_venda` | Volume | Meaning | Canal |
|---|---|---|---|
| FISICO | highest | Physical store sale | Físico |
| ONLINE | high | Direct ecommerce | Online |
| ESTOQUE PROPRIO | medium | Ship-from-own-inventory | Físico |
| DEVOLUCAO | medium | Post-sale return (neg qty, neg revenue) | Online |
| SOMASTORE | low | SomaStore marketplace | Físico |
| VITRINE | very low | Showroom/vitrine | Físico |

Channel classification rule: see `business-rules.md` §2.
