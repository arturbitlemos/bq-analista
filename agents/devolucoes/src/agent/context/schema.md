# Schema Reference — Agente de Devoluções

> Documento vivo. Atualizar depois de cada sessão onde descobrir algo novo
> (novo valor categórico, novo gotcha, regra de negócio que faltava).

**Dataset:** `soma-crm-bi.dados_trusted`
**Tabela única no escopo do MVP:** `trusted_troque_devolucao`

---

## 1. `trusted_troque_devolucao`

**Full path:** `soma-crm-bi.dados_trusted.trusted_troque_devolucao`
**Grão:** 1 linha por mudança de status de um pedido de reversa (troca/devolução).
A tabela carrega o histórico de status via CDC — um mesmo `id_troque` aparece
múltiplas vezes conforme muda de status. Para análise de "foto corrente", ver
regra crítica §1.1 em `business-rules.md`.

**Data column:** `data_solicitacao` (DATETIME) — filtro padrão em toda análise.

### 1.1 Colunas do núcleo da análise ✅

Estas são as colunas que o agent usa ativamente.

**Identificação**

| Coluna | Tipo | Uso |
|---|---|---|
| `id_troque` | STRING | ID canônico do pedido de reversa |
| `pacote` | STRING | ID do pacote (pode agrupar múltiplos itens) |

**Classificação**

| Coluna | Tipo | Uso |
|---|---|---|
| `rede_lojas` | INT64 | Código da marca — ver §3 mapa de marcas |
| `marca` | STRING | Nome legível da marca (redundante com rede_lojas, útil pra output) |
| `tipo_reversa` | STRING | Tipo de reversa — ver §4 glossário |

**Datas**

| Coluna | Tipo | Uso |
|---|---|---|
| `data_solicitacao` | DATETIME | ✅ **Filtro padrão** — quando o cliente pediu a reversa |
| `data_evento` | DATE | Data do evento (pode diferir de solicitação — investigar caso a caso) |
| `data_entrega_prevista` | DATE | SLA previsto de entrega |
| `data_entrega` | DATE | Entrega real |
| `data_finalizacao_reversa` | TIMESTAMP | Quando o processo da reversa fechou |
| `data_criacao_rastreamento` | TIMESTAMP | Quando começou o rastreamento logístico |

**Status (🔴 regras críticas — ver `business-rules.md` §1)**

| Coluna | Tipo | Uso |
|---|---|---|
| `status` | STRING | Status atual da linha no CDC |
| `ultimo_status` | STRING | Último status do pedido |

> 🔴 **Sempre `LOWER(status) = LOWER(ultimo_status)`** para foto corrente.
> 🔴 **Sempre `LOWER()` em comparações** (há valores com case inconsistente, ex: `"Cancelado"` com C maiúsculo).

**Produto**

| Coluna | Tipo | Uso |
|---|---|---|
| `ref_id_produto` | STRING | Formato `produto_cor_tamanho` (ex: `07.20.7491_0005_2`) — ver §5 extração |
| `cod_produto` | STRING | Código do produto (parte antes do primeiro `_` do ref_id) |

> Para obter `cod_cor` e `tamanho`, fazer SPLIT do `ref_id_produto` — ver §5.

**Análise qualitativa**

| Coluna | Tipo | Uso |
|---|---|---|
| `motivo` | STRING | Categórico controlado — 9 valores fixos, ver §6 |
| `comentario_loja` | STRING | Texto livre — comentário da loja |
| `comentario_cliente` | STRING | Texto livre — comentário do cliente |

**Valores e logística**

| Coluna | Tipo | Uso |
|---|---|---|
| `valor_prod` | FLOAT64 | Valor do produto devolvido |
| `preco_frete` | FLOAT64 | Custo do frete da reversa |
| `transportadora` | STRING | Transportadora bruta |
| `transportadora_tratada` | STRING | Transportadora normalizada — preferir esta em agrupamentos |
| `destino_produto` | STRING | Destino final do item (CD, loja, outro) |

**Geografia do cliente**

| Coluna | Tipo | Uso |
|---|---|---|
| `cidade_cliente` | STRING | Cidade do cliente |
| `estado_cliente` | STRING | UF do cliente |

**Métricas de SLA já calculadas**

| Coluna | Tipo | Uso |
|---|---|---|
| `tempo_total_reversa_dias` | INT64 | Duração total do processo (dias) |
| `tempo_postagem_dias` | INT64 | Tempo até postagem |
| `tempo_translado_dias` | INT64 | Tempo em trânsito |
| `tempo_recebimento_dias` | INT64 | Tempo de recebimento |

### 1.2 PII — 🔴 NÃO selecionar

| Coluna | Motivo |
|---|---|
| `cpf_cliente` | Documento pessoal — nunca listar linha individual; nunca incluir em output |

