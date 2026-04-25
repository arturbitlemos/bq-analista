# Schema Reference — Azzas 2154 BigQuery (Linx silver)

> Living doc. Atualize depois de cada sessão onde descobrir tabelas, colunas ou valores novos.

**Dataset principal:** `soma-pipeline-prd.silver_linx`
**Todas as tabelas são EXTERNAL** — não há partitioning nativo. Filtre sempre pelas colunas `DATA_*` correspondentes para controlar scan. Todas carregam 4 colunas de CDC no fim (`pk_merge`, `op`, `data_cdc`, `ts_ms`) — ignore-as em análise.

---

## 1. Vendas — `TB_WANMTP_VENDAS_LOJA_CAPTADO`

**Full path:** `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO`
**Grão:** 1 linha por item vendido (produto × cor × tamanho × ticket × filial).
**Data column:** `DATA_VENDA` (DATE).

### Colunas por categoria

**Datas**
| Coluna | Tipo | Uso |
|---|---|---|
| `DATA_VENDA` | DATE | ✅ **Filtro padrão** — data da venda |
| `DATA_VENDA_RELATIVA` | DATE | Data ajustada p/ comparativo (ano anterior etc.) |
| `DATA_VENDA_TICKET` | DATE | Data do ticket (p/ FISICO) |
| `DATA_DIGITACAO` | DATE | Data em que a venda foi digitada no sistema |
| `DATA_DESATIVACAO` | DATE | Data de desativação (cancelamento) |

**Identificação da venda**
| Coluna | Tipo | Uso |
|---|---|---|
| `TICKET` | STRING | ID do ticket — canônico p/ transação FISICO |
| `ITEM_VENDA` | INTEGER | Sequencial do item no ticket |
| `PEDIDO_SITE` | STRING | ID do pedido ecom (quando aplicável) |
| `OPERACAO_VENDA` | STRING | Tipo operação (venda, devolução, troca…) |
| `TIPO_VENDA` | STRING | Canal primário — valores: `VENDA_LOJA`, `VENDA_ECOM`, `VENDA_OMNI`, `VENDA_VITRINE` |
| `SUB_TIPO_VENDA` | STRING | Sub-canal — valores: `VENDA_FISICA`, `VENDA_ECOM`, `VENDA_VITRINE`, `ATEND_OMNI`, `ATEND_OMNI_PICKUP`, `DEV_ATEND_OMNI` |

**Produto**
| Coluna | Tipo | Uso |
|---|---|---|
| `PRODUTO` | STRING | Código do produto — FK p/ PRODUTOS, PRODUTOS_PRECOS, PRODUTO_CORES |
| `COR_PRODUTO` | STRING | Código da cor — FK (PRODUTO + COR_PRODUTO) p/ PRODUTO_CORES |
| `TAMANHO` | INTEGER | Índice posicional do tamanho (1..N) — resolver via PRODUTOS_TAMANHOS |
| `CODIGO_BARRA` | STRING | EAN |

**Filial / rede (vários contextos)**
O modelo Linx traz até 5 pares `RL_xxx + FILIAL_xxx + CODIGO_FILIAL_xxx`:
| Contexto | Código | Texto | Rede |
|---|---|---|---|
| Atendimento | `CODIGO_FILIAL_ATEND` | `FILIAL_ATEND` | `RL_ATEND` |
| Faturamento | `CODIGO_FILIAL_FAT` | `FILIAL_FAT` | `RL_FAT` |
| Origem (estoque) | `CODIGO_FILIAL_ORIGEM` | `FILIAL_ORIGEM` | `RL_ORIGEM` |
| Destino | `CODIGO_FILIAL_DESTINO` | `FILIAL_DESTINO` | `RL_DESTINO` |
| Vendedor | `CODIGO_FILIAL_VENDEDOR` | `FILIAL_VENDEDOR` | `RL_VENDEDOR` |

Indicadores ecom por contexto: `INDICA_ORIGEM_ECOM`, `INDICA_DESTINO_ECOM`, `INDICA_FAT_ECOM`, `INDICA_VENDEDOR_ECOM`, `INDICA_PEDIDO_VITRINE`.

**Default para análise de venda em loja:** usar `CODIGO_FILIAL_DESTINO` / `RL_DESTINO` (loja de destino da venda). Só use FAT, VENDEDOR, ATEND ou ORIGEM quando **explicitamente solicitado** — nunca assuma.

> ⚠️ `RL_DESTINO` é INTEGER (não STRING como `RL_ORIGEM`/`RL_FAT`/`RL_ATEND`). Ao joinar com `LOJAS_REDE.REDE_LOJAS` (STRING), use `CAST(v.RL_DESTINO AS STRING) = lr.REDE_LOJAS`.

**Valores**
| Coluna | Tipo | Descrição |
|---|---|---|
| `VALOR_PAGO_PROD` | BIGNUMERIC | ✅ **Venda líquida** (pós-desconto) — métrica padrão |
| `PRECO_LIQUIDO_PROD` | NUMERIC | Preço unitário líquido |
| `DESCONTO_PROD` | BIGNUMERIC | Desconto aplicado — **armazenado NEGATIVO** (validado 2026-04-18: ~99% negativo ou zero, min −9995, max 1398) |
| `QTDE_PROD` | INTEGER | Unidades |
| `QTDE_TROCA_PROD` | INTEGER | Unidades de troca |
| `QTDE_VALE_RECEBIDO` | INTEGER | Unidades recebidas como vale |
| `CODIGO_TAB_PRECO` | STRING | Tabela de preço usada no momento da venda |

> **CMV / margem de contribuição** não estão nesta tabela. Para margem, joinar com `PRODUTOS_PRECOS` (tabela CT) pelo PRODUTO e calcular `VALOR_PAGO_PROD - QTDE_PROD * PRECO_CUSTO`.

**🔴 PII — NÃO selecionar**
| Coluna | Motivo |
|---|---|
| `CODIGO_CLIENTE` | ID individual do cliente |
| `VENDEDOR`, `VENDEDOR_ATEND`, `VENDEDOR_AFILIADO` | Matrícula / identificador de funcionário |
| `GERENTE_LOJA` | Identificador de funcionário |

