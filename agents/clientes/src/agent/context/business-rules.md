# Business Rules — Azzas 2154 Clientes

> Documento canônico de regras de negócio para análises sobre `soma-crm-bi.dashboards_corp.*`.
> Complementa `schema.md` (dicionário de dados) e `analyst principles.md` (método analítico).
>
> **Convenção:** ao descobrir/corrigir uma regra, atualize este arquivo e comite. Regras aqui são compartilhadas entre todos os usuários do produto.

---

## 0. Aliases e agrupamentos de marca (resolver sem perguntar)

A coluna `marca` em `acomp_clientes_base` é case-sensitive e tem valores específicos. Resolver entrada do usuário conforme tabela abaixo. Aplicar **sempre**, mesmo que o usuário use minúsculas/acentos diferentes.

| Pedido do usuário | Filtro SQL | Disclaimer obrigatório |
|---|---|---|
| "FARM" / "Farm" (sem qualificador) | `marca = 'FARM'` | ℹ️ Avisar que **FARM ETC NÃO está incluída** e oferecer alternativa (ver §0.1.a) |
| "FARM ETC" / "Farm ETC" / "ETC" | `marca = 'FARM ETC'` | ℹ️ Avisar que **FARM não está incluída** e oferecer alternativa (ver §0.1.a) |
| "FARM + ETC" / "Farm e ETC juntas" / "Farm consolidada" | `marca IN ('FARM','FARM ETC')` | ℹ️ Explicar que **cada marca conta sua própria base** (ver §0.1.b) |
| "FARM Global" (sem região) | `marca IN ('FARM Global EU','FARM Global UK','FARM Global US')` | ℹ️ Mencionar que **inclui as 3 regiões** consolidadas (transparência) |
| "FARM Global EU" / "Europa" | `marca = 'FARM Global EU'` | — |
| "FARM Global UK" / "Inglaterra" | `marca = 'FARM Global UK'` | — |
| "FARM Global US" / "EUA" / "USA" | `marca = 'FARM Global US'` | — |
| "FARM tudo" / "Toda a FARM" | `marca IN ('FARM','FARM ETC','FARM Global EU','FARM Global UK','FARM Global US')` | ℹ️ Explicar que **cada marca conta sua própria base** (ver §0.1.b) |
| Outras marcas (Animale, Cris Barros, Foxton, etc.) | `marca = '<exato>'` | — |

### 0.1 Disclaimers obrigatórios — FARM / FARM ETC / FARM Global

FARM e FARM ETC são **marcas distintas no dado**, mas culturalmente costumam ser tratadas como a mesma coisa (mesmas lojas, comprador mistura produtos). O agente precisa **sempre ser transparente** sobre qual recorte está usando, dos dois lados.

#### 0.1.a Quando o filtro for marca única (FARM ou FARM ETC sozinha)

Mostrar o número da marca pedida normalmente, mas adicionar este disclaimer na resposta:

> ℹ️ Considerei apenas **FARM**. FARM ETC é tratada como marca separada no dado e ficou de fora deste recorte — se quiser ver as duas consolidadas, peça "FARM + ETC" (mas atenção ao double-count, ver abaixo).

Adaptar o nome ("FARM" ↔ "FARM ETC") conforme o caso. Para FARM Global, mencionar que inclui as 3 regiões.

#### 0.1.b Quando o filtro for combinação de marcas (FARM + ETC, "FARM tudo", etc.)

Quando agrupar mais de uma marca, **cada marca conta a sua própria base**. Um cliente que compra em duas marcas tem um relacionamento independente com cada uma e aparece nas duas — isso é uma escolha de visão (marcas tratadas como entidades distintas), **não é erro**.

Exemplo: cliente X comprou na FARM em jan/2026 e na FARM ETC em fev/2026.
- Em `marca = 'FARM'`: 1 cliente (statuscliente depende do histórico dele na FARM)
- Em `marca = 'FARM ETC'`: 1 cliente (statuscliente pode ser diferente — a relação com a ETC tem trajetória própria)
- Soma consolidada: 2 clientes — porque a leitura aqui é "soma das bases de marca", não "CPFs únicos"

Disclaimer:

> ℹ️ FARM e FARM ETC são tratadas como marcas distintas neste relatório. Cada uma conta a sua própria base — um cliente que compra nas duas tem relacionamento independente com cada marca e aparece em ambas. A Qtde Clientes consolidada é a **soma das bases** das marcas, não a contagem de CPFs únicos.

A mesma regra vale pra "FARM tudo" e qualquer combinação multi-marca.

### 0.2 Como cada métrica se comporta em consolidação multi-marca

| Métrica | Comportamento em consolidação multi-marca |
|---|---|
| Qtde Clientes | Soma das bases de cada marca. Um cliente em N marcas conta N vezes (cada relacionamento de marca é independente). |
| Receita / Pedidos / Produtos / Rec Markup / CMV | Soma direta — cada compra é atribuída à marca onde aconteceu, sem sobreposição. |
| VA (Receita / Qtde) | Reflete o "VA por relacionamento de marca", não "VA por CPF único". Se o cliente compra em N marcas, ele entra no denominador N vezes. |
| MACO (Margem / Qtde) | Mesma lógica do VA — "MACO por relacionamento de marca". |
| Markup (Rec Markup / CMV) | Não depende de Qtde Clientes — número é diretamente comparável entre cortes. |
| Ticket Médio (Receita / Pedidos), Frequência, PA, PM | Não dependem de Qtde Clientes — números são diretamente comparáveis entre cortes. |

