# Schema Reference — Azzas 2154 BigQuery (Clientes)

> Living doc. Atualize depois de cada sessão onde descobrir tabelas, colunas ou valores novos.

**Dataset principal:** `soma-crm-bi.dashboards_corp`

Este agente cobre a **base de clientes do grupo Azzas 2154** com perspectiva de:
- **Ano de competência** — janelas fechadas por ano calendário (tabela `acomp_clientes_base`).
- **Janela móvel 12m** — últimos 12 meses corridos (fonte a ser confirmada / inserida).

A receita aqui **NÃO bate** com o agente de vendas. É por desenho: marketplaces (ex.: Mercado Livre) geram receita Azzas 2154 mas o cliente final pertence ao marketplace, então não entram no universo deste agente.

---

## 1. Acompanhamento de Clientes — Ano de Competência — `acomp_clientes_base`

**Full path:** `soma-crm-bi.dashboards_corp.acomp_clientes_base`
**Tamanho:** ~416k linhas / ~0.1 GB (queries são baratas — costumam ficar abaixo de US$0.001).
**Range temporal:** 2019-01 a 2026-05 (89 meses).
**Grão:** uma linha por combinação de:
`marca × redelojas × subredelojas × anomes × tipo_canal × canal_entrada × canal_cliente × plataforma_entrada × statuscliente × detalhe_status × cluster_freq_dia_atual × rec_90dias × rec_90dias_entrada × rec_365dias × check_cpf`.

> ⚠️ A tabela **já é agregada**. Cada linha contém somatórios de receita, contagem de clientes, pedidos, peças, etc. — não há registros transacionais individuais. Isso elimina risco de PII.

### Colunas

**Dimensões temporais**
| Coluna | Tipo | Uso |
|---|---|---|
| `anomes` | STRING | "YYYY-MM" — chave temporal canônica |
| `ano` | INTEGER | Ano (filtro principal) |
| `mes` | INTEGER | Mês (1..12) |

**Dimensões de marca / loja**
| Coluna | Tipo | Uso |
|---|---|---|
| `marca` | STRING | Marca do grupo — filtro obrigatório (excluir NULL por padrão) |
| `redelojas` | NUMERIC | Código da rede de lojas |
| `SubRedeLojas` | NUMERIC | Sub-rede |

**Dimensões de canal**
| Coluna | Tipo | Uso |
|---|---|---|
| `tipo_canal` | STRING | `canal entrada` (default) ou `canal` — ver §1.1 |
| `canal_entrada` | STRING | Canal de entrada do pedido |
| `canal_cliente` | STRING | Canal do cliente — valores incluem `Multicanal` e `Multicanal c/ Franquia` (precisam dedup ao filtrar — ver business-rules) |
| `plataforma_entrada` | STRING | Plataforma de entrada |

**Dimensões de cliente**
| Coluna | Tipo | Uso |
|---|---|---|
| `statuscliente` | STRING | `Novo` / `Retido` / `Reativado` (+ NULL ~986 linhas em 2026) |
| `detalhe_status` | STRING | `Compra Única` / `Recorrente` (pouco usado) |
| `check_cpf` | STRING | `valido` / `invalido` — **NÃO é PII**: indica se a venda teve CPF válido identificado |
| `cluster_freq_dia_atual` | STRING | Cluster de frequência |

**Flags de recência (pré-calculadas para o snapshot da linha)**
| Coluna | Tipo | Uso |
|---|---|---|
| `rec_90dias_entrada` | BOOLEAN | Recência ≤ 90 dias por canal de entrada |
| `rec_90dias` | BOOLEAN | Recência ≤ 90 dias |
| `rec_365dias` | BOOLEAN | Recência ≤ 365 dias |

**Métricas — ano fechado**
| Coluna | Tipo | Uso |
|---|---|---|
| `rec_marca` | FLOAT | **Receita Marca** — base da medida `Receita` |
| `pedidos_marca` | INTEGER | Quantidade de pedidos — base da medida `Pedidos` |
| `prod_marca` | NUMERIC | Quantidade de peças vendidas — base da medida `Produtos` |
| `qtde_cli_marca` | INTEGER | Quantidade de clientes (sem dedup de ano) |
| `qtde_cli_1a_compra_ano` | INTEGER | **Clientes contados apenas na 1ª compra do ano** — base da medida `Qtde Clis`. Permite somar meses dentro de um ano sem double-count |
| `rec_markup` | FLOAT | **Receita Markup** — base da medida homônima |
| `cmv` | FLOAT | **CMV** — base da medida homônima |

**Métricas — ano em curso (truncadas até hoje, para comparativos parciais YoY)**
| Coluna | Tipo | Uso |
|---|---|---|
| `rec_marca_ate_DiaAtual` | FLOAT | Receita acumulada até hoje |
| `pedidos_marca_ate_DiaAtual` | INTEGER | Pedidos até hoje |
| `prod_marca_ate_DiaAtual` | NUMERIC | Peças até hoje |
| `qtde_cli_marca_ate_DiaAtual` | INTEGER | Clientes até hoje |
| `qtde_cli_1a_compra_ano_ate_DiaAtual` | INTEGER | Clientes em 1ª compra até hoje |
| `rec_markup_ate_DiaAtual` | FLOAT | Receita markup até hoje |
| `cmv_ate_DiaAtual` | FLOAT | CMV até hoje |

