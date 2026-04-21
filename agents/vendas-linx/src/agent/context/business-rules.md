# Business Rules — Farm/Azzas Sales Analytics (Linx silver)

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

### Filtros adicionais a decidir caso a caso

| Situação | Regra | Status |
|---|---|---|
| Excluir devoluções | filtrar `VALOR_PAGO_PROD > 0` **ou** `QTDE_PROD > 0` | ✅ ok |
| Excluir marketplace externo | não aplicável — marketplace externo não aparece nesta tabela | ✅ não se aplica |
| Excluir franquia | não aplicável — franquia não aparece nesta tabela | ✅ não se aplica |
| Excluir cancelados | não necessário — cancelados não contaminam esta tabela | ✅ não se aplica |

Quando filtro adicional for necessário e estiver marcado pendente acima, **peça confirmação ao usuário** antes de rodar.

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
| Venda Líquida | `VALOR_PAGO_PROD` | ✅ **Default em toda análise** |
| Preço unitário líquido | `PRECO_LIQUIDO_PROD` | Análise de ticket de produto |
| Desconto | `DESCONTO_PROD` | Gravado como **NEGATIVO** (validado 2026-04-18) |
| Peças | `QTDE_PROD` | Pode ser negativo em devolução/troca |
| Troca | `QTDE_TROCA_PROD` | Unidades de troca |
| CMV | `PRODUTOS_PRECOS.PRECO_CUSTO` via join | Ver §4 |

**Regra de ouro:** se o usuário não especifica, **venda líquida (`VALOR_PAGO_PROD`)**.

---

## 6. Datas — qual coluna usar

| Situação | Coluna recomendada |
|---|---|
| Análise de venda (default) | `DATA_VENDA` ✅ |
| Ticket físico (momento exato no caixa) | `DATA_VENDA_TICKET` |
| Venda digitada no ERP | `DATA_DIGITACAO` |
| Comparativo YoY com calendário ajustado | `DATA_VENDA_RELATIVA` |
| Filtro de canceladas | `DATA_DESATIVACAO` (semântica a confirmar) |

`DATA_VENDA` é a escolha segura para quase toda análise. Usar `DATA_VENDA_RELATIVA` apenas quando **explicitamente** pedido comparativo com semana/dia equivalente do ano anterior.

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

## 8. Hierarquia de rede (marca/loja)

Modelo Linx tem 5 pares `RL_xxx / CODIGO_FILIAL_xxx / FILIAL_xxx` — ver `schema.md` §1.

**Default em análises de venda:** `RL_ORIGEM` + `CODIGO_FILIAL_ORIGEM` (loja que consumiu estoque). Só trocar para `FAT`, `ATEND`, `VENDEDOR` ou `DESTINO` quando **explicitamente pedido**.

### Marca (nome legível)

`RL_ORIGEM` vem como código. Resolver via `LOJAS_REDE`:

```sql
LEFT JOIN `soma-pipeline-prd.silver_linx.LOJAS_REDE` r
  ON v.RL_ORIGEM = r.RL
```

O texto da marca fica em `r.REDE_LOJAS` (ou coluna equivalente — ver `schema.md` §3 para nome canônico da coluna).

### Filial (nome legível)

```sql
LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f
  ON v.CODIGO_FILIAL_ORIGEM = f.COD_FILIAL
```

**Gotcha validado (2026-04-18):** o join é `CODIGO_FILIAL_ORIGEM = COD_FILIAL`, **não** `= FILIAL` (FILIAL é o nome, COD_FILIAL é o código numérico).

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

### Fotos de produto em relatórios

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
- **Dimensões:** `PRODUTO + COR_PRODUTO` (grão default, §8.1), `RL_ORIGEM`, canal (§2 — pendente)
- **Métricas:** top N por receita, peças, ticket médio, desconto
- **Período típico:** 7 ou 30 dias

### 10.2 Loja × Marca (ranking)
- **Dimensões:** `CODIGO_FILIAL_ORIGEM`, `RL_ORIGEM`
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

## Histórico de atualizações

| Data | Mudança |
|---|---|
| 2026-04-18 | Criação (modelo `refined_captacao`). |
| 2026-04-19 | **Rewrite completo** para modelo Linx silver. Chave de pedido validada empiricamente (§3). Canal marcado como pendente (§2). CMV migrado para join com `PRODUTOS_PRECOS` (§4). |
| 2026-04-19 | Adicionado §8.1 — grão default "por produto" = `PRODUTO + COR_PRODUTO` (agregar tamanho, não agregar cor). |