Para análises consolidadas multi-marca, mencionar na resposta que VA e MACO refletem "por relacionamento de marca" — não tem nada errado com o número, mas é importante o usuário saber que se ele dividir pela base única de CPFs (não disponível neste agente), os valores seriam diferentes.

---

## 1. Roteamento — este agente vs vendas-linx

| Pergunta do usuário | Agente correto |
|---|---|
| Receita, ticket, volume, qualquer indicador de negócio em geral | **vendas-linx** (default) |
| "Quantos clientes Novos / Retidos / Reativados?" | **clientes** |
| "Base ativa, LTV, recência, frequência, segmentação" | **clientes** |
| "Decompõe a árvore lógica da base de clientes" | **clientes** |

A **receita do clientes não bate** com a do vendas-linx. Marketplaces (ex.: Mercado Livre) geram receita Azzas mas o cliente final pertence ao marketplace — então não entra aqui. Sempre que o usuário estranhar a divergência, **explique esse motivo** ao invés de tentar reconciliar.

---

## 2. Perspectivas — ano de competência vs janela móvel 12m

Os indicadores podem ser vistos em **duas perspectivas distintas, com fontes diferentes**:

| Perspectiva | Tabela / View | Definição | Custo típico |
|---|---|---|---|
| **Ano de competência** | `soma-crm-bi.dashboards_corp.acomp_clientes_base` (tabela agregada) | Janela = ano calendário fechado | ~0,001 GB / US$ 0,0001 |
| **Janela móvel 12m** | `soma-crm-bi.dashboards.crm_clientes_tabela1` (VIEW) | Janela = últimos 12 meses corridos a partir da data de referência | ~9 GB / US$ 0,045 fixo |

> ℹ️ **Custos diferentes — usar com consciência.** A janela 12m tem custo perceptível (~US$ 0,045/query); pra ano de competência fica abaixo de US$ 0,001. Em ambas, seguir o gate padrão de estimativa + confirmação. Pra janela 12m, preferir 1 query consolidada (PIVOT) em vez de várias separadas.
>
> ⚠️ **Aliases de marca da §0 valem APENAS para `acomp_clientes_base`.** A view da janela 12m tem lista de marcas diferente (sem FARM ETC, sem split FARM Global EU/UK/US) — ver §11.5.

### Exemplo canônico — a mesma compra muda o status

Cliente faz 1ª compra 30/dez/2026, e 2ª compra 01/jan/2027.

- **Ano de competência:** Retido em 2027 (comprou em 2026 e em 2027).
- **Janela móvel 12m em 01/jan/2027:** ainda Novo (a janela anterior 01/jan/2025–01/jan/2026 não tem compra). Só vira Retido se comprar a partir de 31/dez/2027.

### Como aplicar

- Em toda resposta, **declarar explicitamente qual perspectiva está sendo usada**.
- Se o pedido do usuário não especificar, **perguntar** antes de calcular.
- Quando a fonte for `acomp_clientes_base`, a perspectiva é **ano de competência**, sem exceção.

---

## 3. Filtros padrão sobre `acomp_clientes_base`

Aplicar em **toda** análise sobre essa tabela, salvo se o usuário pedir explicitamente o contrário:

```sql
WHERE marca IS NOT NULL AND marca <> ''         -- replica "Marca não é (Em branco)" do dashboard
  AND tipo_canal = 'canal entrada'              -- default; muda se houver filtro de canal (§4)
  AND ano = :ano                                -- filtro temporal obrigatório
```

> **Por que excluir `marca = NULL`:** linhas sem marca representam ~16k clientes em 2026 que não foram atribuídos a nenhuma marca. O dashboard gabarito exclui — fazemos o mesmo para os números baterem.

> **Filtro temporal obrigatório:** sem `ano = X` (ou range de `anomes`), a query varre ~89 meses de histórico. Sempre estabelecer a janela explicitamente.

---

## 4. SWITCH de canal — espelha o DAX do dashboard

A tabela `acomp_clientes_base` contém linhas duplicadas por `tipo_canal` (`canal entrada` vs `canal`). Toda medida segue este padrão:

| Cenário | `WHERE tipo_canal = ?` |
|---|---|
| Nenhum filtro de canal aplicado (default) | `'canal entrada'` |
| Usuário filtrou por `canal_entrada` OU `canal_cliente` | `'canal'` |

**Implementação em SQL:**

```sql
-- Sem filtro de canal (default)
WHERE tipo_canal = 'canal entrada'

-- Com filtro por canal_entrada ou canal_cliente
WHERE tipo_canal = 'canal'
  AND canal_entrada IN (...)         -- se filtrado
  AND canal_cliente IN (...)         -- se filtrado
```

### 4.1 Dedup de Multicanal — aplicar APENAS em Qtde Clis quando filtrar por canal

Clientes que compram em múltiplos canais aparecem em N linhas de `tipo_canal = 'canal'`, uma para cada canal — isso causa double-count em `qtde_cli_1a_compra_ano`. **Outras métricas (receita, pedidos, peças, markup, cmv) NÃO precisam dedup** — elas estão corretamente rateadas por canal.