**✅ Categóricos (não-PII, validado 2026-04-18):**
| Coluna | Cardinalidade | Natureza |
|---|---|---|
| `PERFIL_VENDEDOR` | 14 | Cargo operacional: CAIXA, VENDEDOR, GERENTE DA LOJA, BACKOFFICE, ESTOQUISTA, LOGÍSTICA, ATEND ECOMMERCE, ADORO CODIGO, OUTROS, etc. |
| `DESC_CARGO` | >30 | Títulos de cargo genéricos (ANALISTA DE X, ASSISTENTE DE Y, APRENDIZ…) — sem nomes próprios |
| `SELLER` | 16 | Instância de marketplace: `VTEX - LOJAFARM`, `VTEX - BYNV`, `VTEX - LOJAANIMALE`, `VTEX - LOJAOFFPREMIUM`, `VTEX - MARIAFILO`, `VTEX - CAROLBASSI`, `VTEX - LOJAFABULA`, `VTEX - FOXTON`, `VTEX - LOJACRISBARROS`, `UNICO VITRINE`, `VTEX - GALLERIST`, `VTEX - BYNVINT`, `VTEX - BABADOTOP`, `SSIM` |

> `OPERACAO_VENDA` tem ~55 códigos mas não é campo relevante para análise — **ignorar**.

### Filtros críticos — **ainda em construção**

- **Excluir marketplace externo**: candidatos visíveis — `SELLER` contém instâncias VTEX internas (sites próprios) e externas (`SSIM`, `UNICO VITRINE`, `VTEX - GALLERIST`, `VTEX - BABADOTOP`). Regra definitiva depende da decisão de canal (pendência §10.1).
- **Escopo de data obrigatório**: sempre `DATA_VENDA BETWEEN ... AND ...`.

---

## 2. Produto — dimensão

### 2.1 `PRODUTOS` (master do produto)

**Full path:** `soma-pipeline-prd.silver_linx.PRODUTOS`
**Chave:** `PRODUTO` (STRING).

Colunas-chave (há ~180 no total — lista abaixo é o que importa para análise comercial):

| Coluna | Tipo | Uso |
|---|---|---|
| `PRODUTO` | STRING | Código do produto (PK) |
| `DESC_PRODUTO` | STRING | Descrição |
| `COLECAO` | STRING | Coleção |
| `ANM_MARCA` | STRING | Marca (texto) |
| `ANM_TIPO_PRODUTO` | STRING | Tipo (vestido, blusa…) |
| `REDE_LOJAS` | STRING | Rede do produto |
| `CATEGORIA_B2C` / `SUBCATEGORIA_B2C` | INTEGER | Hierarquia B2C |
| `GRUPO_PRODUTO` / `SUBGRUPO_PRODUTO` | STRING | Hierarquia gerencial |
| `LINHA` | STRING | Linha |
| `MODELAGEM` | STRING | Modelagem |
| `MODELO` | STRING | Modelo |
| `COMPRADORA` | STRING | Compradora responsável |
| `ESTILISTA` / `MODELISTA` | STRING | Responsáveis de desenvolvimento |
| `STATUS_PRODUTO` | STRING | Status atual |
| `TIPO_STATUS_PRODUTO` | INTEGER | Código do status |
| `DATA_CADASTRAMENTO` | DATE | Data de cadastro |
| `DATA_INICIO_DESENVOLVIMENTO` | DATE | Início de desenvolvimento |
| `ANM_DT_INI_VENDA_ECOM` / `ANM_DT_FIM_VENDA_ECOM` | DATE | Janela de venda ecom |
| `GRADE` | STRING | Código da grade (FK p/ PRODUTOS_TAMANHOS) |
| `CARTELA` | STRING | Cartela |
| `UNIDADE` | STRING | Unidade |
| `INATIVO` | INTEGER | 1 = inativo |

**Preços de reposição também estão aqui** (4 faixas cada): `CUSTO_REPOSICAO1..4`, `PRECO_REPOSICAO_1..4`, `PRECO_A_VISTA_REPOSICAO_1..4` — todos NUMERIC. ⚠️ Para preço de venda efetivo, preferir `PRODUTOS_PRECOS`.

### 2.2 `PRODUTOS_PRECOS` (preços por tabela)

**Chave:** `(PRODUTO, CODIGO_TAB_PRECO)`.

| Coluna | Tipo | Uso |
|---|---|---|
| `PRODUTO` | STRING | FK |
| `CODIGO_TAB_PRECO` | STRING | Tabela (ver códigos abaixo) |
| `PRECO1..PRECO4` | STRING | ⚠️ Armazenado como STRING — usar `SAFE_CAST(PRECO1 AS NUMERIC)` |
| `PRECO_LIQUIDO1..4` | STRING | Idem |
| `MARK_UP_PREVISTO` | STRING | Markup previsto (STRING → cast) |
| `INICIO_PROMOCAO` / `FIM_PROMOCAO` | INTEGER | Janela de promoção |
| `LIMITE_DESCONTO` | STRING | Limite de desconto |

**Códigos de tabela de preço relevantes (`CODIGO_TAB_PRECO`):**
| Código | Significado |
|---|---|
| `CT` | CUSTO (preço de custo) |
| `VO` | VAREJO ORIGINAL (preço "de") |
| `V` | VAREJO (preço "por") |

> Para cálculo de margem: joinar a venda com preço `CT` (custo) e calcular `VALOR_PAGO_PROD - QTDE_PROD * preco_custo`. Para desconto vs tabela: comparar `PRECO_LIQUIDO_PROD` com `V` (varejo "por") ou `VO` (varejo "de").

### 2.3 `PRODUTO_CORES` (cores do produto)

**Chave:** `(PRODUTO, COR_PRODUTO)`.

| Coluna | Tipo | Uso |
|---|---|---|
| `PRODUTO` | STRING | FK |
| `COR_PRODUTO` | STRING | Código da cor (PK parcial) |
| `COR` | STRING | Código interno de cor |
| `DESC_COR_PRODUTO` | STRING | ✅ Descrição textual da cor |
| `COR_COLECAO` | STRING | Cor por coleção |
| `COR_FABRICANTE` | STRING | Referência do fabricante |
| `COR_MATERIAL` / `MATERIAL` | STRING | Material |
| `COR_RGB` | INTEGER | RGB numérico |
| `STATUS_VENDA_ATUAL` | STRING | Status atual da cor |
| `GS_CURVA_ABC` | STRING | Curva ABC da cor |
| `GS_FAIXA_PRECO` | STRING | Faixa de preço |
| `GS_CANAL_VENDA` | STRING | Canal |
| `GS_ETAPA` | STRING | Etapa de venda |
| `COTA_VENDA` | STRING | Cota de venda (STRING → cast se numérico) |
| `INICIO_VENDAS` / `FIM_VENDAS` | INTEGER | Janela de vendas |
| `PATH_FOTO_COR` | STRING | Caminho da imagem |

### 2.4 `PRODUTOS_TAMANHOS` (grade → posição → tamanho)

**Chave:** `GRADE` (ou `GRADE_CODIGO`).

Esta tabela é um **lookup posicional**: cada linha é uma grade com até 48 posições (`TAMANHO_1`, `TAMANHO_2`, …, `TAMANHO_48`) que mapeiam o índice numérico para o label do tamanho (ex.: `TAMANHO_3 = "M"`).

