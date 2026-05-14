# Schema Reference — Ciclo de Venda Atacado (atacado_processed)

> Documento canônico de schema para o domínio Atacado da BU Fashion & Lifestyle do Grupo Azzas 2154.
> Atualizar após cada sessão em que novas colunas ou comportamentos forem descobertos.

**Dataset principal:** `soma-dl-refined-online.atacado_processed`
**Projeto de dados (billing):** via env var `MCP_BQ_BILLING_PROJECT_ID`

**Convenção SQL obrigatória:** todos os nomes de colunas e tabelas devem ser referenciados entre crases.
Exemplo: `` SELECT `COLECAO`, `CLIENTE` FROM `soma-dl-refined-online.atacado_processed.info_venda` ``

---

## 0. Arquitetura de dados

`info_venda` é a tabela central do modelo. Tabelas transacionais derivadas (`info_cancelamento`, `info_embalado`, `info_fat_nf`) fazem JOIN nela para obter `TIPO_VENDA`. Dimensões (`dim_clientes_v2`, `info_produto_v2`) enriquecem a análise.

```
                   ┌───────────────┐
                   │  info_produto_v2 │
                   │  PRODUTO +    │
                   │  COR_PRODUTO  │
                   └──────┬────────┘
                          │ RIGHT join
┌──────────────────────┐  ┌────▼──────────────┐  ┌─────────────────────┐
│ info_cancelamento    │  │                   │  │   dim_clientes_v2   │
│ info_devolucao_v2    ├─►│    info_venda     │◄─┤   CLIFOR + MARCA    │
│ PEDIDO+PRODUTO+      │  │   [FACT CORE]     │  │                     │
│ COR_PRODUTO          │  └────┬──────────────┘  │ NOME_WISE ──────────┼──► info_metas
└──────────────────────┘       │ RIGHT join       └─────────────────────┘
                               │ PEDIDO+PRODUTO
┌─────────────────┐            │ +COR_PRODUTO
│  info_embalado  │◄───────────┤
│  PEDIDO+PRODUTO │       ┌────▼──────────────┐
│  +COR_PRODUTO   │       │   info_fat_nf     │
└─────────────────┘       │   PEDIDO+PRODUTO  │
                          │   +COR_PRODUTO    │
                          └───────────────────┘
```

### Chaves de join

| De | Para | Chave | Observação |
|---|---|---|---|
| `info_venda` | `dim_clientes_v2` | `CLIFOR + MARCA` | Sempre ambas as colunas — nunca só CLIFOR |
| `info_venda` | `info_produto_v2` | `PRODUTO + COR_PRODUTO` | Nunca usar `COLECAO` como critério |
| `info_venda` | `info_metas` | `NOME_WISE + MARCA + COLECAO` | Via `dim_clientes_v2.NOME_WISE` |
| `info_cancelamento` | `info_venda` | `PEDIDO + PRODUTO + COR_PRODUTO` | JOIN obrigatório para filtrar `TIPO_VENDA` |
| `info_embalado` | `info_venda` | `PEDIDO + PRODUTO + COR_PRODUTO` | JOIN obrigatório para filtrar `TIPO_VENDA` |
| `info_fat_nf` | `info_venda` | `PEDIDO + PRODUTO + COR_PRODUTO` | Inclui `REDISTRIBUIÇÃO`; usar `VENDA_ORIGINAL >= 0` |
| `info_devolucao_v2` | `info_venda` | `PEDIDO + PRODUTO + COR_PRODUTO` | JOIN obrigatório para filtrar `TIPO_VENDA`; analisada por `DATA_RECEBIMENTO` |

> `TIPO_VENDA` só existe em `info_venda` — tabelas derivadas sempre fazem JOIN para filtrá-lo (ver business-rules §2).

### Sub-sistemas complementares

Além do ciclo de venda principal, o dataset contém quatro sub-sistemas independentes:

**Financeiro** — `info_financeira` conecta-se a `dim_clientes_v2` via `CLIFOR + MARCA`. Snapshot atual do status financeiro do cliente; não filtrar por coleção.

```
┌──────────────────┐          ┌─────────────────────┐
│  info_financeira │──CLIFOR──►   dim_clientes_v2   │
│  CLIFOR + MARCA  │  +MARCA  │   (dimensão core)   │
└──────────────────┘          └─────────────────────┘
```

**Somaplace** — `cadastro_somaplace_v2` e `venda_somaplace_v2` são ligadas por `CLIFOR + MARCA`. Sub-sistema independente do ciclo de venda; GMV calculado sobre `venda_somaplace_v2`. Comissão por cliente disponível em `cadastro_somaplace_v2.COMISSAO`.

```
┌──────────────────────────┐  CLIFOR  ┌─────────────────────┐
│  cadastro_somaplace_v2   │──+MARCA──►   venda_somaplace_v2   │
│  CLIFOR + MARCA          │          │   (transações GMV)  │
│  COMISSAO (% do grupo)   │          │                     │
└──────────────────────────┘          └─────────────────────┘
```

**Afiliados** — `afiliados_venda_v2` é a tabela central, com JOINs opcionais para `afiliados_multimarca` (CLIFOR × MARCA) e `afiliados_vendedores` (CODIGO_VENDEDOR). `afiliados_multimarca` faz INNER JOIN com `afiliados_vendedores` via `CLIFOR`.

```
┌───────────────────────────────────────────────────────────────────┐
│                         afiliados_venda_v2                        │
│  DATA, PEDIDO, MARCA, CLIFOR, CODIGO_VENDEDOR, PRODUTO, CIDADE    │
└──────────┬────────────────────────────────────────┬───────────────┘
           │ LEFT JOIN CLIFOR+MARCA                  │ LEFT JOIN CODIGO_VENDEDOR
           ▼                                        ▼
┌──────────────────────┐         ┌────────────────────────────────┐
│ afiliados_multimarca │──CLIFOR──► afiliados_vendedores           │
│ CLIFOR + MARCA       │  INNER  │  (⚠️ PII: cpf_vendedor, nome)  │
└──────────────────────┘         └────────────────────────────────┘
```

| De | Para | Chave | Sub-sistema |
|---|---|---|---|
| `info_financeira` | `dim_clientes_v2` | `CLIFOR + MARCA` | Financeiro |
| `cadastro_somaplace_v2` | `venda_somaplace_v2` | `CLIFOR + MARCA` | Somaplace |
| `afiliados_venda_v2` | `afiliados_multimarca` | `CLIFOR + MARCA` | Afiliados |
| `afiliados_venda_v2` | `afiliados_vendedores` | `CODIGO_VENDEDOR` | Afiliados |
| `afiliados_multimarca` | `afiliados_vendedores` | `CLIFOR` (INNER) | Afiliados |
| `info_ecommerce` | `info_produto_v2` | `PRODUTO + COR_PRODUTO` | E-commerce (somente sob demanda explícita) |

