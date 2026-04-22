# Business Rules — Agente de Devoluções

> Documento canônico de regras de negócio para análises sobre
> `soma-crm-bi.dados_trusted.trusted_troque_devolucao`.
>
> Complementa `schema.md` (dicionário de dados) e `SKILL.md` (workflow do agent).
>
> **Convenção:** ao descobrir ou corrigir uma regra, atualize este arquivo e
> comite. Regras aqui são compartilhadas entre todos os usuários do agent.

---

## 1. Regras críticas — 🔴 nunca remover sob nenhuma hipótese

### 1.1 Anti-duplicação (CDC): foto corrente

A tabela carrega o **histórico de status via CDC** — cada mudança de status gera
uma nova linha para o mesmo `id_troque`. Para contar pedidos, valores, tempos ou
qualquer métrica de "estado atual", sempre filtrar:

```sql
LOWER(status) = LOWER(ultimo_status)
```

**Sem esse filtro, cada pedido é contado múltiplas vezes.**

Validado 2026-04-21 (Animale, últimos 30 dias, `tipo_reversa = 'devolução'`):
- Sem o filtro: 7.994 linhas
- Com o filtro: 3.087 linhas
- Descartadas: 4.907 linhas (**61%**)

Ou seja, remover o filtro infla a contagem em **~2,6×**.

### 1.2 Comparações de status sempre em lowercase

A coluna `status`/`ultimo_status` tem **case inconsistente** no storage. Já foi
observado `"Cancelado"` com C maiúsculo, mas outros valores podem ter variações.
Comparações case-sensitive geram bugs silenciosos (filtro não funciona, retorna
linhas que deveriam sair).

**Regra:** SEMPRE usar `LOWER()` em comparações com literais.

```sql
-- ✅ Correto
LOWER(ultimo_status) <> 'cancelado'
LOWER(ultimo_status) = 'finalizado'

-- ❌ Errado — bug silencioso
ultimo_status <> 'cancelado'    -- não exclui 'Cancelado' com C maiúsculo
```

Regra também se aplica a `status`, `tipo_reversa`, e qualquer outra coluna STRING
onde observarmos case inconsistente no futuro.

---

## 2. Marca (`rede_lojas`) — filtro obrigatório, usuário sempre especifica

A tabela contém dados de **9 marcas** da Soma (ver `schema.md` §3). O escopo de
uma análise é sempre **uma marca** (ou, explicitamente, "todas" com consolidação).

### Protocolo

- Agent **nunca assume uma marca** como default.
- Se o usuário não especificar, **perguntar antes de rodar**:
  > "Sobre qual marca você quer analisar? (Animale, Farm, Fábula, OFF Premium,
  > Foxton, Cris Barros, Maria Filó, NV/BYNV, Carol Bassi)"
- Se o usuário disser "todas" ou "consolidado", rodar agrupando por `rede_lojas`
  e apresentar o recorte por marca — **nunca somar entre marcas sem mostrar a
  quebra**, porque volumes variam muito entre elas.

### Filtro SQL

```sql
rede_lojas = <N>          -- uma marca
-- ou
rede_lojas IN (1, 2, 5)   -- subset explícito
```

---

## 3. Tipo de reversa (`tipo_reversa`) — dimensão de análise, não filtro fixo

`tipo_reversa` tem 4 valores (ver `schema.md` §4). Cada um representa um tipo
distinto de reversa no negócio:

| Valor | Significado |
|---|---|
| `devolução` | Estorno — cliente devolve, recebe valor de volta |
| `troca` | Troca — cliente devolve, recebe outro produto |
| `troca e devolução` | Híbrido — parte vira troca, parte vira estorno |
| `sem reembolso` | Híbrido — devolve sem receber valor |

### Protocolo de diálogo

Quando o usuário disser "devoluções", **o termo é ambíguo**. Agent **pergunta**
o recorte antes de rodar:

> "Quer analisar só estornos puros (`devolução`), a reversa total (inclui trocas
> e híbridos), ou um subconjunto específico?"

Opções que o agent aceita:
- **Estorno puro:** `tipo_reversa = 'devolução'`
- **Reversa total:** sem filtro em `tipo_reversa` (todas as 4 categorias)
- **Só trocas:** `tipo_reversa = 'troca'`
- **Subconjunto explícito:** `tipo_reversa IN (...)` com os valores que o usuário pediu