| Valor de `canal_cliente` | Fator de divisão para `qtde_cli_1a_compra_ano` |
|---|---|
| `Multicanal` | `/ 2` |
| `Multicanal c/ Franquia` | `/ 3` |
| Demais valores | `/ 1` (sem dedup) |

**SQL:**

```sql
-- Apenas quando filtrar por canal:
SUM(
  CASE canal_cliente
    WHEN 'Multicanal' THEN qtde_cli_1a_compra_ano / 2.0
    WHEN 'Multicanal c/ Franquia' THEN qtde_cli_1a_compra_ano / 3.0
    ELSE qtde_cli_1a_compra_ano
  END
) AS qtde_clis
```

---

## 5. Medidas canônicas (espelham o DAX do Power BI)

> Todas as medidas abaixo respeitam o SWITCH de canal (§4). O SQL aqui usa a forma **default** (`tipo_canal = 'canal entrada'`). Para versão filtrada por canal, trocar para `tipo_canal = 'canal'` e aplicar dedup em Qtde Clis (§4.1).

### 5.1 Medidas-base (somatórios diretos)

```sql
-- Receita
SUM(rec_marca) AS receita

-- Pedidos
SUM(pedidos_marca) AS pedidos

-- Produtos (peças)
SUM(prod_marca) AS produtos

-- Receita Markup
SUM(rec_markup) AS receita_markup

-- CMV
SUM(cmv) AS cmv

-- Qtde Clis (cuidado — usa qtde_cli_1a_compra_ano, NÃO qtde_cli_marca)
SUM(qtde_cli_1a_compra_ano) AS qtde_clis
```

> **Por que `qtde_cli_1a_compra_ano` e não `qtde_cli_marca`:** dentro de um ano, o mesmo cliente pode aparecer em vários meses. `qtde_cli_1a_compra_ano` marca o cliente apenas no mês da 1ª compra do ano — somar 12 meses retorna **clientes únicos do ano** sem double-count.

### 5.2 Medidas derivadas

| Medida | Fórmula |
|---|---|
| `VA` | `receita / qtde_clis` |
| `Ticket Médio (TM)` | `receita / pedidos` |
| `Frequência` | `pedidos / qtde_clis` |
| `PA` | `produtos / pedidos` |
| `PM` | `receita / produtos` |
| `Markup` | `receita_markup / cmv` |
| `MACO` | `(receita_markup - cmv) / qtde_clis` |

### 5.3 Identidades da árvore lógica (validar sempre)

```
Receita ≡ Qtde Clientes × VA
VA      ≡ Ticket Médio × Frequência
TM      ≡ PA × PM
Qtde Clientes ≡ Retido + Novo + Reativado
```

Quando montar um relatório/decomposição, **validar essas identidades** antes de fechar a resposta. Se não baterem, há algo errado (filtro inconsistente, agregação no lugar errado, dedup esquecido).

---

## 6. Query gabarito — número total para `ano = 2026`

Esta query reproduz **exatamente** o número-raiz da árvore lógica do dashboard (1.344.408 clientes / R$ 1.667 Mi):

```sql
SELECT
  SUM(qtde_cli_1a_compra_ano) AS qtde_clientes,
  SUM(rec_marca)               AS receita,
  SUM(pedidos_marca)           AS pedidos,
  SUM(prod_marca)              AS produtos,
  SUM(rec_markup)              AS receita_markup,
  SUM(cmv)                     AS cmv
FROM `soma-crm-bi.dashboards_corp.acomp_clientes_base`
WHERE marca IS NOT NULL AND marca <> ''
  AND tipo_canal = 'canal entrada'
  AND ano = 2026
```

Resultado esperado para 2026 (validado 2026-05-14):
- Qtde Clientes: **1.344.408**
- Receita: **R$ 1.677,6 Mi**

> Os R$ 1.667 Mi do dashboard são após uma normalização (R$ 10,6 Mi de diferença, ~0,6%) — provavelmente alguma exclusão de status ou ajuste secundário não identificado. Para análises operacionais use o número da query; para reportar "vs dashboard" mencione a margem.

---

## 7. Status do cliente — Novo / Retido / Reativado

**Origem:** coluna `statuscliente` já vem categorizada na tabela com a lógica do ano de competência.

**Valores conhecidos** (em 2026 com filtro de marca):
| Status | Definição | Volume 2026 |
|---|---|---|
| `Novo` | 1ª compra na marca dentro do ano | 449.258 |
| `Retido` | Comprou no ano anterior e voltou neste ano | 641.138 |
| `Reativado` | Já comprou na marca antes, com gap, retornou neste ano | 253.026 |
| NULL | Não classificado (~986 linhas) | considerar exclusão caso atrapalhe |

**Soma `Novo + Retido + Reativado` = 1.343.422**, ~1.000 abaixo do total 1.344.408 — diferença é a fração com `statuscliente = NULL`. Para a maioria das análises por status, excluir NULL.

---

## 8. Comparação vs Last Year (LY) — fórmula canônica do dashboard

> 🚨 **Regra absoluta:** LY tem que cobrir exatamente a **mesma janela do CY**, dia-a-dia. Filtrar `mes BETWEEN 1 AND N` **não é suficiente** quando o mês N do CY está parcial — o mesmo mês do LY entra cheio e infla a base de comparação.

### A lógica do dashboard (`Qtde Clis Ant` em DAX)

