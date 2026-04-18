# Business Rules — Farm Group Sales Analytics

> Documento canônico de regras de negócio para análises sobre a tabela `soma-dl-refined-online.soma_online_refined.refined_captacao`.
> Todas as análises publicadas neste portal devem respeitar estas regras.
>
> **Convenção:** Ao descobrir uma regra nova ou corrigir uma existente, atualizar este arquivo e comitar. Regras aqui são compartilhadas entre todos os usuários do produto.

---

## 1. Filtros padrão (sempre aplicar)

```sql
WHERE ultimo_status NOT IN ('CANCELADO', 'CANCELADO AUTOMATICO')
  AND tipo_seller <> 'EXTERNO'
  AND NOT (tipo_venda = 'FISICO' AND programa = 'franquia')
  AND TIMESTAMP_TRUNC(data_evento, DAY) >= TIMESTAMP_TRUNC(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL N DAY), DAY)
```

**Motivação:**
- Cancelados distorcem volumes e margens.
- Seller externo é marketplace de terceiros (fora do P&L próprio).
- Franquia física é P&L independente — separada da operação própria.
- Filtro temporal é obrigatório: tabela não tem partição nativa; sem filtro, varre ~6 anos de histórico.

---

## 2. Mapeamento de canal (tipo_venda → Físico/Online)

Definição oficial para qualquer análise de canal:

| `tipo_venda` | Canal |
|---|---|
| `FISICO` | Físico |
| `ESTOQUE PROPRIO` | Físico |
| `SOMASTORE` | Físico |
| `VITRINE` | Físico |
| `ONLINE` | Online |
| `DEVOLUCAO` | Online |

**SQL pattern:**
```sql
CASE
  WHEN tipo_venda IN ('ONLINE','DEVOLUCAO') THEN 'Online'
  WHEN tipo_venda IN ('FISICO','ESTOQUE PROPRIO','SOMASTORE','VITRINE') THEN 'Físico'
END AS canal
```

**Por quê:**
- `DEVOLUCAO` é devolução pós-venda de pedidos online → reduz venda líquida do canal online (correto).
- `ESTOQUE PROPRIO`, `SOMASTORE`, `VITRINE` são operações vinculadas à loja física (ship-from-store, marketplace próprio, vitrine/showroom).

**Se aparecer um `tipo_venda` fora dessa lista:** perguntar ao usuário antes de classificar. Não improvisar.

---

## 3. Chave de pedido / atendimento (pacote tratado)

Para contagem de atendimentos, PA, ticket médio e frequência, usar `pacote` tratado — **não** `chave_atendimento` diretamente.

**Regra de tratamento:**

1. **Ecommerce (ONLINE, SOMASTORE):** `pacote` vem com sufixo `-NN` indicando subpacotes/remessas do mesmo pedido lógico.
   - Ex: `v1035019crb-01`, `v1035019crb-02`, `v1035019crb-03` → mesmo pedido `v1035019crb`.
   - **Ação:** remover o sufixo `-NN` para agregar corretamente.

2. **Físico (FISICO, ESTOQUE PROPRIO, VITRINE) e DEVOLUCAO:** `pacote` é sequencial por filial/dia (ex: `00009999`, `70000002`). **Não é único globalmente** — a mesma string se repete em outras filiais/datas.
   - **Ação:** compor chave com `(data, filial, pacote)`.

**SQL pattern canônico:**

```sql
CASE
  WHEN REGEXP_CONTAINS(pacote, r'-[0-9]{1,2}$')
    THEN REGEXP_REPLACE(pacote, r'-[0-9]{1,2}$', '')       -- ecom: strip -NN
  ELSE CONCAT(
    FORMAT_DATE('%Y%m%d', DATE(data_evento)), '|',
    COALESCE(codigo_filial_mais_vendas, 'X'), '|',
    pacote
  )                                                         -- físico/devolução: composite
END AS chave_pedido
```

**Atenção regex:** usar `-[0-9]{1,2}$` (1 ou 2 dígitos). VITRINE tem pacotes como `1-2621228` que cairiam num regex ganancioso `-[0-9]+$` e seriam destruídos.

**Por quê:** `pacote` é o identificador primário no sistema transacional. `chave_atendimento` funciona, mas é um derivado. Além disso, `COUNT(DISTINCT pacote)` puro subconta atendimentos (colisão entre filiais/dias no físico).

---

## 4. CMV com sinal: sempre positivo no source

**Bug observado:** a coluna `cmv` é gravada **sempre como valor positivo**, mesmo em linhas de devolução ou troca interna. Não tem o sinal operacional da transação.

**Evidência (YTD 2026):**

| `tipo_venda` | Venda líquida | CMV | Linhas CMV<0 |
|---|---:|---:|---:|
| DEVOLUCAO | −R$ 75M | **+R$ 27M** | 0 |
| FISICO (trocas internas) | mix ± | sempre + | 0 |

**Consequência se ignorado:** Ao agregar vendas e devoluções, o CMV é **duplicado** (contado na venda original + contado de novo na devolução). Markup e margem ficam artificialmente comprimidos.

**Caso real:** OFF PREMIUM Online apareceu com markup 0,69x — impossível para outlet nessa escala. Após correção, 1,37x (consistente).

**Correção canônica — sempre aplicar em agregações que misturem sinais:**

```sql
-- CMV líquido: alinha sinal à quantidade para que devoluções subtraiam custo também
IF(quantidade < 0, -ABS(cmv), ABS(cmv)) AS cmv_liquido
```

**Dispensável quando:** a análise filtra apenas `valor_pago_produto > 0` (exclui devoluções). Mas nunca misturar sem corrigir.