| Coluna | Tipo | Uso |
|---|---|---|
| `GRADE` / `GRADE_CODIGO` / `GRADE_BASE` | STRING | Identificadores |
| `NUMERO_TAMANHOS` | INTEGER | Quantos tamanhos a grade tem |
| `TAMANHOS_DIGITADOS` | INTEGER | idem |
| `TAMANHO_1`…`TAMANHO_48` | STRING | Label por posição |
| `NUMERO_QUEBRAS` | INTEGER | Nº de quebras da grade |
| `QUEBRA_1..5` | STRING | Quebras (bloco de tamanhos) |
| `INATIVO` | BOOLEAN | |

**Para resolver tamanho em venda:** join `PRODUTOS.GRADE` → `PRODUTOS_TAMANHOS.GRADE`, depois usar o índice `VENDAS.TAMANHO` (1..48) para selecionar a coluna correta. O mesmo vale para `ANMN_ESTOQUE_HISTORICO_PROD_GRADE.T1..T10`.

---

## 3. Rede / Marca — `LOJAS_REDE`

**Full path:** `soma-pipeline-prd.silver_linx.LOJAS_REDE`
**Chave:** `REDE_LOJAS` (STRING).

| Coluna | Tipo | Uso |
|---|---|---|
| `REDE_LOJAS` | STRING | Código da rede |
| `DESC_REDE_LOJAS` | STRING | ✅ Nome da marca |
| `REDE_SIGLA` | STRING | Sigla |
| `ANM_SEQUENCIAL` | STRING | Sequencial interno |

**Uso:** de-para de `RL_DESTINO` (default) / `RL_FAT` / `RL_ORIGEM` / etc. da venda para nome da marca.

> ⚠️ Note que no modelo Linx `RL_*` em vendas aparece como STRING (em RL_ATEND, RL_FAT, RL_ORIGEM) ou INTEGER (RL_DESTINO, RL_VENDEDOR). Cast consistente pode ser necessário no JOIN.

---

## 4. Filial — `FILIAIS`

**Full path:** `soma-pipeline-prd.silver_linx.FILIAIS`

**⚠️ Convenção de chaves (validada 2026-04-18 — duas armadilhas):**

**Armadilha 1 — `FILIAL` não é código.**
- `FILIAL` (STRING) = **NOME** da loja em texto (ex.: `"ANIMALE ALPHAVILLE CM"`, `"2 ALIANÇAS"`). Mesmo formato usado em `LOJAS_PREVISAO_VENDAS.FILIAL` e `ANMN_ESTOQUE_HISTORICO_PROD.FILIAL`.
- `COD_FILIAL` (STRING) = **código numérico** 4–6 dígitos (ex.: `"550317"`, `"802083"`).

**Armadilha 2 — `COD_FILIAL` ≠ `CODIGO_FILIAL_*`.**
Os nomes dos campos são diferentes entre tabelas (fácil de digitar errado no SQL):

| Tabela | Campo-código | Campo-nome |
|---|---|---|
| `FILIAIS` | `COD_FILIAL` (abreviado) | `FILIAL` |
| `TB_WANMTP_VENDAS_LOJA_CAPTADO` | `CODIGO_FILIAL_ORIGEM` / `_FAT` / `_ATEND` / `_DESTINO` / `_VENDEDOR` (completo com sufixo) | `FILIAL_ORIGEM` / `FILIAL_FAT` / … |
| `LOJAS_PREVISAO_VENDAS` | — (só nome) | `FILIAL` |
| `ANMN_ESTOQUE_HISTORICO_PROD*` | — (só nome) | `FILIAL` |

Os **valores** batem (ex.: `"550317"`), mas os **nomes de coluna** são distintos. Sempre conferir antes de escrever o JOIN: `v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL` (default), nunca `v.COD_FILIAL` nem `f.CODIGO_FILIAL`.
- **2.157 filiais** no cadastro total.

**Regras de join (cola):**
- vendas (`CODIGO_FILIAL_DESTINO`, default) → FILIAIS.`COD_FILIAL`
- cota (`LOJAS_PREVISAO_VENDAS.FILIAL`) → FILIAIS.`FILIAL` (nome = nome)
- estoque (`ANMN_ESTOQUE_HISTORICO_PROD.FILIAL`) → FILIAIS.`FILIAL` (nome = nome)
- Para juntar vendas com cota ou estoque, **sempre passar por FILIAIS** (código ↔ nome).

**Armadilha 3 — sufixos de CNPJ: mesma loja, CNPJs distintos.**

Os sufixos no final do nome de uma filial indicam sob qual CNPJ (empresa contábil) ela está registrada. **Operacionalmente são a mesma loja** — foram migradas ao longo do tempo por estratégia fiscal:

| Sufixo | Significado | Período |
|---|---|---|
| `CM` | Cidade Maravilhosa (CNPJ original) | anterior à incorporação |
| `SB` | Soma Brands (CNPJ pós-incorporação) | após migração para Soma Brands |
| `HRG` | outro CNPJ do grupo | ativo em paralelo |
| `RBX` | CNPJ legado | geralmente fechado (DATA_FECHAMENTO preenchida) |

Exemplos: `FARM ECOMMERCE CM`, `FARM ECOMMERCE SB` e `FARM ECOMMERCE HRG` são **o mesmo canal de ecommerce da FARM** sob CNPJs diferentes.

**Consequência para análise:**
- Nunca tratar CM × SB × HRG como lojas distintas para fins comerciais.
- Para análise de venda/cota/estoque, **sempre agregar pelo nome-base** (sem sufixo) ou pelo `REDE_LOJAS` (código de marca).
- Ao longo do tempo, a mesma loja pode mudar de `COD_FILIAL` ao migrar de CNPJ — filtrar por `DATA_FECHAMENTO IS NULL` pega só o CNPJ ativo, mas o histórico pode estar no CNPJ anterior.
- Para séries históricas longas (>1 ano), incluir todos os sufixos conhecidos ou filtrar por `REDE_LOJAS`.

Colunas-chave:

| Coluna | Tipo | Uso |
|---|---|---|
| `FILIAL` | STRING | **NOME** da loja (PK texto) |
| `COD_FILIAL` | STRING | **Código numérico** (PK para join com vendas) |
| `REDE_LOJAS` | STRING | FK → LOJAS_REDE |
| `REGIAO` | STRING | Região comercial |
| `REGIAO_SUPERVISAO` | STRING | Supervisão |
| `TIPO_FILIAL` | STRING | Tipo da filial — valores conhecidos abaixo |
| `FILIAL_PROPRIA` | BOOLEAN | Própria (true) vs franquia (false) |
| `INDICA_FRANQUIA` | BOOLEAN | Flag franquia |
| `INDICA_ARMAZEM` | BOOLEAN | Flag CD |
| `MATRIZ` / `MATRIZ_CONTROLADORA` / `MATRIZ_FISCAL` | STRING | Hierarquia |
| `DATA_ABERTURA` / `DATA_FECHAMENTO` | DATE | Ciclo de vida |
| `AREA_M2` | INTEGER | Área da loja |
| `EMPRESA` | INTEGER | Empresa contábil |
| `REGIME_TRIBUTACAO` / `TIPO_TRIBUTACAO` | INT/STR | Fiscal |

