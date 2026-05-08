# Business Rules — Azzas 2154 Sales Analytics (BigQuery)

> Documento canônico de regras de negócio para análises de vendas.
> Complementa `schema-v2.md` (dicionário de dados).
>
> **IMPORTANTE — Tabelas acessíveis:**
> - `soma-pipeline-prd.silver_linx.*` — vendas, filiais, produtos, preços, estoque, cota
> - `apt-bonbon-179602.atelier.*` — vendedores, cota vendedor, filiais atelier
> - `soma-dl-refined-online.soma_online_refined.*` — captação, fluxo, branches
>
>
> **Ambiente:** BigQuery. Sintaxe SQL = GoogleSQL (Standard SQL).
> Tabela de vendas `tb_wanmtp_vendas_loja_captado` é **particionada por `DATA_VENDA`** — filtro obrigatório.
>
> **🔴 VISÃO DEFAULT = FATURADO.** Usar `refined_captacao` **somente** sob pedido explícito do usuário ("captado", "+vendas", "mais vendas"). Ver §11.

---

## 0. Aliases de marca (resolver sem perguntar)

| Input do usuário | Marca canônica | RL_DESTINO |
|---|---|---|
| NV | BYNV | 16 |
| Farm | FARM | 2 |
| Animale | ANIMALE | 1 |
| Fábula | FABULA | 5 |
| Off Premium / Outlet | OFF PREMIUM | 6 |
| Foxton | FOXTON | 7 |
| Cris Barros | CRIS BARROS | 9 |
| Maria Filó / MF | MARIA FILO | 15 |
| Carol Bassi | CAROL BASSI | 30 |
| Farm Etc | FARM ETC | 26 |

---

## 1. Filtros padrão

Aplicar em **toda** análise sobre `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO`:

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

| Situação | Regra |
|---|---|
| Excluir marketplace externo | não aplicável — marketplace externo não aparece nesta tabela |
| Excluir franquia | não aplicável — franquia não aparece nesta tabela |
| Excluir cancelados | não necessário — cancelados não contaminam esta tabela |

Quando um filtro adicional for necessário e não estiver coberto acima, **peça confirmação ao usuário** antes de rodar.

---

## 2. Canal (Físico × Digital) — classificação padrão

A regra de canal é uniforme para **todas as marcas**:

### 2.1 Classificação de TIPO_VENDA

| `TIPO_VENDA` | Canal classificado | Justificativa |
|---|---|---|
| `VENDA_LOJA` | **VENDA FISICA** | Venda em balcão de loja física |
| `VENDA_VITRINE` | VENDA ONLINE | Venda assistida via dispositivo na loja, mas fulfillment digital — classificada como online |
| `VENDA_ECOM` | VENDA ONLINE | Venda ecommerce pura |
| `VENDA_OMNI` | VENDA ONLINE | Venda iniciada no digital com fulfillment que pode ser físico — classificada como online pela **origem do pedido** |

```sql
CASE
  WHEN TIPO_VENDA = 'VENDA_LOJA' THEN 'VENDA FISICA'
  ELSE 'VENDA ONLINE'
END AS tipo_venda_classificado
```

### 2.2 Escopo de canal default por tipo de análise

| Tipo de análise | Filtro de canal padrão | Justificativa |
|---|---|---|
| "venda da marca X" / totais de marca | Todos os canais (sem filtro em `TIPO_VENDA`) | Receita total inclui físico + digital |
| "venda por loja" / ranking de lojas | `TIPO_VENDA = 'VENDA_LOJA'` | Lojas físicas vendem apenas por VENDA_LOJA |
| "venda digital" / ecommerce | `TIPO_VENDA IN ('VENDA_ECOM','VENDA_OMNI','VENDA_VITRINE')` | Tudo que não é VENDA_LOJA é digital |

Quando o usuário não especifica canal, aplicar o filtro da linha correspondente ao tipo de análise pedido. Nunca perguntar "qual canal?" se já está claro pelo contexto.

### 2.3 Venda Normal vs Venda Código

A receita é dividida em dois componentes mutuamente exclusivos com base na **filial de destino**:

- **venda_normal**: Venda física em balcão (VENDA_LOJA) OU venda digital pura (originada e atribuída a uma filial ECOMMERCE)
- **venda_codigo**: Venda digital (online) atribuída a uma filial que **não** é ECOMMERCE — ou seja, venda feita online mas creditada a uma loja física (via código de vendedor)

A lógica opera **após** a reclassificação de canal (§2.1): neste ponto, `TIPO_VENDA` já é 'VENDA_LOJA' (= FISICA) ou qualquer outro valor (= ONLINE).

```sql
-- Venda Código: venda ONLINE atribuída a loja física (não-ECOMMERCE)
CASE
  WHEN TIPO_VENDA != 'VENDA_LOJA'
       AND FILIAL_DESTINO IS NOT NULL
       AND FILIAL_DESTINO NOT LIKE '%ECOMMERCE%'
    THEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)
  ELSE 0
END AS venda_codigo,

-- Venda Normal: venda física OU venda digital de filial ECOMMERCE
CASE
  WHEN TIPO_VENDA = 'VENDA_LOJA'
    THEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)
  WHEN TIPO_VENDA != 'VENDA_LOJA'
       AND FILIAL_DESTINO LIKE '%ECOMMERCE%'
    THEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)
  ELSE 0
END AS venda_normal
```

> **Resumo:** Se a filial de destino é ECOMMERCE, a venda online é "normal" (digital puro). Se a filial de destino é uma loja física, a venda online é "código" (vendedor usou código para captar venda digital para sua loja).
>
> Em análises simples de receita total, não é necessário separar. O split só é relevante para análises de performance de vendedor ou atribuição de receita por canal.

### 2.4 Cobertura e giro — escopo de canal deve ser consistente

> ⚠️ **Nunca misturar escopos entre numerador e denominador de cobertura/giro.**

| Estoque usado | Venda a usar | Erro comum |
|---|---|---|
| Estoque físico (loja) | `TIPO_VENDA = 'VENDA_LOJA'` | Usar venda total com estoque físico → cobertura inflada |
| Estoque total (CD + lojas) | Todos os canais | — |

---

## 3. Chave de pedido (atendimento)

Para contagem de **atendimentos, PA, ticket médio, frequência**: usar `chave_pedido`.

### Fórmula canônica (padrão para TODAS as marcas)

```sql
CONCAT(FORMAT_DATE('%Y-%m-%d', DATA_VENDA), '_', TICKET, '_', FILIAL_DESTINO) AS chave_pedido
```

### Regra de comportamento — "quantas transações?"

Quando o usuário pedir contagem de transações **sem especificar canal**:
- Usar sempre `COUNT(DISTINCT chave_pedido)`.
- Retornar quebrado por canal (físico / digital) **e** o total consolidado.
- **Nunca defaultar silenciosamente para um canal só.** Se o contexto for ambíguo, confirmar antes de executar.

---

## 4. Marcação de TROCA (caso_venda)

A classificação de atendimentos como **TROCA** ou **VENDA NORMAL** é fundamental para calcular corretamente:
- **PA de troca** vs **PA de venda** (peça/atendimento segregado por caso)
- **Tickets de troca** vs **tickets de venda** (contagem segregada)
- **Trocas positivas** vs **trocas zeradas** (upsell ou não)
- **Upsell de troca** por vendedor (quanto a mais o vendedor vendeu além do devolvido)
- **Taxa de troca** (% dos atendimentos que são troca)

Sem essa marcação, todas essas métricas ficam misturadas e perdem significado analítico.

### 4.1 Regra de marcação

Um ticket é classificado como **TROCA** quando:
1. Existe pelo menos um item com `QTDE_TROCA_PROD > 0` no ticket
2. E a venda é física (`TIPO_VENDA = 'VENDA_LOJA'`)

```sql
-- Identificar tickets de troca
WITH tickets_troca AS (
  SELECT DISTINCT DATA_VENDA, FILIAL_DESTINO, TICKET
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO`
  WHERE QTDE_TROCA_PROD > 0 AND TIPO_VENDA = 'VENDA_LOJA'
    AND DATA_VENDA BETWEEN :start AND :end
)

-- Marcar caso_venda no dataset principal
SELECT v.*,
  CASE WHEN t.TICKET IS NOT NULL THEN 'TROCA' ELSE 'VENDA NORMAL' END AS caso_venda
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
LEFT JOIN tickets_troca t
  ON v.DATA_VENDA = t.DATA_VENDA
  AND v.FILIAL_DESTINO = t.FILIAL_DESTINO
  AND v.TICKET = t.TICKET