> **Quando usar `_ate_DiaAtual`:** comparar YTD do ano corrente vs YTD do ano anterior na **mesma janela de dias**. Para anos fechados, usar as colunas sem sufixo.

### 1.1 Duplicação por `tipo_canal` — atenção ao filtrar

A tabela contém **linhas duplicadas pelo grão de canal**, distinguidas por `tipo_canal`:
- `canal entrada` — agregação pelo canal de entrada do pedido (ótica "como o cliente chegou")
- `canal` — agregação pelo canal atual / multicanalidade

**Regra de filtro:**
- **Default (sem filtro de canal):** `WHERE tipo_canal = 'canal entrada'`
- **Quando filtrar por `canal_entrada` OU `canal_cliente`:** `WHERE tipo_canal = 'canal'` (e aplicar dedup de Multicanal — ver business-rules §3)

Aplicar o filtro errado causa double-count silencioso.

### 1.2 Valores conhecidos de `marca` (2026)

Animale, Carol Bassi, Cris Barros, FARM, FARM ETC, FARM Global EU, FARM Global UK, FARM Global US, Foxton, Fábula, Maria Filó, NV, OFF Premium, Oficina, Reserva. (NULL existe e deve ser excluído por padrão — replica filtro "Marca não é (Em branco)" do dashboard gabarito.)

### 1.3 Colunas PII identificadas

Nenhuma coluna desta tabela contém PII direta. `check_cpf` indica apenas se a transação teve CPF válido (`valido`/`invalido`), não o CPF em si. A tabela está agregada — não há linhas com identificador individual.

---

## 2. Janela Móvel 12m — `crm_clientes_tabela1` (view)

**Full path:** `soma-crm-bi.dashboards.crm_clientes_tabela1`
**Tipo:** VIEW (não tabela física). Re-executa a query interna a cada SELECT.
**Custo:** fixo ~9 GB / US$ 0,045 por query, independente de column pruning ou filtro de Data — a view tem `GROUP BY` + 4 `JOIN`s internos que impedem pruning externo. Acompanha o gate de confirmação padrão (estimativa + "sim" do usuário). Pra reduzir custo total, preferir 1 query consolidada (PIVOT por `Periodo`) em vez de várias separadas — ver business-rules §11.0.

### 2.1 Tabelas físicas subjacentes (acessadas pela view)

| Tabela | Papel | Tamanho |
|---|---|---|
| `soma-crm-bi.tabelas.crm_pesquisa_vendas` | Fato principal — vendas | 34 GB / 66 Mi rows / particionada por `AnoMes` / clustered por `RedeLojas` |
| `soma-dl-refined-online.marketing.cliente` | JOIN para enriquecer com UF, Sexo (`A.ClienteID = B.CPF AND id_labels`) | — |
| `soma-dl-refined-online.marketing.filial` | JOIN para `nome_filial` | — |
| `soma-dl-refined-online.soma_online_refined.refined_entrega` | JOIN para `pais` (apenas FARM LATAM via REDELOJAS=27) | — |

Para o agent rodar queries na view, a SA precisa de `roles/bigquery.dataViewer` em **todos os 4 datasets** acima (`dashboards`, `tabelas`, `marketing`, `soma_online_refined`).

### 2.2 Lógica interna da view (resumida)

1. `UNION ALL` da fato em dois "Periodos":
   - `Atual`: registros reais de `2020-01-01` a `CURRENT_DATE - 1 dia`
   - `Ano Anterior`: registros de `2019-01-01` a `CURRENT_DATE - 1 dia - 1 ano`, com `DataPedido` shiftado +1 ano (a coluna `Data` da view nessa branch representa a data deslocada)
2. JOINs com `cliente`, `filial`, `entrega` para enriquecer dimensões.
3. `GROUP BY` pesado para agregar por grão de pedido × marca × cliente × filial × UF × Sexo.

> **Implicação:** uma única query na view varre ~9 GB. CY+LY já vêm separados pela coluna `Periodo` — não precisa de self-join. Mas o custo é inelástico (column/partition pruning do SELECT externo não propaga).

### 2.3 Grão e colunas

**Grão da view:** uma linha por combinação de
`Marca × ClienteIdDia × canal_cliente × Filial × ChavePedido × Data × DiaSemana × TipoCliente × OrderPedido × Periodo × UF × Sexo`.

Na prática equivale a **pedido**, com pequena explosão por JOIN com `cliente` (se o mesmo CPF tem múltiplas `(UF, Sexo)` em `marketing.cliente`).