A medida `Qtde Clis Ant` decide o LY assim:

```
SE (ano selecionado contém o mês atual do ano corrente):
   LY = [acumulado dos meses anteriores ao atual no LY]
      + [valor "até o dia atual" do mês atual no LY]   -- ate_DiaAtual
SENÃO (ano corrente fechado, ou recorte que não inclui o mês corrente):
   LY = soma do ano anterior inteiro
```

Em SQL:

| Cenário | LY |
|---|---|
| **CY parcial** (ano corrente, último mês incompleto, ex.: jan-mai 2026 com mai parcial) | `SUM(qtde_cli_1a_compra_ano)` em LY para meses 1..N-1 cheios + `SUM(qtde_cli_1a_compra_ano_ate_DiaAtual)` em LY para o mês N |
| **CY ano fechado** (ex.: 2024 vs 2023) | `SUM(qtde_cli_1a_compra_ano)` em LY pro ano inteiro |
| **CY range fechado** (ex.: fev-abr 2025 vs fev-abr 2024) | `SUM(qtde_cli_1a_compra_ano)` em LY filtrado pelos mesmos meses |

### Template SQL — CY parcial (caso mais comum)

```sql
-- Hoje 2026-05-14: CY = jan-mai 2026 (mai parcial); LY = jan-abr 2025 cheio + mai 2025 ate_DiaAtual
WITH cy AS (
  SELECT SUM(qtde_cli_1a_compra_ano) AS valor
  FROM `soma-crm-bi.dashboards_corp.acomp_clientes_base`
  WHERE marca IS NOT NULL AND tipo_canal = 'canal entrada'
    AND ano = 2026 -- CY inteiro: o mês parcial já entra naturalmente pelo refresh da tabela
    -- + outros filtros (statuscliente, canal, etc.)
),
ly_meses_cheios AS (
  -- Jan-Abr 2025 cheio
  SELECT SUM(qtde_cli_1a_compra_ano) AS valor
  FROM `soma-crm-bi.dashboards_corp.acomp_clientes_base`
  WHERE marca IS NOT NULL AND tipo_canal = 'canal entrada'
    AND ano = 2025 AND mes BETWEEN 1 AND 4
    -- + mesmos filtros do CY
),
ly_mes_parcial AS (
  -- Mai 2025 truncado ao mesmo dia da janela atual
  SELECT SUM(qtde_cli_1a_compra_ano_ate_DiaAtual) AS valor
  FROM `soma-crm-bi.dashboards_corp.acomp_clientes_base`
  WHERE marca IS NOT NULL AND tipo_canal = 'canal entrada'
    AND ano = 2025 AND mes = 5
    -- + mesmos filtros do CY
)
SELECT
  cy.valor AS cy,
  ly_meses_cheios.valor + ly_mes_parcial.valor AS ly,
  ROUND((cy.valor / (ly_meses_cheios.valor + ly_mes_parcial.valor) - 1) * 100, 1) AS var_pct
FROM cy, ly_meses_cheios, ly_mes_parcial
```

**Como detectar "CY parcial":** o último `anomes` da tabela está dentro do `ano` selecionado E o `mes` desse anomes é o mês mais recente com dados. Operacionalmente, basta perguntar: o range pedido inclui o mês corrente do refresh? Se sim → fórmula parcial.

### Aplicar a mesma lógica para outras métricas

Toda métrica do `acomp_clientes_base` tem versão `_ate_DiaAtual`:
- `rec_marca` ↔ `rec_marca_ate_DiaAtual`
- `pedidos_marca` ↔ `pedidos_marca_ate_DiaAtual`
- `prod_marca` ↔ `prod_marca_ate_DiaAtual`
- `qtde_cli_marca` ↔ `qtde_cli_marca_ate_DiaAtual`
- `qtde_cli_1a_compra_ano` ↔ `qtde_cli_1a_compra_ano_ate_DiaAtual`
- `rec_markup` ↔ `rec_markup_ate_DiaAtual`
- `cmv` ↔ `cmv_ate_DiaAtual`

Use a mesma estrutura (meses cheios com coluna normal + mês parcial com `_ate_DiaAtual`) para qualquer KPI.

### Anti-padrões — NUNCA faça

- ❌ Comparar `ano = 2026` (parcial) com `ano = 2025` (fechado inteiro) sem alinhar janela — infla LY artificialmente, deflaciona a variação.
- ❌ Filtrar `mes BETWEEN 1 AND N` nos dois lados quando o mês N do CY está parcial — LY entra com o mês N cheio, ainda há desalinhamento.
- ❌ Usar `_ate_DiaAtual` no CY mas coluna normal no LY (ou vice-versa) — comparação assimétrica.
- ❌ Reportar variação YoY sem confirmar que CY e LY cobrem a mesma janela dia-a-dia.

### Histórico de erros nesta tabela (lições aprendidas — não repetir)

| Tentativa | CY (NV Retidos jan-mai 2026) | LY usado | Var | Por que estava errado |
|---|---|---|---|---|
| 1ª | 33.544 | 46.968 (2025 inteiro) | -28,6% | Parcial vs fechado inteiro |
| 2ª | 33.544 | 33.259 (jan-mai 2025 cheio) | +0,9% | Mai 2025 cheio vs mai 2026 parcial (ainda desalinhado) |
| 3ª ✅ | 33.544 | 31.389 (jan-abr 2025 cheio + mai 2025 `_ate_DiaAtual`) | **+6,9%** | Janelas alinhadas dia-a-dia |

