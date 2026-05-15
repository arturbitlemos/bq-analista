---
name: querying-azzas-clientes
description: Use this skill whenever the user asks questions about customer base, segmentation (Novo/Retido/Reativado), customer counts, VA, MACO, Markup, Ticket Médio, Frequência, PA or PM from the **customer perspective** (não de vendas). Para perguntas de receita/volume em geral, o agente vendas-linx é o default — só use este se o pedido for explícito sob ótica de clientes.
---

# Azzas 2154 — Análise de Clientes (BigQuery)

## Roteamento — quando este agente faz sentido

| Tipo de pergunta | Agente correto |
|---|---|
| Receita, ticket, volume, qualquer KPI de negócio em geral | **vendas-linx** (default) |
| "Quantos clientes Novo/Retido/Reativado?" | **clientes** |
| "Base ativa, LTV, recência, frequência, segmentação" | **clientes** |
| "Decompõe a árvore lógica da base de clientes" | **clientes** |

> ⚠️ **A receita aqui não bate com a do agente de vendas** — por desenho. Marketplaces (ex.: Mercado Livre) geram receita Azzas, mas o cliente final pertence ao marketplace, então não entram no universo deste agente. Quando o usuário estranhar a divergência, **explique esse motivo** ao invés de tentar reconciliar.

## Perspectiva — declarar SEMPRE

Os indicadores podem ser vistos sob **duas perspectivas distintas, com fontes de dados diferentes**:

| Perspectiva | Fonte | Custo típico |
|---|---|---|
| **Ano de competência** | `soma-crm-bi.dashboards_corp.acomp_clientes_base` (tabela agregada) | ~US$ 0,0001/query |
| **Janela móvel 12m** | `soma-crm-bi.dashboards.crm_clientes_tabela1` (VIEW) | ~US$ 0,045/query (~9 GB, fixo) |

Ambas as perspectivas são primárias e legítimas. O custo da janela 12m é maior, mas perfeitamente aceitável — basta usar com consciência (pedir o que precisa numa query só, evitar re-rodar sem necessidade).

A mesma compra pode mudar o status do cliente entre as duas perspectivas. Exemplo: cliente compra 30/dez/2026 + 01/jan/2027 → Retido no ano de competência 2027, mas continua Novo na janela móvel 12m até 31/dez/2027.

**Regra absoluta:**
- Em toda resposta, declarar explicitamente qual perspectiva está sendo usada.
- Se o pedido não especificar, **perguntar** antes de calcular. **Não tente deduzir pela métrica nem pelo período** — as fontes têm grão, marcas e statuses diferentes.
- **Cross-perspective não é diretamente comparável** — números não batem 1:1 (lista de marcas diferente, statuscliente granular diferente). Se o usuário estranhar a divergência, explicar como em "marketplaces" (regra de roteamento clientes vs vendas).

## Setup Check

Antes de qualquer query, verifique auth:
```bash
bq ls
```
Se falhar, rode `gcloud auth application-default login` primeiro.

## Query Pattern (obrigatório)

> 🚨 **Gate antes de qualquer execução:**
> 1. Estime o custo com base no período, tabelas e joins.
> 2. Informe ao usuário: `⚠️ Estimativa: ~X GB → ~US$ X.XX (teto: 15 GB)`
> 3. **Aguarde confirmação explícita ("sim") antes de executar.** Nunca execute sem resposta do usuário.

```bash
# 1. Dry-run — confirma custo antes de executar
bq query --use_legacy_sql=false --dry_run '<SQL>'

# 2. Executa só após confirmação do usuário
bq query --use_legacy_sql=false --format=prettyjson '<SQL>'
```

Referência: US$ 5,00 por TB = US$ 0,005 por GB. Teto: **15 GB por query**.

**Custos típicos por perspectiva:**

| Fonte | Custo típico/query | Observação |
|---|---|---|
| `acomp_clientes_base` (ano competência) | < US$ 0,001 (~0,001 GB) | Tabela agregada, ~0,1 GB total |
| `crm_clientes_tabela1` (janela 12m) | ~US$ 0,045 (~9 GB) | Fixo (column pruning não ajuda). Reportar o número e seguir o gate padrão — o usuário decide |

**Best practice na janela 12m:** rodar **uma query com vários KPIs (PIVOT por `Periodo`)** em vez de queries separadas — uma execução já traz CY+LY+todas as medidas pelo mesmo preço. Pra múltiplas análises sobre o mesmo recorte, materializar via `CREATE TEMP TABLE` e fazer análises subsequentes em cima.

## Schema Discovery

**Para ano de competência (`acomp_clientes_base`):**
```bash
bq show --schema --format=prettyjson soma-crm-bi:dashboards_corp.acomp_clientes_base
bq query --use_legacy_sql=false 'SELECT * FROM `soma-crm-bi.dashboards_corp.acomp_clientes_base` LIMIT 20'
```