**Valores de `TIPO_FILIAL` (validados em produção):**

| Valor | Significado | Entra em análise de venda? |
|---|---|---|
| `LOJA VAREJO` | Loja física de varejo ✅ | Sim — default para análise de lojas |
| `FRANQUIA` | Loja franqueada | Depende — ver `INDICA_FRANQUIA` e `FILIAL_PROPRIA` |
| `MATRIZ` | Escritório / sede | Não |
| `CDS` / `CD` | Centro de distribuição | Não |
| `ATACADO` | Canal atacado | Não (a menos que pedido explicitamente) |
| `ECOMMERCE` | Filial digital | Não em análise física — usar via §2.2 |

**Filtro canônico para "lojas físicas ativas" de varejo próprio:**
```sql
WHERE TIPO_FILIAL = 'LOJA VAREJO'
  AND FILIAL_PROPRIA = TRUE
  AND DATA_FECHAMENTO IS NULL
  AND FILIAL NOT LIKE '%ECOMMERCE%'
  AND FILIAL NOT LIKE '%MATRIZ%'
  AND FILIAL NOT LIKE '%CDS%'
```

> 📌 **Pendência de ferramenta:** `list_active_retail_stores(marca)` — futura ferramenta MCP que aplicará esse filtro server-side. Enquanto não existir, usar o WHERE acima. Ver `business-rules.md §13`.

**🔴 PII — NÃO selecionar:**
- `CGC_CPF`, `CPF_CONTA_STONE` — documentos
- `NOME_RESPONSAVEL` — nome pessoal
- `EMAIL_CONTA_STONE`, `CELULAR_CONTA_STONE` — contatos pessoais
- `CHAVE_API`, `PWD_CONTA_STONE`, `USER_CONTA_STONE` — credenciais (🔴🔴 nunca expor)
- `RESPONSAVEL_CONTA_STONE`, `ID_CONTA_STONE` — identificadores financeiros

---

## 5. Cota / Metas — `LOJAS_PREVISAO_VENDAS`

**Full path:** `soma-pipeline-prd.silver_linx.LOJAS_PREVISAO_VENDAS`
**Grão:** 1 linha por `(FILIAL, DATA_VENDA)` — previsão diária; `DATA_VENDA_MENSAL` agrega metas mensais.

| Coluna | Tipo | Uso |
|---|---|---|
| `FILIAL` | STRING | FK → FILIAIS |
| `DATA_VENDA` | DATE | Data da meta diária |
| `DATA_VENDA_MENSAL` | DATE | Data do mês agregado |
| `PREVISAO_VALOR` | STRING | ✅ Meta R$ diária (cast p/ NUMERIC) |
| `PREVISAO_VALOR_MES` | STRING | Meta R$ mensal |
| `PREVISAO_QTDE` | INTEGER | Meta em peças (diária) |
| `PREVISAO_QTDE_MES` | INTEGER | Meta em peças (mês) |
| `VENDA` | STRING | 🚫 **NÃO USAR** — campo não é atualizado de forma confiável pelo sistema Linx. Não reflete a venda real. Para venda realizada, sempre calcular via `TB_WANMTP_VENDAS_LOJA_CAPTADO`. |
| `CUSTO` | STRING | Custo R$ (cast) — mesma ressalva: não confiável |
| `DESCONTO` | STRING | Desconto R$ (cast) — mesma ressalva: não confiável |
| `QTDE_VENDA` | INTEGER | Qtd vendida |
| `QTDE_ENTRADA` / `QTDE_SAIDA` / `QTDE_TROCA` | INTEGER | Movimentação |
| `NUMERO_TICKETS` | INTEGER | Transações |
| `ESTOQUE` | INTEGER | Estoque |
| `ESTOQUE_VALORIZADO` / `ESTOQUE_VALORIZADO_MOEDA` | STRING | Estoque R$ |
| `PRAZO_MEDIO` | INTEGER | Prazo médio |
| `SEMANA` | STRING | Semana |
| `META_CANAL_1..3` | STRING | Meta por canal |
| `META_VENDEDOR_VALOR_DIA` / `_MES` | STRING | Meta vendedor R$ |
| `META_VENDEDOR_QTDE_DIA` / `_MES` | INTEGER | Meta vendedor peças |
| `TROCA`, `TROCA_CUSTO`, `TROCA_DESCONTO` | STRING | Trocas R$ |
| `INATIVA_FLASH` | BOOLEAN | Flag |

**⛔ Padrão ERRADO — nunca fazer:**
```sql
-- ❌ LOJAS_PREVISAO_VENDAS.VENDA não é confiável — não representa a venda real
SAFE_DIVIDE(SAFE_CAST(VENDA AS NUMERIC), SAFE_CAST(PREVISAO_VALOR AS NUMERIC)) AS atingimento_valor
```

**✅ Padrão correto — venda sempre de TB_WANMTP_VENDAS_LOJA_CAPTADO** (ver §8 e business-rules.md §12)

⚠️ Muitos valores numéricos estão como STRING — sempre `SAFE_CAST(... AS NUMERIC)`.

---

## 6. Estoque — ⚠️ ALTO CUSTO, MUITO CUIDADO

> **Tabelas enormes: foto diária de estoque por loja × produto (× cor × tamanho).**
> Regra operacional: **nunca rodar query que custe > 1 USD**. Sempre filtrar `DATA` a uma data específica ou pequena janela, e se possível escopo de `FILIAL` e/ou `PRODUTO`.

### Quando usar qual tabela

| Tabela | Grão | Quando usar |
|---|---|---|
| `ANMN_ESTOQUE_HISTORICO_PROD` | produto × cor × filial × dia | Análise de cobertura geral, ruptura por cor, valor de estoque |
| `ANMN_ESTOQUE_HISTORICO_PROD_GRADE` | produto × cor × **tamanho** × filial × dia | Quando precisa quebrar por tamanho (mix de grade, ruptura de tamanho) |

### 6.1 `ANMN_ESTOQUE_HISTORICO_PROD` (prod-cor-loja)

