# Business Rules — Ciclo de Venda Atacado (Azzas 2154)

> Documento canônico de regras de negócio para análises do canal Atacado da BU Fashion & Lifestyle.
> Dataset: `soma-dl-refined-online.atacado_processed`
> Complementa `schema.md` (dicionário de dados) e `analyst principles.md` (método analítico).

---

## 0. Contexto de negócio

### Grupo Azzas 2154
Holding de moda brasileira organizada em Business Units (BUs). O foco deste agente é a **BU Fashion & Lifestyle**. O canal Atacado expande a presença das marcas através de multimarcas (lojistas) distribuídas pelo Brasil.

### Estrutura comercial
A operação depende da sinergia entre:
- **Representantes** (externos): responsáveis pela carteira de clientes por marca e estado
- **Coordenadores** (internos): supervisão e suporte à operação

### Ciclo operacional — 4 coleções anuais
| Estação | Sigla | Ano no nome | Período de venda (aprox.) |
|---|---|---|---|
| VERÃO | VER | ano seguinte | Abril |
| ALTO VERÃO | AV | ano seguinte | Julho |
| INVERNO | INV | ano seguinte | Outubro |
| ALTO INVERNO | AI | ano corrente | Janeiro |

Cada coleção tem duas fases:
1. **Venda:** período de pedidos e análise de catálogo pelos lojistas
2. **Faturamento:** produção, envio e pagamento — inicia ~3 meses após a venda

A **curva de faturamento** se refere à progressão mensal do valor faturado ao longo do período de faturamento.

### Prateleira Infinita
Canal de venda complementar ao pedido inicial da coleção. Envolve produtos já prontos no CD (entrega mais rápida). Usada para reposição de estoque ou teste de novos produtos. **Acesso exclusivo** para produtos de coleções que o cliente já adquiriu; mantém o mesmo markup da última compra realizada.

### Programas digitais

#### Afiliados
Multimarcas recrutam vendedores digitais que divulgam as marcas com códigos personalizados. Comissão: 10% → 4% ao vendedor, **5% à multimarca** (crédito para abater títulos a vencer — reduz inadimplência), 1% ao representante.

#### Somaplace
Marketplace onde a multimarca inclui seus produtos comprados na coleção nos sites oficiais das marcas do grupo. Expande visibilidade e atuação geográfica da loja parceira usando o tráfego dos e-commerces próprios do Grupo. Divisão de receita: **variável por cliente** — grupo retém `COMISSAO`% (padrão 20%), multimarca recebe o restante, calculado sobre o GMV Líquido. Clientes com logística via Correios pagam comissão superior ao padrão. Ver §20.

---

## 1. Aliases de marca (resolver sem perguntar)

Aliases são usados **exclusivamente para identificar a marca** a partir do input do usuário. O valor que vai para o SQL é sempre o `MARCA` canônico — nunca o alias. A lista abaixo é **exaustiva**: não existem outras marcas além destas no escopo deste agente.

| `MARCA` canônica | Aliases aceitos | Observação |
|---|---|---|
| `ANIMALE` | — | — |
| `ANIMALE JEANS` | AJ | — |
| `BYNV` | NV, ByNV, By NV, Nati Vozza | — |
| `FARM` | FARM Rio, Farm Rio, FARM moda | — |
| `FARM ETC` | Etc, Me Leva | Marca separada — não incluir FARM ou FARM PRAIA |
| `FARM PRAIA` | Praia, FARM Beachwear, FARM Swim | — |
| `FABULA` / `FÁBULA` | FABULA, FÁBULA | Filtrar sempre `MARCA IN ('FABULA', 'FÁBULA')` |
| `FOXTON` | — | — |
| `MARIA FILÓ` / `MARIA FILO` | MF, Maria Filo | Filtrar sempre ambas as formas com e sem acento |
| *(via SEGMENTO)* | Teen, Linha Teen, Fábula Teen, FARM Teen | Não possui MARCA própria — identificar via `SEGMENTO` (ver §4) |

**Regra geral:** filtrar sempre em MAIÚSCULA, com e sem acento:
```sql
WHERE `MARCA` IN ('FABULA', 'FÁBULA')
WHERE `MARCA` IN ('MARIA FILÓ', 'MARIA FILO')
WHERE `COLECAO` IN ('VERAO 2026', 'VERÃO 2026')
```

### 1.1 Aliases de representante (resolver sem perguntar)

Aliases são usados **exclusivamente para identificar o representante** a partir do input do usuário. O valor que vai para o SQL é sempre o `NOME_WISE` canônico — nunca o alias. A lista abaixo é **exaustiva**: não existem outros representantes além destes, a não ser que o usuário especifique um valor diferente.

Lista completa de valores válidos de `NOME_WISE` e seus aliases de entrada:

| `NOME_WISE` canônico | Aliases aceitos |
|---|---|
| AMAIS | — |
| ANGELO | FENNYZ |
| ATENDIMENTO INTERNO | — |
| BAH | — |
| BR BRAND | — |
| CBL & REPRESENTACOES | — |
| CECILINO | — |
| CJK | — |
| CLEBER | HUB |
| CMIX | — |
| COCAR | — |
| DRANKA | — |
| DREAMS | — |
| DUO | — |
| EDGAR JUNIOR | — |
| EDGAR JUNIOR ALTO TIETE | — |

> **Desambiguação EDGAR JUNIOR / EDGAR JUNIOR ALTO TIETE:** quando o usuário mencionar "Edgar Junior" sem especificar a variante geográfica, considerar **ambos** na query e apresentar os resultados discriminados por `NOME_WISE` na resposta final.
| FACEX | — |
| FC SHOWROOM | — |
| FLUMINENSE | — |
| GFN | GUSTAVO FARAH, GUSTAVO |
| JADE | — |
| JULIANO TINELLI | — |
| JULIANO TINELLI CUIABA | — |
| JULIANO TINELLI CUIABÁ | — |

> **Desambiguação JULIANO TINELLI:** quando o usuário mencionar "Juliano Tinelli" sem especificar a variante geográfica, considerar **todas as variantes** (`JULIANO TINELLI`, `JULIANO TINELLI CUIABA`, `JULIANO TINELLI CUIABÁ`) na query e apresentar os resultados discriminados por `NOME_WISE` na resposta final. `JULIANO TINELLI CUIABA` e `JULIANO TINELLI CUIABÁ` são a mesma variante — filtrar sempre ambas as formas com e sem acento.
| KL | — |
| M R TEDESCO | MOACIR, MOACIR TEDESCO |
| M R TEDESCO SC | MOACIR TEDESCO, MOACIR |

> **Desambiguação M R TEDESCO / M R TEDESCO SC:** quando o usuário mencionar qualquer alias compartilhado (MOACIR, MOACIR TEDESCO), considerar **ambos os representantes** na query e apresentar os resultados discriminados por `NOME_WISE` na resposta final — nunca consolidar os dois em uma única linha.
| MAZAL | MARCELO SERRUYA, SERRUYA |
| MOL | JOMA, RAFAEL NAGIB, POWDER TENIS |
| POZZA | — |
| RCG | — |
| ROTHA | — |
| RVM | — |
| RVM RJ | — |
| SADDI | — |
| SILVANA | — |
| SIZE REPRESENTACOES | — |
| SLIM | — |
| SP PRIME | — |
| UNDERGROUND | — |
| UP | GALERIA |
| VALERIA WEBER | VWM |
| WE REPRESENTAÇÕES | — |
| WELLMAN | — |

### 1.2 Aliases de coordenador (resolver sem perguntar)

Aliases são usados **exclusivamente para identificar o coordenador** a partir do input do usuário. O valor que vai para o SQL é sempre o `COORDENADOR` canônico — nunca o alias. A lista abaixo é **exaustiva**: não existem outros coordenadores além destes, a não ser que o usuário especifique um valor diferente.

Lista completa de valores válidos de `COORDENADOR` e seus aliases de entrada:

| `COORDENADOR` canônico | Aliases aceitos |
|---|---|
| CAROLINA ALPES | CAROL ALPES |
| GUSTAVO | — |
| LUA | — |
| MARIANA | — |
| MARINA | — |
| MARTA | — |
| MILLENA | — |
| ROBERTA | — |
| VERONICA | — |

### 1.3 Desambiguação de nomes

Quando um nome for mencionado na pergunta e **não puder ser identificado como representante** (via `NOME_WISE`) **nem como coordenador** (via `COORDENADOR`), deve ser tratado como **cliente** e buscado no campo `CLIENTE` de `dim_clientes_v2` usando `LIKE '%NOME%'`, incluindo variações de acento.

**Correspondência aproximada — validar com o usuário antes de prosseguir:**
Se a busca não encontrar um cliente com nome idêntico ao mencionado, mas retornar nomes semelhantes, **não assumir** qual é o correto. Apresentar as opções ao usuário e confirmar antes de executar a análise:

> "Não encontrei um cliente com o nome exato '[nome]'. Os mais próximos que encontrei foram: [lista]. Você se referia a algum deles?"

---

## 2. Tipo de venda — filtros padrão

Em toda análise sobre `info_venda`, `info_cancelamento`, `info_embalado` e `info_fat_nf`, o filtro padrão é:
```sql
WHERE `TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
```

Prateleira Infinita (incluindo `PRONTA ENTREGA`, nome legado) e Redistribuição são **excluídas por padrão** — só entram quando explicitamente solicitadas.

Como `TIPO_VENDA` só existe em `info_venda`, as demais tabelas fazem JOIN:
```sql
JOIN `soma-dl-refined-online.atacado_processed.info_venda` v
  ON tabela.`PEDIDO` = v.`PEDIDO`
 AND tabela.`PRODUTO` = v.`PRODUTO`
 AND tabela.`COR_PRODUTO` = v.`COR_PRODUTO`
