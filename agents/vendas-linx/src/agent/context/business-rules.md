# Business Rules — Azzas 2154 Sales Analytics (Linx silver)

> Documento canônico de regras de negócio para análises sobre `soma-pipeline-prd.silver_linx.*`.
> Complementa `schema.md` (dicionário de dados) e `analyst principles.md` (método analítico).
>
> **Convenção:** ao descobrir/corrigir uma regra, atualize este arquivo e comite. Regras aqui são compartilhadas entre todos os usuários do produto.
>
> **Status do modelo:** migrado de `refined_captacao` → `silver_linx` em 2026-04-18 (commit b902c35). Este arquivo foi reescrito em 2026-04-19 para refletir o Linx.

---

## 1. Filtros padrão

Aplicar em **toda** análise sobre `TB_WANMTP_VENDAS_LOJA_CAPTADO`:

```sql
WHERE DATA_VENDA BETWEEN :start AND :end
```

**Por quê:** tabela é EXTERNAL e **não tem partição nativa**. Sem filtro de data, varre histórico inteiro a cada query — custo alto.

### 1.1 Devoluções — incluir por padrão (venda líquida real)

> 🚫 **NUNCA aplicar `VALOR_PAGO_PROD > 0` ou `QTDE_PROD > 0` por conta própria.**
>
> O **default é sempre venda líquida incluindo devoluções** — é essa a métrica que representa o resultado comercial real da loja/marca/período. Uma devolução entra na tabela com `VALOR_PAGO_PROD` e `QTDE_PROD` negativos, e precisa ser somada (não filtrada) para o líquido bater com o que o negócio enxerga.

**Quando filtrar devoluções:**
- **Só** quando o usuário **explicitamente** pedir ("venda bruta", "só venda positiva", "excluir devoluções", "só entradas").
- Se ele pedir algo ambíguo ("venda do dia", "quanto vendemos"), **não filtrar** — é líquido.
- Se houver dúvida real, **perguntar** antes de rodar. Não assumir.

**Quando precisar filtrar (sob pedido explícito):**

| Situação pedida | Filtro |
|---|---|
| "Só venda positiva" / "Excluir devoluções" | `AND SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) > 0` |
| "Só devoluções" | `AND SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) < 0` |
| "Venda bruta (antes de devolução)" | `AND SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) > 0` + rotular como "bruta" na resposta |

**Gate antes de rodar a query:** tem `VALOR_PAGO_PROD > 0` no `WHERE`? O usuário pediu explicitamente? Se não — tirar.

### 1.2 Outros filtros a decidir caso a caso

| Situação | Regra | Status |
|---|---|---|
| Excluir marketplace externo | não aplicável — marketplace externo não aparece nesta tabela | ✅ não se aplica |
| Excluir franquia | não aplicável — franquia não aparece nesta tabela | ✅ não se aplica |
| Excluir cancelados | não necessário — cancelados não contaminam esta tabela | ✅ não se aplica |

Quando um filtro adicional for necessário e não estiver coberto acima, **peça confirmação ao usuário** antes de rodar.

---

## 2. Canal (Físico × Digital) — ✅ validada 2026-04-20

Usar o campo `TIPO_VENDA`. Mapeamento canônico:

| `TIPO_VENDA` | Canal |
|---|---|
| `VENDA_LOJA` | Físico |
| `VENDA_ECOM` | Digital |
| `VENDA_OMNI` | Digital |
| `VENDA_VITRINE` | Digital |

```sql
CASE TIPO_VENDA
  WHEN 'VENDA_LOJA' THEN 'Físico'
  ELSE 'Digital'
END AS canal
```

**Notas:**
- `VENDA_OMNI` é classificada como Digital pela **origem do pedido** (iniciado pelo cliente no digital, mesmo com fulfillment físico).
- `VENDA_VITRINE` é venda assistida via dispositivo na loja, mas o fulfillment é via ecom — digital.
- **Métrica default: receita** (`SUM(VALOR_PAGO_PROD)`). Análises por volume de pedidos só se explicitamente solicitado.
- O usuário pode pedir breakdowns alternativos (ex: ver omni separado) — nesses casos, use `TIPO_VENDA` cru ao invés do agrupamento canal.