**Sem LY disponível:** marcar com `❓ Sem LY` na resposta. Não inventar proxy nem usar benchmark externo.

---

## 9. PII

A tabela `acomp_clientes_base` é **agregada** — não há linhas com identificador individual. Não há PII direta.

- `check_cpf` = `valido` / `invalido` — apenas flag, não é o CPF.
- Não há nome, e-mail, telefone, ID de cliente.

Mesmo assim, manter o protocolo de PII para qualquer tabela nova que vier a ser adicionada ao agente. Quando confirmar a fonte da **janela móvel 12m**, validar schema antes de incluir.

---

## 10. Pitfalls conhecidos

- **Esquecer `tipo_canal = 'canal entrada'`** → double-count de tudo. Sempre filtrar.
- **Usar `qtde_cli_marca` em vez de `qtde_cli_1a_compra_ano`** → double-count de clientes entre meses.
- **Esquecer dedup de Multicanal ao filtrar canal** → infla Qtde Clis em ~20-30% conforme distribuição.
- **Incluir `marca = NULL`** → adiciona ~16k clientes sem marca atribuída que o dashboard gabarito exclui.
- **Misturar perspectivas** — somar `qtde_cli_1a_compra_ano` em janela 12m que cruza anos calendários double-counta clientes (uma 1ª compra em cada ano calendário). Para janela móvel, usar a tabela específica (a confirmar).
- **Combinar marcas (FARM + ETC, ou "FARM tudo") sem o disclaimer §0.1.b** — Qtde Clientes vira "soma das bases por marca", VA e MACO viram "por relacionamento de marca". Não é erro, é uma visão diferente, mas precisa ser explicitada.
- **Tratar `FARM ETC` como parte da `FARM`** — são marcas distintas. Pedido "FARM" → `marca = 'FARM'` apenas. Pedido "FARM Global" sem qualificador → as 3 regiões.

---

## 11. Janela Móvel 12m — `crm_clientes_tabela1` (view)

> **Esta seção é PARALELA à §§3–10**, que tratam de `acomp_clientes_base`. Não compartilhe regras entre seções — as fontes têm grão, lista de marcas e status diferentes. Para análises **na perspectiva janela móvel 12m**, use SOMENTE esta §11.

### 11.0 Fonte, custo e gate de execução

- **View:** `soma-crm-bi.dashboards.crm_clientes_tabela1`
- **Fato subjacente:** `soma-crm-bi.tabelas.crm_pesquisa_vendas` (34 GB / 66 Mi rows / particionada por `AnoMes`)
- **Joins internos da view:** `marketing.cliente`, `marketing.filial`, `soma_online_refined.refined_entrega`

**Custo:** ~9 GB / **~US$ 0,045 por query, fixo**. Column pruning e filtros externos de Data **não reduzem** (a view tem GROUP BY + JOINs que bloqueiam pruning, e `Data` é coluna calculada que não propaga pro partition `AnoMes`).

> **Gate (vale pra qualquer query, regra geral do projeto):**
> 1. Dry-run com `--dry_run` pra confirmar o scan.
> 2. Reportar ao usuário a estimativa real (`⚠️ Estimativa: ~9 GB → ~US$ 0,045`).
> 3. Aguardar "sim" explícito.
>
> Apresente o número como informação factual — o usuário decide. **Não enquadre como "alarme" ou "custo proibitivo"** — janela 12m é uma perspectiva primária e legítima do produto.

**Best practice:** rodar **uma query com vários KPIs** em PIVOT por `Periodo` em vez de queries separadas. Você paga US$ 0,045 1 vez e traz CY+LY+todas as métricas. Para múltiplas análises sobre o mesmo recorte, considerar `CREATE TEMP TABLE` materializando o resultado, depois rodar análises baratas em cima.

**Tech debt (pós-v0):** bypass via tabela física `crm_pesquisa_vendas` com `WHERE AnoMes BETWEEN ...` derrubaria o custo pra ~1–3 GB/query, mas exige replicar a lógica da view (canal_cliente, marcas via RedeLojas, UF/país). Vale a pena quando o uso da janela 12m crescer.

### 11.1 Escopo de data por medida — **a pegadinha**

> ⚠️ **A regra mais importante desta seção.** No DAX do dash, **somente** a medida `Clientes (Base Ativa)` tem `DATESINPERIOD(MAX(Date), -12, MONTH)`. **Todas as outras medidas** (Receita, Pedidos, TM, MultiCanais, Peças, Frequência, etc.) usam o **filtro nativo do slicer** (que pode ser 1 dia, 11 dias, 1 mês...).

Implicações para SQL:

| Medida | Janela aplicada | Como filtrar no SQL |
|---|---|---|
| Clientes Base Ativa | 12 meses corridos até MAX(Data do slicer) | `WHERE Data BETWEEN <max-12m+1> AND <max>` |
| Receita / Pedidos / TM / Peças / MultiCanais / Devolução / Frequência (num e den) | range nativo do slicer | `IF(Data BETWEEN <slicer_start> AND <slicer_end>, ..., 0)` dentro do agg |