**Uso:**
- Markup: `SUM(valor_pago_produto) / SUM(cmv_liquido)`
- Margem bruta: `SUM(valor_pago_produto - cmv_liquido) / SUM(valor_pago_produto)`

---

## 5. Métrica default e variações

| Conceito | Coluna | Quando usar |
|---|---|---|
| Venda Líquida | `valor_pago_produto` | **Default em toda análise** |
| Venda Bruta | `valor_produto` | Cálculo de taxa de desconto |
| Desconto | `valor_desconto` | Gravado como **número negativo** |
| CMV | `cmv` → `cmv_liquido` | Sempre corrigir sinal (ver §4) |
| Margem de contribuição | `maco` | Já inclui rateios — validar antes de usar em análise ad-hoc |
| Peças | `quantidade` | Pode ser negativo em devolução/troca |

**Regra de ouro:** se o usuário não especifica, **usar sempre venda líquida (`valor_pago_produto`)**.

---

## 6. Datas — qual coluna usar

| Situação | Coluna recomendada |
|---|---|
| Análise de captura/status (default) | `data_evento` |
| Venda realizada (faturamento) físico | `data_faturamento` |
| Pagamento ecommerce | `data_pagamento` |
| Original de uma devolução | `data_venda_original` |

`data_evento` é a escolha segura para quase toda análise — é o timestamp do registro da linha.

---

## 7. KPIs — fórmulas canônicas

| KPI | Fórmula | Benchmark moda premium |
|---|---|---|
| Ticket Médio | `SUM(valor_pago_produto) / COUNT(DISTINCT chave_pedido)` | varia por posicionamento |
| PA (Peças/Atendimento) | `SUM(quantidade) / COUNT(DISTINCT chave_pedido)` | 1,8–2,5 |
| Taxa de Desconto | `(SUM(valor_produto) - SUM(valor_pago_produto)) / SUM(valor_produto)` | 15–25% saudável |
| Markup | `SUM(valor_pago_produto) / SUM(cmv_liquido)` | 2,5–4,0x |
| Margem Bruta | `(SUM(valor_pago_produto) - SUM(cmv_liquido)) / SUM(valor_pago_produto)` | 55–70% |

**Sempre que usar markup ou margem:** aplicar correção de CMV (§4).
**Sempre que usar PA ou ticket:** usar `chave_pedido` tratada (§3), não `chave_atendimento` puro.

---

## 8. Hierarquia de rede (marca/loja)

| Coluna | Uso |
|---|---|
| `rede_lojas_mais_vendas` | **Marca principal do atendimento** — usar para análise por marca |
| `rede_lojas_produto` | Marca do produto (pode diferir em cross-sell) |
| `rede_lojas_evento` | Marca no momento do evento |
| `rede_lojas_faturamento` | Marca no faturamento |

Para análises por marca, default é `rede_lojas_mais_vendas` (INTEGER).

**Mapeamento:**

| Código | Marca |
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

---

## 9. Template de análise (hierarquia analítica)

Toda análise deve seguir a ordem:

```
1. Contexto   — o que estamos medindo e por quê
2. Volume     — quanto vendeu (unidades, receita)
3. Eficiência — como vendeu (ticket, PA, desconto)
4. Rentab.    — valeu a pena (margem, markup)
5. Diagnóstico— por que (vs período, vs marca, vs loja)
6. Recomendação— o que fazer
```

Não pular direto pra KPI complexo sem ancorar volume primeiro.

---

## 10. Tipos de análise catalogados

Análises recorrentes e seus padrões de execução:

### 10.1 Produto × Marca × Canal
- **Dimensões:** `produto`, `rede_lojas_mais_vendas`, canal (§2)
- **Métricas:** top N por receita, peças, ticket médio, desconto
- **Período típico:** 7 dias (semanal) ou 30 dias
- **Ver exemplo:** `analyses/*/farm-produto-ecomm-*.html`

### 10.2 Canal × Marca (comparativo)
- **Dimensões:** canal (§2), `rede_lojas_mais_vendas`
- **Métricas:** venda líquida, peças, PA, markup (com `cmv_liquido`)
- **Uso de chave:** `chave_pedido` (§3) para PA
- **Período típico:** YTD, YoY
- **Ver exemplo:** `analyses/*/canal-marcas-ytd-*.html`

### 10.3 Loja × Marca (ranking)
- **Dimensões:** `codigo_filial_mais_vendas`, `rede_lojas_mais_vendas`
- **Métricas:** receita, ticket, PA, sell-through
- **Atenção:** filtrar `tipo_venda = 'FISICO'` normalmente

### 10.4 Tendência (YoY / período a período)
- **Padrão:** comparar períodos equivalentes, nunca absolutos.
- **Para moda:** preferir YoY sobre MoM.
- **Isolar:** datas promocionais (Black Friday, Dia das Mães, Natal) quando relevante.

### 10.5 Desconto & margem
- **Metric:** taxa de desconto, markup, margem bruta.
- **Obrigatório:** aplicar `cmv_liquido` (§4).

---

## 11. Princípio anti-hallucination

**Nunca inventar um número.** Todo valor em resposta deve vir de:
1. Query executada nesta sessão (✅ Dado real)
2. Valor explicitamente dado pelo usuário
3. Benchmark de mercado com fonte (📊 Benchmark)

Se não tem: dizer *"não tenho esse dado disponível"*. Não extrapolar.

Labels obrigatórios em qualquer número citado:

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
| 2026-04-18 | Criação. Incorpora: mapeamento de canal, chave de pedido via pacote, correção de CMV, KPIs canônicos, tipos de análise catalogados. |