---

## 3. Chave de pedido (atendimento) — validada empiricamente 2026-04-19

Para contagem de **atendimentos, PA, ticket médio, frequência**: usar `chave_pedido` conforme abaixo. Nunca `COUNT(DISTINCT TICKET)` puro — o TICKET é sequencial por filial e colide (22% dos tickets físicos aparecem em >1 filial).

### Fórmula canônica

```sql
COALESCE(
  NULLIF(PEDIDO_SITE, ''),
  CONCAT(FORMAT_DATE('%Y%m%d', DATA_VENDA), '|',
         CAST(CODIGO_FILIAL_ORIGEM AS STRING), '|', TICKET)
) AS chave_pedido
```

### Lógica

- **Com `PEDIDO_SITE` preenchido** (ecom, omni, vitrine, e parte do físico): `PEDIDO_SITE` é único globalmente (0% colisão de filial em 30 dias).
- **Sem `PEDIDO_SITE`** (físico puro): compor com `(data, filial, ticket)`.

> ⚠️ **Por que esta chave usa `CODIGO_FILIAL_ORIGEM` mesmo com o default analítico sendo DESTINO:** o `TICKET` é sequencial **por filial origem** (loja que emitiu o ticket no caixa). A composição com ORIGEM garante unicidade — foi validada empiricamente (100% cobertura, 0 colisões). Trocar para DESTINO quebra a unicidade. Esta é uma regra técnica de chave, **não** o default de atribuição analítica (esse virou DESTINO em 2026-04-22 — ver §8).

### Validação (30 dias, rodada em 2026-04-19)

| `TIPO_VENDA` | Linhas | Pedidos distintos | Itens/pedido | Linhas sem chave |
|---|---:|---:|---:|---:|
| VENDA_LOJA | 403.664 | 180.131 | 2,24 | 0 |
| VENDA_ECOM | 180.257 | 109.299 | 1,65 | 0 |
| VENDA_OMNI | 133.667 | 90.961 | 1,47 | 0 |
| VENDA_VITRINE | 173 | 137 | 1,26 | 0 |

**Cobertura 100%, zero colisão.** A fórmula é a definitiva até prova em contrário.

### Nota sobre subpacotes

Em ecom/omni, ~8% dos `PEDIDO_SITE` têm múltiplos `TICKET` (remessas separadas). A chave acima **já agrega corretamente** porque usa `PEDIDO_SITE` como pai — os múltiplos tickets caem no mesmo pedido.

---

## 4. CMV e margem

**CMV não existe como coluna** em `TB_WANMTP_VENDAS_LOJA_CAPTADO`. Para margem/markup, joinar com `PRODUTOS_PRECOS` (tabela CT) e calcular.

**Padrão validado:**

```sql
SELECT
  SUM(v.VALOR_PAGO_PROD)              AS venda_liquida,
  SUM(v.QTDE_PROD * p.PRECO_CUSTO)    AS cmv,
  SUM(v.VALOR_PAGO_PROD)
    / NULLIF(SUM(v.QTDE_PROD * p.PRECO_CUSTO), 0) AS markup
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
LEFT JOIN `soma-pipeline-prd.silver_linx.PRODUTOS_PRECOS` p
  ON v.PRODUTO = p.PRODUTO
 AND p.CODIGO_TAB_PRECO = 'CT'
WHERE v.DATA_VENDA BETWEEN :start AND :end
```

**Regras:**
- Sempre filtrar `CODIGO_TAB_PRECO = 'CT'` no join — essa é a tabela de custo.
- CMV = `QTDE_PROD * PRECO_CUSTO` (custo unitário × quantidade). Se são 3 peças, o CMV é 3× o custo unitário.
- Em devoluções, `QTDE_PROD` é negativo → CMV fica negativo (correto, alinha o sinal da receita).

---

## 5. Métrica default e variações