**Estratégia recomendada (PIVOT único):**
```sql
WHERE Data BETWEEN <janela 12m>           -- pra Clientes Base Ativa
GROUP BY Periodo
-- métricas do dia/range via agregação condicional:
SUM(IF(Data BETWEEN <range slicer>, ...))
COUNT(DISTINCT IF(Data BETWEEN <range slicer>, ClienteIdDia, NULL))
```

Misturar tudo no mesmo WHERE inflaciona absurdamente Receita/Pedidos (já vimos: 2.200× maior). Sintoma típico do erro: TM gigante (ex.: R$ 400 mil/pedido).

### 11.2 `Periodo` — CY/LY pré-materializado

A view já materializa CY e LY como `UNION ALL` interno (LY = mesma janela com `DataPedido + 1 ano`). **Não fazer self-join manual.** Basta:

```sql
GROUP BY Periodo  -- 'Atual' = CY; 'Ano Anterior' = LY
```

O filtro `WHERE Data BETWEEN ...` aplica simultaneamente nos dois (graças ao shift +1 ano da branch LY).

### 11.3 Medidas canônicas (espelham o DAX do dash)

| Medida | Fórmula DAX | SQL equivalente |
|---|---|---|
| Clientes Base Ativa | `CALCULATE(DISTINCTCOUNT(ClienteIdDia), DATESINPERIOD(...))` | `COUNT(DISTINCT ClienteIdDia)` na janela 12m |
| Clientes (Base) | `DISTINCTCOUNT(ClienteIdDia)` | `COUNT(DISTINCT ClienteIdDia)` no range do slicer |
| Receita Faturada Total | `CALCULATE(SUM(ValorPago), QtdProd > 0)` | `SUM(IF(QtdProd > 0, ValorPago, 0))` |
| Devolução | `SUMX(BaseVendas, -ValorPago) WHERE QtdProd < 1` | `SUM(IF(QtdProd < 1, -ValorPago, 0))` ← **sai NEGATIVA** (§11.8) |
| Receita Líquida | `[Faturada] + [Devolução]` | `Faturada + Devolução` ← subtração efetiva |
| Quantidade de Pedidos | `DISTINCTCOUNT(ChavePedido)` | `COUNT(DISTINCT ChavePedido)` |
| Ticket Médio | `[Faturada] / [Pedidos]` | `SAFE_DIVIDE(Faturada, Pedidos)` |
| Peças Atendimento | `SUM(QtdProd) / [Pedidos]` | `SAFE_DIVIDE(SUM(QtdProd), Pedidos)` |
| MultiCanais Convertidos | `CALCULATE(DISTINCTCOUNT(ClienteIdDia), MultiGanhoDia = 1)` | `COUNT(DISTINCT IF(MultiGanhoDia=1, ClienteIdDia, NULL))` |
| Frequência | `COUNTROWS(BaseVendas) / [Clientes (Base)]` | `SAFE_DIVIDE(COUNT(*), Clientes_do_dia)` ← **denominador é dia, não 12m** |

### 11.4 Filtros default observados nos dashes

Filtro recorrente que precisa ser aplicado pra reproduzir os números do gabarito:

```sql
AND Filial NOT LIKE '%CRIS BARROS SB%'
AND Filial NOT LIKE '%CRIS BARROS EVENTO%'
```

São lojas de showroom/evento que não contam como varejo. **A confirmar:** se é regra global do dash inteiro ou só de páginas específicas. Por enquanto: aplicar por default e marcar o assumption na resposta ao usuário.

### 11.5 Lista de marcas — diferente do `acomp_clientes_base`

Mapeada via `CASE WHEN RedeLojas IN (...) THEN ...` interno da view:

| Pedido do usuário | Filtro SQL |
|---|---|
| "FARM" (sem qualificador) | `Marca = 'FARM'` (RedeLojas=2). **Aqui não há FARM ETC** — não precisa disclaimer §0.1.a |
| "FARM Global" | `Marca = 'FARM Global'` (RedeLojas=0, consolidado — sem split EU/UK/US) |
| "FARM LATAM" | `Marca = 'FARM LATAM'` (RedeLojas=27) |
| "Maria Filó", "Fábula" | ⚠️ usar `LIKE` com prefixo sem acento — ver §11.9 |
| Demais (Animale, Animale ORO, A.Brand, FYI, OFF Premium, Foxton, Cris Barros, NV, Carol Bassi) | `Marca = '<exato>'` |
| (NULL) | Exclui via `Marca IS NOT NULL` se quiser replicar dashboards |

**Diferenças vs `acomp_clientes_base`:**
- `FARM ETC`: **não existe** aqui (na acomp é marca separada com double-count) → cross-perspective não é diretamente comparável
- `FARM Global` consolidado (na acomp tem EU/UK/US separados)
- Sem `Oficina`, `Reserva` (presentes na acomp)
- Outras marcas (FARM LATAM, NV, Carol Bassi, Animale ORO) presentes aqui

### 11.6 `TipoCliente` — granularidade extra

4 valores: `Novo`, `Retido`, `Reativado Inativo`, `Reativado Perdido` (+ NULL residual).

Diferença vs `acomp_clientes_base` (que tem 3: Novo, Retido, Reativado em bucket único). Aqui Reativado é separado em **Inativo** e **Perdido** — diferença de tempo desde a última compra (definição exata pendente, mas a divisão é semanticamente útil pra análises de churn).