WHERE v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
```

**Prateleira Infinita:** quando incluída, considerar sempre `PRATELEIRA INFINITA`, `PRATELEIRA INFINITA - EXTERNA` e `PRONTA ENTREGA` (nome legado) juntos. Separar estoque interno/externo só sob pedido explícito.

**Redistribuição:** mercadoria devolvida e refaturada para outro cliente. Em `info_venda`, aparece como `TIPO_VENDA = 'REDISTRIBUIÇÃO'` com `VENDA_ORIGINAL = 0` — excluída automaticamente pelo filtro `VENDA_ORIGINAL > 0`. Em `info_fat_nf`, aparece como faturamento e deve ser incluída com `VENDA_ORIGINAL >= 0`. Contexto de negócio: ver §18.

**Filtro obrigatório adicional em info_venda:**
```sql
AND `VENDA_ORIGINAL` > 0
```

---

## 3. Venda: bruta vs líquida

- **Venda (padrão)** = `VENDA_ORIGINAL` (valor bruto, sem cancelamentos deduzidos) — apresentar simplesmente como "Venda", nunca como "Venda Bruta"
- **Venda Líquida** = `VENDA` (com cancelamentos deduzidos) — usar só quando explicitamente solicitada

> Sinônimos e contexto de negócio: ver §18 (Venda Bruta, Venda Líquida).

---

## 4. Marcas virtuais (sem campo MARCA próprio)

### FARM FUTURA (linha teen feminina da FABULA)
```sql
WHERE `MARCA` IN ('FABULA', 'FÁBULA') AND p.`SEGMENTO` = 'MENINA TEEN'
```
Linha iniciada a partir de **VERÃO 2026** — não há dados de FARM FUTURA em coleções anteriores. Se o usuário perguntar sobre períodos anteriores ao VERÃO 2026, informar que a marca só iniciou sua operação no canal Atacado a partir desta coleção.

### BENTO (linha infantil masculina da FABULA)
```sql
WHERE `MARCA` IN ('FABULA', 'FÁBULA') AND p.`SEGMENTO` IN ('MENINO', 'BEBE MENINO')
```

### Ecossistemas
- **Ecossistema FARM:** FARM, FARM ETC, FARM PRAIA, FARM FUTURA, FÁBULA e BENTO
- **Ecossistema FÁBULA:** FÁBULA, BENTO e FARM FUTURA
- Marcas são tratadas individualmente salvo quando o ecossistema for pedido explicitamente.
- "Fábula" sem especificação = `MARCA IN ('FABULA', 'FÁBULA')` completo (inclui BENTO e FARM FUTURA). Desagregar só sob pedido.
- **FARM, FARM PRAIA e FARM ETC são marcas distintas** — filtrar exatamente pelo valor mencionado.

---

## 5. Coleções

### Estrutura
Coleções são sempre `ESTAÇÃO + ANO` (ex: `VERAO 2026`). ALTO INVERNO usa o **ano corrente**; demais usam o **ano seguinte**.

### Ordenação de estações
| Estação | Ordem |
|---|---|
| VERAO | 1 |
| ALTO VERAO | 2 |
| INVERNO | 3 |
| ALTO INVERNO | 4 |

### Etapas
- **Primeira Etapa:** VERÃO e INVERNO
- **Segunda Etapa:** ALTO VERÃO e ALTO INVERNO

### Comparações
Sempre entre coleções da **mesma estação** (VERÃO 2026 vs VERÃO 2025). Quando não especificada a coleção de comparação, assumir a imediatamente anterior da mesma estação.

### Coleção mais recente
Estação mencionada sem ano → considerar a coleção mais recente disponível nas tabelas.

### Filtros por coleção
Análises de venda, cancelamento, embalado e faturamento filtradas por `COLECAO = 'VERAO 2026'`, **nunca** por intervalo de datas. **Exceções:** devoluções (`DATA_RECEBIMENTO`), Prateleira Infinita e Somaplace (analisadas por data — campo `DATA`). `info_financeira` não usa filtro de coleção (snapshot atual).

### Ano dinâmico
```sql
EXTRACT(YEAR FROM CURRENT_DATE())   -- nunca hardcoded
```

### Quando um ano é referenciado
`ANO` = `EXTRACT(YEAR FROM CURRENT_DATE())` — nunca hardcoded. Em SQL, sempre use a função dinâmica; nunca substitua por um literal numérico (ex: `2026`).

`ALTO INVERNO [ANO]`, `VERAO [ANO+1]`, `ALTO VERAO [ANO+1]`, `INVERNO [ANO+1]`

### Coleções de um ano
"Coleções de [ANO]" = coleções **vendidas** naquele ano — não as que terminam com esse número no nome da coleção.

| Ano de referência | Coleções (período de venda) |
|---|---|
| 2026 | ALTO INVERNO 2026, VERAO 2027, ALTO VERAO 2027, INVERNO 2027 |
| 2025 | ALTO INVERNO 2025, VERAO 2026, ALTO VERAO 2026, INVERNO 2026 |

### Marcas que não participam do ALTO INVERNO
**FÁBULA** e **FARM PRAIA** não realizam venda na estação ALTO INVERNO. Não incluir essas marcas em análises de ALTO INVERNO salvo pedido explícito e verificação de dados disponíveis.

### Coleções — nunca hardcoded; usar CTE canônica

Nunca escrever coleções literais em análises que dependem de "últimas N coleções" ou de referência temporal dinâmica. Usar sempre a CTE canônica abaixo para derivar a lista ordenada a partir dos dados reais do banco.

#### CTE canônica de ordenação

```sql
WITH tpt_parsed_collections AS (
  SELECT DISTINCT
    `COLECAO`,
    CAST(SUBSTR(`COLECAO`, LENGTH(`COLECAO`) - 3, 4) AS INT64) AS `Ano`,
    CASE
      WHEN STARTS_WITH(`COLECAO`, 'VERAO')        THEN 1
      WHEN STARTS_WITH(`COLECAO`, 'ALTO VERAO')   THEN 2
      WHEN STARTS_WITH(`COLECAO`, 'INVERNO')      THEN 3
      WHEN STARTS_WITH(`COLECAO`, 'ALTO INVERNO') THEN 4
      ELSE 99
    END AS `Ordem_Estacao`
  FROM `soma-dl-refined-online.atacado_processed.info_venda`
  WHERE `COLECAO` NOT LIKE 'NAO INFORMADA%'  -- erro de banco; sempre desconsiderar
),
tpt_collections_ordered AS (
  SELECT
    `COLECAO`,
    `Ano`,
    `Ordem_Estacao`,
    ROW_NUMBER() OVER (ORDER BY `Ano` DESC, `Ordem_Estacao` DESC) AS `Posicao`
  FROM tpt_parsed_collections
)
```

`Posicao = 1` = coleção mais recente. Quanto maior o número, mais antiga a coleção.

#### Padrão — últimas N coleções antes de uma referência (exclusive)

```sql
, ref AS (
  SELECT `Posicao` AS ref_pos
  FROM tpt_collections_ordered
  WHERE `COLECAO` = '<COLECAO_REFERENCIA>'  -- ex: 'VERAO 2026'
)
SELECT co.`COLECAO`
FROM tpt_collections_ordered co
CROSS JOIN ref
WHERE co.`Posicao` > ref.ref_pos           -- mais antigas que a referência
  AND co.`Posicao` <= ref.ref_pos + N      -- as N imediatamente anteriores