WHERE v.DATA_VENDA BETWEEN :start AND :end
```

**Regras:**
- Somente vendas físicas (`VENDA_LOJA`) podem ser TROCA. Vendas digitais são sempre VENDA NORMAL.
- A marcação é no **nível do ticket** (todos os itens do ticket são marcados), não do item individual.
- `VENDA_PECAS` em contexto de troca = `QTDE_PROD - QTDE_TROCA_PROD` (peças líquidas efetivamente vendidas, descontando as recebidas de volta).

### 4.2 Métricas derivadas da marcação de troca

| Métrica | Fórmula | Filtro de caso_venda |
|---|---|---|
| `tickets_troca` | `COUNT(DISTINCT chave_pedido) WHERE caso_venda = 'TROCA'` | TROCA |
| `tickets_venda` | `COUNT(DISTINCT chave_pedido) WHERE caso_venda = 'VENDA NORMAL'` | VENDA NORMAL |
| `pa_troca` | `SUM(QTDE_PROD - QTDE_TROCA_PROD) / COUNT(DISTINCT chave_pedido)` | TROCA |
| `pa_venda` | `SUM(QTDE_PROD) / COUNT(DISTINCT chave_pedido)` | VENDA NORMAL |
| `taxa_troca` | `tickets_troca / (tickets_troca + tickets_venda)` | — |

### 4.3 Troca positiva vs troca zerada

Classificação **por ticket** (não por item):

```sql
-- Dentro de tickets marcados como TROCA:
SELECT
  chave_pedido,
  SUM(SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)) AS valor_liquido_ticket,
  CASE
    WHEN SUM(SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)) > 0 THEN 'TROCA POSITIVA'
    ELSE 'TROCA ZERADA'
  END AS tipo_troca
FROM vendas_com_caso
WHERE caso_venda = 'TROCA'
GROUP BY chave_pedido
```

- **Troca positiva:** valor total do ticket > 0 → vendedor fez upsell (cliente levou mais do que devolveu)
- **Troca zerada:** valor total do ticket ≤ 0 → troca pura sem upsell (ou cliente devolveu mais)

### 4.4 Upsell de troca (por vendedor)

O upsell é o **valor líquido** do ticket de troca (receita total do atendimento, já considerando positivos e negativos) dividido pelo valor absoluto das devoluções. Mede quanto de receita incremental o vendedor gerou **além** de repor o que foi devolvido.

```sql
SELECT
  VENDEDOR,
  -- Receita líquida dos tickets de troca (positivo = vendeu mais do que devolveu)
  SUM(SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)) AS receita_liquida_troca,
  -- Valor absoluto do que foi devolvido (itens negativos)
  ABS(SUM(CASE WHEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) < 0
               THEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) ELSE 0 END)) AS devolucao_troca,
  -- Upsell = líquido / devolução
  SAFE_DIVIDE(
    SUM(SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)),
    ABS(SUM(CASE WHEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) < 0
                 THEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) ELSE 0 END))
  ) AS upsell_troca
FROM vendas_com_caso
WHERE caso_venda = 'TROCA'
GROUP BY VENDEDOR
```

**Interpretação do `upsell_troca`:**
- `> 0` → vendedor gerou receita incremental além do devolvido (bom)
- `= 0` → troca pura sem ganho (cliente levou exatamente o mesmo valor)
- `< 0` → vendedor não conseguiu repor o valor devolvido (cliente levou menos)

> **Exemplo:** cliente devolveu R\$200 e comprou R\$300 → líquido = +R\$100, devolução = R\$200, upsell = 100/200 = **0.5** (50% de receita incremental sobre o devolvido).

---

## 5. Venda MALA

Mala = produto enviado ao cliente para escolha (em casa) antes da compra efetiva. A marcação usa a tabela `loja_reserva`.

### Regra de marcação

Uma venda é classificada como **MALA** quando existe pelo menos uma reserva ativa para o mesmo cliente + filial no período da venda.

> ⚠️ **A data usada para o match é a data de FATURAMENTO, não a data do evento/captura.**
> Na visão faturado, `DATA_VENDA` = data de faturamento (correto).
> Na visão captado, usar `data_faturamento` (NUNCA `data_evento`).
> A lógica é: a mala é considerada se o **faturamento** ocorreu dentro da janela da reserva — porque o evento de captura pode ocorrer antes da mala ser emitida ou depois de ser devolvida.

### ⚠️ Cuidado com duplicação de receita

Um `LEFT JOIN` direto com `loja_reserva` pode gerar **multiplicação de linhas** quando um mesmo cliente/filial possui múltiplas reservas com períodos sobrepostos. Para evitar isso, usar `EXISTS` (apenas marca TRUE/FALSE, sem criar linhas extras):

**Visão Faturado (default):**

```sql
SELECT v.*,
  CASE
    WHEN EXISTS (
      SELECT 1
      FROM `soma-pipeline-prd.silver_linx.LOJA_RESERVA` r
      WHERE r.codigo_cliente = v.CODIGO_CLIENTE
        AND r.filial = v.FILIAL_DESTINO
        AND v.DATA_VENDA >= r.emissao
        AND v.DATA_VENDA <= DATE_ADD(r.encerramento, INTERVAL 7 DAY)
        AND r.encerramento IS NOT NULL
        AND r.codigo_cliente IS NOT NULL
        AND r.codigo_cliente != ''
    ) THEN TRUE
    ELSE FALSE
  END AS mala
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
WHERE v.DATA_VENDA BETWEEN :start AND :end
```

**Visão Captado (quando §11 se aplica):**

```sql
-- Na visão captado, o match de mala usa data_faturamento + filial (atribuição) + cpf_cliente
SELECT v.*,
  CASE
    WHEN EXISTS (
      SELECT 1
      FROM `soma-pipeline-prd.silver_linx.LOJA_RESERVA` r
      WHERE r.codigo_cliente = v.cpf_cliente
        AND r.filial = v.filial           -- filial de atribuição (codigo_filial_mais_vendas resolvido para nome)
        AND CAST(v.data_faturamento AS DATE) >= r.emissao
        AND CAST(v.data_faturamento AS DATE) <= DATE_ADD(r.encerramento, INTERVAL 7 DAY)
        AND r.encerramento IS NOT NULL
        AND r.codigo_cliente IS NOT NULL
    ) THEN TRUE
    ELSE FALSE
  END AS mala
FROM refined_captacao_filtrado v
```

> **Por que `data_faturamento` e não `data_evento`?**
> A mala é enviada ao cliente e depois devolvida/encerrada. O que importa é se a compra foi **faturada** (confirmada) dentro da janela da reserva. O `data_evento` pode ser anterior (captura antes do envio da mala) ou posterior (evento registrado após devolução), tornando-o inadequado para essa verificação.

### Condições de match

| Campo vendas (faturado) | Campo vendas (captado) | Campo reserva | Condição |
|---|---|---|---|
| `CODIGO_CLIENTE` | `cpf_cliente` | `codigo_cliente` | Igualdade (exclui NULL e vazio) |
| `FILIAL_DESTINO` | `filial` (nome) | `filial` | Igualdade |
| `DATA_VENDA` | `data_faturamento` ⚠️ | `emissao` / `encerramento` | `data_fat BETWEEN emissao AND encerramento + 7 dias` |

### Filtros na reserva (obrigatórios)

- `encerramento IS NOT NULL` — reserva deve estar encerrada (mala devolvida/concluída)
- `codigo_cliente IS NOT NULL AND codigo_cliente != ''` — precisa de identificação do cliente

### Métrica `venda_mala`

```sql
SUM(CASE WHEN mala = TRUE THEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) ELSE 0 END) AS venda_mala
```

> **`venda_mala`** é a receita total dos itens marcados como mala. Não é um tipo de venda separado — é um **flag transversal** que indica as vendas que foram influenciadas por mala enviadas a clientes.

---

## 6. CMV e margem (MACO)

**CMV não existe como coluna** em `tb_wanmtp_vendas_loja_captado`. Precisa ser construído a partir das tabelas de preços.

### 6.0 Custo unitário — resolução de preço com flag `varia_preco_cor`

Alguns produtos têm custo/preço que **varia por cor** (flag `varia_preco_cor = TRUE` em `produtos`). Para esses, o preço deve vir de `produtos_preco_cor` (grão produto+cor). Para os demais, o preço vem de `produtos_precos` (grão produto).

**Regra de resolução (CASE, não COALESCE puro):**

| `varia_preco_cor` | Fonte primária | Fallback (proteção contra cadastro vazio) |
|---|---|---|
| `TRUE` | `produtos_preco_cor` (por cor) | `produtos_precos` (por produto) — se preço por cor for NULL |
| `FALSE` ou `NULL` | `produtos_precos` (por produto) | — |

Dentro de cada fonte, a prioridade de tabela de preço é: **CT** (custo gerencial) → **C0** (custo alternativo).

### ⚠️ Deduplicação obrigatória antes do join

As tabelas de preços podem conter **mais de uma linha por produto** (duplicatas de cadastro). Joinar diretamente causa multiplicação de receita. Sempre pré-agregar com `AVG` em CTEs antes de joinar com vendas:

```sql
WITH -- Deduplicar preços por cor (1 linha por produto+cor+tabela)
preco_cor AS (
  SELECT produto, cor_produto, codigo_tab_preco,
    AVG(SAFE_CAST(preco1 AS NUMERIC)) AS preco1
  FROM `soma-pipeline-prd.silver_linx.PRODUTOS_PRECO_COR`
  WHERE codigo_tab_preco IN ('CT', 'C0')
  GROUP BY produto, cor_produto, codigo_tab_preco
),
-- Deduplicar preços por produto (1 linha por produto+tabela)
preco_prod AS (
  SELECT PRODUTO, CODIGO_TAB_PRECO,
    AVG(SAFE_CAST(PRECO1 AS NUMERIC)) AS PRECO1
  FROM `soma-pipeline-prd.silver_linx.PRODUTOS_PRECOS`
  WHERE CODIGO_TAB_PRECO IN ('CT', 'C0')
  GROUP BY PRODUTO, CODIGO_TAB_PRECO
),
-- Flag de variação de preço por cor
flags AS (
  SELECT produto, varia_preco_cor
  FROM `soma-pipeline-prd.silver_linx.PRODUTOS`
)