### 11.7 Cliente pode ocupar múltiplos `TipoCliente` na mesma janela 12m

**Subtleza importante.** Quando o usuário filtra por TipoCliente no dash, o filtro propaga pra TODAS as medidas, **inclusive `Clientes Base Ativa`** (porque o `DATESINPERIOD` substitui só o filtro de `Data`, não o de TipoCliente).

Logo:
- Um cliente que apareceu como `Novo` em fev/2025 e `Retido` em ago/2025 entra **nas duas buckets** na janela 12m.
- **Soma de `Clientes 12m` agrupado por TipoCliente pode EXCEDER o total geral** — não é bug, é "soma das bases por status do relacionamento ao longo do ano".

Exemplo empírico (Maria Filó, 12m até 11/11/2025):
- Soma por TipoCliente = 34.776 + 59.019 + 16.950 + 26.389 = **137.134**
- TOTAL (sem TipoCliente no GROUP BY) = **113.690**
- Diferença ≈ 23k clientes que mudaram de status dentro da janela.

**Disclaimer obrigatório** quando agrupar por TipoCliente:

> ℹ️ Soma das bases por TipoCliente excede o total porque alguns clientes mudaram de classificação dentro da janela 12m (ex: foi Novo em fev e virou Retido em ago — entra nas duas buckets). Não é double-count; é "soma de relacionamentos por status" no período.

### 11.8 Devolução — sinal invertido

Nas linhas de devolução (`QtdProd < 1`, ou seja `QtdProd = 0` ou negativo), `ValorPago` é **POSITIVO** (representa o valor estornado). Logo:
- `-ValorPago` é **negativo**
- `SUM(IF(QtdProd < 1, -ValorPago, 0))` retorna número **negativo**
- `Receita Líquida = Faturada + Devolução` faz **subtração efetiva**

Mantenha sinal negativo na coluna `devolucao` da query para transparência (e evitar confusão na hora de interpretar).

### 11.9 Bug de encoding com acentos — workaround obrigatório

Quando SQL passa por shell Windows (cmd/PowerShell) com caracteres acentuados em literal de filtro, o byte da acentuação se corrompe e o `=` não casa com o valor real:

```sql
-- ❌ FALHA silenciosamente em ambientes Windows-cmd:
WHERE Marca = 'Maria Filó'

-- ✅ Workaround robusto:
WHERE Marca LIKE 'Maria Fil%'
WHERE Marca LIKE 'F_bula'           -- F + 1 char + bula
WHERE Marca LIKE 'F%bula'           -- F + qualquer prefixo + bula
```

**Marcas afetadas:** `Maria Filó`, `Fábula`.

> Sintoma de que o bug aconteceu: a query retorna 0 linhas mesmo com filtros corretos, ou retorna marca aparecendo como `Maria Fil?` em `SELECT DISTINCT Marca`.

### 11.10 MultiCanais Convertidos — definição não confirmada

`MultiGanhoDia = 1` quando, no agregado da linha, `SUM(crm_pesquisa_vendas.MultiGanho) > 0`. Distribuição:
- 95,4% `MultiGanho = 0`
- 4,4% `MultiGanho = 1`
- 0,16% `NULL`

**Hipótese de produto** (não confirmada): "cliente que originalmente era de multicanal e foi convertido em cliente da marca". A definição precisa ser validada com quem desenhou o dash original.

Observação empírica útil:
- Praticamente **só `TipoCliente = Retido`** tem `MultiGanhoDia = 1`. Novo / Reativado Inativo / Reativado Perdido têm zero ou quase zero.
- Faz sentido conceitualmente: pra haver "ganho multicanal", o cliente precisa de histórico prévio.

Pra v0: implementar o KPI como `COUNT(DISTINCT ClienteIdDia) WHERE MultiGanhoDia = 1` (reproduz o dash perfeitamente). **Não tentar narrativa sobre "o que significa" sem validação.**

### 11.11 Query gabarito — página OVERVIEW (1 dia)

Validada `2026-05-15` contra dash de `01/01/2026`. Bate todos os 7 KPIs.

```sql
WITH base AS (
  SELECT
    Periodo,
    COUNT(DISTINCT ClienteIdDia)                                                       AS clientes_12m,
    COUNT(DISTINCT IF(Data = '2026-01-01', ClienteIdDia, NULL))                        AS clientes_1d,
    SUM(IF(Data = '2026-01-01' AND QtdProd > 0, ValorPago, 0))                         AS receita_faturada_1d,
    SUM(IF(Data = '2026-01-01' AND QtdProd < 1, -ValorPago, 0))                        AS devolucao_1d,
    COUNT(DISTINCT IF(Data = '2026-01-01', ChavePedido, NULL))                         AS pedidos_1d,
    SUM(IF(Data = '2026-01-01', QtdProd, 0))                                           AS pecas_1d,
    COUNT(DISTINCT IF(Data = '2026-01-01' AND MultiGanhoDia = 1, ClienteIdDia, NULL))  AS multicanais_1d,
    COUNTIF(Data = '2026-01-01')                                                       AS countrows_1d
  FROM `soma-crm-bi.dashboards.crm_clientes_tabela1`
  WHERE Data BETWEEN '2025-01-02' AND '2026-01-01'        -- 12m para Clientes Base Ativa
    AND Filial NOT LIKE '%CRIS BARROS SB%'
    AND Filial NOT LIKE '%CRIS BARROS EVENTO%'
  GROUP BY Periodo
)
SELECT
  Periodo, clientes_12m, clientes_1d, receita_faturada_1d, devolucao_1d,
  receita_faturada_1d + devolucao_1d                                AS receita_liquida_1d,
  pedidos_1d, pecas_1d, multicanais_1d, countrows_1d,
  ROUND(SAFE_DIVIDE(countrows_1d, clientes_1d), 4)                  AS frequencia,
  ROUND(SAFE_DIVIDE(receita_faturada_1d, pedidos_1d), 2)            AS ticket_medio,
  ROUND(SAFE_DIVIDE(pecas_1d, pedidos_1d), 4)                       AS pecas_atendimento
FROM base
ORDER BY CASE Periodo WHEN 'Atual' THEN 1 ELSE 2 END
```