ORDER BY co.`Posicao`
```

#### Padrão — N coleções mais recentes disponíveis

```sql
SELECT `COLECAO`
FROM tpt_collections_ordered
WHERE `Posicao` <= N   -- ex: <= 4 para as últimas 4
ORDER BY `Posicao`
```

> ⚠️ **Ponto de atenção obrigatório:** antes de entregar qualquer análise que filtre coleções, verificar se as coleções cobertas pela query estão corretas — especialmente em análises de cluster (§9), segmentação de clientes (§9) e atingimento de meta (§14).

---

## 6. Markup e markup realizado

### Extração do markup
Campo `TABELA_MKP`: número após "VENDA ATACADO". Ex: `"VENDA ATACADO 2.35"` → markup = 2.35. Sem número → considerar 2.2. Definições e fórmula de Markup Realizado: ver §18.

### Tolerância de ponto flutuante
```
valor >= limiar * (1 - 0.001)
```

---

## 7. Cancelamento

- **Cancelamento Comercial:** todos os `TIPO_CANCELAMENTO` exceto `'05-BLOQUEIO FINANCEIRO'`
- **Cancelamento Financeiro:** apenas `TIPO_CANCELAMENTO = '05-BLOQUEIO FINANCEIRO'`
- **Exibição:** remover prefixo numérico ao exibir ao usuário (`"BLOQUEIO FINANCEIRO"`, não `"05-BLOQUEIO FINANCEIRO"`)

### Valores válidos de `TIPO_CANCELAMENTO` (lista exaustiva)

| Valor no banco | Classificação | Observação |
|---|---|---|
| `01-SALDO NAO PRDOUZIDO` | Comercial | ⚠️ typo no banco — usar exatamente este valor no SQL |
| `02-FALTA DE SALDO ENTREGA` | Comercial | — |
| `03-DESISTENCIA CLIENTE` | Comercial | — |
| `04-ALTERAÇÃO DE PEDIDO` | Comercial | — |
| `05-BLOQUEIO FINANCEIRO` | **Financeiro** | — |
| `06-CANCELAMENTO COMERCIAL` | Comercial | — |
| `07-TRANSF. DE CADASTRO` | Comercial | — |
| `10-PEDIDO EM DUPLICIDADE` | Comercial | — |
| `11-ERRO DIGITAÇÃO` | Comercial | — |
| `13-AGUARDANDO REPASSE` | Comercial | — |
| `99-OUTROS CANCELAMENTOS` | Comercial | — |
| `WMS-TROCA DE DESTINO` | Comercial | — |

> Definições completas e sinônimos: ver §18 (Cancelamento).

---

## 8. Faturamento

- **Faturamento Bruto:** soma de `VALOR_FATURADO` sem deduzir devoluções (padrão)
- **Faturamento Líquido:** Faturamento Bruto menos `VALOR_NF` de devoluções do mesmo período
- Quando pedido "faturamento", trazer **sempre ambos**, discriminados por Bruto e Líquido
- **Curva de Faturamento:** progressão mensal do valor faturado — usar Faturamento Líquido
- **Quebra:** percentual do pedido não faturado — fórmula canônica em §18

---

## 9. Clientes

### Cliente Ativo (operacional)
Realizou compra em alguma das últimas 4 coleções. Um cliente **bloqueado impossibilita compra** na coleção.

> **Desambiguação:** quando o usuário disser "cliente ativo" sem qualificar, usar esta definição (últimas 4 coleções). A variante "Cliente Ativo (análise de coleção)" na tabela abaixo aplica-se somente em análises explícitas de perfil de coleção. Em contexto de **Somaplace** (§20) e **Afiliados** (§21), "ativo" significa venda confirmada nos últimos 2 meses — definição independente das duas anteriores.

### Segmentação por histórico de compra (por coleção, por marca)

| Segmento | Critério |
|---|---|
| Cliente Novo | Primeira compra exatamente na coleção em análise, sem histórico anterior |
| SCS (Same Client Sale) | Comprou na coleção em análise E na imediatamente anterior da mesma estação |
| Cliente Ativo (análise de coleção) | Comprou em alguma das últimas 3 coleções de outras estações, mas não na imediatamente anterior |
| Resgate | Voltou após ausência de mais de 4 coleções consecutivas, com histórico anterior |

### Janela de avaliação para Cliente Novo e Resgate

Para classificar um cliente como **Novo** ou **Resgate**, considerar **apenas as coleções anteriores à coleção de referência** — desconsiderar coleções posteriores, mesmo que o cliente as tenha comprado.

> Exemplo: para classificar um cliente na coleção VERAO 2027, avaliar somente se ele teve compras antes de VERAO 2027. Se ele comprou em ALTO VERAO 2027 (posterior), essa compra não entra na avaliação.

### Pulo de coleção

A ausência de compra em uma coleção **não significa** que o cliente encerrou o relacionamento. Clientes frequentemente pulam coleções por excesso de estoque, sazonalidade ou restrição financeira pontual. Ao analisar clientes ausentes ou inativos, **verificar o histórico completo de coleções** para identificar padrões de pulo recorrentes antes de concluir abandono.

### Exibição de nome de cliente

Sempre que o nome do cliente (`CLIENTE`) aparecer em qualquer output — tabela, gráfico, lista, texto corrido — o `CLIFOR` correspondente deve estar presente na mesma linha/trecho. Isso vale para respostas parciais, exemplos e rankins. Nunca exibir `CLIENTE` sem `CLIFOR`.

### Número de atendimentos
```sql
COUNT(DISTINCT `CLIFOR`) AS atendimentos
-- filtro: TIPO_VENDA IN ('VENDA', 'PRE VENDA'), analisado por COLECAO
```

### Bloqueio financeiro
Tabela: `info_financeira`. Regras operacionais completas: ver §19. Resumo:
- `SITUACAO = 'BLOQUEADO'` → cliente impedido de comprar
- Bloqueio se propaga a todo o grupo econômico
- **Inadimplência:** `SUM(VALOR_VENCIDO)` onde `SITUACAO = 'BLOQUEADO'`
- **Aging:** `DATE_DIFF(CURRENT_DATE(), DATE(DATA_BLOQ), DAY)`

### Cluster (segmentação por porte)
Calculado sobre soma das vendas nas últimas 4 coleções **incluindo a coleção de referência** (incluindo Prateleira Infinita), por marca.

| Marca | PP | P | M | G | GG |
|---|---|---|---|---|---|
| ANIMALE | até 120k | 120k–230k | 230k–350k | 350k–580k | > 580k |
| ANIMALE JEANS | até 40k | 40k–72k | 72k–110k | 110k–180k | > 180k |
| BYNV | até 120k | 120k–230k | 230k–370k | 370k–650k | > 650k |
| FARM | até 100k | 100k–180k | 180k–330k | 330k–650k | > 650k |
| FARM ETC | até 30k | 30k–60k | 60k–100k | 100k–250k | > 250k |
| FARM PRAIA | até 16k | 16k–24k | 24k–45k | 45k–75k | > 75k |
| MARIA FILÓ | até 55k | 55k–90k | 90k–140k | 140k–250k | > 250k |
| FÁBULA | até 20k | 20k–45k | 45k–65k | 65k–120k | > 120k |

> **FOXTON — sem clusterização:** FOXTON não possui thresholds de cluster definidos.
> - Se o usuário solicitar clusterização **específica de FOXTON**: informar que a marca não possui clusterização disponível.
> - Se o usuário solicitar clusterização **geral** (todas as marcas ou sem especificar): **excluir FOXTON** da análise sem mencionar, a menos que o usuário pergunte.

### Normalização de cidades
Ver nota na coluna `CIDADE` em schema.md §7.

---

## 10. Representantes — exclusões em análises comparativas

**ATENDIMENTO INTERNO** (`NOME_WISE = 'ATENDIMENTO INTERNO'`) **e FACEX** (`NOME_WISE = 'FACEX'`) são excluídos de rankings, desempenho e análises comparativas entre representantes. Entram apenas em somatórios gerais (visão de marca ou grupo). Os clientes geridos por eles seguem a mesma regra.

> **Exceção:** em cálculos de **atingimento de meta** (§14), FACEX e ATENDIMENTO INTERNO são **incluídos** tanto na venda quanto na meta.

---

## 11. Produto

**Sinônimos:** peça, SKU — quando o usuário disser "peça" ou "SKU", interpretar como o produto canônico identificado por `PRODUTO` + `COR_PRODUTO`.

- A coluna `PRODUTO` **nunca deve ser analisada sozinha** — a unidade mínima de análise é sempre a chave composta `PRODUTO` + `COR_PRODUTO`.
- Resultado deve incluir `DESC_PRODUTO` e `DESC_COR_PRODUTO`.
- JOIN com `info_produto_v2` **nunca** usa `COLECAO` — apenas `PRODUTO` + `COR_PRODUTO`.
- Para filtros de característica, aplicar OR em todos os campos:
```sql
(`LINHA` = 'X' OR `LINHA_MIX` = 'X' OR `GRUPO_PRODUTO` = 'X'
 OR `SUBGRUPO_PRODUTO` = 'X' OR `SOLUCAO` = 'X')
```

### Filtros por atributo de produto — fluxo obrigatório

Os campos `LINHA`, `LINHA_MIX`, `GRUPO_PRODUTO`, `SUBGRUPO_PRODUTO`, `SOLUCAO` e `TIPO_PRODUTO` **não têm valores fixos documentados**. Sempre que o usuário pedir análise por um desses atributos, seguir obrigatoriamente:

**Passo 1 — Consultar valores distintos disponíveis:**
```sql
SELECT
  DISTINCT `LINHA`, `LINHA_MIX`, `GRUPO_PRODUTO`, `SUBGRUPO_PRODUTO`, `SOLUCAO`, `TIPO_PRODUTO`