SELECT
  SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS venda_liquida,
  SUM(
    (v.QTDE_PROD - v.QTDE_TROCA_PROD) *
    CASE
      -- Produto com preço variável por cor: tenta cor primeiro, fallback para produto
      WHEN f.varia_preco_cor = TRUE THEN
        COALESCE(pcc_ct.preco1, pp_ct.PRECO1, pcc_c0.preco1, pp_c0.PRECO1)
      -- Produto SEM variação por cor: usa direto a tabela por produto
      ELSE
        COALESCE(pp_ct.PRECO1, pp_c0.PRECO1)
    END
  ) AS cmv,
  SAFE_DIVIDE(
    SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC))
      - SUM(
          (v.QTDE_PROD - v.QTDE_TROCA_PROD) *
          CASE
            WHEN f.varia_preco_cor = TRUE THEN
              COALESCE(pcc_ct.preco1, pp_ct.PRECO1, pcc_c0.preco1, pp_c0.PRECO1)
            ELSE
              COALESCE(pp_ct.PRECO1, pp_c0.PRECO1)
          END
        ),
    SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC))
  ) AS maco_pct
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
-- Flag do produto
LEFT JOIN flags f
  ON f.produto = v.PRODUTO
-- Preço CT por cor (usado quando varia_preco_cor = TRUE)
LEFT JOIN preco_cor pcc_ct
  ON pcc_ct.produto = v.PRODUTO AND pcc_ct.cor_produto = v.COR_PRODUTO AND pcc_ct.codigo_tab_preco = 'CT'
-- Preço C0 por cor (fallback quando varia_preco_cor = TRUE e CT cor é NULL)
LEFT JOIN preco_cor pcc_c0
  ON pcc_c0.produto = v.PRODUTO AND pcc_c0.cor_produto = v.COR_PRODUTO AND pcc_c0.codigo_tab_preco = 'C0'
-- Preço CT por produto (usado quando varia_preco_cor = FALSE, ou fallback)
LEFT JOIN preco_prod pp_ct
  ON pp_ct.PRODUTO = v.PRODUTO AND pp_ct.CODIGO_TAB_PRECO = 'CT'
-- Preço C0 por produto (último recurso)
LEFT JOIN preco_prod pp_c0
  ON pp_c0.PRODUTO = v.PRODUTO AND pp_c0.CODIGO_TAB_PRECO = 'C0'
WHERE v.DATA_VENDA BETWEEN :start AND :end
```

**Regras:**
- **Deduplicação:** `AVG(SAFE_CAST(preco1 AS NUMERIC))` nas CTEs garante 1 linha por chave. Sem isso, duplicatas na tabela de preço multiplicam receita no join.
- **CASE pela flag:** não usar COALESCE puro. A decisão de qual tabela usar é pela flag `varia_preco_cor`. Dentro de cada ramo, aí sim COALESCE para priorizar CT sobre C0.
- **Fallback obrigatório:** mesmo quando `varia_preco_cor = TRUE`, se o preço por cor for NULL (erro de cadastro), o COALESCE interno cai para a tabela por produto. Isso protege contra furos no cadastro.
- **Quantidade:** `QTDE_PROD - QTDE_TROCA_PROD` — deduz peças de troca. `QTDE_PROD` puro superestima CMV.
- **Case-sensitivity:** `produtos_preco_cor` tem colunas minúsculas (`produto`, `cor_produto`, `preco1`); `produtos_precos` tem MAIÚSCULAS (`PRODUTO`, `PRECO1`).

### 6.1 Preços de venda (para markup e análise de desconto)

A mesma lógica de resolução (flag + deduplicação) vale para preços de venda:

| Código tabela | Significado | Uso |
|---|---|---|
| `CT` | Custo gerencial | ✅ CMV / MACO |
| `C0` | Custo alternativo | Fallback quando CT é NULL |
| `VO` | Varejo original (preço "de") | Markup, análise de desconto |
| `V` | Varejo atual (preço "por") | Preço vigente de venda |
| `20` | Varejo OFF (outlet) | Preço Off Premium |

Para análises de markup/desconto, replicar o padrão das CTEs acima trocando `'CT', 'C0'` por `'VO', 'V'` (ou `'20'` para Off Premium).

### 6.2 Alias MACO — sempre explicitar

Internamente no grupo, **MACO = Margem Bruta**. Quando o usuário pedir "MACO", calcular como margem bruta e deixar explícito:
> "MACO calculado como Margem Bruta: (Receita − CMV) / Receita."

**Formato de entrega obrigatório — sempre trazer MACO em duas formas:**

| Coluna | Fórmula |
|---|---|
| `maco_rs` | `venda_liquida - cmv` |
| `maco_pct` | `maco_rs / venda_liquida` |

Nunca entregar só o percentual — o valor absoluto (R$) é obrigatório.

---

## 7. KPIs — fórmulas canônicas

### 7.1 Métricas por filial

| KPI | Fórmula |
|---|---|
| `receita_total` | `SUM(SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC))` |
| `receita_fisica` | `SUM(...) WHERE TIPO_VENDA = 'VENDA_LOJA'` |
| `receita_codigo` | `SUM(...) WHERE TIPO_VENDA != 'VENDA_LOJA' AND FILIAL_DESTINO NOT LIKE '%ECOMMERCE%'` (§2.3) |
| `qtd_pecas_total` | `SUM(QTDE_PROD)` |
| `cota` | `SUM(SAFE_CAST(PREVISAO_VALOR AS NUMERIC)) FROM lojas_previsao_vendas` |
| `fluxo` | `SUM(Visitantes) FROM seed_fluxo_loja` |
| `qtd_ticket_total` | `COUNT(DISTINCT chave_pedido)` |
| `qtd_ticket_fisico` | `COUNT(DISTINCT chave_pedido) WHERE TIPO_VENDA = 'VENDA_LOJA'` |
| `atingimento_cota` | `receita_total / cota` (0 se cota = 0) |
| `ticket_medio_total` | `receita_total / qtd_ticket_total` |
| `ticket_medio_fisico` | `receita_fisica / qtd_ticket_fisico` |
| `conversao` | `qtd_ticket_fisico / fluxo` (**cap 30%**: acima = 0, dado inconsistente) |
| `pa_total` | `qtd_pecas_total / qtd_ticket_total` |
| `pa_fisico` | `qtd_pecas_fisica / qtd_ticket_fisico` |
| `pv_medio_total` | `receita_total / qtd_pecas_total` |
| `pv_medio_fisico` | `receita_fisica / qtd_pecas_fisica` |
| `venda_mala` | `SUM(VALOR_PAGO_PROD) WHERE mala = TRUE` (via EXISTS — §5) |

- **Sempre que usar markup/margem:** dois joins com `PRODUTOS_PRECOS` (CT e C0) — ver §6.
- **Sempre que usar PA ou ticket:** usar `chave_pedido` via §3.
- `DESCONTO_PROD` é negativo → inverter sinal (`-DESCONTO_PROD`) pra somar como valor positivo de desconto.

### 7.2 Conversão — cap de 30%

```sql
CASE
  WHEN fluxo > 0 AND SAFE_DIVIDE(CAST(qtd_ticket_fisico AS FLOAT64), fluxo) <= 0.3
    THEN SAFE_DIVIDE(CAST(qtd_ticket_fisico AS FLOAT64), fluxo)
  ELSE 0.0