Se o usuário disser "qualquer" ou "tanto faz", usar **reversa total** como default
e documentar essa escolha na resposta.

---

## 4. Query canônica (base de toda análise)

Toda análise parte de uma **CTE base** com os filtros obrigatórios aplicados.
Agent pode adicionar dimensões, agregações e filtros adicionais em cima, mas
os filtros abaixo **nunca são removidos**.

```sql
WITH base AS (
  SELECT
    id_troque,
    pacote,
    rede_lojas,
    marca,
    tipo_reversa,
    data_solicitacao,
    status,
    ultimo_status,
    motivo,
    comentario_loja,
    comentario_cliente,
    ref_id_produto,
    cod_produto,
    SPLIT(ref_id_produto, '_')[SAFE_OFFSET(1)] AS cod_cor,
    valor_prod,
    preco_frete,
    transportadora_tratada,
    tempo_total_reversa_dias,
    cidade_cliente,
    estado_cliente
  FROM `soma-crm-bi.dados_trusted.trusted_troque_devolucao`
  WHERE
    -- 🔴 filtros críticos (nunca remover)
    LOWER(status) = LOWER(ultimo_status)
    AND LOWER(ultimo_status) <> 'cancelado'

    -- ✅ escopo obrigatório (usuário especifica)
    AND rede_lojas = @rede_lojas
    AND data_solicitacao >= @data_inicio
    AND data_solicitacao <  @data_fim

    -- 🔀 tipo_reversa: aplicar conforme diálogo §3
    -- AND tipo_reversa = 'devolução'           (estorno puro)
    -- AND tipo_reversa IN ('devolução', ...)   (subconjunto)
    -- (sem filtro)                             (reversa total)
)
SELECT ...
FROM base
...
```

### Variações flexíveis (usuário pode ajustar)

- **Janela de data:** default últimos 30 dias (`data_solicitacao >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)`), mas usuário pode pedir outra.
- **Marca:** sempre especificada (§2).
- **`tipo_reversa`:** dialogado (§3).

### Variações bloqueadas (nunca mudar)

- Os dois filtros 🔴 do §1 sempre presentes.
- `cpf_cliente` nunca sai no SELECT (PII — ver `schema.md` §1.2).
- Flags INT64 desconhecidas não são usadas (ver `schema.md` §1.3).

---

## 5. KPIs canônicos

Todas as fórmulas abaixo assumem que a CTE `base` do §4 já foi aplicada.

### 5.1 Volume de reversas

```sql
COUNT(DISTINCT id_troque) AS pedidos_reversa
COUNT(*) AS itens_reversa
```

> Diferença importante: `id_troque` é o pedido; um pedido pode ter múltiplos
> itens (linhas). Usar `COUNT(DISTINCT id_troque)` para "quantos clientes
> pediram reversa" e `COUNT(*)` para "quantos itens foram devolvidos".

### 5.2 Valor total devolvido

```sql
SUM(valor_prod) AS valor_total_devolvido
```

> `valor_prod` é o valor do item. Para "valor total + frete da reversa",
> somar `valor_prod + COALESCE(preco_frete, 0)`.

### 5.3 Ticket médio de reversa

```sql
SUM(valor_prod) / NULLIF(COUNT(DISTINCT id_troque), 0) AS ticket_medio_reversa
```

### 5.4 Distribuição de motivos

```sql
SELECT motivo, COUNT(*) AS n
FROM base
GROUP BY motivo
ORDER BY n DESC
```

### 5.5 SLA — tempo total de reversa

```sql
AVG(tempo_total_reversa_dias) AS sla_medio_dias
APPROX_QUANTILES(tempo_total_reversa_dias, 100)[OFFSET(50)] AS sla_mediano_dias
APPROX_QUANTILES(tempo_total_reversa_dias, 100)[OFFSET(90)] AS sla_p90_dias
```

> Mediana e p90 são mais informativas que média — SLA tem cauda longa.

### 5.6 Top produtos devolvidos