---

## 1. Venda — `info_venda`

**Full path:** `soma-dl-refined-online.atacado_processed.info_venda`
**Grão:** 1 linha por produto × cor × pedido (item de pedido de venda atacado).

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `COLECAO` | STRING | Coleção à qual o pedido pertence (ex: VERAO 2026) | ✅ SEGURO |
| `CLIENTE` | STRING | Nome do cliente (entidade jurídica — multimarca) | ✅ SEGURO |
| `CLIFOR` | STRING | Código único do cliente no sistema interno | ✅ SEGURO |
| `PRODUTO` | STRING | Código do produto comprado | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código da cor do produto comprado | ✅ SEGURO |
| `PEDIDO` | STRING | Número do pedido no sistema interno | ✅ SEGURO |
| `PEDIDO_WISE` | STRING | Número do pedido na plataforma Wise | ✅ SEGURO |
| `EMISSAO` | DATETIME | Data de emissão do pedido | ✅ SEGURO |
| `MARCA` | STRING | Marca do pedido | ✅ SEGURO |
| `VENDA` | NUMERIC | Valor líquido do item (com cancelamentos deduzidos) | ✅ SEGURO |
| `VENDA_ORIGINAL` | NUMERIC | Valor bruto — **campo padrão de "venda"** | ✅ SEGURO |
| `QTDE_TOTAL` | INTEGER | Quantidade total de peças compradas neste item | ✅ SEGURO |
| `T1`…`T8` | INTEGER | Quantidade por tamanho (T1 = 1º tamanho da grade, …) | ✅ SEGURO |
| `CONDICAO_PAGAMENTO` | STRING | Prazo de pagamento negociado (ex: 30/45/60/90) | ✅ SEGURO |
| `TABELA_MKP` | STRING | Tabela de markup aplicada (ex: "VENDA ATACADO 2.35") | ✅ SEGURO |
| `TIPO_VENDA` | STRING | Modalidade da venda. Valores: VENDA, PRE VENDA, PRATELEIRA INFINITA, PRATELEIRA INFINITA - EXTERNA, PRONTA ENTREGA, REDISTRIBUIÇÃO | ✅ SEGURO |

**Filtros padrão obrigatórios:**
```sql
WHERE `TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND `VENDA_ORIGINAL` > 0
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `parte_de` | ItemVenda | Pedido | N:1 | Vários itens compõem um pedido |
| `realizado_por` | Pedido | Cliente | N:1 | Um pedido é feito por um cliente |
| `referencia` | ItemVenda | Produto | N:1 | Cada item referencia um produto |
| `pertence_a` | Pedido | Colecao | N:1 | Um pedido pertence a uma coleção |
| `classificado_como` | ItemVenda | TipoVenda | N:1 | Cada item possui uma modalidade de venda |
| `regido_por` | Pedido | CondicaoComercial | N:1 | Cada pedido tem suas condições comerciais |
| `vinculado_a` | Pedido | Marca | N:1 | Um pedido pertence a uma marca |

---

## 2. Cancelamento — `info_cancelamento`

**Full path:** `soma-dl-refined-online.atacado_processed.info_cancelamento`
**Grão:** 1 linha por produto × cor × pedido cancelado.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `MARCA` | STRING | Marca do pedido cancelado | ✅ SEGURO |
| `CLIENTE_ATACADO` | STRING | Nome do cliente cujo pedido foi cancelado | ✅ SEGURO |
| `CLIFOR` | STRING | Código do cliente | ✅ SEGURO |
| `COLECAO` | STRING | Coleção do pedido cancelado | ✅ SEGURO |
| `PEDIDO` | STRING | Código do pedido | ✅ SEGURO |
| `EMISSAO` | DATETIME | Data de emissão do cancelamento | ✅ SEGURO |
| `PRODUTO` | STRING | Código do produto cancelado | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código da cor cancelada | ✅ SEGURO |
| `TIPO_CANCELAMENTO` | STRING | Motivo (ex: "05-BLOQUEIO FINANCEIRO") | ✅ SEGURO |
| `VALOR` | NUMERIC | Valor monetário cancelado | ✅ SEGURO |
| `QTDE` | INTEGER | Quantidade total cancelada | ✅ SEGURO |
| `T1`…`T8` | INTEGER | Quantidade cancelada por tamanho | ✅ SEGURO |