END AS conversao
```

Valores acima de 30% indicam inconsistência no dado de fluxo — retornar 0.

### 7.3 Filiais ecommerce — zerar métricas físicas

Filiais cujo nome contém 'ECOMMERCE' ou 'MARKET PLACE':
- `receita_fisica = 0`, `qtd_pecas_fisica = 0`, `ticket_medio_fisico = 0`, `pa_fisico = 0`

### 7.4 Taxa de Desconto

```sql
SAFE_DIVIDE(
  SUM(-DESCONTO_PROD),
  SUM(SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)) + SUM(-DESCONTO_PROD)
) AS taxa_desconto
```

`DESCONTO_PROD` é negativo → inverter sinal. Benchmark saudável: 15–25%.

---

## 8. Métricas por vendedor

### 8.1 KPIs totais e físicos

| KPI | Fórmula |
|---|---|
| `receita_total` | `SUM(SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC))` por VENDEDOR |
| `receita_fisica` | `SUM(...) WHERE TIPO_VENDA = 'VENDA_LOJA'` por VENDEDOR |
| `receita_codigo` | `SUM(...) WHERE TIPO_VENDA != 'VENDA_LOJA' AND FILIAL_DESTINO NOT LIKE '%ECOMMERCE%'` por VENDEDOR (§2.3) |
| `cota_total` | Via `lojas_previsao_vendas_vendedor` JOIN `vendedor` ON `id_vendedor` → usar `vendedor.vendedor` para cruzar com `VENDEDOR` da venda (§12.5) |
| `atingimento_cota` | `receita_total / cota_total` |
| `qtd_ticket_total` | `COUNT(DISTINCT chave_pedido)` por VENDEDOR |
| `qtd_ticket_fisico` | `COUNT(DISTINCT chave_pedido) WHERE TIPO_VENDA = 'VENDA_LOJA'` por VENDEDOR |
| `pa_total` | `SUM(QTDE_PROD) / qtd_ticket_total` |
| `pa_fisico` | `SUM(QTDE_PROD) WHERE TIPO_VENDA = 'VENDA_LOJA' / qtd_ticket_fisico` |
| `ticket_medio_total` | `receita_total / qtd_ticket_total` |
| `ticket_medio_fisico` | `receita_fisica / qtd_ticket_fisico` |
| `pv_medio_total` | `receita_total / SUM(QTDE_PROD)` |
| `pv_medio_fisico` | `receita_fisica / SUM(QTDE_PROD) WHERE TIPO_VENDA = 'VENDA_LOJA'` |
| `upsell_troca` | `receita_liquida_troca / devolucao_troca` (§4.4) |
| `venda_mala` | `SUM(VALOR_PAGO_PROD) WHERE mala = TRUE` por VENDEDOR |

> **Default em análise de vendedor:** mostrar métricas físicas (`receita_fisica`, `pa_fisico`, `ticket_medio_fisico`) como principal, pois vendedores operam primariamente em loja. Incluir `receita_codigo` como complemento para mostrar captação digital.

### 8.2 Troca positiva vs zerada

- **Troca positiva:** ticket de troca onde valor total comprado > valor devolvido (vendedor fez upsell)
- **Troca zerada:** ticket de troca onde valor total comprado ≤ valor devolvido

Ver §4.3 para fórmula detalhada.

### 8.3 Filtro de vendedores válidos

Excluir:
- Nome NULL ou vazio
- `vendedor_apelido = 'ATEND PADRAO'`
- Inativos (`data_desativacao IS NOT NULL` quando filtrar por ativos)

Fonte: `apt-bonbon-179602.atelier.vendedor`

---

## 9. Datas — qual coluna usar

| Situação | Coluna recomendada | Tabela |
|---|---|---|
| Análise de venda faturada (default) | `DATA_VENDA` ✅ | `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` |
| Ticket físico (momento no caixa) | `DATA_VENDA_TICKET` | idem |
| Venda digitada no ERP | `DATA_DIGITACAO` | idem |
| Venda captada | `data_evento` | `soma-dl-refined-online.soma_online_refined.refined_captacao` |

`DATA_VENDA` é a escolha segura para quase toda análise.

### 9.1 DATA_VENDA_RELATIVA — NÃO USAR (coluna nula em produção)

> 🚫 **`DATA_VENDA_RELATIVA` é NULL em todas as partições históricas. Não usar para nada.**

Para comparativo LY (last year), usar data fixa calculada no SQL:

```sql
-- LY: mesmo dia do ano anterior
DATE_SUB(DATA_VENDA, INTERVAL 1 YEAR)

-- LY: weekday-equivalent (mesma semana × dia da semana do ano anterior)
-- usar apenas se o usuário pedir explicitamente "semana equivalente"
DATE_SUB(DATA_VENDA, INTERVAL 52 WEEK)
```

**Regra:** LY default = mesmo dia do calendário (`INTERVAL 1 YEAR`). Só usar weekday-equivalent se o usuário pedir.

### 9.2 Glossário de janelas temporais

| Termo | Significado | Filtro SQL (padrão) |
|---|---|---|
| **MTD** (month-to-date) | Do 1º dia do mês corrente **até ontem** (inclusive) | `DATA_VENDA BETWEEN DATE_TRUNC(CURRENT_DATE(), MONTH) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)` |
| **YTD** (year-to-date) | Do 1º dia do ano corrente **até ontem** (inclusive) | `DATA_VENDA BETWEEN DATE_TRUNC(CURRENT_DATE(), YEAR) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)` |

- Regra: **MTD e YTD nunca incluem o dia de hoje** — o fechamento do dia corrente é parcial e distorce a análise. O corte é sempre `CURRENT_DATE() - 1`.
- Comparativos (MTD vs. MTD do mês/ano anterior) aplicam a mesma janela deslocada: mesmo nº de dias, terminando na data equivalente.

---

## 10. Hierarquia de rede (marca/loja)

**Default em análises de venda:** `RL_DESTINO` + `CODIGO_FILIAL_DESTINO` (loja de destino). Só trocar para `FAT`, `ATEND`, `VENDEDOR` ou `ORIGEM` quando **explicitamente pedido**.

### Marca (nome legível)

`RL_DESTINO` vem como **INT** — cast obrigatório no join:

```sql
LEFT JOIN `soma-pipeline-prd.silver_linx.LOJAS_REDE` r
  ON CAST(v.RL_DESTINO AS STRING) = r.REDE_LOJAS
```

O texto da marca fica em `r.DESC_REDE_LOJAS`.

### Filial (nome legível)

```sql
LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f
  ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