**Para janela móvel 12m (`crm_clientes_tabela1`):**
```bash
# Inspect view metadata + SQL interna (sem custo)
bq show --format=prettyjson soma-crm-bi:dashboards.crm_clientes_tabela1

# Inspect fato físico subjacente (sem custo)
bq show --format=prettyjson soma-crm-bi:tabelas.crm_pesquisa_vendas
```

> ⚠️ **NUNCA fazer `SELECT *` na view sem WHERE.** Cada `SELECT *` na view custa US$ 0,045 (toca o fato subjacente).

## Filtros padrão (sempre aplicar em `acomp_clientes_base`)

```sql
WHERE marca IS NOT NULL AND marca <> ''        -- replica filtro do dashboard
  AND tipo_canal = 'canal entrada'             -- default; muda se houver filtro de canal
  AND ano = :ano                               -- temporal obrigatório
```

**Por que:**
- `marca IS NULL` representa ~16k clientes sem marca atribuída — o dashboard exclui, fazemos o mesmo.
- `tipo_canal = 'canal entrada'` é o default porque a tabela duplica linhas por grão de canal. Se filtrar por `canal_entrada` ou `canal_cliente`, alternar para `tipo_canal = 'canal'` (e aplicar dedup de Multicanal — ver `business-rules.md` §3.1).
- Filtro temporal evita scan de 89 meses inteiros (~0.1 GB → 0.001 GB).

## Medidas-chave

Detalhe completo em `business-rules.md`. Resumo:

```sql
SUM(rec_marca)                 AS receita
SUM(qtde_cli_1a_compra_ano)    AS qtde_clis        -- NÃO use qtde_cli_marca
SUM(pedidos_marca)             AS pedidos
SUM(prod_marca)                AS produtos
SUM(rec_markup)                AS receita_markup
SUM(cmv)                       AS cmv
```

Derivadas:
- VA = receita / qtde_clis
- TM = receita / pedidos
- Freq = pedidos / qtde_clis
- PA = produtos / pedidos
- PM = receita / produtos
- Markup = receita_markup / cmv
- MACO = (receita_markup - cmv) / qtde_clis

**Sempre validar as identidades da árvore lógica antes de fechar a resposta:**
```
Receita ≡ Qtde Clientes × VA
VA      ≡ TM × Frequência
TM      ≡ PA × PM
Qtde Clientes ≡ Novo + Retido + Reativado
```

## Filtros e medidas — janela móvel 12m (`crm_clientes_tabela1`)

**Filtros default observados nos dashes:**
```sql
WHERE Filial NOT LIKE '%CRIS BARROS SB%'
  AND Filial NOT LIKE '%CRIS BARROS EVENTO%'
-- + filtro temporal obrigatório (ver abaixo)
```

**Escopo de data — pegadinha crítica:** somente `Clientes Base Ativa` roda em janela 12m via DATESINPERIOD. Todas as outras métricas usam o range nativo do slicer. Estratégia SQL obrigatória:

```sql
WHERE Data BETWEEN <janela 12m>                                -- pra Clientes Base Ativa
-- todas as outras métricas usam agregação condicional:
COUNT(DISTINCT IF(Data BETWEEN <range slicer>, ClienteIdDia, NULL)),
SUM(IF(Data BETWEEN <range slicer> AND QtdProd>0, ValorPago, 0)),
...
```

Aplicar `WHERE Data BETWEEN <12m>` uniformemente em todas as agregações **infla Receita/Pedidos em 100–2.000×**. Ver §11.1 do business-rules.

**Medidas-chave (espelham o DAX do dash):**
```sql
COUNT(DISTINCT ClienteIdDia)                                   AS clientes_12m     -- na janela 12m
COUNT(DISTINCT IF(Data BETWEEN <slicer>, ClienteIdDia, NULL))  AS clientes_range   -- no range slicer
SUM(IF(Data BETWEEN <slicer> AND QtdProd>0, ValorPago, 0))     AS receita_faturada
SUM(IF(Data BETWEEN <slicer> AND QtdProd<1, -ValorPago, 0))    AS devolucao        -- NEGATIVA (§11.8)
COUNT(DISTINCT IF(Data BETWEEN <slicer>, ChavePedido, NULL))   AS pedidos
SUM(IF(Data BETWEEN <slicer>, QtdProd, 0))                     AS pecas
COUNT(DISTINCT IF(Data BETWEEN <slicer> AND MultiGanhoDia=1, ClienteIdDia, NULL)) AS multicanais
COUNTIF(Data BETWEEN <slicer>)                                 AS countrows        -- pra Frequência
```

Derivadas:
- TM = receita_faturada / pedidos
- Peças Atendimento = pecas / pedidos
- Frequência = countrows / **clientes_range** (denominador é dia/range, **não** clientes_12m)
- Receita Líquida = receita_faturada + devolucao (subtração efetiva, devolução é negativa)

**Agrupar por `Periodo`** (`Atual` / `Ano Anterior`) — view já materializa CY+LY internamente.