| Conceito | Coluna | Quando usar |
|---|---|---|
| Venda Líquida | `VALOR_PAGO_PROD` | ✅ **Default em toda análise** — soma tudo (inclui devoluções como negativo) |
| Preço unitário líquido | `PRECO_LIQUIDO_PROD` | Análise de ticket de produto |
| Desconto | `DESCONTO_PROD` | Gravado como **NEGATIVO** (validado 2026-04-18) |
| Peças | `QTDE_PROD` | Pode ser negativo em devolução/troca |
| Troca | `QTDE_TROCA_PROD` | Unidades de troca |
| CMV | `PRODUTOS_PRECOS.PRECO_CUSTO` via join | Ver §4 |

**Regra de ouro:** se o usuário não especifica, **venda líquida (`VALOR_PAGO_PROD`)** — `SUM` direto, sem filtrar por sinal. Devoluções entram com valor negativo e **devem** ser somadas para o líquido refletir a realidade. Só filtrar `> 0` sob pedido explícito (ver §1.1).

---

## 6. Datas — qual coluna usar

| Situação | Coluna recomendada |
|---|---|
| Análise de venda (default) | `DATA_VENDA` ✅ |
| Ticket físico (momento exato no caixa) | `DATA_VENDA_TICKET` |
| Venda digitada no ERP | `DATA_DIGITACAO` |
| Filtro de canceladas | `DATA_DESATIVACAO` (semântica a confirmar) |

`DATA_VENDA` é a escolha segura para quase toda análise.

### 6.1 DATA_VENDA_RELATIVA — NÃO USAR (coluna nula em produção)

> 🚫 **`DATA_VENDA_RELATIVA` é NULL em todas as partições históricas (validado 2026-04-25). Não usar para nada.**

Para comparativo LY (last year), usar data fixa calculada no SQL:

```sql
-- LY: mesmo dia do ano anterior
DATE_SUB(DATA_VENDA, INTERVAL 1 YEAR)

-- LY: weekday-equivalent (mesma semana × dia da semana do ano anterior)
-- usar apenas se o usuário pedir explicitamente "semana equivalente" ou
-- "calendário ajustado" — e só quando o calendário comercial for anunciado aqui
DATE_SUB(DATA_VENDA, INTERVAL 52 WEEK)
```

**Regra:** LY default = mesmo dia do calendário (`INTERVAL 1 YEAR`). Só usar weekday-equivalent se o usuário pedir e se a diferença de calendário for documentada neste arquivo.

### 6.1 Glossário de janelas temporais

| Termo | Significado | Filtro SQL (padrão) |
|---|---|---|
| **MTD** (month-to-date) | Do 1º dia do mês corrente **até ontem** (inclusive) | `DATA_VENDA BETWEEN DATE_TRUNC(CURRENT_DATE(), MONTH) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)` |
| **YTD** (year-to-date) | Do 1º dia do ano corrente **até ontem** (inclusive) | `DATA_VENDA BETWEEN DATE_TRUNC(CURRENT_DATE(), YEAR) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)` |

- Regra: **MTD e YTD nunca incluem o dia de hoje** — o fechamento do dia corrente é parcial e distorce a análise. O corte é sempre `CURRENT_DATE() - 1`.
- Comparativos (MTD vs. MTD do mês/ano anterior) aplicam a mesma janela deslocada: mesmo nº de dias, terminando na data equivalente.
- Para comparativos YoY com calendário ajustado, ver `DATA_VENDA_RELATIVA` no §6.

---

## 7. KPIs — fórmulas canônicas

| KPI | Fórmula | Benchmark moda premium |
|---|---|---|
| Ticket Médio | `SUM(VALOR_PAGO_PROD) / COUNT(DISTINCT chave_pedido)` | varia por posicionamento |
| PA (Peças/Atendimento) | `SUM(QTDE_PROD) / COUNT(DISTINCT chave_pedido)` | 1,8–2,5 |
| Taxa de Desconto | `SUM(-DESCONTO_PROD) / (SUM(VALOR_PAGO_PROD) + SUM(-DESCONTO_PROD))` | 15–25% saudável |
| Markup | `SUM(VALOR_PAGO_PROD) / SUM(QTDE_PROD * PRECO_CUSTO)` | 2,5–4,0x |
| Margem Bruta | `1 - SUM(QTDE_PROD * PRECO_CUSTO) / SUM(VALOR_PAGO_PROD)` | 55–70% |