```

**Gotcha validado (2026-04-18):** o join é `CODIGO_FILIAL_xxx = COD_FILIAL`, **não** `= FILIAL` (FILIAL é o nome, COD_FILIAL é o código numérico). Mesma convenção para os 5 contextos (DESTINO default, ORIGEM/FAT/ATEND/VENDEDOR sob pedido).

### 10.1 Grão de produto — default `PRODUTO + COR_PRODUTO`

Quando o usuário pedir "por produto", agregar tamanhos, **NÃO agregar cores**. A cor é dimensão comercial relevante.

| Pedido do usuário | Grão |
|---|---|
| "por produto" (default) | `PRODUTO + COR_PRODUTO` ✅ |
| "por SKU" ou "por tamanho" | `PRODUTO + COR_PRODUTO + TAMANHO` |
| "só por estilo" ou "ignora cor" | `PRODUTO` — **perguntar antes** |

### 10.1.1 Categoria de produto — `LINHA` vs `GRUPO_PRODUTO`

| Campo | Uso típico |
|---|---|
| `LINHA` | Macro-categoria (default quando usuário pede "por categoria") |
| `GRUPO_PRODUTO` | Agrupamento mais granular dentro da linha |

**Regra:** quando o usuário pedir "por categoria" ou "por tipo de produto" sem especificar, **perguntar** qual campo. Se disser "tanto faz", usar `LINHA` como default. Ambas vivem em `produtos` — joinar via `PRODUTO`.

### 10.2 Escopo por marca

| Marca | RL_DESTINO | Observação |
|---|---|---|
| Animale | 1 | Exclui sub-redes (8, 10, 11, 12, 13, 14, 96) |
| Farm | 2 | |
| Fabula | 5 | |
| Off Premium | 6 | |
| Foxton | 7 | |
| Cris Barros | 9 | |
| Maria Filo | 15 | |
| BYNV | 16 | |
| Farm Etc | 26 | |
| Carol Bassi | 30 | |

**Regra:** ao receber "analise X" onde X é marca, filtrar `CAST(RL_DESTINO AS STRING) = '<código>'` — nunca assumir que múltiplos RL representam a mesma marca.

### 10.3 Formato de entrega padrão — HTML

> **Default de todo relatório é HTML inline.** Markdown só sob pedido explícito.

- Tabelas HTML (`<table>`) quando output é tabular
- Seções `<h2>`/`<h3>` para hierarquia
- Incluir foto de produto quando o grão é produto × cor (ver §10.4)

### 10.4 Fotos de produto em relatórios

Quando o output for tabela cujo grão é produto × cor, **incluir sempre** a imagem.

**URL padrão (mesmo padrão de `planejamento_comercial_ds.objetos.produto_cor`):**

```
https://mais-produtos-api-wlavxis5jq-uc.a.run.app/v1/sku_public/{PRODUTO}_{COR_PRODUTO}_1/vtex-images?brandId={BRAND_ID}
```

**Mapeamento `rede_lojas` → `brandId`:**

| rede_lojas | brandId | Marca |
|---|---|---|
| 1 | 6 | Animale |
| 2 | 12 | Farm |
| 5 | 13 | Fábula |
| 7 | 1820 | Foxton |
| 10 | 361151 | Animale Jeans |
| 15 | 361157 | Maria Filó |
| 16 | 361158 | NV |
| 24 | 361164 | Farm Beachwear |
| 25 | 361165 | Farm Shoes |
| 26 | 361167 | Farm Etc |

**SQL para gerar a URL:**

```sql
CONCAT(
  'https://mais-produtos-api-wlavxis5jq-uc.a.run.app/v1/sku_public/',
  v.PRODUTO, '_', v.COR_PRODUTO, '_1/vtex-images?brandId=',
  CASE CAST(v.RL_DESTINO AS STRING)
    WHEN '1' THEN '6'
    WHEN '2' THEN '12'
    WHEN '5' THEN '13'
    WHEN '7' THEN '1820'
    WHEN '10' THEN '361151'
    WHEN '15' THEN '361157'
    WHEN '16' THEN '361158'
    WHEN '24' THEN '361164'
    WHEN '25' THEN '361165'
    WHEN '26' THEN '361167'
    ELSE CAST(v.RL_DESTINO AS STRING)
  END
) AS url_foto
```

**Regras:**
- Dimensão recomendada: 80×80px inline na coluna
- Se a imagem não carregar (404), deixar placeholder — não quebrar a tabela
- O sufixo `_1` após `{PRODUTO}_{COR_PRODUTO}` indica a primeira foto (frente)

---

## 11. Visão Captado vs Faturado

> ⚠️ **REGRA ABSOLUTA:** O padrão de toda análise é a visão **FATURADO** usando `tb_wanmtp_vendas_loja_captado`.
> Usar `refined_captacao` **SOMENTE** quando o usuário pedir explicitamente "visão captado", "captação", "mais vendas" ou "+vendas".
> Na dúvida, **usar faturado**. Nunca alternar por conta própria.

| Visão | Tabela | Data de referência | Filial de atribuição | Quando usar |
|---|---|---|---|---|
| **Faturado** ✅ (default) | `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` | `DATA_VENDA` | `CODIGO_FILIAL_DESTINO` / `FILIAL_DESTINO` | **Sempre**, a menos que o usuário peça captado |
| **Captado** | `soma-dl-refined-online.soma_online_refined.refined_captacao` | `data_evento` | `codigo_filial_mais_vendas` | Só sob pedido explícito: "captado", "+vendas", "mais vendas" |

**Gatilhos para usar captado (TODOS exigem menção explícita):**
- "visão captado" / "captação"
- "mais vendas" / "+vendas" / "filial +vendas"
- "data de captura" / "data do evento"
- "antes do faturamento"

**Se o usuário disser apenas "venda", "receita", "quanto vendeu" → usar FATURADO.**

### 11.1 Mapeamento de colunas (Faturado → Captado)

| Conceito | Faturado (`tb_wanmtp_vendas_loja_captado`) | Captado (`refined_captacao`) |
|---|---|---|
| Data principal | `DATA_VENDA` (DATE, partição) | `data_evento` (TIMESTAMP → CAST AS DATE) |
| Data faturamento | = DATA_VENDA | `data_faturamento` |
| Filial atribuição | `CODIGO_FILIAL_DESTINO` (código) / `FILIAL_DESTINO` (nome) | `codigo_filial_mais_vendas` (código) |
| Filial evento | `CODIGO_FILIAL_ORIGEM` | `codigo_filial_evento` |
| Filial faturamento | `CODIGO_FILIAL_FAT` | `codigo_filial_faturamento` |
| Rede/Marca | `RL_DESTINO` (INT) | `rede_lojas_mais_vendas` (INT) |
| Receita líquida | `VALOR_PAGO_PROD` (STRING → NUMERIC) | `valor_pago_produto` (DOUBLE) |
| Quantidade | `QTDE_PROD` - `QTDE_TROCA_PROD`| `quantidade` |
| Produto | `PRODUTO` | `produto` |
| Cor | `COR_PRODUTO` | `produto_cor` |
| Tamanho | `TAMANHO` | `tamanho` |
| Ticket | `TICKET` | `pacote` |
| Vendedor | `VENDEDOR` | `vendedor` |
| Tipo venda (raw) | `TIPO_VENDA` (VENDA_LOJA, VENDA_ECOM...) | `tipo_venda` (FISICO, ONLINE, DEVOLUCAO) |
| Status | — (faturado = tudo confirmado) | `status_evento` / `ultimo_status` |
| Cliente | `CODIGO_CLIENTE` | `cpf_cliente` |
| Programa | — | `programa` (próprio, multimarca) |

### 11.2 Filtros obrigatórios na visão captado

```sql
-- 1. Remover cancelados com valor zero (evita distorção de contagem de tickets)
WHERE (ultimo_status <> 'CANCELADO' OR valor_pago_produto <> 0)

-- 2. Somente filiais próprias (via refined_branches)
  AND codigo_filial_mais_vendas IN (
    SELECT codigo_filial FROM `soma-dl-refined-online.soma_online_refined.refined_branches`
    WHERE programa_filial = 'próprio'
  )

-- 3. Filtro de marca (exemplo MF)
  AND rede_lojas_mais_vendas = 15
```

> **Nota:** `refined_captacao` contém multimarcas e franquias. O INNER JOIN com `refined_branches WHERE programa_filial = 'próprio'` é **obrigatório** para análises de vendas da marca — sem ele, números ficam inflados.

### 11.3 Redirect de multimarcas (filiais ecommerce)

Vendas com `programa = 'multimarca'` originadas em filiais ecommerce específicas devem ser redirecionadas ao `codigo_filial_mais_vendas` correto:

```sql
CASE
  -- Animale: ECOMMERCE (000900), ANIMALE ECOMMERCE SB (550317), ANIMALE ECOMMERCE CM (190454)
  WHEN programa = 'multimarca' AND codigo_filial_evento IN ('000900', '550317', '190454')
    THEN '190454'  -- redireciona para ANIMALE ECOMMERCE CM
  -- Maria Filó: ECOMMERCE MF (000864), MF ECOMMERCE SB (550321), MF ECOMMERCE CM (190458)
  WHEN programa = 'multimarca' AND codigo_filial_evento IN ('000864', '550321', '190458')
    THEN '190458'  -- redireciona para MF ECOMMERCE CM
  ELSE codigo_filial_mais_vendas
END AS codigo_filial_mais_vendas
```

### 11.4 Classificação tipo_venda no captado

O campo `tipo_venda` em `refined_captacao` tem valores **diferentes** da tabela faturada:
- Faturado: `VENDA_LOJA`, `VENDA_ECOM`, `VENDA_OMNI`, `VENDA_VITRINE`
- Captado (raw): `FISICO`, `ONLINE`, `DEVOLUCAO`, NULL

**Regra de classificação (padrão Maria Filó — universal para todas as marcas):**

```sql
CASE
  WHEN tipo_venda IN ('ONLINE', 'DEVOLUCAO') THEN 'VENDA ONLINE'
  WHEN tipo_venda IS NULL OR tipo_venda NOT IN ('ONLINE', 'DEVOLUCAO') THEN 'VENDA FISICA'
END AS tipo_venda_classificado
```

### 11.5 Venda Normal vs Venda Código (captado)

Mesma lógica do faturado (§2.3), mas usando o campo `filial` (nome da filial de atribuição):

```sql
-- Venda Código: ONLINE atribuída a loja física (não-ECOMMERCE) → vendedor usou código
CASE
  WHEN NOT (
    (tipo_venda_classificado = 'VENDA FISICA')
    OR (tipo_venda_classificado = 'VENDA ONLINE' AND filial LIKE '%ECOMMERCE%')
    OR (tipo_venda_classificado IS NULL OR filial IS NULL)
  )
  THEN valor_pago_produto
  ELSE 0