FROM `soma-dl-refined-online.atacado_processed.info_produto_v2`
WHERE `MARCA` = '<MARCA>'   -- filtrar pela marca relevante quando aplicável
ORDER BY 1, 2, 3, 4, 5, 6
```

**Passo 2 — Identificar o valor correto** a partir dos resultados e do contexto trazido pelo usuário (nome informal, categoria, tipo de peça etc.).

**Passo 3 — Aplicar o filtro** com o valor exato encontrado no banco — nunca assumir ou hardcodar.

---

## 12. Embalado e expedição

- **Disponível para faturar:** apenas caixas com `STATUS_CAIXA = 'EXPEDICAO'` (status original). Valor embalado = sem filtro de STATUS_CAIXA.
- **Caixa Quebrada:** `CX_QUEBRADA = 1` → grade incompleta, requer atenção antes do faturamento.
- **Teto de Faturamento:** limite máximo faturável para um cliente em uma semana.

### Agrupamento de STATUS_CAIXA para exibição

Todos os filtros por STATUS_CAIXA devem usar os valores em **MAIÚSCULA** conforme a tabela abaixo.

| Exibir como | `STATUS_CAIXA` originais (exatos, MAIÚSCULA) |
|---|---|
| PICKING GRADE QUEBRADA | `AGUARDANDO PICKING GQ`, `PENDENTE PICKING GQ`, `PICKING GQ` |
| ABAIXO DO MÍNIMO | `MINIMO NOTA`, `VOLUME MINIMO` |
| BLOQUEIO DE TETO | `CAIXA FORA DA SEMANA`, `CAIXA SEM TETO`, `CAIXA VIRTUAL NAO CRIADA`, `CLIENTE JA FAT SEMANA`, `LIBERACAO MANUAL`, `LIBERAÇÃO MANUAL` |
| BLOQUEIO FINANCEIRO | `BLOQUEADO`, `BLOQUEADO EXPEDICAO` |
| LIBERAÇÃO POR UF | `CAIXA A LIBERAR`, `LIBERACAO AGENDADA` |
| PRODUTO PRÓX COLEÇÃO | `COLECAO NAO LIBERADA`, `AGUARDAR DATA DE ENTREGA` |
| LIBERADO PARA FATURAR | `EXPEDICAO` |
| SEM CAIXA + FATURÁVEL DISPONÍVEL | `SEM CAIXA` |
| (nome direto — sem agrupamento) | `CANCELADO`, `CLIENTE INATIVO`, `ECOMMERCE`, `EXPEDICAO CLIENTE ESPECIAL`, `GRADE QUEBRADA`, `PEDIDO NAO APROVADO`, `TRANSF FILIAL` |

---

## 13. Prazo médio de pagamento

Somar todos os prazos e dividir pela quantidade de parcelas. Ex: `30/45/60/90` → (30+45+60+90)/4 = 56,25 dias.
- Valores não numéricos ou NULL → considerar 0 (à vista)
- `'120 DIAS'` → 120 dias corridos

---

## 14. Atingimento de meta

O atingimento de venda sempre se refere à comparação `Venda / META`:
```sql
SAFE_DIVIDE(SUM(v.`VENDA_ORIGINAL`), MAX(m.`META`)) AS atingimento
```
`META DESAFIO` e `META ATENDIMENTO` só são usadas quando explicitamente solicitadas.

> **Exceção à §10:** para cálculo de atingimento de meta, **FACEX e ATENDIMENTO INTERNO devem ser incluídos** — não excluir esses representantes da venda nem da meta ao calcular o atingimento.

---

## 15. Capilaridade — fluxo obrigatório de análise

> Capilaridade = quantidade de cidades onde o representante tem venda / total de cidades nos estados em que ele atua.

**Quando o usuário perguntar sobre capilaridade de um representante, seguir OBRIGATORIAMENTE os passos abaixo:**

### Passo 1 — Buscar os estados em que o representante tem venda

Consultar `info_venda` com JOIN em `dim_clientes_v2`:
```sql
SELECT DISTINCT c.`ESTADO`
FROM `soma-dl-refined-online.atacado_processed.info_venda` v
JOIN `soma-dl-refined-online.atacado_processed.dim_clientes_v2` c
  ON v.`CLIFOR` = c.`CLIFOR` AND v.`MARCA` = c.`MARCA`
WHERE c.`NOME_WISE` = '<NOME_WISE>'
  AND v.`COLECAO` = '<COLECAO>'
  AND v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
```

### Passo 2 — Buscar todas as cidades de cada estado

Chamar a tool `web_search` para cada estado retornado no Passo 1:
> "Lista completa de municípios do estado `<ESTADO>` Brasil"

Garantir a **lista completa** de municípios — não truncar.

### Passo 3 — Buscar as cidades com venda do representante por estado

Consultar `info_venda` com JOIN em `dim_clientes_v2`, filtrando por estado:
```sql
SELECT DISTINCT c.`CIDADE`
FROM `soma-dl-refined-online.atacado_processed.info_venda` v
JOIN `soma-dl-refined-online.atacado_processed.dim_clientes_v2` c
  ON v.`CLIFOR` = c.`CLIFOR` AND v.`MARCA` = c.`MARCA`
WHERE c.`NOME_WISE` = '<NOME_WISE>'
  AND c.`ESTADO` = '<ESTADO>'
  AND v.`COLECAO` = '<COLECAO>'
  AND v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
```
Repetir para cada estado. Normalizar acentuação de `CIDADE` antes de comparar.

### Passo 4 — Calcular o percentual

Calcular diretamente a partir dos dados coletados nos passos anteriores:
```
capilaridade_por_estado = cidades_com_venda / total_cidades_do_estado
capilaridade_total      = soma(cidades_com_venda) / soma(total_cidades_por_estado)
```

**Exemplo completo:**
```
Pergunta: Qual a capilaridade do representante GFN na coleção VERAO 2026?

1. Query info_venda → estados distintos do GFN no VERAO 2026
   → Rio de Janeiro, São Paulo

2. web_search → "Lista completa de municípios do estado Rio de Janeiro Brasil"
   web_search → "Lista completa de municípios do estado São Paulo Brasil"
   → RJ: 92 municípios | SP: 645 municípios

3. Query info_venda → cidades do RJ com venda do GFN no VERAO 2026 → ex: 18 cidades
   Query info_venda → cidades de SP com venda do GFN no VERAO 2026 → ex: 47 cidades

4. calculate:
   RJ: 18/92 = 19,6%
   SP: 47/645 = 7,3%
   Total: 65/737 = 8,8%
```

> ⚠️ Esta é a **única** situação em que uma pesquisa na internet é realizada.

---

## 16. Convenções SQL

```sql
-- Crases obrigatórias em colunas e tabelas
SELECT `MARCA`, `COLECAO`, SUM(`VENDA_ORIGINAL`) AS venda
FROM `soma-dl-refined-online.atacado_processed.info_venda`
WHERE `TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND `VENDA_ORIGINAL` > 0

-- Ano sempre dinâmico
EXTRACT(YEAR FROM CURRENT_DATE())

-- JOIN dim_clientes_v2 sempre por CLIFOR + MARCA
JOIN `soma-dl-refined-online.atacado_processed.dim_clientes_v2` c
  ON v.`CLIFOR` = c.`CLIFOR` AND v.`MARCA` = c.`MARCA`

-- Hora desconsiderada em campos DATETIME
DATE(v.`EMISSAO`)   -- para agrupar por dia
```

### Uso de LIMIT

**Nunca use `LIMIT` em queries analíticas.** O `LIMIT` trunca o resultado silenciosamente e produz totais errados, rankings incompletos e métricas enganosas.

**Exceção única:** rankings de TOP N explícitos — Top vendedores, Top clientes, Top produtos — onde o objetivo é exatamente mostrar os N maiores. Nesses casos, use `ORDER BY ... DESC LIMIT N`.

```sql
-- ❌ Proibido — LIMIT em query analítica
SELECT `MARCA`, SUM(`VENDA_ORIGINAL`) AS venda
FROM `soma-dl-refined-online.atacado_processed.info_venda`
WHERE `COLECAO` = 'VERAO 2026'
GROUP BY 1
LIMIT 100   -- errado: omite marcas e distorce o total

-- ✅ Correto — sem LIMIT
SELECT `MARCA`, SUM(`VENDA_ORIGINAL`) AS venda
FROM `soma-dl-refined-online.atacado_processed.info_venda`
WHERE `COLECAO` = 'VERAO 2026'
GROUP BY 1
ORDER BY venda DESC

-- ✅ Correto — LIMIT apenas em ranking explícito de TOP N
SELECT `CLIFOR`, `CLIENTE`, SUM(`VENDA_ORIGINAL`) AS venda
FROM `soma-dl-refined-online.atacado_processed.info_venda`
WHERE `COLECAO` = 'VERAO 2026'
GROUP BY 1, 2
ORDER BY venda DESC
LIMIT 10   -- Top 10 clientes — uso legítimo
```

---

## 17. Anti-hallucination

Nunca inventar um número. Labels obrigatórios:

| Label | Uso |
|---|---|
| ✅ Dado real | Resultado de query executada nesta sessão |
| 📊 Benchmark | Referência de mercado (citar fonte) |
| 🔶 Estimativa | Calculado a partir de dado real |
| ❓ Indisponível | Não presente nas tabelas — não inventar |

---

## 18. Glossário de negócio

### Clifor
**Sinônimos:** Código do Cliente, ID do Cliente, Cliente ID
Identificador único do cliente (multimarca) no sistema interno. Um mesmo grupo econômico pode ter vários clifors (uma loja = um clifor). Quando um cliente muda de CNPJ, deve ser mapeado via CNPJ ou Grupo Econômico. O clifor é único por loja/CNPJ, independente da marca.

### Grupo Econômico
**Sinônimos:** Rede, Grupo de Lojas, Holding Cliente
Agrupamento de todas as lojas (clifors e CNPJs) pertencentes ao mesmo proprietário. Usado para consolidar performance de clientes que operam com múltiplos CNPJs. Essencial para evitar dupla contagem.

### Coleção
**Sinônimos:** Temporada, Safra, Season
Conjunto de produtos lançados em uma temporada específica. Nomeadas como `ESTAÇÃO ANO` (ex: VERÃO 2027). ALTO INVERNO usa o ano corrente; demais usam o ano seguinte. Comparações sempre entre coleções de mesma estação.

### Período de Venda
**Sinônimos:** Janela de Pedidos, Período de Compra, Campanha de Vendas
Fase em que as multimarcas analisam o catálogo e realizam pedidos. Não há entrega nesta fase. Tipos válidos: VENDA e PRE VENDA (sem acento no banco). Calendário: Janeiro=ALTO INVERNO, Abril=VERÃO, Julho=ALTO VERÃO, Outubro=INVERNO.

### Período de Faturamento
**Sinônimos:** Fase de Entrega, Ciclo de Faturamento
Fase de produção, envio e pagamento — inicia ~3 meses após a venda. VERÃO e INVERNO: ~6 meses. ALTO VERÃO e ALTO INVERNO: ~3 meses. Faturamento bruto por padrão; líquido exclui devoluções.

### Primeira Etapa
**Sinônimos:** Grandes Coleções, Coleções Principais
VERÃO e INVERNO. Maior volume de vendas e faturamento. VERÃO é a maior coleção entre as de Primeira Etapa.

### Segunda Etapa
**Sinônimos:** Coleções de Alto, Coleções Complementares
ALTO VERÃO e ALTO INVERNO. Menor volume. ALTO VERÃO é a maior entre as de Segunda Etapa. **FÁBULA e FARM PRAIA não realizam venda no ALTO INVERNO.**