- **Sempre que usar markup/margem:** join com `PRODUTOS_PRECOS` (§4).
- **Sempre que usar PA ou ticket:** usar `chave_pedido` via §3.
- `DESCONTO_PROD` é negativo → inverter sinal (`-DESCONTO_PROD`) pra somar como valor positivo de desconto.

---

## 6.2 Limite de complexidade de query

> ⚠️ **Tabelas EXTERNAL não têm partição nativa — o plano de execução é linear no volume total.**

Para análises multi-dimensão (ex.: venda × LY × cota × estoque × cobertura num único SQL):

✅ **Fazer:** N queries menores, cada uma com 1–2 CTEs, agregadas no cliente (Python/JS).
❌ **Não fazer:** mega-query com >3 CTEs e múltiplos LEFT JOINs entre tabelas EXTERNAL — alto risco de timeout.

Exemplos de splits seguros:
- Query 1: venda do período (com filtro de data)
- Query 2: venda LY (com filtro de data equivalente)
- Query 3: cota do período
- Query 4: foto de estoque (1 data específica, com filtro de loja/produto)

Cada query retorna em segundos. A consolidação multi-métrica acontece no cliente após as queries.

---

## 8. Hierarquia de rede (marca/loja)

Modelo Linx tem 5 pares `RL_xxx / CODIGO_FILIAL_xxx / FILIAL_xxx` — ver `schema.md` §1.

**Default em análises de venda:** `RL_DESTINO` + `CODIGO_FILIAL_DESTINO` (loja de destino da venda). Só trocar para `FAT`, `ATEND`, `VENDEDOR` ou `ORIGEM` quando **explicitamente pedido**.

### Marca (nome legível)

`RL_DESTINO` vem como código **INTEGER** — cast obrigatório no join:

```sql
LEFT JOIN `soma-pipeline-prd.silver_linx.LOJAS_REDE` r
  ON CAST(v.RL_DESTINO AS STRING) = r.REDE_LOJAS
```

O texto da marca fica em `r.DESC_REDE_LOJAS` (ver `schema.md` §3).

### Filial (nome legível)

```sql
LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f
  ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
```

**Gotcha validado (2026-04-18):** o join é `CODIGO_FILIAL_xxx = COD_FILIAL`, **não** `= FILIAL` (FILIAL é o nome, COD_FILIAL é o código numérico). Mesma convenção para os 5 contextos (DESTINO default, ORIGEM/FAT/ATEND/VENDEDOR sob pedido).

---

## 8.1 Grão de produto — default `PRODUTO + COR_PRODUTO`

Quando o usuário pedir análise "por produto", o grão padrão é **produto × cor** — **agregar tamanhos, NÃO agregar cores**.

**Por quê:** a cor é uma dimensão comercial relevante (coleção, ruptura, performance de variante). Tamanho é dimensão operacional (grade) que só importa em análise de estoque/grade específica.

### SQL pattern

```sql
SELECT
  v.PRODUTO,
  v.COR_PRODUTO,
  SUM(v.VALOR_PAGO_PROD) AS venda_liquida,
  SUM(v.QTDE_PROD) AS pecas
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
WHERE v.DATA_VENDA BETWEEN :start AND :end
GROUP BY 1, 2
```

### Quando mudar o grão

| Pedido do usuário | Grão |
|---|---|
| "por produto" (default) | `PRODUTO + COR_PRODUTO` ✅ |
| "por SKU" ou "por tamanho" | `PRODUTO + COR_PRODUTO + TAMANHO` |
| "só por estilo" ou "ignora cor" | `PRODUTO` (agregado) — **perguntar antes**, é contra-intuitivo |

### 8.1.1 Categoria de produto — `LINHA` vs. `GRUPO_PRODUTO`

Os dois campos principais de categorização de produto são:

| Campo | Uso típico |
|---|---|
| `LINHA` | Categoria de nível mais alto / macro-categoria (default) |
| `GRUPO_PRODUTO` | Agrupamento mais granular dentro da linha |

