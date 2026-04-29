---
name: querying-farm-sales
description: Use this skill whenever the user asks questions about sales, revenue, stores, products, brands, or retail KPIs using BigQuery. Covers venda líquida, venda bruta, CMV, markup, ticket médio, PA, and brand/store dimensions. Triggers on any analytics question about Azzas 2154 data.
---

# Azzas 2154 — BigQuery Sales Analytics

## Setup Check
Before any query, verify auth:
```bash
bq ls
```
If this fails, run `gcloud auth application-default login` first.

## Query Pattern (always use this)

> 🚨 **OBRIGATÓRIO — gate antes de qualquer execução:**
> 1. Estime o custo com base no período, tabelas envolvidas e joins.
> 2. Informe ao usuário: `⚠️ Estimativa: ~X GB → ~US$ X.XX (teto: 15 GB)`
> 3. **Aguarde confirmação explícita ("sim") antes de executar.** Nunca execute sem resposta do usuário.

```bash
# 1. Dry-run — confirma custo antes de executar
bq query --use_legacy_sql=false --dry_run '<SQL>'

# 2. Executa só após confirmação do usuário
bq query --use_legacy_sql=false --format=prettyjson '<SQL>'
```

Referência de custo: US$ 5,00 por TB = US$ 0,005 por GB.
Teto configurado: **15 GB por query**. Queries que estimativamente ultrapassem esse limite devem ser divididas ou reescritas antes de executar.

Tabelas de referência para estimativa:
| Tabela | Custo estimado por mês de dados |
|---|---|
| `TB_WANMTP_VENDAS_LOJA_CAPTADO` | ~2–4 GB |
| `ANMN_ESTOQUE_HISTORICO_PROD` | ~3–8 GB por data única (foto) |
| `ANMN_ESTOQUE_HISTORICO_PROD_GRADE` | ~5–15 GB por data única |
| `PRODUTOS_PRECOS` (join) | ~0,1 GB adicional |
| `LOJAS_PREVISAO_VENDAS` | ~0,5 GB por mês |

## Schema Discovery
```bash
# Inspect a table
bq show --schema --format=prettyjson PROJECT:DATASET.TABLE

# Sample data (always do this before writing complex SQL)
bq query --use_legacy_sql=false 'SELECT * FROM `PROJECT.DATASET.TABLE` LIMIT 20'

# List tables in dataset
bq ls PROJECT:DATASET
```

## Business Rules — Read business-rules.md for full detail

**Key fields:**
- `rede_lojas_mais_vendas` → brand code (INTEGER — see schema.md for mapping)
- `codigo_filial_mais_vendas` → store (point of sale)
- `valor_produto` → gross sales (before discount)
- `valor_pago_produto` → net sales (after discount) — **default metric**
- `cmv` → cost of goods sold
- `quantidade` → units sold

**Always use `valor_pago_produto` as the base metric unless explicitly told otherwise.**

**Core KPIs (see `business-rules.md` for canonical formulas with sign/key corrections):**
- Markup = `SUM(valor_pago_produto) / SUM(cmv_liquido)` — use `cmv_liquido` to avoid double-counting in returns
- Ticket Médio = `SUM(valor_pago_produto) / COUNT(DISTINCT chave_pedido)` — use treated `pacote` as `chave_pedido`
- PA = `SUM(quantidade) / COUNT(DISTINCT chave_pedido)`
- Margem Bruta = `(SUM(valor_pago_produto) - SUM(cmv_liquido)) / SUM(valor_pago_produto)`
- Taxa de Desconto = `(SUM(valor_produto) - SUM(valor_pago_produto)) / SUM(valor_produto)`

**Crítico — sempre consultar `business-rules.md`** antes de análises que envolvam:
- Canal (§2: mapeamento tipo_venda → Físico/Online)
- PA, ticket, contagem de atendimentos (§3: chave_pedido via pacote tratado)
- Markup ou margem (§4: correção de sinal do CMV)