### Venda Bruta
**Sinônimos:** Gross Sales, Venda, Pedido Bruto
Campo `VENDA_ORIGINAL`. Indicador padrão — apresentar sempre como "Venda". Filtrar `TIPO_VENDA IN ('VENDA','PRE VENDA')`. Não incluir Prateleira Infinita salvo pedido explícito. Convenção de nomes: ver §3.

### Venda Líquida
**Sinônimos:** Net Sales, Venda Descontada
Campo `VENDA` — já inclui descontos e cancelamentos. Usar apenas quando explicitamente solicitado.

### Markup
**Sinônimos:** MKP, Fator de Markup, Tabela de Markup
Multiplicador aplicado ao custo para definir o preço de venda ao atacado. Extraído do campo `TABELA_MKP` (número após "VENDA ATACADO"). Sem número → considerar 2.2. Quanto maior a compra, melhor o markup negociado.

### Markup Realizado
**Sinônimos:** MKP Realizado, Markup Efetivo, MKP Médio
Média ponderada dos markups: `Σ(VENDA_ORIGINAL × markup) / Σ(VENDA_ORIGINAL)`. Ver §6 para tolerância de ponto flutuante.

### Prazo de Pagamento
**Sinônimos:** Condição de Pagamento, Prazo
Campo `CONDICAO_PAGAMENTO` em `info_venda`. Intervalo de tempo para quitação dos títulos. Alavanca comercial — volume de compra melhora prazo e markup simultaneamente.

### Prateleira Infinita
**Sinônimos:** PI, Reposição (Pronta Entrega é nome anterior)
Canal complementar após o período de venda. Estoque já pronto no CD — entrega mais rápida. `TIPO_VENDA IN ('PRATELEIRA INFINITA', 'PRATELEIRA INFINITA - EXTERNA', 'PRONTA ENTREGA')`. Incluída apenas quando explicitamente solicitado. Cliente acessa só produtos de coleções que já comprou, com o mesmo markup da última compra.

### Faturamento Bruto
**Sinônimos:** Gross Billing, Fat Bruto
Total faturado sem deduções de devoluções. Padrão de análise.

### Faturamento Líquido
**Sinônimos:** Fat Líquido, Net Billing, Faturamento Deduzido
Faturamento Bruto deduzido do `VALOR_NF` de devoluções recebidas no mesmo período. Usado na Curva de Faturamento. Regras completas: ver §8.

### Curva de Faturamento
**Sinônimos:** Curva de Entrega, Ritmo de Faturamento, Fat Mensal
Progressão mensal do valor faturado ao longo de uma coleção. Construída com Faturamento Líquido.

### Quebra
**Sinônimos:** Break, Perda de Faturamento, Gap Venda-Fat
`Quebra = 1 – (VALOR_FATURADO / VENDA_ORIGINAL)`. Quebras internas: problema de fornecedor, falta de insumo. Quebras externas: recusa, cancelamento ou devolução pelo cliente. Regra de uso: ver §8.

### Cancelamento
**Sinônimos:** Canc, Cancel
Anulação total ou parcial de pedido antes do faturamento. Cancelamento Comercial = todos os tipos exceto `05-BLOQUEIO FINANCEIRO`. Cancelamento Financeiro = apenas `05-BLOQUEIO FINANCEIRO`. Um cliente com cancelamento financeiro está bloqueado. Exibir motivos sem prefixo numérico. Filtros SQL: ver §7.

### Devolução
**Sinônimos:** Retorno, NF de Devolução, Dev
Retorno de mercadorias já faturadas ao CD. Analisada sempre por período (`DATA_RECEBIMENTO`), não por coleção.

### Redistribuição
**Sinônimos:** Refaturar
Mercadoria devolvida refaturada para outra multimarca. Reduz a quebra. Filtros e comportamento por tabela: ver §2.

### Representante
**Sinônimos:** Rep, Representante Comercial, Vendedor Externo, NOME_WISE
Profissional externo responsável pela venda às multimarcas. Sempre referenciar pelo campo `NOME_WISE`. Associado a uma ou mais marcas e estados.

### Atendimento Interno
**Sinônimos:** Representante Interno
Representante dedicado aos key accounts (ecommerces) do Atacado. Não contabilizado em comparações com outros representantes — apenas em somatórios gerais de marca/grupo. Mesma regra se aplica aos seus clientes.

### Coordenador
**Sinônimos:** Coord, Coordenador Comercial, Gerente Comercial, Supervisor
Profissional interno que gerencia representantes externos por marca e região. Cada combinação marca × estado possui um coordenador e um representante dedicados.

### Meta
**Sinônimos:** Target, Objetivo de Vendas, Meta Financeira
Campo `META`. Atingimento = Venda / Meta. `META DESAFIO` e `META ATENDIMENTO` só sob pedido explícito.

### Meta Desafio
**Sinônimos:** Meta Estendida
Objetivo mais ambicioso que a meta padrão. Campo `META DESAFIO`. Usar apenas quando explicitamente solicitado.

### Atendimento
**Sinônimos:** Clientes Ativos, Clientes com Compra, Nº de Clientes Atendidos
`COUNT(DISTINCT CLIFOR)` com `TIPO_VENDA IN ('VENDA','PRE VENDA')`, analisado por coleção. Métrica de cobertura da carteira. SQL completo: ver §9.

### Cluster
**Sinônimos:** Porte do Cliente, Segmento de Cliente, Tier
Segmentação PP/P/M/G/GG por soma das vendas nas últimas 4 coleções (incluindo Prateleira Infinita) por marca. Thresholds por marca: ver §9.

### Cliente Novo
**Sinônimos:** New Customer, Cliente Estreante
Primeira compra exatamente na coleção em análise, sem histórico anterior. Tratado por marca salvo especificação. **Avaliação:** considerar apenas compras anteriores à coleção de referência — coleções posteriores não entram no critério.

### SCS (Same Client Sale)
**Sinônimos:** Cliente Recorrente, Compra Recorrente
Comprou na coleção em análise E na imediatamente anterior da mesma estação.

### Cliente Ativo (análise de coleção)
**Sinônimos:** Ativo, Cliente Ativo (recorrência)
Comprou em alguma das últimas 3 coleções de outras estações, mas não na imediatamente anterior. Não confundir com "ativo operacional" (compra nas últimas 4 coleções).

### Perda
**Sinônimos:** Cliente Perdido, Churn, Evasão
Comprou em pelo menos uma das 4 coleções anteriores à coleção de referência, mas **não** comprou na coleção de referência. **Avaliação:** considerar apenas compras anteriores à coleção de referência — coleções posteriores não entram no critério.
**Exemplo:** Coleção de referência = Verão 25. Se o cliente comprou em pelo menos uma das coleções Alto Inverno 2024, Inverno 2024, Alto Verão 2024 ou Verão 2024, mas não registrou nenhuma compra em Verão 25, é classificado como Perda.

> **Não confundir com** `TIPO_BLOQUEIO = 'PERDA'` em `info_financeira` (§19) — esse valor indica um status de bloqueio financeiro, não segmentação de churn de cliente.

### Resgate
**Sinônimos:** Reativação, Cliente Reativado
Voltou a comprar após ausência de mais de 4 coleções consecutivas. Deve ter histórico anterior de compras. **Avaliação:** considerar apenas compras anteriores à coleção de referência — coleções posteriores não entram no critério.

### Bloqueio Financeiro
**Sinônimos:** Bloqueio, Block, Inadimplência
`SITUACAO = 'BLOQUEADO'`. Impede novas compras em qualquer marca do grupo. Inadimplência = `SUM(VALOR_VENCIDO)` de clientes bloqueados. Regras e fórmulas SQL completas: ver §19.

### Bloqueio Comercial
**Sinônimos:** Cross-Block, Bloqueio em Cascata
Extensão automática do bloqueio financeiro de uma marca para todas as demais marcas do grupo do cliente.

### Aging
**Sinônimos:** Tempo de Bloqueio, Dias Bloqueado
`DATE_DIFF(CURRENT_DATE(), DATE(DATA_BLOQ), DAY)`. Tempo em dias desde o bloqueio.

### Embalado
**Sinônimos:** Produto Embalado, Caixa, Estoque Embalado
Produto separado e embalado no CD, aguardando despacho. `STATUS_CAIXA = 'EXPEDICAO'` = liberado para faturar.

### Caixa
**Sinônimos:** Box, Embalagem, Caixa de Expedição
Unidade física de embalagem destinada a um cliente. `CX_QUEBRADA = 1` = grade incompleta. Teto de faturamento = limite máximo faturável por semana. Abaixo do mínimo = caixa sem valor mínimo para envio.

### Grade de Tamanhos
**Sinônimos:** Grade, Size Grid, Tamanhos
Conjunto de tamanhos disponíveis (ex: PP-P-M-G-GG). Campos T1, T2… correspondem a cada posição da grade em ordem. Enviar grade completa é boa prática de faturamento.

### Afiliados
**Sinônimos:** Programa Afiliados, Affiliate Program
Multimarcas recrutam vendedores digitais. Comissão 10%: 4% ao vendedor, 5% à multimarca (crédito em títulos), 1% ao representante. Classificação de status e regras SQL: ver §21.

### Vendedora Digital
**Sinônimos:** Afiliada, Vendedor Afiliado, Programa de Vendedores
Pessoa física recrutada por multimarca para divulgar as marcas via canais digitais. Comissão de 4% sobre `venda_liquida`. Identificada por `codigo_vendedor` iniciado em `'7'`. Ativa = venda confirmada nos últimos 2 meses.