### 11.12 Query gabarito — página Perfil de Cliente (TipoCliente × range)

Validada `2026-05-15` contra dash de `01–11/Nov/2025` com Marca=Maria Filó. Usa `GROUPING SETS` pra trazer cada TipoCliente + TOTAL na mesma query (1× US$ 0,045 em vez de 5×).

```sql
WITH base AS (
  SELECT
    Periodo,
    TipoCliente,
    COUNT(DISTINCT ClienteIdDia)                                                       AS clientes_12m,
    COUNT(DISTINCT IF(Data BETWEEN '2025-11-01' AND '2025-11-11', ClienteIdDia, NULL)) AS clientes_range,
    SUM(IF(Data BETWEEN '2025-11-01' AND '2025-11-11' AND QtdProd > 0, ValorPago, 0))  AS receita_faturada_range,
    SUM(IF(Data BETWEEN '2025-11-01' AND '2025-11-11' AND QtdProd < 1, -ValorPago, 0)) AS devolucao_range,
    COUNT(DISTINCT IF(Data BETWEEN '2025-11-01' AND '2025-11-11', ChavePedido, NULL))  AS pedidos_range,
    SUM(IF(Data BETWEEN '2025-11-01' AND '2025-11-11', QtdProd, 0))                    AS pecas_range,
    COUNT(DISTINCT IF(Data BETWEEN '2025-11-01' AND '2025-11-11' AND MultiGanhoDia=1, ClienteIdDia, NULL)) AS multicanais_range,
    COUNTIF(Data BETWEEN '2025-11-01' AND '2025-11-11')                                AS countrows_range
  FROM `soma-crm-bi.dashboards.crm_clientes_tabela1`
  WHERE Data BETWEEN '2024-11-12' AND '2025-11-11'
    AND Marca LIKE 'Maria Fil%'                            -- ⚠️ LIKE p/ contornar encoding (§11.9)
    AND Filial NOT LIKE '%CRIS BARROS SB%'
    AND Filial NOT LIKE '%CRIS BARROS EVENTO%'
  GROUP BY GROUPING SETS ((Periodo, TipoCliente), (Periodo))
)
SELECT
  Periodo,
  COALESCE(TipoCliente, 'TOTAL')                                       AS tipo_cliente,
  clientes_12m, clientes_range,
  receita_faturada_range, devolucao_range,
  receita_faturada_range + devolucao_range                             AS receita_liquida_range,
  pedidos_range, pecas_range, multicanais_range, countrows_range,
  ROUND(SAFE_DIVIDE(countrows_range, clientes_range), 4)               AS frequencia,
  ROUND(SAFE_DIVIDE(receita_faturada_range, pedidos_range), 2)         AS ticket_medio,
  ROUND(SAFE_DIVIDE(pecas_range, pedidos_range), 4)                    AS pecas_atendimento
FROM base
ORDER BY CASE Periodo WHEN 'Atual' THEN 1 ELSE 2 END,
         CASE tipo_cliente WHEN 'TOTAL' THEN 99
                           WHEN 'Novo' THEN 1
                           WHEN 'Retido' THEN 2
                           WHEN 'Reativado Inativo' THEN 3
                           WHEN 'Reativado Perdido' THEN 4
                           ELSE 50 END
```

### 11.13 Pitfalls específicos da janela 12m

- **Aplicar o WHERE Data BETWEEN somente como 12m amplo** sem agregação condicional para outras métricas → infla Receita/Pedidos/TM 100×–2.000×. **Padrão obrigatório**: WHERE amplo (12m) + `IF(Data BETWEEN <range>)` nas demais agregações.
- **Confundir `Clientes Base Ativa` (12m) com `Clientes (Base)` (range do slicer)** — são duas medidas distintas. Frequência usa `Clientes (Base)` no denominador, não a 12m.
- **Tratar `ClienteIdDia` como cliente+dia** — é só o CPF. O nome é enganoso.
- **Filtro `Marca = 'Maria Filó'`** em shell Windows → 0 resultados. Usar `LIKE 'Maria Fil%'`.
- **Esquecer filtro CRIS BARROS** → números aumentam ~2-5% vs gabarito do dash.
- **Comparar números da janela 12m com `acomp_clientes_base`** — perspectivas, marcas e status diferentes. Não há reconciliação 1:1. Se o usuário pedir cross-perspective, explicar que são fontes/regras independentes.
- **Tentar otimizar custo via column pruning** — não funciona na view. Único caminho efetivo: bypass via tabela física (tech debt pós-v0).