| Coluna | Tipo | Uso |
|---|---|---|
| `DATA` | DATE | ✅ Filtro obrigatório |
| `PRODUTO` | STRING | FK |
| `COR_PRODUTO` | STRING | FK |
| `FILIAL` | STRING | FK |
| `ESTOQUE` | INTEGER | Estoque total |
| `ESTOQUE_DISPONIVEL` | INTEGER | Disponível p/ venda |
| `ESTOQUE_EM_TRANSITO` | INTEGER | Em trânsito |
| `ESTOQUE_VENDA_EXTERNA` | INTEGER | Reservado p/ venda externa |
| `PRECO_VAREJO` | STRING | Preço referência (cast) |

### 6.2 `ANMN_ESTOQUE_HISTORICO_PROD_GRADE` (prod-cor-tam-loja)

| Coluna | Tipo | Uso |
|---|---|---|
| `DATA` | DATE | ✅ Filtro obrigatório |
| `PRODUTO` / `COR_PRODUTO` / `FILIAL` | STRING | FKs |
| `QTDE_ESTOQUE` | INTEGER | Total |
| `QTDE_DISPONIVEL` | INTEGER | Disponível |
| `QTDE_EMBALADA` | INTEGER | Embalada |
| `QTDE_TRANSITO` | INTEGER | Em trânsito |
| `T1`..`T10` | INTEGER | Estoque por posição de tamanho (resolver via PRODUTOS.GRADE → PRODUTOS_TAMANHOS.TAMANHO_n) |
| `EST1`..`EST10` | INTEGER | Estoque base por tamanho |
| `EMB1`..`EMB10` | INTEGER | Embalado por tamanho |
| `ED1`..`ED10` | INTEGER | Em trânsito / disponível por tamanho |

### Padrão anti-custo (estoque)

**❌ NUNCA:**
```sql
SELECT * FROM `soma-pipeline-prd.silver_linx.ANMN_ESTOQUE_HISTORICO_PROD_GRADE`
WHERE DATA BETWEEN '2024-01-01' AND '2024-12-31'
-- ^ varre 365 fotos × N lojas × N produtos. Pode custar dezenas de USD.
```

**✅ Sempre:**
```sql
-- 1) Fixar em 1 data (foto única)
SELECT PRODUTO, COR_PRODUTO, FILIAL, ESTOQUE_DISPONIVEL
FROM `soma-pipeline-prd.silver_linx.ANMN_ESTOQUE_HISTORICO_PROD`
WHERE DATA = '2026-04-18'
  AND FILIAL IN ('000261', '000123')  -- escopo de filial
  AND PRODUTO LIKE 'V1035019%'         -- escopo de produto quando possível

-- 2) Antes de rodar, conferir custo estimado no dry-run
bq query --dry_run --use_legacy_sql=false 'SELECT ...'
```

**Checklist antes de rodar query em estoque:**
1. Tenho filtro exato em `DATA` (ou janela ≤ 7 dias)?
2. Tenho escopo em `FILIAL` ou `PRODUTO`?
3. Estou projetando só as colunas necessárias (nunca `SELECT *`)?
4. Rodei `--dry_run` e confirmei bytes processados < ~200 GB (~1 USD a 5 USD/TB)?

### 6.3 Giro (stock turnover)

**Default: SEMPRE calcular giro em peças.**

> `giro_pecas = pecas_vendidas / (pecas_vendidas + estoque_final_pecas)`
> onde `estoque_final_pecas` = foto de estoque na **data final** do período (não média).

**Variante em valor — só usar se o usuário pedir, e confirmando a regra de negócio:**

> `giro_valor = valor_vendido / (valor_vendido + estoque_final_pecas * preco_varejo_original)`
>
> Note a assimetria intencional: o numerador é venda **realizada** (líquida, pós-desconto), mas o denominador valoriza o estoque a **VAREJO ORIGINAL** (`PRODUTOS_PRECOS.CODIGO_TAB_PRECO = 'VO'` — preço "de", não o "por"). Isso reflete o potencial de receita do estoque na posição, sem desconto embutido.

**Protocolo ao responder "qual o giro de X":**
1. **Estabelecer o período de análise** antes de qualquer coisa. Se o usuário não disser, perguntar (últimos 30d? mês corrente? coleção X?).
2. **Default = peças**. Não inferir "valor" do contexto. Se o usuário pedir giro em valor/R$, **confirmar a regra**: numerador = venda líquida realizada; denominador = venda líquida + estoque_pecas × VO (preço varejo original).
3. Somar venda no período usando `CODIGO_FILIAL_DESTINO` / `RL_DESTINO` como default.
4. Puxar **1 foto de estoque** na data final do período (ver protocolo anti-custo §6).
5. Calcular e interpretar: giro alto (próximo de 1) = saída > posição; giro baixo (próximo de 0) = estoque parado.

```sql
-- Giro em PEÇAS (default) — por produto × filial_destino
-- ATENÇÃO: vendas usa CÓDIGO de filial; estoque usa NOME. Ponte via FILIAIS.
WITH vendas AS (
  SELECT
    f.FILIAL AS filial_nome,
    v.CODIGO_FILIAL_DESTINO AS filial_cod,
    v.PRODUTO, v.COR_PRODUTO,
    SUM(v.QTDE_PROD) AS pecas_vendidas
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f
    ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
  WHERE v.DATA_VENDA BETWEEN @data_inicio AND @data_fim
  GROUP BY 1, 2, 3, 4
),
estoque_final AS (
  SELECT FILIAL AS filial_nome, PRODUTO, COR_PRODUTO,
         ESTOQUE_DISPONIVEL AS estoque_pecas
  FROM `soma-pipeline-prd.silver_linx.ANMN_ESTOQUE_HISTORICO_PROD`
  WHERE DATA = @data_fim
)
SELECT
  v.filial_cod, v.filial_nome, v.PRODUTO, v.COR_PRODUTO,
  v.pecas_vendidas,
  COALESCE(e.estoque_pecas, 0) AS estoque_final_pecas,
  SAFE_DIVIDE(v.pecas_vendidas,
              v.pecas_vendidas + COALESCE(e.estoque_pecas, 0)) AS giro_pecas
FROM vendas v
LEFT JOIN estoque_final e USING (filial_nome, PRODUTO, COR_PRODUTO)
```