### Somaplace
**Sinônimos:** Marketplace Somaplace, Soma Marketplace, Marketplace
Multimarcas incluem produtos da coleção nos sites das marcas do grupo. Comissão variável por cliente: padrão 20% para o grupo / 80% para a multimarca. Clientes com logística via Correios pagam comissão superior — usar sempre `COMISSAO` de `cadastro_somaplace_v2`, nunca valor fixo. Pagamento todo dia 13. GMV = `SUM(VALOR_PAGO)` onde `STATUS = 'CAPTURADO'`. GMV Líquido = sem filtros (cancelados e devoluções entram negativos). Comissão calculada sobre GMV Líquido. **Cliente ativo** = cadastrado em `cadastro_somaplace_v2` + ao menos 1 transação `CAPTURADO` nos últimos 2 meses — ver §20 para queries completas e distinção ativo vs inativo.

### GMV
**Sinônimos:** Gross Merchandise Volume, Volume Bruto de Vendas
Valor bruto de vendas via Somaplace. Padrão de análise ("venda do programa"). Líquido só sob pedido explícito.

### Praça
**Sinônimos:** Cidade, Município, Local, Região de Venda
Termo comercial usado para se referir a uma **cidade**. "Praça de Friburgo" = cidade de Nova Friburgo; "praça de Curitiba" = cidade de Curitiba. Sempre interpretar "praça" como `CIDADE` em `dim_clientes_v2`. Normalizar acentos antes de comparar (ver §16 e nota de normalização de cidades em §9).

### Produto
**Sinônimos:** SKU, Item, Peça
Identificado por `PRODUTO + COR_PRODUTO`. Segmento determina submarca quando `MARCA = 'FABULA'`.

### Linha
**Sinônimos:** Linha de Produto, Product Line
Campo `LINHA` em `info_produto_v2`. Agrupamento por tipo de fabricação (ex: Malha, Denim). Análise de mix de produto.

### Segmento
**Sinônimos:** Público-Alvo, Segment
Campo `SEGMENTO` em `info_produto_v2`. Classifica submarcas dentro de Fábula: `MENINA TEEN` = FARM FUTURA; `MENINO` / `BEBE MENINO` = BENTO; demais = Fábula. Filtros SQL: ver §4.

---

## 19. Financeiro — regras de consulta (`info_financeira`)

`info_financeira` é um **snapshot atual** do status financeiro dos clientes. Não representa histórico — não filtrar por coleção nem por data de faturamento.

### Status e bloqueio

- **Bloqueado:** `SITUACAO = 'BLOQUEADO'`
- **Liberado:** `SITUACAO = 'LIBERADO'`
- O bloqueio em uma marca propaga-se a **todas as marcas do mesmo grupo econômico** — sempre consolidar por `GRUPO_ECONOMICO` quando a análise envolver impacto total.

### Valores válidos de `TIPO_BLOQUEIO` (lista exaustiva)

| Valor no banco |
|---|
| `ACORDO FINANCEIRO` |
| `BLOQUEIO PEDIDO` |
| `BLOQUEIO POR GRUPO` |
| `COBRANÇA EXTERNA` |
| `COMERCIAL` |
| `FINANCEIRO` |
| `INATIVO` |
| `LIBERADO` |
| `PERDA` |
| `REAVALIAR` |

> **Não confundir** o valor `PERDA` de `TIPO_BLOQUEIO` com a segmentação de churn "Perda" do glossário §18 — são conceitos distintos: aqui indica um status de bloqueio financeiro do cliente.
| `SOLICITAÇÃO DO REPRESENT.` |

### Inadimplência

```sql
-- Total inadimplente por marca
SELECT `MARCA`, SUM(`VALOR_VENCIDO`) AS inadimplencia
FROM `soma-dl-refined-online.atacado_processed.info_financeira`
WHERE `SITUACAO` = 'BLOQUEADO'
GROUP BY 1

-- Inadimplência + aging por cliente (grão CLIFOR × MARCA — sem GROUP BY)
SELECT `CLIFOR`, `CLIENTE`, `MARCA`,
  `VALOR_VENCIDO`                                         AS inadimplencia,
  DATE_DIFF(CURRENT_DATE(), DATE(`DATA_BLOQ`), DAY)       AS dias_bloqueado
FROM `soma-dl-refined-online.atacado_processed.info_financeira`
WHERE `SITUACAO` = 'BLOQUEADO'
```

### Aging (tempo de bloqueio)

```sql
DATE_DIFF(CURRENT_DATE(), DATE(`DATA_BLOQ`), DAY)
```

### Elegibilidade para pedido

Um cliente **só pode realizar um pedido se estiver com `SITUACAO = 'LIBERADO'`** em `info_financeira`. Clientes bloqueados não podem comprar em nenhuma marca do grupo (bloqueio em cascata via grupo econômico).

```sql
-- Clientes elegíveis para novo pedido
WHERE `SITUACAO` = 'LIBERADO'

-- Clientes impedidos
WHERE `SITUACAO` = 'BLOQUEADO'
```

> `VALOR_VENCIDO` = títulos já vencidos; `VALOR_A_VENCER` = títulos dentro do prazo. Para saldo total devedor: `VALOR_VENCIDO + VALOR_A_VENCER`.

---

## 20. Somaplace — regras de consulta

Somaplace é analisado via `venda_somaplace_v2` (transações) e `cadastro_somaplace_v2` (adesões e comissão). Sub-sistema **independente** de info_venda — não aplicar filtros de TIPO_VENDA.

### GMV

| Métrica | Definição | Filtro SQL |
|---|---|---|
| GMV Bruto (padrão) | Soma de `VALOR_PAGO` de transações capturadas | `WHERE STATUS = 'CAPTURADO'` |
| GMV Líquido | Soma de `VALOR_PAGO` sem filtro de STATUS | Sem WHERE de STATUS (cancelamentos e devoluções entram negativos) |

> Ao citar "venda do Somaplace" sem qualificação, usar **GMV Bruto**. GMV Líquido só sob pedido explícito.

### Divisão de receita

A divisão é calculada sobre o **GMV Líquido** (sem filtro de STATUS — cancelamentos e devoluções entram negativos). O percentual do grupo é definido pelo campo `COMISSAO` de `cadastro_somaplace_v2`, armazenado como inteiro (ex: `20` = 20%). Nunca usar valor fixo.

| Destinatário | Percentual | Cálculo |
|---|---|---|
| Grupo Azzas 2154 | `COMISSAO`% (padrão: 20%) | `gmv_liquido * (cs.COMISSAO / 100)` |
| Multimarca | `(100 - COMISSAO)`% (padrão: 80%) | `gmv_liquido * ((100 - cs.COMISSAO) / 100)` |

> Clientes com logística via Correios têm custo maior e pagam `COMISSAO` superior ao padrão de 20% — sempre buscar o valor da coluna, nunca assumir 20%.

```sql
-- GMV Líquido com divisão variável por COMISSAO
WITH gmv_liq AS (
  SELECT vs.`CLIFOR`, vs.`MARCA`, SUM(vs.`VALOR_PAGO`) AS gmv_liquido
  FROM `soma-dl-refined-online.atacado_processed.venda_somaplace_v2` vs
  GROUP BY 1, 2
)
SELECT
  gl.`CLIFOR`, gl.`MARCA`,
  cs.`COMISSAO`,
  gl.gmv_liquido,
  gl.gmv_liquido * ((100 - cs.`COMISSAO`) / 100) AS receita_multimarca,
  gl.gmv_liquido * (cs.`COMISSAO` / 100)          AS receita_grupo
FROM gmv_liq gl
JOIN `soma-dl-refined-online.atacado_processed.cadastro_somaplace_v2` cs
  ON gl.`CLIFOR` = cs.`CLIFOR` AND gl.`MARCA` = cs.`MARCA`
```

### Filtros de STATUS

| STATUS | Classificação | `VALOR_PAGO` na tabela |
|---|---|---|
| `'CAPTURADO'` | Venda confirmada (entra no GMV Bruto) | Positivo |
| `'CANCELADO'` | Transação cancelada (entra no GMV Líquido como dedução) | **Negativo** |
| `'DEVOLVIDO'` | Mercadoria devolvida (entra no GMV Líquido como dedução) | **Negativo** |

> `CANCELADO` e `DEVOLVIDO` têm `VALOR_PAGO` negativo na tabela. Por isso o GMV Líquido (sem filtro de `STATUS`) subtrai automaticamente cancelamentos e devoluções.

### Filtros de período

- Filtrar por `DATA` (campo TIMESTAMP) — usar `DATE(DATA)` para filtrar por dia. Não filtrar por COLECAO (usar DATA).
- `COLECAO` disponível para análise de mix, mas não é o critério de período principal.

### Cliente ativo no Somaplace

Multimarca **cadastrada** em `cadastro_somaplace_v2` que possui ao menos uma transação com `STATUS = 'CAPTURADO'` nos **últimos 2 meses** (campo `DATA` de `venda_somaplace_v2`).

> **Desambiguação:** "cliente ativo" ≠ "cliente cadastrado". Um cliente pode constar em `cadastro_somaplace_v2` sem nunca ter gerado venda — não é considerado ativo.

#### Classificação de atividade

| Classificação | Critério |
|---|---|
| **Ativo** | Cadastrado + ao menos 1 `STATUS = 'CAPTURADO'` nos últimos 2 meses |
| **Inativo** | Cadastrado + nenhuma transação `CAPTURADO` nos últimos 2 meses (inclui quem nunca vendeu) |

#### Query — contagem de clientes ativos por marca

```sql
SELECT
  cs.`MARCA`,
  COUNT(DISTINCT cs.`CLIFOR`) AS clientes_ativos
FROM `soma-dl-refined-online.atacado_processed.cadastro_somaplace_v2` cs
INNER JOIN `soma-dl-refined-online.atacado_processed.venda_somaplace_v2` vs
  ON cs.`CLIFOR` = vs.`CLIFOR` AND cs.`MARCA` = vs.`MARCA`
WHERE vs.`STATUS` = 'CAPTURADO'
  AND DATE(vs.`DATA`) >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 MONTH)
GROUP BY 1
ORDER BY 2 DESC
```