**Join obrigatório para filtro de TIPO_VENDA:**
```sql
JOIN `soma-dl-refined-online.atacado_processed.info_venda` v
  ON c.`PEDIDO` = v.`PEDIDO`
 AND c.`PRODUTO` = v.`PRODUTO`
 AND c.`COR_PRODUTO` = v.`COR_PRODUTO`
WHERE v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `cancela` | ItemCancelamento | ItemVenda | N:1 | Um cancelamento anula um item de venda |
| `parte_de` | ItemCancelamento | Pedido | N:1 | Vários itens cancelados compõem o cancelamento de um pedido |
| `pertence_a` | Pedido | Cliente | N:1 | O pedido cancelado pertence a um cliente |
| `referencia` | ItemCancelamento | Produto | N:1 | Cada item cancelado referencia um produto |
| `classificado_por` | ItemCancelamento | MotivoCancelamento | N:1 | Cada item tem um motivo de cancelamento |
| `vinculado_a` | Pedido | Colecao | N:1 | O pedido pertence a uma coleção e marca |

---

## 3. Devolução — `info_devolucao_v2`

**Full path:** `soma-dl-refined-online.atacado_processed.info_devolucao_v2`
**Grão:** 1 linha por PEDIDO × PRODUTO × COR_PRODUTO.
**Análise por data** — usar `DATA_RECEBIMENTO` (DATETIME, usar `DATE()` para agrupar por dia). `COLECAO` disponível para análise de mix por coleção.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `DATA_RECEBIMENTO` | DATETIME | Data e hora do recebimento físico da devolução no CD. Usar `DATE(DATA_RECEBIMENTO)` para agrupar por dia | ✅ SEGURO |
| `MARCA` | STRING | Marca dos produtos devolvidos — sempre em MAIÚSCULA | ✅ SEGURO |
| `CLIFOR` | STRING | Código do cliente que realizou a devolução | ✅ SEGURO |
| `CLIENTE` | STRING | Nome do cliente que realizou a devolução | ✅ SEGURO |
| `PEDIDO` | STRING | Código do pedido original — chave de join com `info_venda` (PEDIDO + PRODUTO + COR_PRODUTO) | ✅ SEGURO |
| `COLECAO` | STRING | Coleção do pedido devolvido (ex: VERAO 2026) — útil para análise de volume por coleção | ✅ SEGURO |
| `NF_ENTRADA` | STRING | Número da nota fiscal de entrada da devolução | ✅ SEGURO |
| `SERIE_NF_ENTRADA` | STRING | Série da nota fiscal de devolução | ✅ SEGURO |
| `PRODUTO` | STRING | Código do produto devolvido — com `PEDIDO` e `COR_PRODUTO` forma chave de join com `info_venda`; com `COR_PRODUTO` forma chave de join com `info_produto_v2` | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código de cor do produto devolvido — junto com `PRODUTO` forma chave composta para join em `info_venda` e `info_produto_v2` | ✅ SEGURO |
| `VALOR_NF` | FLOAT | Valor total do item na nota fiscal de devolução em R$ | ✅ SEGURO |
| `QTDE` | INTEGER | Quantidade total de peças devolvidas neste item — deve igualar a soma de `T1` a `T8` | ✅ SEGURO |
| `T1` | INTEGER | Quantidade devolvida no tamanho 1 (menor da grade) | ✅ SEGURO |
| `T2` | INTEGER | Quantidade devolvida no tamanho 2 | ✅ SEGURO |
| `T3` | INTEGER | Quantidade devolvida no tamanho 3 | ✅ SEGURO |
| `T4` | INTEGER | Quantidade devolvida no tamanho 4 | ✅ SEGURO |
| `T5` | INTEGER | Quantidade devolvida no tamanho 5 | ✅ SEGURO |
| `T6` | INTEGER | Quantidade devolvida no tamanho 6 | ✅ SEGURO |
| `T7` | INTEGER | Quantidade devolvida no tamanho 7 | ✅ SEGURO |
| `T8` | INTEGER | Quantidade devolvida no tamanho 8 (maior da grade) | ✅ SEGURO |

**Join obrigatório com info_venda para filtrar TIPO_VENDA:**
```sql
JOIN `soma-dl-refined-online.atacado_processed.info_venda` v
  ON d.`PEDIDO`      = v.`PEDIDO`
 AND d.`PRODUTO`     = v.`PRODUTO`
 AND d.`COR_PRODUTO` = v.`COR_PRODUTO`
WHERE v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `emitida_por` | ItemDevolucao | Cliente | N:1 | Cada item devolvido pertence a um cliente |
| `refere_a` | ItemDevolucao | Marca | N:1 | Cada devolução refere-se a uma marca |
| `registrada_em` | ItemDevolucao | EventoRecebimento | N:1 | Itens da mesma NF compartilham data de recebimento no CD |
| `reverte` | ItemDevolucao | ItemPedido | N:1 | Cada item devolvido reverte um item de pedido original |
| `classifica` | ItemDevolucao | Produto | N:1 | Cada item identifica um PRODUTO × COR_PRODUTO devolvido |

---

## 4. Embalado — `info_embalado`

**Full path:** `soma-dl-refined-online.atacado_processed.info_embalado`
**Grão:** 1 linha por produto × cor × caixa × pedido.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `MARCA` | STRING | Marca do pedido | ✅ SEGURO |
| `CLIENTE` | STRING | Nome do cliente destinatário | ✅ SEGURO |
| `CLIFOR` | STRING | Código do cliente destinatário | ✅ SEGURO |
| `PEDIDO` | STRING | Código do pedido ao qual a caixa pertence | ✅ SEGURO |
| `COLECAO` | STRING | Coleção do pedido | ✅ SEGURO |
| `PRODUTO` | STRING | Código do produto embalado | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código da cor do produto embalado | ✅ SEGURO |
| `APROVACAO` | STRING | Tipo de aprovação da caixa no processo de expedição | ✅ SEGURO |
| `CAIXA` | STRING | Número da caixa física | ✅ SEGURO |
| `CAIXA_VIRTUAL` | STRING | Número da caixa virtual associada ao envio | ✅ SEGURO |
| `CX_QUEBRADA` | INTEGER | 1 = grade incompleta (um ou mais tamanhos ausentes) | ✅ SEGURO |
| `STATUS_CAIXA` | STRING | Status atual da caixa (ver agrupamento em business-rules §12) | ✅ SEGURO |
| `QTDE` | INTEGER | Quantidade do produto nesta caixa | ✅ SEGURO |
| `T1`…`T8` | INTEGER | Quantidade por tamanho nesta caixa | ✅ SEGURO |
| `VALOR_LIQUIDO` | NUMERIC | Valor total do produto nesta caixa | ✅ SEGURO |
| `DIA LIBERAÇÃO` | STRING | Dia da semana previsto para liberação da caixa | ✅ SEGURO |

**Join obrigatório para filtro de TIPO_VENDA:**
```sql
JOIN `soma-dl-refined-online.atacado_processed.info_venda` v
  ON e.`PEDIDO` = v.`PEDIDO`
 AND e.`PRODUTO` = v.`PRODUTO`
 AND e.`COR_PRODUTO` = v.`COR_PRODUTO`
WHERE v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `parte_de` | ItemEmbalado | Caixa | N:1 | Vários itens compõem uma caixa |
| `destinada_a` | Caixa | Cliente | N:1 | Uma caixa é destinada a um cliente |
| `originado_de` | ItemEmbalado | Pedido | N:1 | Um item embalado vem de um pedido |
| `contem` | Caixa | Produto | N:N | Uma caixa contém um ou mais produtos |
| `possui_status` | Caixa | StatusCaixa | 1:1 | Cada caixa tem um status |
| `precede` | ItemEmbalado | Faturamento | 1:1 | Embalado precede o faturamento ao cliente |

---

## 5. Faturamento — `info_fat_nf`

**Full path:** `soma-dl-refined-online.atacado_processed.info_fat_nf`
**Grão:** 1 linha por produto × cor × nota fiscal de saída.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `MARCA` | STRING | Marca do pedido faturado | ✅ SEGURO |
| `COLECAO` | STRING | Coleção à qual o pedido pertence | ✅ SEGURO |
| `CLIENTE` | STRING | Nome do cliente que recebeu o faturamento | ✅ SEGURO |
| `PEDIDO` | STRING | Código do pedido faturado | ✅ SEGURO |
| `NF_SAIDA` | STRING | Número da nota fiscal de saída | ✅ SEGURO |
| `SERIE_NF` | STRING | Série da nota fiscal de saída | ✅ SEGURO |
| `PRODUTO` | STRING | Código do produto faturado | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código da cor do produto faturado | ✅ SEGURO |
| `QTDE_FATURADA` | INTEGER | Quantidade total de peças faturadas | ✅ SEGURO |
| `T1_FAT`…`T8_FAT` | INTEGER | Quantidade faturada por tamanho | ✅ SEGURO |
| `VALOR_FATURADO` | NUMERIC | Valor do produto faturado neste evento | ✅ SEGURO |
| `DATA_FATURAMENTO` | DATETIME | Data de emissão do faturamento | ✅ SEGURO |

**Join obrigatório para filtro de TIPO_VENDA (inclui REDISTRIBUIÇÃO no faturamento):**
```sql
JOIN `soma-dl-refined-online.atacado_processed.info_venda` v
  ON f.`PEDIDO` = v.`PEDIDO`
 AND f.`PRODUTO` = v.`PRODUTO`
 AND f.`COR_PRODUTO` = v.`COR_PRODUTO`