```sql
-- Giro em VALOR (só usar após confirmação com o usuário)
-- numerador: valor líquido vendido
-- denominador: valor líquido vendido + estoque_pecas × preço VAREJO ORIGINAL (VO)
WITH vendas AS (
  SELECT
    f.FILIAL AS filial_nome,
    v.CODIGO_FILIAL_DESTINO AS filial_cod,
    v.PRODUTO, v.COR_PRODUTO,
    SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS venda_liquida
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f
    ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
  WHERE v.DATA_VENDA BETWEEN @data_inicio AND @data_fim
  GROUP BY 1, 2, 3, 4
),
estoque_final AS (
  SELECT FILIAL AS filial_nome, PRODUTO, COR_PRODUTO,
         ESTOQUE_DISPONIVEL AS estoque_pecas
  FROM `soma-pipeline-prd.silver_linx.ANMN_ESTOQUE_HISTORICO_PROD`
  WHERE DATA = @data_fim
),
preco_vo AS (
  SELECT PRODUTO, SAFE_CAST(PRECO1 AS NUMERIC) AS preco_varejo_original
  FROM `soma-pipeline-prd.silver_linx.PRODUTOS_PRECOS`
  WHERE CODIGO_TAB_PRECO = 'VO'
)
SELECT
  v.filial_cod, v.filial_nome, v.PRODUTO, v.COR_PRODUTO,
  v.venda_liquida,
  COALESCE(e.estoque_pecas, 0) AS estoque_final_pecas,
  COALESCE(e.estoque_pecas, 0) * p.preco_varejo_original AS estoque_final_valor_vo,
  SAFE_DIVIDE(
    v.venda_liquida,
    v.venda_liquida + COALESCE(e.estoque_pecas, 0) * p.preco_varejo_original
  ) AS giro_valor
FROM vendas v
LEFT JOIN estoque_final e USING (filial_nome, PRODUTO, COR_PRODUTO)
LEFT JOIN preco_vo p USING (PRODUTO)
```

### 6.4 Cobertura (days of cover)

**Definição:**
> `cobertura_dias = estoque_atual / venda_diaria_projetada`
> responde: "quantos dias esse estoque dura no ritmo projetado?"

**Protocolo ao responder "qual a cobertura de X":**
1. **SEMPRE perguntar para quantos dias** o usuário quer projetar (30d? 60d? até fim da coleção?). Não assuma.
2. **Grão é sempre por loja** (`FILIAL` em `FILIAIS` via `CODIGO_FILIAL_DESTINO`). Só consolidar por cidade/região/marca **após** calcular por loja — nunca começar agregado.
3. **Fonte da venda projetada (em ordem de preferência):**
   - (a) **Cota (`LOJAS_PREVISAO_VENDAS.PREVISAO_QTDE` / `PREVISAO_VALOR`)** quando existir para a filial no período.
   - (b) **Forecast da curva histórica** quando não houver cota — projetar a venda diária média dos últimos 30–90 dias da própria loja, ajustada pela sazonalidade da curva.
4. Puxar estoque atual (foto mais recente de `ANMN_ESTOQUE_HISTORICO_PROD` — respeitar §6 anti-custo).
5. Calcular: `cobertura = estoque / venda_diaria_projetada`. Se > N dias pedidos → sobra; se < → ruptura projetada.

**Sempre responder por loja primeiro, só depois consolidar.** Consolidação por cidade/região/marca faz-se via `FILIAIS.REGIAO` / `FILIAIS.REGIAO_SUPERVISAO` / `LOJAS_REDE.DESC_REDE_LOJAS`, somando estoque e venda projetada separadamente **antes** de recalcular o ratio — nunca média de covers.

```sql
-- Cobertura por loja para N dias (parametrizado)
-- Preferência 1: usa PREVISAO_VALOR da cota; fallback: média móvel 30d da própria loja
DECLARE dias_proj INT64 DEFAULT 30;  -- SEMPRE perguntar ao usuário
DECLARE data_ref DATE DEFAULT CURRENT_DATE();

-- ATENÇÃO: estoque e cota usam NOME da filial (FILIAL texto);
-- vendas usa CÓDIGO. Ponte pelo FILIAIS (FILIAL=nome, COD_FILIAL=código).
WITH estoque AS (
  SELECT FILIAL AS filial_nome, SUM(ESTOQUE_DISPONIVEL) AS estoque_qtde
  FROM `soma-pipeline-prd.silver_linx.ANMN_ESTOQUE_HISTORICO_PROD`
  WHERE DATA = data_ref
  GROUP BY 1
),
cota AS (
  SELECT FILIAL AS filial_nome,
         SUM(PREVISAO_QTDE) / dias_proj AS pecas_dia_cota
  FROM `soma-pipeline-prd.silver_linx.LOJAS_PREVISAO_VENDAS`
  WHERE DATA_VENDA BETWEEN data_ref AND DATE_ADD(data_ref, INTERVAL dias_proj DAY)
  GROUP BY 1
),
fallback_hist AS (
  -- Forecast por média móvel 30d da própria loja (usado quando cota = NULL)
  SELECT f.FILIAL AS filial_nome,
         SUM(v.QTDE_PROD) / 30.0 AS pecas_dia_hist
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f
    ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
  WHERE v.DATA_VENDA BETWEEN DATE_SUB(data_ref, INTERVAL 30 DAY) AND DATE_SUB(data_ref, INTERVAL 1 DAY)
  GROUP BY 1
)
SELECT
  f.COD_FILIAL, f.FILIAL AS filial_nome, f.REGIAO, lr.DESC_REDE_LOJAS AS marca,
  e.estoque_qtde,
  COALESCE(c.pecas_dia_cota, fh.pecas_dia_hist) AS pecas_dia_projetadas,
  CASE WHEN c.pecas_dia_cota IS NOT NULL THEN 'cota' ELSE 'forecast_curva' END AS fonte_forecast,
  SAFE_DIVIDE(e.estoque_qtde,
              COALESCE(c.pecas_dia_cota, fh.pecas_dia_hist)) AS cobertura_dias
FROM estoque e
JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f ON e.filial_nome = f.FILIAL
LEFT JOIN `soma-pipeline-prd.silver_linx.LOJAS_REDE` lr ON f.REDE_LOJAS = lr.REDE_LOJAS
LEFT JOIN cota c USING (filial_nome)
LEFT JOIN fallback_hist fh USING (filial_nome)
```

**Consolidação correta (por região, exemplo):**
```sql
-- Depois de calcular por loja, consolidar somando numerador e denominador,
-- nunca fazendo AVG(cobertura_dias).
SELECT REGIAO,
       SUM(estoque_qtde) AS estoque_regiao,
       SUM(pecas_dia_projetadas) AS pecas_dia_regiao,
       SAFE_DIVIDE(SUM(estoque_qtde), SUM(pecas_dia_projetadas)) AS cobertura_dias_regiao
FROM <resultado_por_loja>
GROUP BY 1
```

---

## 7. Colunas PII consolidadas (por tabela)