**Regra de conduta:**
- Quando o usuário pedir análise "por categoria", "por tipo de produto" ou algo similar sem especificar, **perguntar qual campo ele quer** (`LINHA` ou `GRUPO_PRODUTO`).
- Se ele não responder ou disser "tanto faz / o que for melhor", usar **`LINHA`** como default.
- Ambas as colunas vivem em `PRODUTOS` — joinar via `USING (PRODUTO)`.

### 8.2 Escopo por marca — mapeamento canônico de RL_DESTINO

Quando o usuário pedir análise "de Animale" (ou qualquer marca), usar **exatamente** o(s) código(s) da rede abaixo — não incluir sub-redes ou variantes a não ser que explicitamente pedido.

| Marca | RL_DESTINO(s) default | Excluir da análise física | Observação |
|---|---|---|---|
| Animale | `1` | `CODIGO_FILIAL_DESTINO = 190454` (ANIMALE ECOMMERCE CM — filial digital, não física) | Redes 8 (MAS ANIMALE), 10 (ANIMALE JEANS), 11 (ATACADO), 12 (ESTOQUES), 13 (ECOMMERCE), 14 (JOIAS), 96 (ANIMALE SP) **não entram** no filtro default "Animale" |
| Farm | `2` | — | |
| Fabula | `5` | — | |
| Outlet | `6` | — | |
| Foxton | `7` | — | |
| Cris Barros | `9` | — | |
| Maria Filo | `15` | — | |
| BYNV | `16` | — | |
| Carol Bassi | `30` | — | |

**Regra:** ao receber pedido "analise X" onde X é uma marca, filtrar `CAST(RL_DESTINO AS STRING) = '<código>'` — nunca assumir que múltiplos RL representam a mesma marca. Se o usuário quiser ver sub-redes (ex.: "MAS Animale separado"), ele deve pedir explicitamente.

### 8.3 Formato de entrega padrão — HTML, não markdown

> **Default de todo relatório é HTML inline.** Markdown só sob pedido explícito do usuário ("me dá em markdown", "exporta como .md", "só o texto").

```
Relatório default = HTML inline
  ├── com foto quando o grão é produto × cor (ver §8.4 abaixo)
  ├── com tabelas HTML (<table>) quando o output é tabular
  └── com seções <h2>/<h3> para hierarquia

Markdown = só se explicitamente pedido
```

### 8.4 Fotos de produto em relatórios

Quando o output for uma lista/tabela cujo grão é produto × cor, **incluir sempre** a foto usando:
```
https://images.somalabs.com.br/query/{w}/{h}/{PRODUTO}/{COR_PRODUTO}
```
Regras completas, exemplos SQL e dimensões recomendadas estão na seção `product-photos` do contexto (abaixo, carregada junto com este doc). Não é uma ferramenta MCP separada — é um padrão documental a ser aplicado inline na montagem do HTML/Markdown do relatório.

---

## 9. Hierarquia analítica (template de resposta)

Toda análise deve seguir a ordem:

```
1. Contexto    — o que estamos medindo e por quê
2. Volume      — quanto vendeu (unidades, receita)
3. Eficiência  — como vendeu (ticket, PA, desconto)
4. Rentab.     — valeu a pena (margem, markup)
5. Diagnóstico — por que (vs período, vs marca, vs loja)
6. Recomendação— o que fazer
```

Não pular direto para KPI complexo sem ancorar volume primeiro.

---

## 10. Tipos de análise catalogados

### 10.1 Produto × Marca × Canal
- **Dimensões:** `PRODUTO + COR_PRODUTO` (grão default, §8.1), `RL_DESTINO`, canal (§2 — pendente)
- **Métricas:** top N por receita, peças, ticket médio, desconto
- **Período típico:** 7 ou 30 dias

### 10.2 Loja × Marca (ranking)
- **Dimensões:** `CODIGO_FILIAL_DESTINO`, `RL_DESTINO`
- **Métricas:** receita, ticket, PA, sell-through
- **Filtro típico:** `TIPO_VENDA = 'VENDA_LOJA'` quando a análise for estritamente físico