WHERE v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA', 'REDISTRIBUIÇÃO')
  AND v.`VENDA_ORIGINAL` >= 0
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `origina_de` | ItemFaturamento | Pedido | N:1 | Um item faturado origina-se de um pedido |
| `destinado_a` | ItemFaturamento | Cliente | N:1 | Cada faturamento é destinado a um cliente |
| `referencia` | ItemFaturamento | Produto | N:1 | Cada item faturado referencia um produto |
| `pertence_a` | Pedido | Colecao | N:1 | O pedido pertence a uma coleção |
| `constitui` | ItemFaturamento | EventoFaturamento | N:1 | Vários itens compõem um evento de faturamento |
| `sucede` | ItemFaturamento | ItemEmbalado | 1:1 | Faturamento sucede o embalado |
| `constitui` | ItemFaturamento | NotaFiscal | N:1 | Vários itens compõem uma Nota Fiscal |

---

## 6. Metas — `info_metas`

**Full path:** `soma-dl-refined-online.atacado_processed.info_metas`
**Grão:** 1 linha por representante × marca × coleção.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `MARCA` | STRING | Marca à qual a meta se refere | ✅ SEGURO |
| `REPRESENTANTE` | STRING | Nome original do representante no sistema | ✅ SEGURO |
| `NOME_WISE` | STRING | Nome padronizado do representante | ✅ SEGURO |
| `COLECAO` | STRING | Coleção para a qual a meta foi definida | ✅ SEGURO |
| `META` | NUMERIC | Meta financeira principal (campo padrão) | ✅ SEGURO |
| `META DESAFIO` | NUMERIC | Meta financeira estendida — usar só sob pedido explícito | ✅ SEGURO |
| `META ATENDIMENTO` | NUMERIC | Meta de clientes com compra — usar só sob pedido explícito | ✅ SEGURO |
| `ANO` | INTEGER | Ano da coleção | ✅ SEGURO |

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `atribuida_a` | MetaRepresentante | Representante | N:1 | Cada meta pertence a um representante |
| `definida_para` | MetaRepresentante | Colecao | N:1 | Cada meta é por coleção |
| `associada_a` | MetaRepresentante | Marca | N:1 | Cada meta é por marca |
| `comparada_com` | MetaRepresentante | Venda | 1:1 | Meta é comparada à soma de vendas do representante |

---

## 7. Clientes — `dim_clientes_v2`

**Full path:** `soma-dl-refined-online.atacado_processed.dim_clientes_v2`
**Grão:** 1 linha por CLIFOR × marca.
**Chave de join:** sempre `CLIFOR` + `MARCA` em conjunto.

### Colunas ✅ SEGURAS para SELECT agregado

| Coluna | Tipo | Descrição |
|---|---|---|
| `MARCA` | STRING | Marca à qual o cadastro está vinculado |
| `CLIENTE` | STRING | Nome fantasia da loja multimarca (entidade jurídica) |
| `CLIFOR` | STRING | Código único do cliente no sistema interno |
| `REPRESENTANTE` | STRING | Nome original do representante no sistema |
| `NOME_WISE` | STRING | Nome padronizado do representante |
| `COORDENADOR` | STRING | Nome do coordenador responsável pelo cliente |
| `RAZAO_SOCIAL` | STRING | Razão social jurídica (tratar com cautela: pode ser MEI) |
| `CNPJ` | STRING | CNPJ da loja — não incluir em SELECT sem agrupamento |
| `CEP` | STRING | CEP — usar só agregado, nunca por linha individual |
| `CIDADE` | STRING | Cidade do endereço (pode ter erros de acentuação — normalizar antes de filtrar) |
| `ESTADO` | STRING | UF brasileira |
| `PAIS` | STRING | País do endereço |
| `BAIRRO` | STRING | Bairro — usar só agregado |
| `GRUPO_ECONOMICO` | STRING | Agrupamento de lojas do mesmo proprietário |
| `ID_EXTERNO` | STRING | Concatenação de CLIFOR + MARCA |
| `ACCOUNT_NAME` | STRING | Concatenação de CLIFOR + CLIENTE + MARCA |

### Colunas 🔴 PII — NUNCA incluir no SELECT

| Coluna | Motivo |
|---|---|
| `EMAIL` | E-mail de contato (pode identificar pessoa física) |
| `DDI` | Código internacional de discagem |
| `DDD1` | DDD do telefone principal |
| `TELEFONE1` | Telefone principal |
| `DDD2` | DDD do telefone secundário |
| `TELEFONE2` | Telefone secundário |
| `WPP` | WhatsApp do cliente |
| `ENDERECO` | Logradouro completo |
| `NUMERO` | Número do endereço |
| `COMPLEMENTO` | Complemento do endereço |

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `instancia_de` | CadastroMarca | Cliente | N:1 | Vários cadastros pertencem ao mesmo cliente |
| `vinculado_a` | CadastroMarca | Marca | N:1 | Cada cadastro está associado a exatamente uma marca |
| `agrupa` | GrupoEconomico | CadastroMarca | 1:N | Um grupo econômico reúne vários cadastros |
| `atendido_por` | CadastroMarca | Representante | N:1 | Cada cadastro tem um representante por marca |
| `gerenciado_por` | Representante | Coordenador | N:1 | Um representante é gerenciado por um coordenador |
| `localizado_em` | CadastroMarca | Endereco | 1:1 | Cada cadastro possui um endereço |
| `contactado_via` | CadastroMarca | Contato | 1:1 | Cada cadastro possui meios de contato (🔴 PII) |
| `identificado_por` | CadastroMarca | CNPJ | N:1 | Vários cadastros podem compartilhar o mesmo CNPJ |

---

## 8. Produto — `info_produto_v2`