END AS venda_codigo,

-- Venda Normal: FISICA, ou ONLINE de filial ECOMMERCE, ou NULL
CASE
  WHEN NOT (
    (tipo_venda_classificado = 'VENDA FISICA')
    OR (tipo_venda_classificado = 'VENDA ONLINE' AND filial LIKE '%ECOMMERCE%')
    OR (tipo_venda_classificado IS NULL OR filial IS NULL)
  )
  THEN 0
  ELSE valor_pago_produto
END AS venda_normal
```

### 11.6 Caso de venda (TROCA / DEVOLUÇÃO / NORMAL)

```sql
CASE
  WHEN EXISTS (  -- ticket tem item com qty < 0, tipo FISICO, não cancelado
    SELECT 1 FROM refined_captacao t
    WHERE t.quantidade < 0
      AND t.tipo_venda = 'FISICO'
      AND t.status_evento <> 'CANCELADO'
      AND t.data_evento = v.data_evento
      AND t.filial = v.filial
      AND t.pacote = v.pacote
  ) THEN 'TROCA'
  WHEN tipo_venda = 'DEVOLUCAO' THEN 'DEVOLUCAO'
  ELSE 'VENDA NORMAL'
END AS caso_venda
```

> **Regra:** Somente vendas FISICAS podem ser classificadas como TROCA. Vendas digitais são sempre VENDA NORMAL ou DEVOLUCAO.

### 11.7 Atendimento (ticket calculado no captado)

```sql
-- Padrão todas as marcas:
CONCAT(
  CAST(data_evento AS STRING FORMAT 'YYYY-MM-DD'), '_',
  pacote, '_',
  codigo_filial_mais_vendas
) AS atendimento
```

### 11.8 Resumo: quando NÃO usar refined_captacao

- Para qualquer análise genérica de "venda" / "receita" → **faturado**
- Para análise de vendedor por VENDEDOR código → **faturado** (campo direto)
- Para cota vs venda → **faturado** (§12)
- Para CMV/margem → **faturado** (join com preços — §6)
- Para fluxo × conversão → **faturado** (fluxo usa FILIAL_DESTINO — §13)

**Usar refined_captacao APENAS para:**
- Acompanhamento de pedidos antes do faturamento
- Análise de captação por filial "+vendas" (onde o pedido foi captado vs onde foi faturado)
- Visão de cancelamentos (ultimo_status = 'CANCELADO')
- Quando o usuário explicitamente pedir

---

## 12. Cota / Meta — regras canônicas

### 12.1 Fonte de venda — nunca usar LOJAS_PREVISAO_VENDAS.VENDA

`LOJAS_PREVISAO_VENDAS.VENDA` **não é confiável** — campo não é atualizado pelo sistema. Toda venda realizada vem de `tb_wanmtp_vendas_loja_captado.VALOR_PAGO_PROD`.

### 12.2 Atingimento de meta — loja física

```sql
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
    -- Devoluções INCLUÍDAS por padrão (venda líquida real). Só filtrar sob pedido explícito (§1.1).
  GROUP BY 1
)
SELECT c.FILIAL, v.venda, c.meta, SAFE_DIVIDE(v.venda, c.meta) AS atingimento
FROM cota c
LEFT JOIN venda v ON c.FILIAL = v.filial_nome
```

### 12.3 Atingimento de meta — ecommerce (por marca)

**Contexto estrutural:** os sufixos `CM`, `SB`, `HRG`, `RBX` no nome de uma filial indicam o CNPJ sob o qual ela está registrada — são a **mesma filial operacional** em momentos diferentes da estratégia fiscal do grupo. A cota digital tende a ficar no CNPJ original (ex. `_CM`), enquanto o volume de vendas atual flui pelo CNPJ migrado (ex. `_SB` após incorporação para Soma Brands). Por isso, **nunca comparar cota vs venda digital fazendo join por nome de filial** — o resultado será zero ou errado.

**Regra:** agregar cota e venda digital **por marca (`REDE_LOJAS`)**, usando as filiais canônicas da cota e `TIPO_VENDA IN ('VENDA_ECOM','VENDA_OMNI','VENDA_VITRINE')` para a venda.

#### Tabela canônica — filiais-base ecommerce por marca

A coluna "nome-base" é o nome sem sufixo de CNPJ. Todos os sufixos de um mesmo nome-base são a mesma filial operacional.

| Marca | RL | Nome-base ecommerce | Sufixos observados | Filial da COTA ativa | Observação |
|---|---|---|---|---|---|
| ANIMALE | 1 | `ANIMALE ECOMMERCE` | CM, SB, HRG | `ANIMALE ECOMMERCE CM` | — |
| BYNV | 16 | `NV ECOMMERCE` / `NV ECOMMERCE RJ` | SB, CM, RJ CM, RJ OFF CM | `NV - ECOMMERCE` (nome legado) | Nome da cota difere do padrão atual |
| CAROL BASSI | 30 | `CAROL BASSI ECOMMERCE` | (sem sufixo) | `CAROL BASSI ECOMMERCE` | Único — sem split CNPJ |
| CRIS BARROS | 9 | `CRIS BARROS ECOMMERCE` | CM, SB | `CRIS BARROS ECOMMERCE CM` | — |
| FABULA | 5 | `FABULA ECOMMERCE` | CM, SB, HRG | `ECOMMERCE FABULA RBX` (nome legado) | Nome da cota é um legado RBX |
| FARM | 2 | `FARM ECOMMERCE` | CM, SB, HRG | `FARM ECOMMERCE CM` | — |
| FARM ETC | 26 | `FARM ETC ECOMMERCE` | (sem sufixo) | `FARM ETC ECOMMERCE` | Canal sem volume de venda identificado em 2025 |
| FOXTON | 7 | `FOXTON ECOMMERCE` | CM, SB, HRG | `FOXTON ECOMMERCE CM` | — |
| MARIA FILO | 15 | `MF ECOMMERCE` | CM, SB | `MF ECOMMERCE CM` | — |
| OUTLET | 6 | `CDS OUTLET ECOMMERCE` / `OUTLET ECOMMERCE` | CM, SB | `CDS OUTLET ECOMMERCE CM` | — |

#### Regra de join para cota vs venda digital

**Nunca fazer:**
```sql
-- ❌ Join por nome de filial — CM da cota ≠ SB onde a venda flui
JOIN lojas_previsao_vendas m ON filial_venda = m.FILIAL
```

**Fazer — agregar por marca (`REDE_LOJAS`):**
```sql
-- ✅ Cota: todas as filiais ecommerce da marca (todos os sufixos)
-- ✅ Venda: TIPO_VENDA digital, todos os sufixos da marca
-- ✅ Join por REDE_LOJAS — elimina o problema de sufixo
WITH cota_digital AS (
  SELECT
    f.REDE_LOJAS,
    lr.DESC_REDE_LOJAS AS marca,
    SUM(SAFE_CAST(m.PREVISAO_VALOR AS NUMERIC)) AS meta_digital
  FROM soma-pipeline-prd.silver_linx.LOJAS_PREVISAO_VENDAS m
  LEFT JOIN soma-pipeline-prd.silver_linx.FILIAIS f ON m.FILIAL = f.FILIAL
  LEFT JOIN soma-pipeline-prd.silver_linx.LOJAS_REDE lr ON f.REDE_LOJAS = lr.REDE_LOJAS
  WHERE m.FILIAL IN (
    -- todos os sufixos das filiais ecommerce ativas (CM, SB, HRG, legados)
    'ANIMALE ECOMMERCE CM',
    'NV - ECOMMERCE',            -- nome legado BYNV
    'CAROL BASSI ECOMMERCE',
    'CRIS BARROS ECOMMERCE CM',
    'ECOMMERCE FABULA RBX',      -- nome legado FABULA
    'FARM ECOMMERCE CM',
    'FARM ETC ECOMMERCE',
    'FOXTON ECOMMERCE CM',
    'MF ECOMMERCE CM',
    'CDS OUTLET ECOMMERCE CM'
  )
  AND m.DATA_VENDA BETWEEN :data_inicio AND :data_fim
  GROUP BY 1, 2
),
venda_digital AS (
  SELECT
    CAST(v.RL_DESTINO AS STRING) AS REDE_LOJAS,
    lr.DESC_REDE_LOJAS AS marca,
    SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS venda_digital
  FROM soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO v
  LEFT JOIN soma-pipeline-prd.silver_linx.LOJAS_REDE lr ON CAST(v.RL_DESTINO AS STRING) = lr.REDE_LOJAS
  WHERE v.DATA_VENDA BETWEEN :data_inicio AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
    AND v.TIPO_VENDA IN ('VENDA_ECOM', 'VENDA_OMNI', 'VENDA_VITRINE')
  GROUP BY 1, 2
)
SELECT
  c.marca,
  v.venda_digital,
  c.meta_digital,
  SAFE_DIVIDE(v.venda_digital, c.meta_digital) AS atingimento_digital