### 10.3 Tendência (YoY / período a período)
- Comparar períodos equivalentes, nunca absolutos.
- Para moda, preferir **YoY sobre MoM**.
- Isolar datas promocionais (Black Friday, Dia das Mães, Natal) quando relevante.

### 10.4 Desconto & margem
- Métricas: taxa de desconto, markup, margem bruta.
- **Obrigatório:** join com `PRODUTOS_PRECOS` para CMV (§4).

### 10.5 Giro / cobertura
- Fórmulas e horizonte em `schema.md` §6.3.
- Sempre calcular por loja; perguntar horizonte ao usuário antes de rodar.

---

## 11. Princípio anti-hallucination

**Nunca inventar um número.** Todo valor em resposta deve vir de:
1. Query executada nesta sessão (✅ Dado real)
2. Valor explicitamente dado pelo usuário
3. Benchmark de mercado com fonte (📊 Benchmark)

Se não tem: *"não tenho esse dado disponível"*. Não extrapolar.

Labels obrigatórios em qualquer número:

| Label | Uso |
|---|---|
| ✅ Dado real | Saiu de query nesta sessão |
| 📊 Benchmark | Referência de mercado (citar fonte) |
| 🔶 Estimativa | Calculado a partir de dado real |
| ❓ Indisponível | Não presente — não inventar |

Referência completa: `analyst principles.md`.

---

---

## 12. Venda vs Cota — regras canônicas (validado 2026-04-21)

### 12.1 Fonte de venda — nunca usar LOJAS_PREVISAO_VENDAS.VENDA

`LOJAS_PREVISAO_VENDAS.VENDA` (e `QTDE_VENDA`, `CUSTO`, `DESCONTO`) **não são confiáveis** — o campo existe no schema mas não é atualizado de forma consistente pelo sistema Linx. Nunca usar para calcular atingimento ou qualquer KPI de venda.

**Regra:** toda análise de "venda realizada" usa exclusivamente `TB_WANMTP_VENDAS_LOJA_CAPTADO.VALOR_PAGO_PROD`.

### 12.2 Atingimento de meta — loja física

```sql
-- Padrão correto: cota de LOJAS_PREVISAO_VENDAS + venda de TB_WANMTP_VENDAS_LOJA_CAPTADO
WITH cota AS (
  SELECT FILIAL, SUM(SAFE_CAST(PREVISAO_VALOR AS NUMERIC)) AS meta
  FROM `soma-pipeline-prd.silver_linx.LOJAS_PREVISAO_VENDAS`
  WHERE DATA_VENDA BETWEEN :data_inicio AND :data_fim
  GROUP BY 1
),
venda AS (
  SELECT f.FILIAL AS filial_nome,
         SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS venda
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
  WHERE v.DATA_VENDA BETWEEN :data_inicio AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
    AND v.TIPO_VENDA = 'VENDA_LOJA'
    -- Devoluções INCLUÍDAS por padrão (venda líquida real). Só adicionar
    -- `AND SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC) > 0` se o usuário pedir
    -- explicitamente venda bruta / excluir devoluções (ver §1.1).
  GROUP BY 1
)
SELECT c.FILIAL, v.venda, c.meta, SAFE_DIVIDE(v.venda, c.meta) AS atingimento
FROM cota c
LEFT JOIN venda v ON c.FILIAL = v.filial_nome
```

### 12.3 Atingimento de meta — ecommerce (digital)

**Contexto estrutural:** os sufixos `CM`, `SB`, `HRG`, `RBX` no nome de uma filial indicam o CNPJ sob o qual ela está registrada — são a **mesma filial operacional** em momentos diferentes da estratégia fiscal do grupo. A cota digital tende a ficar no CNPJ original (ex. `_CM`), enquanto o volume de vendas atual flui pelo CNPJ migrado (ex. `_SB` após incorporação para Soma Brands). Por isso, **nunca comparar cota vs venda digital fazendo join por nome de filial** — o resultado será zero ou errado.

**Regra:** agregar cota e venda digital **por marca (`REDE_LOJAS`)**, usando as filiais canônicas da cota (listadas em `schema.md §11`) e `TIPO_VENDA IN ('VENDA_ECOM','VENDA_OMNI','VENDA_VITRINE')` para a venda.