**Full path:** `soma-dl-refined-online.atacado_processed.info_produto_v2`
**Chave composta:** `PRODUTO` + `COR_PRODUTO`
**Uso principal:** enriquecer análises com descrição, segmento e hierarquia; identificar submarcas FARM FUTURA e BENTO dentro de FABULA.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `PRODUTO` | STRING | Código do produto (PK parcial) | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código da cor (PK parcial) | ✅ SEGURO |
| `DESC_PRODUTO` | STRING | Descrição textual do produto | ✅ SEGURO |
| `DESC_COR_PRODUTO` | STRING | Descrição textual da cor | ✅ SEGURO |
| `PRECO` | NUMERIC | Preço do produto | ✅ SEGURO |
| `GRADE` | STRING | Tamanhos praticados (ex: PP-P-M-G-GG) | ✅ SEGURO |
| `COLECAO` | STRING | Coleção à qual o produto pertence | ✅ SEGURO |
| `MARCA` | STRING | Marca comercial do produto | ✅ SEGURO |
| `SEGMENTO` | STRING | Define submarca em Fábula: MENINA TEEN = FARM FUTURA; MENINO / BEBE MENINO = BENTO; demais = Fábula pura. Filtros SQL: ver business-rules §4. | ✅ SEGURO |
| `LINHA` | STRING | Agrupamento por tipo de fabricação (ex: Malha, Denim) | ✅ SEGURO |
| `LINHA_MIX` | STRING | Visão mais macro da linha | ✅ SEGURO |
| `GRUPO_PRODUTO` | STRING | Classificação macro do produto | ✅ SEGURO |
| `SUBGRUPO_PRODUTO` | STRING | Classificação micro do produto | ✅ SEGURO |
| `SOLUCAO` | STRING | Composição do produto | ✅ SEGURO |
| `TIPO_PRODUTO` | STRING | Descrição acerca da fabricação | ✅ SEGURO |

> ⚠️ O JOIN com `info_produto_v2` **nunca** deve usar `COLECAO` como critério — usar apenas `PRODUTO` + `COR_PRODUTO`.

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `variante_de` | ProdutoCor | Produto | N:1 | Uma cor é uma variante de um produto base |
| `pertence_a` | ProdutoCor | Colecao | N:1 | Um produto pertence a uma coleção |
| `fabricado_por` | ProdutoCor | Marca | N:1 | Um produto pertence a uma marca |
| `classificado_em` | ProdutoCor | Segmento | N:1 | Cada produto tem um segmento de público |
| `organizado_em` | ProdutoCor | Hierarquia | 1:1 | Produto possui linha, grupo e subgrupo |
| `disponivel_em` | ProdutoCor | GradeTamanho | 1:1 | Produto possui grade de tamanhos |

---

## 9. Colunas PII consolidadas

| Tabela | Colunas 🔴 PII |
|---|---|
| `dim_clientes_v2` | `EMAIL`, `DDI`, `DDD1`, `TELEFONE1`, `DDD2`, `TELEFONE2`, `WPP`, `ENDERECO`, `NUMERO`, `COMPLEMENTO` |
| `afiliados_vendedores` | `cpf_vendedor`, `nome_vendedor` |

---

## 10. Joins canônicos

```sql
-- Venda enriquecida com cliente e produto (padrão)
SELECT
  v.`MARCA`, v.`COLECAO`, v.`CLIFOR`,
  c.`CLIENTE`, c.`NOME_WISE`, c.`ESTADO`,
  p.`DESC_PRODUTO`, p.`DESC_COR_PRODUTO`, p.`SEGMENTO`,
  SUM(v.`VENDA_ORIGINAL`) AS venda,
  SUM(v.`QTDE_TOTAL`)     AS pecas
FROM `soma-dl-refined-online.atacado_processed.info_venda` v
LEFT JOIN `soma-dl-refined-online.atacado_processed.dim_clientes_v2` c
  ON v.`CLIFOR` = c.`CLIFOR` AND v.`MARCA` = c.`MARCA`
LEFT JOIN `soma-dl-refined-online.atacado_processed.info_produto_v2` p
  ON v.`PRODUTO` = p.`PRODUTO` AND v.`COR_PRODUTO` = p.`COR_PRODUTO`
WHERE v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9
```

```sql
-- Atingimento de meta por representante
SELECT
  v.`MARCA`, v.`COLECAO`, c.`NOME_WISE`,
  SUM(v.`VENDA_ORIGINAL`)                              AS venda,
  MAX(m.`META`)                                        AS meta,
  SAFE_DIVIDE(SUM(v.`VENDA_ORIGINAL`), MAX(m.`META`)) AS atingimento
FROM `soma-dl-refined-online.atacado_processed.info_venda` v
LEFT JOIN `soma-dl-refined-online.atacado_processed.dim_clientes_v2` c
  ON v.`CLIFOR` = c.`CLIFOR` AND v.`MARCA` = c.`MARCA`
LEFT JOIN `soma-dl-refined-online.atacado_processed.info_metas` m
  ON c.`NOME_WISE` = m.`NOME_WISE`
 AND v.`MARCA`    = m.`MARCA`
 AND v.`COLECAO`  = m.`COLECAO`
WHERE v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
GROUP BY 1, 2, 3
```

---

## 11. Financeiro — `info_financeira`

**Full path:** `soma-dl-refined-online.atacado_processed.info_financeira`
**Grão:** 1 linha por CLIFOR × marca (snapshot financeiro atual do cliente).
**Análise:** snapshot — não filtrar por coleção; usar `DATA_ATUALIZACAO` como referência temporal.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `MARCA` | STRING | Marca à qual o status financeiro se refere | ✅ SEGURO |
| `CLIENTE` | STRING | Nome do cliente (entidade jurídica) | ✅ SEGURO |
| `CLIFOR` | STRING | Código único do cliente no sistema interno | ✅ SEGURO |
| `GRUPO_ECONOMICO` | STRING | Agrupamento de lojas do mesmo proprietário | ✅ SEGURO |
| `VALOR_VENCIDO` | NUMERIC | Saldo de títulos já vencidos e não pagos | ✅ SEGURO |
| `VALOR_A_VENCER` | NUMERIC | Saldo de títulos a vencer (dentro do prazo) | ✅ SEGURO |
| `SITUACAO` | STRING | Status financeiro: `'BLOQUEADO'` ou `'LIBERADO'` | ✅ SEGURO |
| `TIPO_BLOQUEIO` | STRING | Motivo do bloqueio. Lista exaustiva de valores: ver `business-rules §19` | ✅ SEGURO |
| `DATA_BLOQ` | DATETIME | Data em que o bloqueio foi aplicado | ✅ SEGURO |
| `DATA_ATUALIZACAO` | DATETIME | Data da última atualização do snapshot | ✅ SEGURO |