Se a análise precisar agrupar por cliente para contagem (ex: "clientes com múltiplas
devoluções"), usar hash ou contagem agregada, **nunca expor o CPF**.

### 1.3 Flags INT64 — 🟠 uso desconhecido, NÃO selecionar

Até a função destas colunas ser documentada, agent **não deve usar** em filtros,
agrupamentos ou output. Se aparecer necessidade, investigar a coluna antes.

| Coluna | Tipo | Nota |
|---|---|---|
| `split` | INT64 | 🟠 desconhecido |
| `coleta` | INT64 | 🟠 desconhecido |
| `completa` | INT64 | 🟠 desconhecido |
| `excecao` | INT64 | 🟠 desconhecido |
| `segunda_troca` | INT64 | 🟠 desconhecido — provavelmente "cliente já trocou antes" |
| `segunda_reversa` | INT64 | 🟠 desconhecido — provavelmente "cliente já devolveu antes" |
| `removido` | INT64 | 🟠 desconhecido |
| `recebido` | INT64 | 🟠 desconhecido |
| `troca_pp` | INT64 | 🟠 desconhecido |
| `flag_historico_criado_por_sistema` | BOOL | 🟠 desconhecido — pode filtrar registros criados por automação |

### 1.4 Outras

| Coluna | Tipo | Nota |
|---|---|---|
| (todas as 40 colunas estão acima) | | |

---

## 2. Filtros obrigatórios em TODA query

Ver `business-rules.md` §1 para detalhes e validação empírica.

```sql
WHERE
  LOWER(status) = LOWER(ultimo_status)       -- 🔴 anti-duplicação CDC
  AND LOWER(ultimo_status) <> 'cancelado'    -- 🔴 exclui cancelados (case-insensitive)
  AND data_solicitacao >= <janela>           -- ✅ filtro de janela obrigatório
  AND rede_lojas = <N>                       -- ✅ marca obrigatória (usuário sempre especifica)
```

---

## 3. Mapa de marcas (`rede_lojas` → `marca`)

Validado 2026-04-21 na própria tabela. Fonte de verdade para o de-para.

| `rede_lojas` | Marca |
|---|---|
| 1 | Animale |
| 2 | Farm |
| 5 | Fábula |
| 6 | OFF Premium |
| 7 | Foxton |
| 9 | Cris Barros |
| 15 | Maria Filó |
| 16 | NV (BYNV) |
| 30 | Carol Bassi |

> Observação: o escopo atual do agent inclui todas as marcas acima, mas o usuário
> sempre deve especificar qual marca quer analisar (ver `business-rules.md` §2).

---

## 4. Glossário — `tipo_reversa`

| Valor | Significado |
|---|---|
| `devolução` | **Estorno** — cliente devolve o produto e recebe o valor de volta |
| `troca` | **Troca** — cliente devolve e recebe outro produto |
| `troca e devolução` | **Híbrido** — parte do pedido vira troca, parte vira estorno |
| `sem reembolso` | **Híbrido** — devolve sem receber valor |

> Não é filtro padrão. É dimensão de análise — ver `business-rules.md` §3 para
> o protocolo de diálogo com o usuário.

---

## 5. Extração de `cod_cor` e `tamanho` a partir de `ref_id_produto`

O `ref_id_produto` tem o formato `produto_cor_tamanho`, separado por `_`.

Exemplo: `07.20.7491_0005_2`
- `07.20.7491` → produto (já disponível na coluna `cod_produto`)
- `0005` → **cod_cor**
- `2` → tamanho (índice de grade)

### SQL canônico

```sql
SPLIT(ref_id_produto, '_')[SAFE_OFFSET(1)] AS cod_cor,
SPLIT(ref_id_produto, '_')[SAFE_OFFSET(2)] AS tamanho_idx
```

> Uso de `SAFE_OFFSET` (não `OFFSET`) é obrigatório: se algum `ref_id_produto`
> vier fora do padrão (NULL, faltando parte), retorna NULL em vez de erro.
>
> ⚠️ Pendência de validação: confirmar que 99%+ das linhas têm exatamente 3 partes.
> Query de validação em `business-rules.md` §6.2.

---

## 6. Valores categóricos de `motivo`

Validado 2026-04-21 (últimos 30 dias, rede_lojas=1, devolução pura, filtros de
foto corrente aplicados). 9 valores distintos, ranked por volume:

| Motivo | Volume (30d, Animale, devolução pura) |
|---|---|
| o tamanho ficou grande | 904 |
| o produto não veste bem | 682 |
| o tamanho ficou pequeno | 577 |
| desisti da compra | 543 |
| não gostei da qualidade do produto | 269 |
| produto com defeito | 53 |
| recebi o produto errado | 37 |
| recebi meu produto incompleto | 21 |
| recebido pelo sistema integrador | 1 |

> **É categórico, não texto livre.** Agent pode agrupar direto por `motivo` sem
> precisar clusterizar. Para análise qualitativa de texto, usar `comentario_cliente`
> e `comentario_loja`.

---

## 7. URL da foto do produto

A URL não está armazenada — é **construída em SQL** a partir de `cod_produto` +
`cod_cor` (extraído via §5) + `rede_lojas` (porque BYNV usa API diferente).

### Fórmula canônica

```sql
CASE
  WHEN rede_lojas <> 16 THEN CONCAT(
    'https://images.somalabs.com.br/query/240/257/',
    cod_produto, '/',
    SPLIT(ref_id_produto, '_')[SAFE_OFFSET(1)]
  )
  ELSE CONCAT(
    'https://mais-produtos-api-wlavxis5jq-uc.a.run.app/v1/sku_public/',
    cod_produto, '_',
    SPLIT(ref_id_produto, '_')[SAFE_OFFSET(1)],
    '/vtex-images?brandId=361158'
  )
END AS url_foto
```

- Resolução 240×257 (retrato, ~2:3) é o default para produtos de moda Soma.
- BYNV (`rede_lojas = 16`) usa endpoint VTEX público com `brandId=361158` fixo.
- Todas as outras marcas usam `images.somalabs.com.br`.

> ⚠️ Pendências de validação:
> - Confirmar que a URL de BYNV não exige autenticação.
> - Confirmar que ambos os endpoints retornam content-type de imagem (pra renderizar
>   direto em markdown no chat).

Uso em output: ver `SKILL.md` §política de foto.

---

## 8. Histórico de atualizações

| Data | Mudança |
|---|---|
| 2026-04-21 | Criação. Schema inicial das 40 colunas. Regras críticas §1.1 (anti-duplicação CDC) e §1.2 (case-insensitive status) validadas empiricamente. Flags INT64 documentadas como desconhecidas. |
