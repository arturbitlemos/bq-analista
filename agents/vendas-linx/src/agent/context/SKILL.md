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
```bash
# 1. Dry-run first — estimate cost
bq query --use_legacy_sql=false --dry_run '<SQL>'

# 2. Execute only after dry-run confirms cost is acceptable
bq query --use_legacy_sql=false --format=prettyjson '<SQL>'
```

> ⚠️ Never execute a query without dry-run first on unknown tables.

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
  "tags": ["farm", "produtividade", "lojas"]
}
```

Nunca usar `titulo`, `marca`, `periodo`, `descricao` — a tool rejeita com `Field required`.