**Join padrão com dim_clientes_v2:**
```sql
JOIN `soma-dl-refined-online.atacado_processed.dim_clientes_v2` c
  ON f.`CLIFOR` = c.`CLIFOR` AND f.`MARCA` = c.`MARCA`
```

**Queries de inadimplência e aging:**
```sql
-- Inadimplência por marca
SELECT `MARCA`, SUM(`VALOR_VENCIDO`) AS inadimplencia
FROM `soma-dl-refined-online.atacado_processed.info_financeira`
WHERE `SITUACAO` = 'BLOQUEADO'
GROUP BY 1

-- Aging (dias de bloqueio)
SELECT `CLIFOR`, `MARCA`,
  DATE_DIFF(CURRENT_DATE(), DATE(`DATA_BLOQ`), DAY) AS dias_bloqueado
FROM `soma-dl-refined-online.atacado_processed.info_financeira`
WHERE `SITUACAO` = 'BLOQUEADO'
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `descreve` | StatusFinanceiro | Cliente | N:1 | Cada registro descreve o status de um CLIFOR × marca |
| `integra` | StatusFinanceiro | GrupoEconomico | N:1 | Bloqueio propaga-se a todo o grupo econômico |
| `refere_a` | StatusFinanceiro | Marca | N:1 | Status é por marca |

---

## 12. Cadastro Somaplace V2 — `cadastro_somaplace_v2`

**Full path:** `soma-dl-refined-online.atacado_processed.cadastro_somaplace_v2`
**Grão:** 1 linha por CLIFOR × marca (registro de adesão da multimarca ao programa Somaplace).

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `MARCA` | STRING | Marca à qual a multimarca está cadastrada no Somaplace | ✅ SEGURO |
| `CLIENTE` | STRING | Nome da multimarca cadastrada | ✅ SEGURO |
| `CLIFOR` | STRING | Código do cliente no sistema interno — chave de join com `venda_somaplace_v2` | ✅ SEGURO |
| `CREATED_AT` | DATETIME | Data de cadastro da multimarca no programa Somaplace | ✅ SEGURO |
| `COMISSAO` | FLOAT | Percentual de comissão retida pelo grupo sobre o GMV Líquido, armazenado como inteiro (ex: `20` = 20%). Padrão = 20. Clientes com logística via Correios têm valor superior ao padrão — sempre usar esta coluna para calcular a divisão de receita, nunca valor fixo | ✅ SEGURO |

**Join com venda_somaplace_v2:**
```sql
JOIN `soma-dl-refined-online.atacado_processed.venda_somaplace_v2` vs
  ON cs.`CLIFOR` = vs.`CLIFOR` AND cs.`MARCA` = vs.`MARCA`
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `habilita` | CadastroSomaplace | Cliente | N:1 | Cada cadastro habilita um CLIFOR no programa |
| `associa_a` | CadastroSomaplace | Marca | N:1 | Cadastro por marca |
| `precede` | CadastroSomaplace | VendaSomaplace | 1:N | Multimarca cadastrada pode gerar vendas |

---

## 13. Venda Somaplace V2 — `venda_somaplace_v2`

**Full path:** `soma-dl-refined-online.atacado_processed.venda_somaplace_v2`
**Grão:** 1 linha por item de pedido Somaplace (PEDIDO × PRODUTO × COR_PRODUTO × TAMANHO_GRADE × STATUS).
**Análise por data:** usar `DATE(DATA)` para agrupar (campo é TIMESTAMP). Filtrar por `COLECAO` para análise de mix.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `DATA` | TIMESTAMP | Data e hora da transação no marketplace. Usar `DATE(DATA)` para agrupar por dia ou `FORMAT_DATE('%Y-%m', DATE(DATA))` para mês/ano | ✅ SEGURO |
| `PEDIDO` | STRING | Código único do pedido Somaplace — identifica a transação | ✅ SEGURO |
| `STATUS` | STRING | Status da transação: `'CAPTURADO'` (confirmada), `'CANCELADO'`, `'DEVOLVIDO'` | ✅ SEGURO |
| `CLIFOR` | STRING | Código da multimarca — chave de join com `cadastro_somaplace_v2` (CLIFOR + MARCA) | ✅ SEGURO |
| `MARCA` | STRING | Marca do produto vendido — sempre em MAIÚSCULA | ✅ SEGURO |
| `PRODUTO` | STRING | Código do produto — chave de join composta com `info_produto_v2` (PRODUTO + COR_PRODUTO) | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código de cor do produto — junto com `PRODUTO` forma chave composta para join em `info_produto_v2` | ✅ SEGURO |
| `TAMANHO_GRADE` | STRING | Tamanho do item vendido na grade (ex: `'P'`, `'M'`, `'G'`, `'36'`, `'38'`) | ✅ SEGURO |
| `COLECAO` | STRING | Coleção do produto vendido (ex: VERAO 2026) | ✅ SEGURO |
| `QUANTIDADE` | INTEGER | Quantidade de unidades deste item no pedido | ✅ SEGURO |
| `VALOR_PRODUTO` | FLOAT | Valor unitário do produto antes do desconto, em R$ | ✅ SEGURO |
| `VALOR_PRODUTO_TOTAL` | FLOAT | Valor total do item (`VALOR_PRODUTO × QUANTIDADE`) antes do desconto, em R$ | ✅ SEGURO |
| `DESCONTO` | FLOAT | Valor do desconto aplicado ao item, em R$ | ✅ SEGURO |
| `VALOR_PAGO` | FLOAT | Valor efetivamente pago pelo consumidor final (`VALOR_PRODUTO_TOTAL − DESCONTO`), em R$. Base para cálculo do GMV | ✅ SEGURO |
| `FRETE` | FLOAT | Valor do frete cobrado ao consumidor, em R$ | ✅ SEGURO |