| Tabela | Colunas 🔴 PII |
|---|---|
| `TB_WANMTP_VENDAS_LOJA_CAPTADO` | `CODIGO_CLIENTE`, `VENDEDOR`, `VENDEDOR_ATEND`, `VENDEDOR_AFILIADO`, `GERENTE_LOJA` |
| `FILIAIS` | `CGC_CPF`, `CPF_CONTA_STONE`, `NOME_RESPONSAVEL`, `EMAIL_CONTA_STONE`, `CELULAR_CONTA_STONE`, `CHAVE_API`, `PWD_CONTA_STONE`, `USER_CONTA_STONE` |
| `PRODUTOS` | `COMPRADORA`, `ESTILISTA`, `MODELISTA` — ⚠️ são nomes próprios; agregar mas não listar linhas individuais |

Colunas com **potencial** PII (classificar na próxima sessão via amostra): `PERFIL_VENDEDOR`, `DESC_CARGO`, `SELLER`, `RESPONSAVEL_CONTA_STONE` em FILIAIS.

---

## 8. Joins canônicos (cola)

```sql
-- Venda enriquecida com marca, filial, produto, cor
-- DEFAULT: filial/rede de DESTINO (use FAT/ORIGEM só se pedido explicitamente)
SELECT
  v.DATA_VENDA,
  lr.DESC_REDE_LOJAS AS marca,
  f.REGIAO, v.CODIGO_FILIAL_DESTINO,
  p.DESC_PRODUTO, p.COLECAO, p.ANM_TIPO_PRODUTO,
  pc.DESC_COR_PRODUTO,
  SUM(v.QTDE_PROD) AS pecas,
  SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS venda_liquida
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
LEFT JOIN `soma-pipeline-prd.silver_linx.LOJAS_REDE` lr
  ON CAST(v.RL_DESTINO AS STRING) = lr.REDE_LOJAS
LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f
  ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
LEFT JOIN `soma-pipeline-prd.silver_linx.PRODUTOS` p
  ON v.PRODUTO = p.PRODUTO
LEFT JOIN `soma-pipeline-prd.silver_linx.PRODUTO_CORES` pc
  ON v.PRODUTO = pc.PRODUTO AND v.COR_PRODUTO = pc.COR_PRODUTO
WHERE v.DATA_VENDA BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE()
GROUP BY 1,2,3,4,5,6,7,8
```

```sql
-- ⛔ NÃO FAZER — usa LOJAS_PREVISAO_VENDAS.VENDA que não é confiável
-- SELECT m.FILIAL, SUM(SAFE_CAST(m.VENDA AS NUMERIC)) AS venda ...

-- ✅ Atingimento de meta por filial FÍSICA (mês corrente)
-- Venda calculada sempre via TB_WANMTP_VENDAS_LOJA_CAPTADO
WITH cota AS (
  SELECT
    m.FILIAL,
    SUM(SAFE_CAST(m.PREVISAO_VALOR AS NUMERIC)) AS meta_valor
  FROM `soma-pipeline-prd.silver_linx.LOJAS_PREVISAO_VENDAS` m
  WHERE DATE_TRUNC(m.DATA_VENDA, MONTH) = DATE_TRUNC(CURRENT_DATE(), MONTH)
  GROUP BY 1
),
venda AS (
  SELECT
    f.FILIAL AS filial_nome,
    SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS venda_liquida
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f ON v.CODIGO_FILIAL_DESTINO = f.COD_FILIAL
  WHERE v.DATA_VENDA BETWEEN DATE_TRUNC(CURRENT_DATE(), MONTH)
                         AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
    AND v.TIPO_VENDA = 'VENDA_LOJA'
    -- Devoluções INCLUÍDAS por padrão (venda líquida real).
    -- Só filtrar `VALOR_PAGO_PROD > 0` se o usuário pedir venda bruta / excluir
    -- devoluções explicitamente — ver business-rules.md §1.1.
  GROUP BY 1
)
SELECT
  c.FILIAL,
  f.REGIAO,
  v.venda_liquida AS venda,
  c.meta_valor AS meta,
  SAFE_DIVIDE(v.venda_liquida, c.meta_valor) AS atingimento
FROM cota c
LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f ON c.FILIAL = f.FILIAL
LEFT JOIN venda v ON c.FILIAL = v.filial_nome
ORDER BY 1
-- Para ecommerce, ver §11 e business-rules.md §12
```

```sql
-- Margem (venda vs custo via tabela CT)
WITH custo AS (
  SELECT PRODUTO, SAFE_CAST(PRECO1 AS NUMERIC) AS custo_unit
  FROM `soma-pipeline-prd.silver_linx.PRODUTOS_PRECOS`
  WHERE CODIGO_TAB_PRECO = 'CT'
)
SELECT
  v.PRODUTO,
  SUM(v.QTDE_PROD) AS pecas,
  SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS venda_liquida,
  SUM(v.QTDE_PROD * c.custo_unit) AS cmv,
  SAFE_DIVIDE(
    SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) - SUM(v.QTDE_PROD * c.custo_unit),
    SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC))
  ) AS margem_pct
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
LEFT JOIN custo c ON v.PRODUTO = c.PRODUTO
WHERE v.DATA_VENDA BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE()
GROUP BY 1
```

---

## 9. Gotchas conhecidos e a validar

- **Valores financeiros como STRING**: `PRODUTOS_PRECOS.PRECO1..4`, `LOJAS_PREVISAO_VENDAS.VENDA/PREVISAO_VALOR/CUSTO/DESCONTO`, `ANMN_ESTOQUE_HISTORICO_PROD.PRECO_VAREJO`. Sempre `SAFE_CAST(... AS NUMERIC)`.
- **`TAMANHO` em vendas é INTEGER posicional** — precisa de `PRODUTOS.GRADE` → `PRODUTOS_TAMANHOS.TAMANHO_n` para virar label (`"P"`, `"M"`, `"38"`…).
- **`RL_*` em vendas tem tipos mistos** (STRING e INTEGER dependendo do campo) — cast consistente no JOIN com LOJAS_REDE.
- **`CODIGO_FILIAL_*` × `FILIAIS`** — vendas usa `CODIGO_FILIAL_*` (com sufixo), FILIAIS usa `COD_FILIAL` (abreviado) p/ código e `FILIAL` p/ NOME. Nomes parecidos, strings SQL distintas. Ver §4.
- **`DESCONTO_PROD`** — **armazenado negativo** (validado). `SUM(DESCONTO_PROD)` dá desconto como valor negativo.
- **Sem partition nativo** — filtros em `DATA_VENDA` / `DATA` são obrigatórios mas NÃO particionam; scan é linear no volume total. Cuidado redobrado em estoque.
- **CDC trailing cols** (`pk_merge`, `op`, `data_cdc`, `ts_ms`): ignorar em análise. `op = 'D'` pode indicar registro deletado — investigar se necessário filtrar.

---

## 10. Pendências (abertas)