Padrão SQL completo e tabela de filiais canônicas: ver `schema.md §11`.

### 12.4 Meta zero — não calcular atingimento

Lojas com `PREVISAO_VALOR = 0` (ou NULL) no período **não têm meta cadastrada** — não calcular atingimento.

```sql
-- ✅ Correto: segregar lojas sem meta
SELECT
  c.FILIAL,
  v.venda,
  c.meta,
  CASE
    WHEN c.meta IS NULL OR SAFE_CAST(c.meta AS NUMERIC) = 0
      THEN NULL  -- sem meta — não calcular
    ELSE SAFE_DIVIDE(v.venda, SAFE_CAST(c.meta AS NUMERIC))
  END AS atingimento,
  CASE
    WHEN c.meta IS NULL OR SAFE_CAST(c.meta AS NUMERIC) = 0
      THEN 'sem meta cadastrada'
    ELSE NULL
  END AS nota
FROM cota c
LEFT JOIN venda v ON c.FILIAL = v.filial_nome
```

Reportar lojas sem meta em bloco separado com flag "⚠️ sem meta cadastrada — verificar planejamento". Nunca incluí-las no cálculo agregado de atingimento da marca.

### 12.4 Cota mista (física + digital juntos)

Para atingimento total (físico + digital combinados por marca):
- Cota: somar todas as filiais da marca em `LOJAS_PREVISAO_VENDAS` (não filtrar por ecom)
- Venda: somar todos os `TIPO_VENDA` com `RL_DESTINO = <código da marca>`
- Agregar por `REDE_LOJAS` / marca

---

## 13. Lojas ativas vs fechadas

### 13.1 Definição canônica de "loja ativa"

```sql
-- Loja ativa = sem data de fechamento E com venda nos últimos 30 dias
DATA_FECHAMENTO IS NULL
AND venda_ultimos_30d > 0
```

Para calcular `venda_ultimos_30d` por loja, fazer subquery em `TB_WANMTP_VENDAS_LOJA_CAPTADO` com `DATA_VENDA >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)`.

### 13.2 Lojas com estoque = 0 e venda = 0

Lojas com `ESTOQUE = 0` AND `SUM(venda 30d) ≤ 0` são **presumivelmente fechadas ou inativas**. Não entram em análises de performance, ranking ou cobertura. Excluí-las silenciosamente e registrar na resposta: "N lojas excluídas por inatividade (sem venda nos últimos 30 dias)."

> 📌 **Pendência de ferramenta:** `list_active_stores(marca, periodo)` — futura ferramenta MCP que retornará as lojas ativas com base nas regras acima, eliminando a necessidade de inferir manualmente. Enquanto não existir, aplicar as regras acima inline.

---

## Histórico de atualizações

| Data | Mudança |
|---|---|
| 2026-04-18 | Criação (modelo `refined_captacao`). |
| 2026-04-19 | **Rewrite completo** para modelo Linx silver. Chave de pedido validada empiricamente (§3). Canal marcado como pendente (§2). CMV migrado para join com `PRODUTOS_PRECOS` (§4). |
| 2026-04-19 | Adicionado §8.1 — grão default "por produto" = `PRODUTO + COR_PRODUTO` (agregar tamanho, não agregar cor). |
| 2026-04-21 | Adicionado §12 — regras canônicas venda vs cota; `LOJAS_PREVISAO_VENDAS.VENDA` documentada como não confiável; mapeamento de filiais ecommerce validado (§11 em schema.md). |
| 2026-04-22 | **Troca do default de filial/rede: ORIGEM → DESTINO.** `RL_DESTINO` + `CODIGO_FILIAL_DESTINO` passam a ser o contexto padrão em §8, §10, §12 e nos exemplos SQL de schema.md §6/§8/§11. `RL_DESTINO` é INTEGER → requer `CAST(... AS STRING)` no join com `LOJAS_REDE`. §3 (chave_pedido) mantém `CODIGO_FILIAL_ORIGEM` — é chave técnica validada empiricamente, não default analítico. |