> ⚠️ **Bug de encoding com acentos:** filtros tipo `Marca = 'Maria Filó'` ou `'Fábula'` falham silenciosamente em shell Windows. **Sempre usar `LIKE`:** `Marca LIKE 'Maria Fil%'`, `Marca LIKE 'F_bula'`. Ver §11.9 business-rules.

## Sempre consultar `business-rules.md` antes de análises envolvendo:

**Ano de competência (`acomp_clientes_base`):**
- **Aliases de marca** (§0): FARM ≠ FARM ETC; FARM Global = EU+UK+US; combinações multi-marca têm double-count
- **Filtro de canal** (§4): troca de `tipo_canal` e dedup de Multicanal
- **Multicanal** (§4.1): dividir Qtde Clis por 2 (`Multicanal`) ou 3 (`Multicanal c/ Franquia`)
- **Status do cliente** (§7): definições de Novo/Retido/Reativado
- **Comparação vs LY** (§8): fórmula canônica do dashboard com `_ate_DiaAtual` para CY parcial

**Janela móvel 12m (`crm_clientes_tabela1`):**
- **Custo + gate de confirmação** (§11.0): ~US$ 0,045/query, alertar SEMPRE antes de executar
- **Escopo de data por medida** (§11.1): só Clientes Base Ativa em 12m; demais no range slicer
- **CY/LY via coluna `Periodo`** (§11.2): não fazer self-join — view já materializa
- **Lista de marcas** (§11.5): sem FARM ETC, FARM Global consolidado, presença de FARM LATAM/NV/Carol Bassi
- **TipoCliente** (§11.6): 4 valores granulares (Reativado dividido em Inativo/Perdido)
- **Cliente em múltiplos TipoCliente na mesma 12m** (§11.7): soma das bases por status pode exceder total — disclaimer obrigatório
- **Devolução sinal** (§11.8): sai NEGATIVA, subtrai de Faturada
- **Bug encoding em acentos** (§11.9): usar `LIKE` em vez de `=` para marcas com acento
- **PII em `ClienteIdDia` = CPF** (schema.md §2.6): nunca expor; só usar em agregações

## Workflow

### Passo 0 — formato da resposta

**Resposta inline:**
- Pergunta pontual ("quantos clientes novos a FARM teve em abril?")
- Verificação rápida ("Multicanal pesa quanto na base?")
- Comparação simples

**Relatório analítico (HTML):**
- Decomposição da árvore lógica completa
- Análise comparativa com várias dimensões
- Pedido explícito de "relatório" / "dashboard"

Quando ambíguo, perguntar.

1. **Entender a pergunta** — perspectiva (ano de competência ou janela móvel)? marca? período? recorte (canal, status, etc.)?
2. **Schema discovery** se for tabela nova (`bq show --schema`)
3. **Dry-run** com filtros padrão aplicados
4. **Executar** após confirmação do usuário
5. **Interpretar** no contexto da árvore lógica (validar identidades)
6. **Comparar vs LY** sempre que possível

## Output Format

- Números no padrão brasileiro: R$ 1.234,56 / 12,3%
- **Declarar a perspectiva** logo no início da resposta (ex.: "📅 Ano de competência 2026")
- **Declarar canal** quando relevante (default: "Todos os canais — filtrado por canal entrada")
- Quando contar Qtde Clientes filtrado por canal, **mencionar o dedup de Multicanal** se houver `Multicanal*` no recorte
- Contextualizar: "Reativados de 253k em 2026, -8,2% vs LY"

## Quando uma análise envolve a árvore lógica

Renderizar como decomposição visual (árvore ou tabela hierárquica). Para o nó principal (Receita), sempre mostrar:
- Total
- Quebra por status (Novo / Retido / Reativado) com Qtde Clientes, Receita, VA, MACO e Markup por status
- Decomposição: VA = TM × Freq, e TM = PA × PM

Antes de fechar a resposta, validar matematicamente as identidades. Se não baterem por > 1%, voltar e revisar filtros / dedup / agregação.

## Antes de gerar uma análise nova: buscar histórico

Sempre que o usuário pedir uma análise não-trivial:

1. Chame `buscar_analises(query=<resumo>, brand=<marca>, agent="clientes")`.
2. Se houver match recente (últimos 30 dias) → ofereça atualizar período via portal em vez de criar nova.
3. Para análise nova, antes de escrever SQL do zero, consulte uma análise prévia relevante e use como ponto de partida.

## Convenções de tags

Slug-case (lowercase, sem acento, hífens). Tags canônicas:
- Temporal: `mtd`, `ytd`, `12m-movel`, `competencia`
- Tipo: `arvore-logica`, `segmentacao`, `ranking`, `comparativo`
- Dimensão: `marca`, `canal`, `status-cliente`
- Métrica em destaque: `va`, `maco`, `markup`, `frequencia`, `ticket-medio`