- [ ] **10.1 Definir a regra de alocação de canal (Físico × Online)** no modelo Linx — a regra antiga do `refined_captacao` (baseada em `tipo_venda`) não se traduz direto. Candidatos: combinar `TIPO_VENDA` (VENDA_LOJA/VENDA_ECOM/VENDA_OMNI/VENDA_VITRINE) + `SUB_TIPO_VENDA` + indicadores `INDICA_ORIGEM_ECOM` / `INDICA_DESTINO_ECOM` / `INDICA_FAT_ECOM` / `INDICA_PEDIDO_VITRINE` + `SELLER` para identificar marketplace externo. Pendente de decisão do usuário.
- [ ] **10.2 Regra "excluir franquia física"** no Linx — no modelo antigo era `tipo_venda=FISICO AND programa=franquia`. Candidatos: `FILIAIS.INDICA_FRANQUIA` ou `FILIAIS.FILIAL_PROPRIA`. Pendente de decisão do usuário.

## 11. Filiais Ecommerce por marca — mapeamento cota × venda (validado 2026-04-21)

> **Contexto:** cada marca tem filiais dedicadas a ecommerce no Linx. A cota digital é registrada nessas filiais em `LOJAS_PREVISAO_VENDAS`, e as vendas digitais saem de `TB_WANMTP_VENDAS_LOJA_CAPTADO` com `TIPO_VENDA IN ('VENDA_ECOM','VENDA_OMNI','VENDA_VITRINE')`.
>
> **Sobre os sufixos CM / SB / HRG / RBX:** a mesma filial operacional pode aparecer com sufixos diferentes porque cada sufixo representa o CNPJ sob o qual ela está registrada (ver §4 Armadilha 3). `FARM ECOMMERCE CM` e `FARM ECOMMERCE SB` são **o mesmo canal de ecommerce da FARM** — a diferença é apenas o CNPJ após a incorporação para Soma Brands. Para análise comercial, **trate todos os sufixos da mesma filial como uma única entidade**.
>
> **Problema de join:** a cota fica registrada em um sufixo (ex. `_CM`) enquanto o volume de venda atual flui pelo outro (ex. `_SB`). Por isso **nunca comparar cota vs venda digital fazendo join por nome de filial** — o cruzamento correto é por marca (`REDE_LOJAS` / `RL_DESTINO`).

### Tabela canônica — filiais-base ecommerce por marca (validada 2025)

A coluna "nome-base" é o nome sem sufixo de CNPJ. Todos os sufixos de um mesmo nome-base são a mesma filial operacional.

| Marca | RL | Nome-base ecommerce | Sufixos observados | Filial da COTA ativa (LOJAS_PREVISAO_VENDAS) | Observação |
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

### Regra de join para cota vs venda digital

**Nunca fazer:**
```sql
-- ❌ Join por nome de filial — CM da cota ≠ SB onde a venda flui
JOIN LOJAS_PREVISAO_VENDAS m ON filial_venda = m.FILIAL
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
  FROM `soma-pipeline-prd.silver_linx.LOJAS_PREVISAO_VENDAS` m
  LEFT JOIN `soma-pipeline-prd.silver_linx.FILIAIS` f ON m.FILIAL = f.FILIAL
  LEFT JOIN `soma-pipeline-prd.silver_linx.LOJAS_REDE` lr ON f.REDE_LOJAS = lr.REDE_LOJAS
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
  FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
  LEFT JOIN `soma-pipeline-prd.silver_linx.LOJAS_REDE` lr ON CAST(v.RL_DESTINO AS STRING) = lr.REDE_LOJAS
  WHERE v.DATA_VENDA BETWEEN :data_inicio AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
    AND v.TIPO_VENDA IN ('VENDA_ECOM', 'VENDA_OMNI', 'VENDA_VITRINE')
    -- Devoluções INCLUÍDAS por padrão (venda líquida real). Só filtrar
    -- `VALOR_PAGO_PROD > 0` sob pedido explícito — ver business-rules.md §1.1.
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

### Notas importantes
- **`LOJAS_PREVISAO_VENDAS.VENDA` nunca usar** — campo não é atualizado de forma confiável. Ver §5.
- CM, SB, HRG, RBX são CNPJs distintos da **mesma filial operacional** — para fins comerciais, são a mesma coisa (ver §4 Armadilha 3).
- A cota tende a ficar registrada no CNPJ mais antigo (CM); à medida que a migração acontece, o volume de venda migra para o novo CNPJ (SB ou HRG). O join por `REDE_LOJAS` resolve isso automaticamente.
- Filiais com nomenclatura totalmente diferente na cota (`NV - ECOMMERCE`, `ECOMMERCE FABULA RBX`) são legados anteriores à padronização de nomes.
- **FARM ETC** tem cota cadastrada mas sem vendas identificadas em 2025 — possível canal ainda não operacional.
- OMNI (`VENDA_OMNI`) é contabilizado como digital — ver business-rules.md §2.

---

## 12. Validações já fechadas (2026-04-18)

- ✅ Join `vendas.CODIGO_FILIAL_DESTINO = FILIAIS.COD_FILIAL` (default) — 11/11 match em amostra (validação original rodada com `CODIGO_FILIAL_ORIGEM`; mesma convenção de `COD_FILIAL`). `FILIAIS.FILIAL` é nome, não código.
- ✅ `DESCONTO_PROD` é armazenado **negativo** (~99% das linhas não-zero).
- ✅ `TIPO_VENDA` tem 4 valores: VENDA_LOJA, VENDA_ECOM, VENDA_OMNI, VENDA_VITRINE.
- ✅ `SUB_TIPO_VENDA` tem 6 valores (ver §1).
- ✅ `SELLER` (16 valores), `PERFIL_VENDEDOR` (14), `DESC_CARGO` (cargos genéricos) — todos **não-PII**.
- ✅ Top 10 marcas via `LOJAS_REDE` (origem, últimos 30 dias — ranking histórico; default atual é DESTINO):
  1. FARM (2) — R$ 77,3M, 128 lojas
  2. ANIMALE (1) — R$ 40,8M, 62 lojas
  3. BYNV (16) — R$ 35,2M, 29 lojas *(antes "NV" no modelo antigo)*
  4. CRIS BARROS (9) — R$ 22,5M, 16 lojas
  5. MARIA FILO (15) — R$ 16,0M, 40 lojas
  6. CAROL BASSI (30) — R$ 11,3M, 13 lojas
  7. FOXTON (7) — R$ 9,3M, 31 lojas
  8. OUTLET (6) — R$ 6,8M, 15 lojas *(antes "OFF PREMIUM")*
  9. FABULA (5) — R$ 2,6M, 12 lojas
  10. FARM ETC (26) — R$ 1,9M, 5 lojas