```sql
SELECT
  cod_produto,
  cod_cor,
  COUNT(*) AS n_devolucoes,
  SUM(valor_prod) AS valor_devolvido,
  <url_foto conforme schema.md §7>
FROM base
GROUP BY cod_produto, cod_cor
ORDER BY n_devolucoes DESC
LIMIT 20
```

> Ver `SKILL.md` política de foto — quando a análise for ranking de produto,
> a foto é incluída no output.

---

## 6. Datas — qual coluna usar

| Situação | Coluna |
|---|---|
| Análise default ("últimos 30 dias", "abril", "ontem") | `data_solicitacao` ✅ |
| Análise de SLA / ciclo completo | `data_finalizacao_reversa` |
| Análise de eventos logísticos | `data_criacao_rastreamento`, `data_entrega` |
| Análise de entrega dentro/fora do prazo | comparar `data_entrega` vs `data_entrega_prevista` |

**`data_solicitacao` é a escolha segura para quase toda análise.** Trocar
apenas quando explicitamente pedido.

### 6.1 Glossário de janelas temporais

| Termo | Significado | Filtro SQL |
|---|---|---|
| MTD | Do 1º do mês corrente até ontem | `BETWEEN DATE_TRUNC(CURRENT_DATE(), MONTH) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)` |
| YTD | Do 1º do ano corrente até ontem | `BETWEEN DATE_TRUNC(CURRENT_DATE(), YEAR) AND DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)` |
| Últimos N dias | N dias antes de ontem até ontem | `>= DATE_SUB(CURRENT_DATE(), INTERVAL N DAY) AND < CURRENT_DATE()` |

> **MTD e YTD nunca incluem o dia de hoje** — o fechamento do dia corrente é
> parcial e distorce a análise. Corte é sempre `CURRENT_DATE() - 1`.

### 6.2 Pendência de validação: formato de `ref_id_produto`

Confirmar que 99%+ das linhas seguem o padrão de 3 partes separadas por `_`.
Query:

```sql
SELECT
  ARRAY_LENGTH(SPLIT(ref_id_produto, '_')) AS n_partes,
  COUNT(*) AS linhas
FROM `soma-crm-bi.dados_trusted.trusted_troque_devolucao`
WHERE data_solicitacao >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND LOWER(ultimo_status) <> 'cancelado'
  AND LOWER(status) = LOWER(ultimo_status)
GROUP BY 1
ORDER BY linhas DESC
```

Se `n_partes = 3` for >99%, o padrão de extração `cod_cor` (schema.md §5) é
confiável. Casos fora do padrão: documentar aqui e decidir fallback.

---

## 7. Hierarquia analítica (template mental de resposta)

Toda análise deve seguir aproximadamente esta ordem:

```
1. Contexto     — o que estamos medindo, para qual marca, qual período
2. Volume       — quantos pedidos, quantos itens, qual valor total
3. Composição   — quebra por motivo, por produto, por geografia (conforme pergunta)
4. SLA          — se relevante à pergunta: tempo total, gargalos
5. Diagnóstico  — comparativo com período anterior, ou com outras marcas
6. Recomendação — só se solicitado ou se houver um padrão evidente
```

Não pular direto para detalhe (ex: "top 1 produto devolvido") sem ancorar o
volume total primeiro (ex: "em 3.087 reversas na Animale nos últimos 30 dias,
o produto mais devolvido foi...").

---

## 8. Princípio anti-hallucination

**Nunca inventar um número.** Todo valor em resposta deve vir de:

1. ✅ **Dado real** — query executada nesta sessão
2. 📊 **Benchmark** — referência de mercado com fonte
3. 🔶 **Estimativa** — cálculo explícito a partir de dado real
4. ❓ **Indisponível** — não está na tabela, não extrapolar

Se agent não tem o dado, a resposta correta é **"não tenho esse dado disponível
nesta tabela"** — nunca inventar ou aproximar sem aviso.

---

## 9. Histórico de atualizações

| Data | Mudança |
|---|---|
| 2026-04-21 | Criação. Regras críticas 1.1 e 1.2 validadas empiricamente. Query canônica definida (Modelo B — CTE base fixa + variações flexíveis). Glossário `tipo_reversa` e protocolo multi-marca documentados. |