For full schema context → read `schema.md`
For all business rules, canonical formulas, and analysis templates → read `business-rules.md`

## Workflow for Analytics Questions

### Passo 0 — Decidir o formato da resposta

Antes de executar qualquer query, classifique o pedido:

**Resposta inline** (responda direto no chat, sem dashboard):
- Pergunta pontual com uma métrica ou dimensão ("qual foi o ticket médio de ontem?")
- Verificação rápida ("quantos pedidos tivemos hoje?")
- Comparação simples entre dois valores
- Pedido explícito de resposta rápida

**Relatório analítico** (gera HTML e exibe inline no chat por padrão; publicar só a pedido explícito):
- Análise com múltiplos KPIs ou seções
- Pedido de "análise", "relatório", "dashboard", "comparativo completo"
- Análise histórica com mais de 2 dimensões

**Quando não for óbvio**, pergunte ao usuário:
> "Você quer uma resposta rápida aqui no chat ou um relatório HTML completo?"

---

1. **Understand the question** — identify dimensions (marca? loja? período?) and metrics (qual KPI?)
2. **Discover schema** if table is unknown (`bq show --schema`)
3. **Sample data** to verify column names and value formats
4. **Dry-run** the query
5. **Execute** and interpret results in business context
6. **Se relatório analítico**: Build HTML dashboard (mobile-first, dark green theme — see existing dashboards for reference) e renderize inline (Artifact / `present_files`). **Inline é o padrão — só rodar `publicar_dashboard` quando o usuário pedir explicitamente (ex.: "publica", "salva na biblioteca", "compartilha no portal").**
   - **Grão produto × cor → foto é OBRIGATÓRIA e deve ser a PRIMEIRA coluna da tabela.** Usar `https://images.somalabs.com.br/brands/{RL_DESTINO}/products/reference_id/{PRODUTO}_{COR_PRODUTO}/image` com `loading="lazy"` e `onerror="this.style.display='none'"`. Detalhes completos em `.claude/skills/product-photos/SKILL.md`. **Omitir a foto é erro de entrega — não fechar o HTML sem ela.**
   - **Canal obrigatório no cabeçalho:** todo relatório deve exibir explicitamente o escopo de canal aplicado — ex.: "Todos os canais (Físico + Digital + Omni)", "Somente Físico", "Somente Digital (Ecom + Omni + Vitrine)". Nunca omitir.
   - **Coluna de pedidos em relatório de produto:** quando o relatório incluir contagem de pedidos por produto, rotular como **"Pedidos"** (não "Atendimentos"). "Pedidos" = `COUNT(DISTINCT chave_pedido)` dos pedidos que continham aquele produto — é diferente de atendimentos totais da loja.
   - **Share de produto:** calcular sempre como `venda_produto / total_marca * 100` — nunca relativo ao produto #1. Usar CTE ou subquery para obter o total da marca no período antes de calcular o share.
   - **Cabeçalho de relatório de produto — não exibir card de Pedidos/Atendimentos por padrão.** O COUNT DISTINCT global requer query separada e ainda inclui devoluções, tornando o número ambíguo. Cabeçalho padrão: Venda Líquida · Peças Totais · Ticket Médio. Se o usuário solicitar explicitamente o total de pedidos, rodar query separada com `COUNT(DISTINCT chave_pedido)` sobre todos os produtos do relatório em conjunto — nunca somar as colunas das linhas.
7. **After corrections** → update `schema.md` with what you learned

## Output Format
- Always present numbers with Brazilian formatting (R$ 1.234,56)
- Percentages with 1 decimal (12,3%)
- When results are large, summarize top 10 and offer to export
- Contextualize results: "Ticket médio de R$320, +8,2% vs LY"

## Comparação vs LY — obrigatório