#### Query — ativo vs inativo (todos os cadastrados)

```sql
SELECT
  cs.`MARCA`,
  cs.`CLIFOR`,
  CASE
    WHEN MAX(
      CASE WHEN vs.`STATUS` = 'CAPTURADO'
                AND DATE(vs.`DATA`) >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 MONTH)
           THEN 1 ELSE 0 END
    ) = 1 THEN 'ATIVO'
    ELSE 'INATIVO'
  END AS status_atividade
FROM `soma-dl-refined-online.atacado_processed.cadastro_somaplace_v2` cs
LEFT JOIN `soma-dl-refined-online.atacado_processed.venda_somaplace_v2` vs
  ON cs.`CLIFOR` = vs.`CLIFOR` AND cs.`MARCA` = vs.`MARCA`
GROUP BY 1, 2
```

### Join cadastro → venda

```sql
FROM `soma-dl-refined-online.atacado_processed.cadastro_somaplace_v2` cs
LEFT JOIN `soma-dl-refined-online.atacado_processed.venda_somaplace_v2` vs
  ON cs.`CLIFOR` = vs.`CLIFOR` AND cs.`MARCA` = vs.`MARCA`
```

---

## 21. Afiliados — regras de consulta

Programa de afiliados analisado via `afiliados_venda_v2` (tabela central), com JOINs opcionais a `afiliados_multimarca` e `afiliados_vendedores`. Sub-sistema **independente** de info_venda.

### Classificação de status em `afiliados_venda_v2`

| Classificação | `STATUS_VENDA` | `TIPO_VENDA` |
|---|---|---|
| Venda confirmada | `'CAPTURADO'` | `'ONLINE'` |
| Devolução | `'CAPTURADO'` | `'DEVOLUÇÃO'` |
| Cancelado | `'CANCELADO'` | `'ONLINE'` |

### Venda Afiliados

O campo `VENDA_LIQUIDA` já representa o valor líquido da transação. A métrica padrão é a **Venda Líquida de Cancelamento**: soma de venda confirmada (CAPTURADO + ONLINE) e cancelamentos (CANCELADO). Devoluções (`CAPTURADO + DEVOLUÇÃO`) são excluídas por padrão e só entram quando explicitamente solicitadas.

```sql
-- Venda Líquida de Cancelamento (PADRÃO)
SELECT SUM(`VENDA_LIQUIDA`) AS venda_liquida_cancelamento
FROM `soma-dl-refined-online.atacado_processed.afiliados_venda_v2`
WHERE (`STATUS_VENDA` = 'CAPTURADO' AND `TIPO_VENDA` = 'ONLINE')
   OR `STATUS_VENDA` = 'CANCELADO'

-- Apenas venda confirmada (sob pedido explícito)
SELECT SUM(`VENDA_LIQUIDA`) AS venda_confirmada
FROM `soma-dl-refined-online.atacado_processed.afiliados_venda_v2`
WHERE `STATUS_VENDA` = 'CAPTURADO' AND `TIPO_VENDA` = 'ONLINE'

-- Incluindo devoluções (sob pedido explícito)
SELECT SUM(`VENDA_LIQUIDA`) AS venda_liquida_com_devolucao
FROM `soma-dl-refined-online.atacado_processed.afiliados_venda_v2`
WHERE `STATUS_VENDA` = 'CAPTURADO'  -- inclui ONLINE e DEVOLUÇÃO
```

### Estrutura de comissão

| Beneficiário | Percentual |
|---|---|
| Vendedor digital | 4% sobre venda líquida |
| Multimarca | 5% sobre venda líquida (crédito para abater títulos a vencer) |
| Representante | 1% sobre venda líquida |
| **Total** | **10%** |

> A comissão da multimarca (5%) é creditada como abatimento de títulos a vencer — reduz inadimplência potencial.

```sql
SUM(`VENDA_LIQUIDA`) * 0.04 AS comissao_vendedor,
SUM(`VENDA_LIQUIDA`) * 0.05 AS comissao_multimarca,
SUM(`VENDA_LIQUIDA`) * 0.01 AS comissao_representante
```

### Identificação de vendedor digital

`CODIGO_VENDEDOR` iniciado em `'7'` identifica vendedoras digitais:

```sql
WHERE `CODIGO_VENDEDOR` LIKE '7%'
```

### Definição de ativo

| Entidade | Critério de ativo |
|---|---|
| Vendedor digital | Venda confirmada nos **últimos 2 meses** — `DATE(DATA) >= DATE_SUB(CURRENT_DATE(), INTERVAL 2 MONTH)` |
| Multimarca (cliente) | Venda confirmada nos **últimos 2 meses** |

### Regras de PII

`CPF_CLIENTE` em `afiliados_venda_v2` e `cpf_vendedor`, `nome_vendedor` em `afiliados_vendedores` são 🔴 PII — **nunca incluir no SELECT**.

```sql
-- ✅ Seguro
SELECT av.`CLIFOR`, av.`MARCA`, av.`CODIGO_VENDEDOR`,
       av.`ESTADO`, av.`CIDADE`, SUM(av.`VENDA_LIQUIDA`) AS venda_total
FROM `soma-dl-refined-online.atacado_processed.afiliados_venda_v2` av
GROUP BY 1, 2, 3, 4, 5

-- ✅ Seguro — afiliados_vendedores
SELECT avd.`codigo_vendedor`, avd.`clifor`, avd.`data_cadastro`, avd.`data_desligamento`

-- ❌ Proibido
-- SELECT av.`CPF_CLIENTE`           -- PII em afiliados_venda_v2
-- SELECT avd.`cpf_vendedor`, avd.`nome_vendedor`  -- PII em afiliados_vendedores
```

### Padrão de JOIN

```sql
FROM `soma-dl-refined-online.atacado_processed.afiliados_venda_v2` av
LEFT JOIN `soma-dl-refined-online.atacado_processed.afiliados_multimarca` am
  ON av.`CLIFOR` = am.`CLIFOR` AND av.`MARCA` = am.`MARCA`
LEFT JOIN `soma-dl-refined-online.atacado_processed.afiliados_vendedores` avd
  ON av.`CODIGO_VENDEDOR` = avd.`codigo_vendedor`
```

### Filtro de pedidos cancelados

Pedidos cancelados possuem `STATUS_VENDA = 'CANCELADO'` com `TIPO_VENDA = 'ONLINE'` — `CANCELADO` nunca ocorre com `TIPO_VENDA = 'DEVOLUÇÃO'`. O filtro por `STATUS_VENDA` é suficiente:

```sql
-- Apenas cancelamentos
SELECT FORMAT_DATE('%Y-%m', DATE(`DATA`)) AS mes,
       `MARCA`,
       `CLIFOR`,
       COUNT(DISTINCT `PEDIDO`) AS qtd_pedidos_cancelados,
       SUM(`VENDA_LIQUIDA`) AS valor_cancelado
FROM `soma-dl-refined-online.atacado_processed.afiliados_venda_v2`
WHERE `STATUS_VENDA` = 'CANCELADO'
GROUP BY 1, 2, 3
ORDER BY 1 DESC

-- Taxa de cancelamento: cancelados ÷ total de pedidos capturados
SELECT `MARCA`,
       COUNTIF(`STATUS_VENDA` = 'CANCELADO') AS qtd_cancelados,
       COUNTIF(`STATUS_VENDA` = 'CAPTURADO' AND `TIPO_VENDA` = 'ONLINE') AS qtd_confirmados,
       SAFE_DIVIDE(
         COUNTIF(`STATUS_VENDA` = 'CANCELADO'),
         COUNTIF(`STATUS_VENDA` = 'CAPTURADO' AND `TIPO_VENDA` = 'ONLINE')
       ) AS taxa_cancelamento
FROM `soma-dl-refined-online.atacado_processed.afiliados_venda_v2`
GROUP BY 1
```

> Não confundir com devolução (`STATUS_VENDA = 'CAPTURADO' AND TIPO_VENDA = 'DEVOLUÇÃO'`): cancelamento ocorre antes da entrega; devolução ocorre após. São sempre mutuamente exclusivos nos dados — nenhum registro tem `STATUS_VENDA = 'CANCELADO' AND TIPO_VENDA = 'DEVOLUÇÃO'`.

### Vendedores desligados

`data_desligamento IS NOT NULL` → vendedor saiu do programa. Excluir de análises de ativos:

```sql
WHERE avd.`data_desligamento` IS NULL
```

---

## 22. Farm Etc — canal Pacific vs Interna

> ⚠️ Esta análise é **exclusiva de `MARCA = 'FARM ETC'`** e **só deve ser executada quando explicitamente solicitada** — ex: *"venda de Farm Etc com quebra entre venda Pacific e venda Interna"*. Nunca aplicar automaticamente ou em outras marcas.

O número do pedido Wise (`PEDIDO_WISE` em `info_venda`) identifica o canal de venda da Farm Etc:

| Classificação | Critério | Descrição |
|---|---|---|
| **PACIFIC** | `PEDIDO_WISE LIKE 'PC%'` | Pedido originado pelo canal Pacific |
| **INTERNA** | `PEDIDO_WISE NOT LIKE 'PC%'` | Pedido originado pelo canal interno |