FROM cota_digital c
LEFT JOIN venda_digital v USING (REDE_LOJAS)
ORDER BY 1
```

#### Notas importantes
- CM, SB, HRG, RBX são CNPJs distintos da **mesma filial operacional** — para fins comerciais, são a mesma coisa.
- A cota tende a ficar registrada no CNPJ mais antigo (CM); à medida que a migração acontece, o volume de venda migra para o novo CNPJ (SB ou HRG). O join por `REDE_LOJAS` resolve isso automaticamente.
- Filiais com nomenclatura totalmente diferente na cota (`NV - ECOMMERCE`, `ECOMMERCE FABULA RBX`) são legados anteriores à padronização de nomes.
- **FARM ETC** tem cota cadastrada mas sem vendas identificadas em 2025 — possível canal ainda não operacional.
- OMNI (`VENDA_OMNI`) é contabilizado como digital — ver §2.

> Ver também `schema-v2.md` §3 (tabela FILIAIS) para a regra geral de sufixos.

### 12.4 Meta zero — não calcular atingimento

Lojas com `PREVISAO_VALOR = 0` (ou NULL) **não têm meta cadastrada** — não calcular atingimento. Reportar em bloco separado com flag "⚠️ sem meta cadastrada".

### 12.5 Cota por vendedor

> ⚠️ `lojas_previsao_vendas_vendedor.id_vendedor` é uma chave surrogate (bigint) que **não bate diretamente** com o campo `VENDEDOR` (código string) da tabela de vendas.
> É obrigatório fazer join com `atelier.vendedor` para obter o código do vendedor.

```sql
SELECT
  vnd.vendedor         AS vendedor,           -- código que bate com vendas.VENDEDOR
  vnd.vendedor_apelido AS vendedor_apelido,
  vnd.codigo_filial    AS codigo_filial,
  SUM(cota.previsao_valor) AS cota_total
FROM `apt-bonbon-179602.atelier.lojas_previsao_vendas_vendedor` cota
INNER JOIN `apt-bonbon-179602.atelier.vendedor` vnd
  ON cota.id_vendedor = vnd.id_vendedor
WHERE CAST(cota.data_venda AS DATE) BETWEEN :data_inicio AND :data_fim
GROUP BY 1, 2, 3
```

**Mapeamento de chaves:**

| Tabela | Campo | Tipo | Papel |
|---|---|---|---|
| `lojas_previsao_vendas_vendedor` | `id_vendedor` | BIGINT | Surrogate key interna |
| `vendedor` | `id_vendedor` | BIGINT | FK → mesma surrogate key |
| `vendedor` | `vendedor` | STRING | Código do vendedor (ex: "M001", "T001") |
| `tb_wanmtp_vendas_loja_captado` | `VENDEDOR` | STRING | Código do vendedor — bate com `vendedor.vendedor` |

**Join com vendas (atingimento de cota por vendedor):**

```sql
-- CTE de cota
cota_vendedor AS (
  SELECT
    vnd.vendedor,
    vnd.codigo_filial,
    SUM(cota.previsao_valor) AS cota_total
  FROM `apt-bonbon-179602.atelier.lojas_previsao_vendas_vendedor` cota
  INNER JOIN `apt-bonbon-179602.atelier.vendedor` vnd
    ON cota.id_vendedor = vnd.id_vendedor
  WHERE CAST(cota.data_venda AS DATE) BETWEEN :data_inicio AND :data_fim
  GROUP BY 1, 2
)
-- Join com vendas
SELECT
  v.VENDEDOR,
  SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS receita,
  c.cota_total,
  SAFE_DIVIDE(SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)), c.cota_total) AS atingimento
FROM soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO v
LEFT JOIN cota_vendedor c
  ON v.VENDEDOR = c.vendedor
  AND v.CODIGO_FILIAL_DESTINO = c.codigo_filial
WHERE v.DATA_VENDA BETWEEN :data_inicio AND :data_fim
GROUP BY 1, 3
```

### 12.6 Cota mista (física + digital por marca)

Para atingimento total (todos os canais combinados por marca):
- **Cota:** somar todas as filiais da marca em `lojas_previsao_vendas` (não filtrar por tipo)
- **Venda:** somar todos os `TIPO_VENDA` com `RL_DESTINO = <código da marca>`
- **Agregar por** `REDE_LOJAS` / marca

---

## 13. Fluxo de loja

Fonte: `soma-dl-refined-online.soma_online_refined.seed_fluxo_loja`

### 13.1 Normalização obrigatória de nomes de filial

Os nomes em `DS_site_id_nome` na tabela de fluxo **não batem diretamente** com `FILIAL_DESTINO` da tabela de vendas. É necessário aplicar as seguintes transformações antes de fazer o join:

```sql
WITH fluxo_normalizado AS (
  SELECT
    Data,
    -- 1. Upper + Trim
    -- 2. Corrigir acentuação para ASCII
    -- 3. ANIMALE BUZIOS → BUZIOS
    -- 4. MARIA FILO → MF (exceto MARIA FILO COPACABANA CM)
    -- 5. Adicionar sufixo " CM" onde não existe (exceto RESERVA)
    CASE
      WHEN UPPER(TRIM(DS_site_id_nome)) = 'MARIA FILO COPACABANA CM'
        THEN 'MARIA FILO COPACABANA CM'
      ELSE
        CASE
          WHEN NOT REGEXP_CONTAINS(
            REGEXP_REPLACE(
              REGEXP_REPLACE(
                REGEXP_REPLACE(
                  REGEXP_REPLACE(
                    REGEXP_REPLACE(
                      REGEXP_REPLACE(
                        UPPER(TRIM(DS_site_id_nome)),
                        r'ANÁLIA', 'ANALIA'),
                      r'PÁTIO', 'PATIO'),
                    r'RIBEIRÃO', 'RIBEIRAO'),
                  r'BRASÍLIA', 'BRASILIA'),
                r'VITÓRIA', 'VITORIA'),
              r'^ANIMALE BUZIOS', 'BUZIOS'),
            r'\sCM$')
            AND NOT REGEXP_CONTAINS(
              REGEXP_REPLACE(
                REGEXP_REPLACE(
                  REGEXP_REPLACE(
                    REGEXP_REPLACE(
                      REGEXP_REPLACE(
                        REGEXP_REPLACE(
                          UPPER(TRIM(DS_site_id_nome)),
                          r'ANÁLIA', 'ANALIA'),
                        r'PÁTIO', 'PATIO'),
                      r'RIBEIRÃO', 'RIBEIRAO'),
                    r'BRASÍLIA', 'BRASILIA'),
                  r'VITÓRIA', 'VITORIA'),
                r'^ANIMALE BUZIOS', 'BUZIOS'),
              r'^RESERVA')
          THEN CONCAT(
            REGEXP_REPLACE(
              REGEXP_REPLACE(
                REGEXP_REPLACE(
                  REGEXP_REPLACE(
                    REGEXP_REPLACE(
                      REGEXP_REPLACE(
                        REGEXP_REPLACE(
                          UPPER(TRIM(DS_site_id_nome)),
                          r'ANÁLIA', 'ANALIA'),
                        r'PÁTIO', 'PATIO'),
                      r'RIBEIRÃO', 'RIBEIRAO'),
                    r'BRASÍLIA', 'BRASILIA'),
                  r'VITÓRIA', 'VITORIA'),
                r'^ANIMALE BUZIOS', 'BUZIOS'),
              r'MARIA FILO', 'MF'),
            ' CM')
          ELSE
            REGEXP_REPLACE(
              REGEXP_REPLACE(
                REGEXP_REPLACE(
                  REGEXP_REPLACE(
                    REGEXP_REPLACE(
                      REGEXP_REPLACE(
                        REGEXP_REPLACE(
                          UPPER(TRIM(DS_site_id_nome)),
                          r'ANÁLIA', 'ANALIA'),
                        r'PÁTIO', 'PATIO'),
                      r'RIBEIRÃO', 'RIBEIRAO'),
                    r'BRASÍLIA', 'BRASILIA'),
                  r'VITÓRIA', 'VITORIA'),
                r'^ANIMALE BUZIOS', 'BUZIOS'),
              r'MARIA FILO', 'MF')
        END
    END AS filial,
    Visitantes
  FROM `soma-dl-refined-online.soma_online_refined.seed_fluxo_loja`
  WHERE Visitantes IS NOT NULL
)
SELECT filial, Data, SUM(Visitantes) AS fluxo_total
FROM fluxo_normalizado
WHERE Data BETWEEN :data_inicio AND :data_fim
GROUP BY filial, Data
```

### 13.2 Resumo das transformações aplicadas

| Passo | Transformação | Motivo |
|---|---|---|
| 1 | `UPPER(TRIM(...))` | Padronizar caixa e remover espaços |
| 2 | `REGEXP_REPLACE` acentos (ANÁLIA→ANALIA, PÁTIO→PATIO, RIBEIRÃO→RIBEIRAO, BRASÍLIA→BRASILIA, VITÓRIA→VITORIA) | Tabela de fluxo tem acentos, tabela de vendas não |
| 3 | `ANIMALE BUZIOS` → `BUZIOS` | Nome divergente entre sistemas |
| 4 | `MARIA FILO` → `MF` | Padrão de nomenclatura (exceto `MARIA FILO COPACABANA CM` que permanece) |
| 5 | Adicionar sufixo ` CM` | Lojas na tabela de vendas têm sufixo CM; fluxo não. Não aplicar a lojas RESERVA |

### 13.3 Join com vendas

Após normalização, o join é direto:

```sql
LEFT JOIN fluxo_normalizado fl
  ON v.FILIAL_DESTINO = fl.filial
  AND v.DATA_VENDA = fl.Data