Sempre que a métrica permitir comparação temporal (venda, ticket médio, PA, markup, margem bruta, taxa de desconto, sell-through, giro, cobertura, etc.), a query **deve** trazer também o valor do **mesmo período do ano anterior (LY)**, e a resposta deve mostrar:

- Valor atual
- Valor LY
- Delta % (com sinal)

**Nunca comparar contra benchmark de mercado** — a referência é sempre histórico interno do grupo Azzas 2154. Usar `DATA_VENDA_RELATIVA` para ajuste de calendário (ver `business-rules.md` §6).

Se não houver LY disponível (produto/coleção nova, série temporal insuficiente), dizer explicitamente `❓ Sem LY` — não inventar proxy nem recorrer a benchmark externo.

**Gate antes de fechar a resposta:** a métrica principal tem delta vs LY? Se não e for possível ter, voltar e adicionar.

---

## Exibindo um Relatório HTML

Quando o fluxo exigir um relatório analítico (ver Passo 0), **renderize o HTML inline na interface** — nunca cole o HTML como bloco de código pro usuário copiar.

### Como entregar (ordem de preferência)

> ⚠️ **Relatórios com fotos de produto:** o artifact inline do Claude roda num sandbox com CSP restritivo que bloqueia `images.somalabs.com.br`. As fotos **não aparecem no artifact** — só aparecem ao abrir o HTML no navegador. Quando o relatório tiver fotos (grão produto × cor), **sempre oriente o usuário a abrir o HTML no navegador** e entregue como artifact avisando isso.

1. **Artifact HTML** (preferido quando disponível): crie um artifact do tipo `text/html` com o relatório completo. Se o relatório contiver fotos de produto, adicione este aviso no chat logo após criar o artifact:
   > "📂 As fotos aparecem ao abrir o HTML no navegador — no preview aqui do Claude elas não carregam por restrição de rede. Salve o artifact como `.html` e abra localmente."
2. **File system tools** (quando o ambiente tem `create_file` + `present_files`, ex. claude.ai com analysis tools): rode `create_file` salvando em `/mnt/user-data/outputs/<nome>.html` e em seguida `present_files` com esse path. O relatório é exibido inline.
3. **Fallback — só se nenhuma das duas acima estiver disponível**: avise o usuário que o ambiente atual não suporta renderização inline e pergunte se ele quer o HTML como bloco de código ou se prefere que você abra como artifact em outra sessão.

**Nunca** devolva o HTML num bloco ```` ```html ... ``` ```` a não ser no fallback (passo 3) e só após avisar o usuário.

### Conteúdo do HTML
- Mobile-first, tema verde escuro, padrão visual dos dashboards existentes.
- Sem dependências externas além de CDN (Chart.js, fontes).
- Logo após criar o artifact/arquivo, resuma os principais achados no chat em 3–6 bullets, seguindo o padrão do `analyst-principles.md` (número + tier + contexto).

### O que NÃO fazer
- ❌ Não colar o HTML como bloco de código no chat (exceto fallback explícito).
- ❌ Não rodar `publicar_dashboard` sem pedido explícito do usuário.
- ❌ Não criar arquivos em `analyses/`, `library/` ou `public/` do repositório manualmente (a tool cuida).
- ❌ Não pedir `USER_EMAIL` nem ler `.env`.

### Publicando (quando pedido explicitamente)

A tool `publicar_dashboard` aceita **exatamente** estes args, em inglês — **não traduzir**:

```json
{
  "title": "Farm · Produtividade por Loja · Abril/2026",
  "brand": "Farm",
  "period": "2026-04-01 a 2026-04-23",
  "description": "Comparativo de venda líquida e PA por filial vs LY.",
  "html_content": "<!doctype html>...",
  "tags": ["farm", "produtividade", "lojas"],
  "refresh_spec": { ... }
}
```

Nunca usar `titulo`, `marca`, `periodo`, `descricao` — a tool rejeita com `Field required`.