```sql
SELECT
  CASE WHEN v.`PEDIDO_WISE` LIKE 'PC%' THEN 'PACIFIC' ELSE 'INTERNA' END AS canal_venda,
  SUM(v.`VENDA_LIQUIDA`) AS venda_liquida
FROM `soma-dl-refined-online.atacado_processed.info_venda` v
WHERE v.`MARCA` = 'FARM ETC'
  AND v.`TIPO_VENDA` IN ('VENDA', 'PRE VENDA')
  AND v.`VENDA_ORIGINAL` > 0
  AND v.`COLECAO` = '<COLECAO>'
GROUP BY 1
ORDER BY 2 DESC
```

---

## 23. E-commerce — regras de consulta (`info_ecommerce`)

> ❌ **Usar esta tabela somente quando o usuário escrever literalmente "ecommerce" ou "e-commerce" na solicitação. Nenhum sinônimo, inferência ou contexto substitui essa menção explícita. Não usar para análises de ciclo de venda, afiliados ou Somaplace por iniciativa própria.**

### STATUS_EVENTO

| Classificação | `STATUS_EVENTO` | Descrição |
|---|---|---|
| Venda confirmada | `'CAPTURADO'` | Evento efetivado |
| Cancelado | `'CANCELADO'` | Evento cancelado |

> ⚠️ **Diferença de nomenclatura em relação a `afiliados_venda_v2`:** o campo de status aqui é `STATUS_EVENTO` (não `STATUS_VENDA`). Devoluções são `TIPO_VENDA = 'DEVOLUCAO'` sem acento (diferente de `'DEVOLUÇÃO'` com acento em `afiliados_venda_v2`). Não reutilizar filtros entre as duas tabelas sem ajustar nome do campo e grafia.

### TIPO_VENDA

| Valor | Descrição |
|---|---|
| `'ONLINE'` | Venda realizada por canal digital |
| `'FISICO'` | Compra realizada em loja física — indica presença de ponto de venda na cidade do cliente |
| `'DEVOLUCAO'` | Devolução de item |

```sql
-- Apenas loja física
WHERE `TIPO_VENDA` = 'FISICO'

-- Apenas venda online
WHERE `TIPO_VENDA` = 'ONLINE'

-- Excluir devoluções
WHERE `TIPO_VENDA` != 'DEVOLUCAO'
```

### Identificação de transação única

Não há coluna `PEDIDO` nesta tabela. Transações únicas são identificadas pela combinação `PRODUTO + COR_PRODUTO + DATE(DATA) + CPF + STATUS_EVENTO + TIPO_VENDA`.

### COLECAO

Não disponível como coluna direta — obter via join com `info_produto_v2` usando `PRODUTO + COR_PRODUTO`.

### PROGRAMA_VENDEDOR — classificação de canal

| Critério | Classificação | Relação |
|---|---|---|
| `PROGRAMA_VENDEDOR = 'MULTIMARCA'` | **AFILIADO (ATACADO)** | Vendedor do programa de afiliados — relacionado ao atacado |
| `PROGRAMA_VENDEDOR IS NOT NULL` (outro valor) | **VAREJO** | Vendedor do canal varejo |
| `PROGRAMA_VENDEDOR IS NULL` | **SEM VENDEDOR** | Venda sem vendedor associado |

Ver SQL de classificação em `schema.md §17`.

> Vendas com `PROGRAMA_VENDEDOR = 'MULTIMARCA'` também estão registradas em `afiliados_venda_v2`. Para qualquer análise do programa de afiliados, usar sempre `afiliados_venda_v2` — não `info_ecommerce`.

### Métrica padrão

`SUM(VALOR_PAGO)` com `STATUS_EVENTO = 'CAPTURADO'` e `TIPO_VENDA != 'DEVOLUCAO'` — equivalente ao GMV Bruto. Devoluções (`TIPO_VENDA = 'DEVOLUCAO'`) são excluídas por padrão e só entram quando explicitamente solicitadas.

```sql
SELECT
  `MARCA`,
  `TIPO_VENDA`,
  SUM(`VALOR_PAGO`) AS receita
FROM `soma-dl-refined-online.atacado_processed.info_ecommerce`
WHERE `STATUS_EVENTO` = 'CAPTURADO'
  AND `TIPO_VENDA` != 'DEVOLUCAO'
  AND DATE(`DATA`) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2
ORDER BY 3 DESC
```

### Análise por cidade / estado

`CIDADE` e `ESTADO` permitem cruzar presença geográfica com outras análises (loja física, produto vendido por região). Normalizar `CIDADE` removendo acentos e ç antes de comparar (mesma regra de `business-rules.md §16`).

```sql
SELECT
  `ESTADO`, `CIDADE`,
  COUNT(*) AS qtd_eventos,
  SUM(`VALOR_PAGO`) AS receita
FROM `soma-dl-refined-online.atacado_processed.info_ecommerce`
WHERE `STATUS_EVENTO` = 'CAPTURADO'
GROUP BY 1, 2
ORDER BY 4 DESC
```

### Regra de PII

`CPF` é 🔴 PII — **nunca incluir no SELECT**. Usar apenas para COUNT(DISTINCT) quando necessário contar clientes únicos, sem expor o valor.

```sql
-- ✅ Seguro — contagem sem expor CPF
SELECT COUNT(DISTINCT `CPF`) AS clientes_unicos
FROM `soma-dl-refined-online.atacado_processed.info_ecommerce`
WHERE `STATUS_EVENTO` = 'CAPTURADO'

-- ❌ Proibido
-- SELECT `CPF`, `VALOR_PAGO` FROM info_ecommerce
```

---

## Histórico de atualizações

| Data | Mudança |
|---|---|
| 2026-04-29 | Criação — regras extraídas do documento "Gemini & Azzas 2154" e especificações de schema. |
| 2026-04-29 | Enriquecimento com contexto de negócio (Afiliados, Somaplace, Prateleira Infinita, ciclo operacional) e fluxo obrigatório de capilaridade. |
| 2026-04-30 | Adição de §19–§21 (Financeiro, Somaplace, Afiliados). Revisão: correção de VALOR VENCIDO → VALOR_VENCIDO; GROUP BY inválido no aging; referência §9→§19 para bloqueio; sinônimos duplicados em glossário; tool `calculate` inexistente removida; Somaplace adicionado às exceções de filtro por data; terminologia GMV Afiliados corrigida para Venda Afiliados. |
| 2026-05-04 | PRATELEIRA INFINITA - EXTERNO → EXTERNA (nomenclatura correta). Adição: FARM FUTURA iniciada no VERÃO 2026; FÁBULA e FARM PRAIA fora do ALTO INVERNO; regra de pulo de coleção; interpretação de "coleções de um ano"; janela de avaliação de Novo/Resgate (apenas coleções anteriores à referência). |
| 2026-05-07 | Adição: "praça" como sinônimo de cidade (§18 Glossário); regra de validação com o usuário ao encontrar nome de cliente aproximado em vez de exato (§1.3). |
| 2026-05-12 | §20 Somaplace: expansão do conceito de cliente ativo — distinção cadastrado vs ativo vs inativo; queries completas de contagem e classificação adicionadas. Glossário §18 Somaplace atualizado com referência a §20. |
| 2026-05-12 | §21 Afiliados: métrica padrão alterada para Venda Líquida de Cancelamento (CAPTURADO+ONLINE + CANCELADO). Devoluções excluídas por padrão — entram só sob pedido explícito. SKILL.md atualizado para refletir novo padrão. |
| 2026-05-13 | Revisão geral: §4 FARM FUTURA com instrução para consultas anteriores ao VERÃO 2026; §9 Resgate uniformizado para "coleções"; §9 Cluster esclarece inclusão da coleção de referência; "Cliente Ativo (recorrência)" renomeado para "análise de coleção"; desambiguação de "ativo" expandida para Somaplace/Afiliados; §18 Faturamento Líquido adicionado ao glossário; desambiguação de "Perda" vs TIPO_BLOQUEIO em §18 e §19; labels de anti-hallucination uniformizados com SKILL.md. |
| 2026-05-13 | §21 Afiliados: `afiliados_vendas` migrado para `afiliados_venda_v2`; grão alterado para pedido × produto × cor_produto; `DATA` (TIMESTAMP) substitui `mes_venda`/`ano_venda`; colunas em MAIÚSCULA; `CPF_CLIENTE` (🔴 PII) adicionado; regra de ativo atualizada para `DATE(DATA)`; filtro de pedidos cancelados documentado com queries de isolamento e taxa de cancelamento. |
| 2026-05-13 | §20 Somaplace: `cadastro_somaplace` migrado para `cadastro_somaplace_v2`; nova coluna `COMISSAO` (FLOAT, inteiro — ex: 20 = 20%); divisão de receita atualizada de 80%/20% fixo para variável via `cs.COMISSAO / 100`; todas as queries do §20 atualizadas; glossário Somaplace atualizado. |
| 2026-05-14 | Revisão de gaps/ambiguidades/duplicidades em ecommerce. §20: DATA corrigido para TIMESTAMP; CANCELADO e DEVOLVIDO documentados como VALOR_PAGO negativo na tabela de STATUS. §21: CANCELADO restrito a TIPO_VENDA='ONLINE' (nunca 'DEVOLUÇÃO'); CANCELADO+DEVOLUÇÃO confirmados como mutuamente exclusivos. §23: SQL de PROGRAMA_VENDEDOR removido (ver schema.md §17); TIPO_VENDA FISICO contextualizado; seções "Identificação de transação única" e "COLECAO" adicionadas; nota sobre overlap info_ecommerce×afiliados_venda_v2; alerta de nomenclatura STATUS_EVENTO/DEVOLUCAO vs STATUS_VENDA/DEVOLUÇÃO. schema.md §17: mesmas adições + regra de literalidade alinhada. SKILL.md: regra de literalidade alinhada com business-rules.md §23. |