```

> ⚠️ **Colunas case-sensitive na tabela original:** `Data`, `DS_site_id_nome`, `Visitantes`.
>
> ⚠️ **Sem a normalização, o join perde ~30% das filiais** por incompatibilidade de nomes.

---

## 14. Princípio anti-hallucination

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

---

## 15. Hierarquia analítica (template de resposta)

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

## 16. Lojas ativas vs fechadas

Filtro canônico para "lojas físicas ativas":
```sql
WHERE TIPO_FILIAL IN ('LOJA VAREJO', 'FRANQUIA')
  AND DATA_FECHAMENTO IS NULL
```

Lojas com estoque = 0 AND venda = 0 nos últimos 30 dias são presumivelmente inativas. Excluí-las de análises de performance e registrar: "N lojas excluídas por inatividade."

---

## 17. Taxa de devolução

### 17.1 Default: receita, regime de faturamento

```sql
SELECT
  CASE TIPO_VENDA WHEN 'VENDA_LOJA' THEN 'Físico' ELSE 'Digital' END AS canal,
  SAFE_DIVIDE(
    SUM(CASE WHEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) < 0
             THEN ABS(SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC)) ELSE 0 END),
    SUM(CASE WHEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) > 0
             THEN SAFE_CAST(VALOR_PAGO_PROD AS NUMERIC) ELSE 0 END)
  ) AS taxa_devolucao
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO`
WHERE DATA_VENDA BETWEEN :start AND :end
GROUP BY 1
```

### 17.2 Benchmarks

| Canal | Referência saudável |
|---|---|
| Físico | < 10% |
| Digital (moda premium) | 15–25% |

> Se o usuário não especificar métrica nem regime, rodar por receita/faturamento e informar qual fórmula foi usada.

### 17.3 Regime de competência (sob pedido explícito)

Matcheia cada devolução à sua venda original via `PEDIDO_SITE` (ecom/omni) ou `TICKET + FILIAL_ORIGEM` (físico). Requer self-join. Usar apenas quando o usuário pedir explicitamente ("taxa de devolução por coleção", "quanto voltou das vendas de fevereiro").

### 17.4 Por peças (sob pedido explícito)

Substituir `VALOR_PAGO_PROD` por `QTDE_PROD` na mesma estrutura do §18.1.

---

## 18. Métrica default e variações

| Conceito | Coluna | Quando usar |
|---|---|---|
| Venda Líquida | `VALOR_PAGO_PROD` | ✅ **Default em toda análise** — soma tudo (inclui devoluções como negativo) |
| Preço unitário líquido | `PRECO_LIQUIDO_PROD` | Análise de ticket de produto |
| Desconto | `DESCONTO_PROD` | Gravado como **NEGATIVO** |
| Peças | `QTDE_PROD` | Pode ser negativo em devolução/troca |
| Troca | `QTDE_TROCA_PROD` | Unidades de troca (≥ 0) |
| CMV | via join com preços (§6) | Nunca está pronto na tabela de vendas |

**Regra de ouro:** se o usuário não especifica, usar `SUM(VALOR_PAGO_PROD)` sem filtrar por sinal.

---

## 19. Tipos de análise catalogados

### 19.1 Produto × Marca × Canal
- **Grão:** `PRODUTO + COR_PRODUTO` (§10.1), `RL_DESTINO`, canal (§2)
- **Métricas:** top N por receita, peças, ticket médio, desconto
- **Período típico:** 7 ou 30 dias

### 19.2 Loja × Marca (ranking)
- **Grão:** `CODIGO_FILIAL_DESTINO`, `RL_DESTINO`
- **Métricas:** receita, ticket, PA, sell-through
- **Filtro típico:** `TIPO_VENDA = 'VENDA_LOJA'`

### 19.3 Tendência (YoY / período a período)
- Comparar períodos equivalentes, nunca absolutos
- Para moda, preferir **YoY sobre MoM**
- Isolar datas promocionais (Black Friday, Dia das Mães, Natal) quando relevante

### 19.4 Desconto & margem
- Métricas: taxa de desconto, markup, margem bruta
- **Obrigatório:** join com preços para CMV (§6)

### 19.5 Giro / cobertura
- Calcular por loja; perguntar horizonte ao usuário antes de rodar
- Nunca misturar escopos (§2.4)

---

## 20. Limite de complexidade de query

Para análises multi-dimensão (ex.: venda × LY × cota × estoque × cobertura num único SQL):

✅ **Fazer:** N queries menores, cada uma com 1–2 CTEs, consolidadas no cliente.
❌ **Não fazer:** mega-query com >3 CTEs e múltiplos LEFT JOINs cruzados.

Exemplos de splits seguros:
- Query 1: venda do período
- Query 2: venda LY (com filtro de data equivalente)
- Query 3: cota do período
- Query 4: fluxo

---

## 21. Padrão de encerramento de análise

Ao terminar qualquer análise, incluir **um próximo passo concreto**:
- Se mostra anomalia: sugerir drill-down
- Se cobriu um período: sugerir comparação vs LY ou vs meta
- Se há dado indisponível: indicar qual tabela/query resolveria

Não inventar próximos passos genéricos. Deve ser específico ao resultado.

---

## Histórico de atualizações

| Data | Mudança |
|---|---|
| 2026-04-18 | Criação original (modelo refined_captacao). |
| 2026-04-19 | Rewrite para modelo Linx silver. Chave de pedido validada empiricamente. CMV migrado para join com PRODUTOS_PRECOS. |
| 2026-04-19 | Adicionado grão default "por produto" = PRODUTO + COR_PRODUTO. |
| 2026-04-21 | Regras canônicas venda vs cota; LOJAS_PREVISAO_VENDAS.VENDA documentada como não confiável. |
| 2026-04-22 | Troca do default de filial: ORIGEM → DESTINO. RL_DESTINO passa a ser INTEGER (cast obrigatório). |
| 2026-04-27 | Correção CMV/MACO: quantidade = QTDE_PROD - QTDE_TROCA_PROD. Preço = COALESCE(CT, C0). |
| 2026-05-07 | **Migração para BigQuery** — tabelas de soma-pipeline-prd, apt-bonbon-179602, soma-dl-refined-online. Reprodução das métricas de objetos via tabelas-fonte. |
| 2026-05-07 | v2 — Removido atendimento_2. Atendimento padrão = DATA_VENDA + TICKET + FILIAL_DESTINO para todas as marcas. Adicionado TROCA e MALA. |
| 2026-05-07 | v3 — Padronizado canal: apenas VENDA_LOJA = VENDA FISICA (padrão Maria Filó). |
| 2026-05-07 | v4 — §5 MALA: EXISTS para evitar duplicação. |
| 2026-05-07 | v5 — §2.3 venda_codigo: lógica por FILIAL_DESTINO NOT LIKE '%ECOMMERCE%'. |
| 2026-05-07 | v6 — §4 TROCA: PA troca/venda, positiva/zerada, upsell, taxa. |
| 2026-05-07 | v7 — §13 Fluxo: normalização de nomes (regex acentos, sufixo CM). |
| 2026-05-07 | v8 — §8 Vendedor: métricas físicas adicionadas. |
| 2026-05-07 | v9 — Resgatados tópicos do arquivo original: LINHA vs GRUPO_PRODUTO, fotos de produto, formato HTML, tipos de análise catalogados, cota mista, taxa devolução (competência/peças), métrica default. Histórico unificado. |