**`refresh_spec` é OBRIGATÓRIO.** A tool rejeita publicação sem ele com `refresh_spec_required`. Veja "Publicação com refresh garantido — contrato do data block" mais abaixo — o HTML precisa ser construído com data islands desde o início, então pense no `refresh_spec` antes de escrever a primeira `consultar_bq`, não depois.

---

## Antes de gerar uma análise nova: buscar histórico

Sempre que o usuário pedir uma análise não-trivial:

1. Chame `buscar_analises(query=<resumo da pergunta>, brand=<marca se houver>, agent="vendas-linx")`.
2. Se houver match recente (últimos 30 dias) com mesma marca + tema:
   - Mostre pro usuário: *"Já existe uma análise parecida: '<título>' (publicada há N dias). Quer atualizar com o novo período em vez de criar uma nova?"*
   - Se sim → instrua: *"abre o portal, clica nos 3 pontinhos do card '<título>' e escolhe 'Atualizar período'."* Não tente fazer o refresh por chat.
   - Se não → siga gerando a análise nova.
3. Para análises não-triviais, antes de escrever SQL do zero, chame `obter_analise(id=<id da mais relevante>)` em 1-2 análises e use as SQLs do `refresh_spec.queries[].sql` como **ponto de partida** (sempre adaptando — período, filtros, dimensões podem ter mudado).
4. Inclua uma linha no rascunho: *"reaproveitando estrutura de '<título da análise prévia>'"*.

## Publicação com refresh garantido — contrato do data block

Toda análise publicada deve atender este contrato:

> **SQL é a única camada de transformação. JS só renderiza. Cada data block tem uma query que retorna EXATAMENTE a forma que o JS lê.**

Isso significa:

- Não pré-agregue, não pré-junte e não calcule deltas em Python antes de embutir no HTML. Faça tudo em SQL (window functions, STRUCT, ARRAY_AGG, self-join CY/LY).
- Cada `<script id="data_X" type="application/json">` recebe o resultado da query `X`. Sem reuso (não mapeie 2 blocks pra mesma query a menos que ambos consumam o resultado idêntico).
- O JS no HTML faz `JSON.parse(...)` e renderiza. Sem agregação no browser.

### Como declarar o schema

No `refresh_spec`, cada `data_block` deve ter `schema = {shape, fields}`:

```jsonc
{
  "queries": [
    { "id": "summary", "sql": "SELECT total_cy, total_ly, ... FROM (...)" },
    { "id": "stores",  "sql": "SELECT n, cy, ly, v, c FROM (...) ORDER BY cy DESC" }
  ],
  "data_blocks": [
    { "block_id": "data_summary", "query_id": "summary",
      "schema": { "shape": "object", "fields": ["total_cy", "total_ly", "var_pct", "lojas"] } },
    { "block_id": "data_stores",  "query_id": "stores",
      "schema": { "shape": "array",  "fields": ["n", "cy", "ly", "v", "c"] } }
  ],
  "original_period": { "start": "2026-01-01", "end": "2026-04-27" }
}
```

- `shape: "array"` — bloco recebe a lista de rows como veio do BQ. JS faz `JSON.parse` e itera.
- `shape: "object"` — query DEVE retornar exatamente 1 row. O servidor desembrulha pra `{...}` antes de gravar. JS lê como objeto.
- `fields` — lista de campos obrigatórios em cada row. Validação roda em publish E em refresh; mismatch falha alta com nome do campo faltante.

### Comparativo CY vs LY — fazer em SQL

A regra "comparação sempre vs LY" continua. A diferença: o cálculo do delta vai pra dentro do SQL. Padrão:

```sql
WITH cy AS (SELECT ..., SUM(...) AS cy_val FROM ... WHERE data BETWEEN '{{start_date}}' AND '{{end_date}}' GROUP BY ...),
     ly AS (SELECT ..., SUM(...) AS ly_val FROM ... WHERE data BETWEEN DATE_SUB(DATE '{{start_date}}', INTERVAL 1 YEAR)
                                                                    AND DATE_SUB(DATE '{{end_date}}',   INTERVAL 1 YEAR) GROUP BY ...)
SELECT cy.dim, cy.cy_val AS cy, ly.ly_val AS ly, SAFE_DIVIDE(cy.cy_val - ly.ly_val, ly.ly_val) * 100 AS v
FROM cy LEFT JOIN ly USING (dim)
ORDER BY cy DESC
```

O placeholder `'{{start_date}}'` / `'{{end_date}}'` é substituído com a string ISO; LY se calcula com `DATE_SUB(..., INTERVAL 1 YEAR)` direto na query.

### Anti-padrões (vão quebrar refresh)

- ❌ Agregar em Python e jogar dict pronto no HTML sem schema correspondente.
- ❌ Mesma query mapeada pra 2 blocks com shapes diferentes.
- ❌ JS que faz `data.reduce(...)` pra calcular total — total deve vir da SQL.
- ❌ Schema declarado com campo `venda` mas SQL retornando `venda_liquida`.

### Período no header/footer — convenção `__period__`

Os relatórios costumam exibir o intervalo da análise em vários lugares (título, navbar, rodapé, metodologia). Pra que o **refresh** atualize esses textos junto com os números, **nunca escreva o período como string literal no HTML**. Use a convenção do bloco reservado `__period__`:

1. Embutir no HTML, junto com os outros data blocks:

```html
<script id="__period__" type="application/json">{
  "start_date": "2026-04-01",
  "end_date": "2026-04-18",
  "label_long": "1 a 18 de abril de 2026",
  "label_short": "01–18 abr 2026"
}</script>
```

2. Adicionar este snippet de JS uma única vez (antes do `</body>` é seguro):

```html
<script>
(() => {
  const meta = document.getElementById('__period__');
  if (!meta) return;
  const data = JSON.parse(meta.textContent);
  document.querySelectorAll('[data-period]').forEach(el => {
    const key = el.dataset.period;
    if (data[key] != null) el.textContent = data[key];
  });
})();
</script>
```

3. Marcar todo lugar que mostra período com o atributo `data-period`:

```html
<h1>Performance · <span data-period="label_long">1 a 18 de abril de 2026</span></h1>
<div class="navbar-meta">MTD · <span data-period="label_short">01–18 abr 2026</span></div>
<footer>Período <span data-period="start_date">2026-04-01</span> a <span data-period="end_date">2026-04-18</span></footer>
```

O texto inicial dentro do `<span>` é fallback caso o JS não rode — mantenha consistente com o que o bloco declara.

**Como o refresh atualiza isso**: o servidor injeta automaticamente um payload novo no `<script id="__period__">` com base no `start`/`end` da requisição (campos `start_date`, `end_date`, `label_long`, `label_short` em pt-BR). Você **não** declara `__period__` em `refresh_spec.data_blocks` — é reservado e tratado fora do contrato de queries. O prefixo `__` é proibido em block_ids de usuário.

Relatórios sem essa convenção continuam refrescando os números, mas os textos de período ficam congelados — só republicar resolve.

## Convenções de tags

Use uma ou mais das tags canônicas pra que `buscar_analises` consiga ranquear bem:

- Recorte temporal: `mtd`, `ytd`, `7d`, `30d`, `90d`
- Tipo: `ranking`, `comparativo`, `tendencia`, `auditoria`
- Dimensão: `produto`, `loja`, `marca`, `canal`, `colecao`, `vendedor`
- Métrica em destaque: `markup`, `giro`, `cobertura`, `pa`, `ticket-medio`

Tags em slug-case (lowercase, sem acento, separado por hífen). Não invente sinônimos — se faltar uma tag canônica pra teu caso, use a que mais aproxima.