**Filtros de status para GMV:**
```sql
-- GMV Bruto (padrão): apenas transações capturadas
WHERE `STATUS` = 'CAPTURADO'

-- GMV Líquido: sem filtro de STATUS (cancelados e devoluções entram negativos)
-- (nenhum WHERE de STATUS)
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `realizada_por` | ItemVendaSomaplace | Cliente | N:1 | Cada item pertence a uma multimarca |
| `referente_a` | ItemVendaSomaplace | Marca | N:1 | Cada item refere-se a uma marca |
| `classifica` | ItemVendaSomaplace | Produto | N:1 | Cada item identifica um PRODUTO × COR_PRODUTO × TAMANHO_GRADE |
| `categorizada_em` | ItemVendaSomaplace | Colecao | N:1 | Item pertence a uma coleção |
| `tem_status` | ItemVendaSomaplace | StatusTransacao | N:1 | Cada item possui um status de transação |

---

## 14. Afiliados Multimarca — `afiliados_multimarca`

**Full path:** `soma-dl-refined-online.atacado_processed.afiliados_multimarca`
**Grão:** 1 linha por CLIFOR × marca (registro de adesão da multimarca ao programa Afiliados).

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `CLIFOR` | STRING | Código da multimarca no sistema interno | ✅ SEGURO |
| `DATA_AFILIACAO` | DATE | Data de entrada da multimarca no programa | ✅ SEGURO |
| `MARCA` | STRING | Marca à qual a multimarca está afiliada | ✅ SEGURO |

**Join padrão com afiliados_vendedores (INNER):**
```sql
INNER JOIN `soma-dl-refined-online.atacado_processed.afiliados_vendedores` av
  ON am.`CLIFOR` = av.`clifor`
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `habilita` | AfiliadosMultimarca | Cliente | N:1 | Cada registro habilita um CLIFOR no programa |
| `associa_a` | AfiliadosMultimarca | Marca | N:1 | Adesão é por marca |
| `possui` | AfiliadosMultimarca | VendedorDigital | 1:N | Multimarca pode ter múltiplos vendedores |

---

## 15. Afiliados Venda V2 — `afiliados_venda_v2`

**Full path:** `soma-dl-refined-online.atacado_processed.afiliados_venda_v2`
**Grão:** 1 linha por item de pedido afiliado (PEDIDO × PRODUTO × COR_PRODUTO × STATUS_VENDA × TIPO_VENDA).
**Análise por data:** usar `DATE(DATA)` para agrupar (campo é TIMESTAMP).
**Tabela central do sub-sistema Afiliados** — JOINs opcionais com multimarca e vendedores.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `DATA` | TIMESTAMP | Data e hora da transação. Usar `DATE(DATA)` para agrupar por dia ou `FORMAT_DATE('%Y-%m', DATE(DATA))` para mês/ano | ✅ SEGURO |
| `PEDIDO` | STRING | Código único do pedido afiliado — identifica a transação | ✅ SEGURO |
| `STATUS_VENDA` | STRING | Status da transação: `'CAPTURADO'` (efetivado) ou `'CANCELADO'` | ✅ SEGURO |
| `TIPO_VENDA` | STRING | Tipo da transação: `'ONLINE'` (venda confirmada) ou `'DEVOLUÇÃO'` | ✅ SEGURO |
| `MARCA` | STRING | Marca do produto vendido (ex: `'FARM'`, `'ANIMALE'`) — sempre em MAIÚSCULA | ✅ SEGURO |
| `CLIFOR` | STRING | Código da multimarca parceira — chave de join com `afiliados_multimarca.CLIFOR` | ✅ SEGURO |
| `CODIGO_VENDEDOR` | STRING | Código da vendedora digital (inicia em `'7'`) — chave de join com `afiliados_vendedores.codigo_vendedor` | ✅ SEGURO |
| `PRODUTO` | STRING | Código do produto vendido — chave de join composta com `info_produto_v2` (PRODUTO + COR_PRODUTO) | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código de cor do produto — junto com `PRODUTO` forma chave composta para join em `info_produto_v2` | ✅ SEGURO |
| `CPF_CLIENTE` | STRING | CPF do cliente final que realizou a compra | 🔴 PII — nunca expor |
| `ESTADO` | STRING | Estado (UF) do endereço do cliente | ✅ SEGURO |
| `CIDADE` | STRING | Cidade do endereço do cliente — normalizar removendo acentos e ç ao comparar | ✅ SEGURO |
| `VENDA_LIQUIDA` | FLOAT | Valor líquido da transação afiliada em R$ | ✅ SEGURO |

**Classificação de status para análise:**
```sql
-- Venda confirmada
WHERE `STATUS_VENDA` = 'CAPTURADO' AND `TIPO_VENDA` = 'ONLINE'

-- Devolução
WHERE `STATUS_VENDA` = 'CAPTURADO' AND `TIPO_VENDA` = 'DEVOLUÇÃO'

-- Cancelado (pedidos com STATUS_VENDA = 'CANCELADO', independente do TIPO_VENDA)
WHERE `STATUS_VENDA` = 'CANCELADO'
```

**Join padrão com multimarca e vendedores:**
```sql
FROM `soma-dl-refined-online.atacado_processed.afiliados_venda_v2` av
LEFT JOIN `soma-dl-refined-online.atacado_processed.afiliados_multimarca` am
  ON av.`CLIFOR` = am.`CLIFOR` AND av.`MARCA` = am.`MARCA`
LEFT JOIN `soma-dl-refined-online.atacado_processed.afiliados_vendedores` avd
  ON av.`CODIGO_VENDEDOR` = avd.`codigo_vendedor`
```

> ⚠️ Nunca incluir `CPF_CLIENTE` no SELECT desta tabela, nem `cpf_vendedor` ou `nome_vendedor` de `afiliados_vendedores` — colunas PII.

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `gerada_por` | VendaAfiliado | VendedorDigital | N:1 | Cada venda vem de um vendedor |
| `pertence_a` | VendaAfiliado | Multimarca | N:1 | Cada venda pertence a uma multimarca |
| `referente_a` | VendaAfiliado | Marca | N:1 | Cada venda é de uma marca |

---

## 16. Afiliados Vendedores — `afiliados_vendedores`

**Full path:** `soma-dl-refined-online.atacado_processed.afiliados_vendedores`
**Grão:** 1 linha por vendedor digital (codigo_vendedor).
**⚠️ Contém PII:** `cpf_vendedor` e `nome_vendedor` — nunca incluir no SELECT.

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `cpf_vendedor` | STRING | CPF da vendedora digital | 🔴 PII — nunca expor |
| `codigo_vendedor` | STRING | Código identificador do vendedor (inicia em `'7'`) | ✅ SEGURO |
| `nome_vendedor` | STRING | Nome da vendedora digital | 🔴 PII — nunca expor |
| `clifor` | STRING | Código da multimarca que a recruta | ✅ SEGURO |
| `data_cadastro` | DATE | Data de entrada no programa | ✅ SEGURO |
| `data_troca_filial` | DATE | Data da última troca de multimarca vinculada | ✅ SEGURO |
| `data_desligamento` | DATE | Data de desligamento do programa (NULL = ativo) | ✅ SEGURO |