| Coluna | Tipo | Uso |
|---|---|---|
| `Marca` | STRING | Mapeada via `CASE WHEN RedeLojas IN (...)` — ver §2.4 |
| `ClienteIdDia` | STRING | 🔴 **É o CPF** — ver §2.6 (PII) |
| `canal_cliente` | STRING | Classificação calculada na view: `Exclusivo Ecommerce`, `Exclusivo Franquia`, `Exclusivo Loja`, `Multicanal Varejo`, `Multicanal` |
| `Filial` | STRING | Nome da filial. Default exclui `%CRIS BARROS SB%` e `%CRIS BARROS EVENTO%` (a confirmar — §11.4 business-rules) |
| `ChavePedido` | STRING | Identificador do pedido — `COUNT(DISTINCT)` para Qtde de Pedidos |
| `Data` | DATE | Data do pedido (ou shifted para LY); coluna calculada — filtros externos NÃO propagam pra `AnoMes` partition |
| `DiaSemana` | STRING | `domingo`, `segunda-feira`... |
| `TipoCliente` | STRING | `Novo`, `Retido`, `Reativado Inativo`, `Reativado Perdido` (+ NULL residual). **Granularidade ≠ `acomp_clientes_base`** — ver §11.6 business-rules |
| `OrderPedido` | NUMERIC | Posição do pedido na sequência do cliente |
| `Periodo` | STRING | `Atual` ou `Ano Anterior` — usado para split CY/LY sem self-join |
| `UF` | STRING | UF do cliente (`-` se ausente) ou `pais` se REDELOJAS=27 (FARM LATAM) |
| `Sexo` | STRING | `Feminino` / `Masculino` / `-` |
| `MultiGanhoDia` | INTEGER | Flag 0/1 — `1` se `SUM(crm_pesquisa_vendas.MultiGanho) > 0` no agregado da linha. Distribuição: 95% =0, 4,4% =1, 0,16% NULL. Semântica não confirmada — ver §11.10 business-rules |
| `ValorPago` | FLOAT | Valor da venda (em devolução, `ValorPago` é positivo e `Devolução = SUM(-ValorPago)` sai negativa) |
| `QtdProd` | NUMERIC | Quantidade de peças — `>0` = venda, `<1` (=0 ou negativo) = devolução |

### 2.4 Lista de marcas (`Marca`)

Mapeada na view por `CASE WHEN RedeLojas IN (...)`:

| RedeLojas | Marca |
|---|---|
| 0 | FARM Global |
| 1 | Animale |
| 2 | FARM |
| 3 | A.Brand |
| 4 | FYI |
| 5 | Fábula |
| 6 | OFF Premium |
| 7 | Foxton |
| 9 | Cris Barros |
| 14 | Animale ORO |
| 15 | Maria Filó |
| 16 | NV |
| 27 | FARM LATAM |
| 30 | Carol Bassi |
| (outros) | NULL |

**Diferenças vs `acomp_clientes_base`:**
- `FARM ETC` **não existe** aqui (na acomp é marca separada)
- `FARM Global` **consolidado** (na acomp existe split EU/UK/US)
- Tem `FARM LATAM`, `Animale ORO`, `NV`, `Carol Bassi` (set parcialmente sobreposto à acomp)

⚠️ **Bug de encoding:** filtros com acento (`Marca = 'Maria Filó'`, `'Fábula'`) podem falhar silenciosamente quando o SQL passa por shell Windows. Workaround: `Marca LIKE 'Maria Fil%'`. Ver §11.9 business-rules.

### 2.5 Valores conhecidos de `TipoCliente`

`Novo`, `Retido`, `Reativado Inativo`, `Reativado Perdido` (+ NULL residual). **Cliente pode aparecer em mais de um TipoCliente dentro da janela 12m** se a classificação dele mudou — ver §11.7 business-rules.

### 2.6 Colunas PII identificadas

🔴 **`ClienteIdDia` É O CPF.** Confirmado pela própria lógica da view:
```sql
A.ClienteId AS ClienteIdDia,
LEFT JOIN soma-dl-refined-online.marketing.cliente B
  ON A.ClienteID = B.CPF AND ... = B.id_labels
```

O nome "ClienteIdDia" sugere granularidade cliente×dia, mas o **valor** da coluna é o CPF. O sufixo "Dia" se refere ao grão da view, não ao conteúdo.

**Regras:**
- ✅ `COUNT(DISTINCT ClienteIdDia)` é seguro (retorna número agregado).
- ❌ `SELECT ClienteIdDia, ... LIMIT 10` está **proibido** — expõe CPF.
- ❌ Nunca incluir `ClienteIdDia` no SELECT final exposto ao usuário.
- ❌ Nunca fazer `GROUP BY ClienteIdDia` no SELECT final retornado (gera linhas individuais identificáveis).

Para análises de granularidade individual, aplicar Protocolo de Recusa (ver CLAUDE.md do repo).

Demais colunas (`Marca`, `Data`, `UF`, `Sexo`, etc.) são dimensões agregáveis e não-PII por si só. Combinações finas (ex: `UF + Sexo + Filial + Data + ValorPago`) podem reidentificar — manter agregação suficiente.