**Consultas seguras (sem PII):**
```sql
-- Contagem de vendedores ativos por multimarca
SELECT av.`clifor`, COUNT(DISTINCT av.`codigo_vendedor`) AS qtd_vendedores
FROM `soma-dl-refined-online.atacado_processed.afiliados_vendedores` av
WHERE av.`data_desligamento` IS NULL
GROUP BY 1

-- Verificar se vendedor está ativo (último JOIN)
LEFT JOIN `soma-dl-refined-online.atacado_processed.afiliados_vendedores` avd
  ON av.`codigo_vendedor` = avd.`codigo_vendedor`
-- Selecionar apenas: avd.`clifor`, avd.`data_cadastro`, avd.`data_desligamento`
-- NUNCA: avd.`cpf_vendedor`, avd.`nome_vendedor`
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `recrutada_por` | VendedorDigital | Multimarca | N:1 | Cada vendedor é recrutado por uma multimarca |
| `gera` | VendedorDigital | VendaAfiliado | 1:N | Um vendedor pode ter múltiplas vendas |
| `identificado_por` | VendedorDigital | CodigoVendedor | 1:1 | Código único iniciado em '7' |

---

## 17. E-commerce — `info_ecommerce`

> ❌ **Usar esta tabela somente quando o usuário escrever literalmente "ecommerce" ou "e-commerce" na solicitação. Nenhum sinônimo, inferência ou contexto substitui essa menção explícita. Não usar para análises de ciclo de venda, afiliados ou Somaplace por iniciativa própria.**

**Full path:** `soma-dl-refined-online.atacado_processed.info_ecommerce`
**Grão:** 1 linha por item de evento de e-commerce (MARCA × PRODUTO × COR_PRODUTO × TAMANHO × TIPO_VENDA × STATUS_EVENTO).
**Análise por data:** usar `DATE(DATA)` para agrupar (campo é TIMESTAMP).

| Coluna | Tipo | Descrição | PII |
|---|---|---|---|
| `DATA` | TIMESTAMP | Data e hora do evento de venda. Usar `DATE(DATA)` para agrupar por dia ou `FORMAT_DATE('%Y-%m', DATE(DATA))` para mês/ano | ✅ SEGURO |
| `CPF` | STRING | CPF do cliente final | 🔴 PII — nunca expor |
| `STATUS_EVENTO` | STRING | Status do evento: `'CAPTURADO'` (confirmado) ou `'CANCELADO'` | ✅ SEGURO |
| `TIPO_VENDA` | STRING | Canal: `'ONLINE'` (venda digital), `'FISICO'` (compra realizada em loja física — indica presença de ponto de venda na cidade do cliente), `'DEVOLUCAO'` (devolução) | ✅ SEGURO |
| `PROGRAMA_VENDEDOR` | STRING | Programa do vendedor associado: `'MULTIMARCA'` = afiliado atacado; outro valor = varejo; `NULL` = sem vendedor | ✅ SEGURO |
| `PRODUTO` | STRING | Código do produto — chave de join composta com `info_produto_v2` (PRODUTO + COR_PRODUTO) | ✅ SEGURO |
| `COR_PRODUTO` | STRING | Código de cor do produto — junto com `PRODUTO` forma chave composta para join em `info_produto_v2` | ✅ SEGURO |
| `TAMANHO` | STRING | Tamanho do item vendido (ex: `'P'`, `'M'`, `'G'`, `'36'`, `'38'`) | ✅ SEGURO |
| `VALOR_PAGO` | FLOAT | Valor efetivamente pago pelo cliente, em R$ | ✅ SEGURO |
| `ESTADO` | STRING | Estado (UF) do endereço do cliente | ✅ SEGURO |
| `CIDADE` | STRING | Cidade do endereço do cliente — normalizar removendo acentos e ç ao comparar | ✅ SEGURO |
| `MARCA` | STRING | Marca do produto vendido — sempre em MAIÚSCULA | ✅ SEGURO |

**Chave de transação única:** não há coluna PEDIDO nesta tabela. Transações únicas são identificadas pela combinação `PRODUTO + COR_PRODUTO + DATE(DATA) + CPF + STATUS_EVENTO + TIPO_VENDA`.

**COLECAO:** não disponível como coluna direta — obter via join com `info_produto_v2` usando `PRODUTO + COR_PRODUTO`.

> ⚠️ **Nomenclatura vs. `afiliados_venda_v2`:** o campo de status aqui é `STATUS_EVENTO` (não `STATUS_VENDA`). Devoluções são `TIPO_VENDA = 'DEVOLUCAO'` sem acento (diferente de `'DEVOLUÇÃO'` com acento em `afiliados_venda_v2`). Não reutilizar filtros entre as duas tabelas sem ajustar nome do campo e grafia.

**Classificação de PROGRAMA_VENDEDOR:**
```sql
CASE
  WHEN `PROGRAMA_VENDEDOR` = 'MULTIMARCA' THEN 'AFILIADO (ATACADO)'
  WHEN `PROGRAMA_VENDEDOR` IS NOT NULL    THEN 'VAREJO'
  ELSE 'SEM VENDEDOR'
END AS tipo_canal_vendedor
```

> Vendas com `PROGRAMA_VENDEDOR = 'MULTIMARCA'` também estão registradas em `afiliados_venda_v2`. Para qualquer análise do programa de afiliados, usar sempre `afiliados_venda_v2` — não `info_ecommerce`.

**Filtro de loja física:**
```sql
WHERE `TIPO_VENDA` = 'FISICO'
```

### Relacionamentos

| Relação | De | Para | Cardinalidade | Descrição |
|---|---|---|---|---|
| `classifica` | ItemEcommerce | Produto | N:1 | Cada item identifica um PRODUTO × COR_PRODUTO |
| `ocorre_em` | ItemEcommerce | Localidade | N:1 | Cada evento tem CIDADE e ESTADO do cliente |
| `pertence_a` | ItemEcommerce | Marca | N:1 | Cada item pertence a uma marca |

---

## Dataset: `soma_online_refined`

**Projeto:** `soma-dl-refined-online`
**Dataset:** `soma_online_refined`

Tabelas de varejo/omnichannel do grupo Azzas 2154. Usadas **exclusivamente como fonte em subqueries ou CTEs** dentro de consultas maiores — não são consultadas diretamente pelo usuário e não têm schema definido neste documento.

| Tabela | Path completo |
|---|---|
| `refined_vendas_mestre` | `soma-dl-refined-online.soma_online_refined.refined_vendas_mestre` |
| `refined_branches` | `soma-dl-refined-online.soma_online_refined.refined_branches` |
| `refined_captacao` | `soma-dl-refined-online.soma_online_refined.refined_captacao` |
| `refined_historico_vendedores` | `soma-dl-refined-online.soma_online_refined.refined_historico_vendedores` |
