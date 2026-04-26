# Plano — Camadas de governança de dados para `bq-analista`

> **Status: ARQUIVADO em 2026-04-26 — para implementação futura.**
> Plano discutido, decisões de design tomadas (AAD groups, SA única, eixos Marca+Canal na Fase 1, evolução em 3 fases). Não implementar agora; retomar quando o usuário pedir.

## Context

Hoje o controle de acesso da plataforma é **binário**: o e-mail está ou não na allowlist (`agents/*/config/allowed_execs.json`), e cada agente declara estaticamente seus datasets em `agents/*/config/settings.toml` (validado por dry-run do BigQuery em `BqClient._check_allowed_datasets`). Isso resolve "quem entra", mas **não** resolve:

- **Quem vê qual marca** (Farm vs Animale vs Foxton vs Carol Bassi…) — 10 marcas hoje, todas misturadas.
- **Quem vê qual canal** (físico × e-com) — squads diferentes, hoje todos veem tudo.
- **Quem vê dados sensíveis** (CMV, margem, preço de custo, SLA reverso) — sem distinção entre analista e diretoria.
- **PII por enforcement de plataforma** (não por disciplina do prompt) — hoje depende do `CLAUDE.md` ser respeitado a cada chamada, sem rede de segurança no servidor.
- **Audit por dimensão de dado** — `BqClient.run_query` já labela jobs com `exec_email`, mas não há registro estruturado de "quem perguntou o quê e viu quais marcas/colunas".

A solução vai crescer de 2 para 10+ agentes. Sem uma camada de governança desenhada agora, cada novo agente vira uma decisão ad-hoc e o blast radius de um vazamento ou erro de escopo vira o grupo todo.

**Decisões já tomadas com o usuário** (perguntas respondidas em 2026-04-26):

| Decisão | Escolha |
|---|---|
| Fonte de identidade/policy | **Grupos do Azure AD** (TI já controla onboarding) |
| Identidade no BQ | **SA única + filtros injetados pela app** (mantém arquitetura atual; audit via job labels) |
| Eixos da Fase 1 | **Marca + Canal** |
| Apetite arquitetural | A definir — o usuário pediu recomendação de longo prazo; este plano apresenta uma evolução em 3 fases |

---

## Visão de longo prazo — evolução em 3 fases

A recomendação **não é "escolher uma arquitetura para sempre"**. É evoluir conforme a dor justifica:

| Fase | Quando | Acréscimo principal | Custo | Justificativa de gatilho |
|---|---|---|---|---|
| **1 — Foundation** | Agora (próx. 4-6 semanas) | PDP interno em Python no `mcp-core`, mapeamento `AAD group → escopo`, injeção de WHERE, BQ policy tags + masking para PII | Baixo, sem stack nova | 2 agentes, ≤20 usuários: OPA/semantic layer seriam over-engineering |
| **2 — Hardening** | Quando passar de ~5 agentes ou ~50 usuários | SA por persona (impersonation), audit estruturado em BQ, extrair PDP para policies declarativas (DSL própria ou Rego/OPA), defesa em profundidade no IAM | Médio | Volume justifica investir em isolamento de blast radius e auditoria por usuário no GCP nativo |
| **3 — Scale** | Quando ≥3 agentes começarem a divergir nas mesmas métricas (PA, ticket, receita líquida) ou quando entrar regulação adicional | Semantic layer (dbt Semantic Layer preferencialmente — alinha com BigQuery), métricas como API governada, agentes consultam SL e não SQL livre | Alto (reforma) | Padroniza KPIs + simplifica governança (uma camada de policy em vez de N) |

**Por que essa ordem**: o foundation (Fase 1) já elimina o risco mais alto (vazamento por marca/canal/PII) sem adicionar dependências. As Fases 2 e 3 são **opcionais condicionadas** a sinais reais de dor, não cronograma.

---

## Fase 1 — Foundation (escopo deste plano)

### Princípios

1. **Filtros são determinísticos, não confiáveis ao LLM.** O agente nunca decide "se aplica" o filtro de marca — o `mcp-core` injeta no SQL antes de submeter, fora do contexto do LLM (defesa contra prompt injection).
2. **PDP separado do PEP.** PDP (decisão) = função pura `evaluate(user_claims, agent, request) → decision`. PEP (enforcement) = `BqClient` injeta WHERE / valida colunas. Assim Fase 2 troca o PDP sem mexer no PEP.
3. **Defense in depth.** Mesmo com SA única, BigQuery aplica policy tags em PII/CMV — se um filtro falhar, o BQ ainda mascara.
4. **Audit-first.** Antes de habilitar enforcement, rodar 2 semanas em modo "shadow" (loga o que rejeitaria, não rejeita), para calibrar policies sem quebrar usuários.

### Arquitetura proposta (Fase 1)

```
Portal (Next.js + MSAL)
   │  JWT com email + groups (AAD)
   ▼
mcp-core auth_middleware  ──→  AllowlistChecker (mantém)
   │
   ▼
PDP em mcp_core/policy/ (NOVO)
   │  decision = evaluate(claims, agent_domain, request)
   │  → { allow: bool, brand_filter: list, channel_filter: list,
   │      column_blocklist: set, reason: str }
   ▼
Tool handler do agente
   │  injeta WHERE/SELECT no SQL conforme decision
   ▼
BqClient.run_query (mantém SA única)
   │  + label exec_email + brand_scope + agent
   │  + audit estruturado (NOVO)
   ▼
BigQuery
   │  policy tags em PII/CMV (NOVO no GCP, fora do código)
   │  authorized datasets opcionais (Fase 1.5)
```

### Modelo de policy (Fase 1)

Mapeamento `AAD group → escopo`, versionado em arquivo no repo (auditável via PR). Estrutura proposta:

```yaml
# packages/mcp-core/config/policies.yaml  (ou agents/*/config/policy.yaml por agente)
version: 1
groups:
  bq-farm-analyst:
    brands: [FARM]
    channels: [VENDA_LOJA, VENDA_ECOM, VENDA_OMNI, VENDA_VITRINE]
    sensitive_columns: deny  # não vê CMV/margem
  bq-ecom-director:
    brands: "*"
    channels: [VENDA_ECOM, VENDA_OMNI, VENDA_VITRINE]
    sensitive_columns: allow
  bq-superadmin:
    brands: "*"
    channels: "*"
    sensitive_columns: allow
defaults:
  brands: []        # se não casa nenhum grupo, nega tudo
  channels: []
  sensitive_columns: deny
```

A decisão é a **união** dos escopos dos grupos do usuário (ex: alguém em `bq-farm-analyst` + `bq-animale-analyst` vê Farm e Animale). `*` é coringa.

### Injeção de filtro (PEP)

`BqClient.run_query` recebe um `PolicyDecision` opcional e:

1. Faz dry-run para extrair tabelas referenciadas.
2. Para cada tabela conhecida em `policy_table_mappings.yaml` (mapa `tabela → coluna_marca, coluna_canal`), injeta `WHERE coluna_marca IN (...) AND coluna_canal IN (...)` via wrapping da query original em um CTE/subquery.
3. Se tabela referenciada não está mapeada, **nega por padrão** (evita atalho via tabela nova).
4. Se `column_blocklist` ativo, valida o schema dos campos de saída e nega se houver coluna sensível no SELECT.

Exemplo de wrap:

```sql
-- query original do agente:
SELECT marca, SUM(receita) FROM v
-- vira:
WITH v AS (
  SELECT * FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO`
  WHERE CAST(RL_DESTINO AS STRING) IN ('2')           -- escopo Farm
    AND TIPO_VENDA IN ('VENDA_LOJA','VENDA_ECOM',...)  -- escopo canal
)
SELECT marca, SUM(receita) FROM v
```

(Wrap é mais simples e auditável que reescrever o WHERE inline; a Fase 2 pode evoluir para sqlglot AST se necessário.)

### Camada nativa do BigQuery (Fase 1.5 — feita no GCP, não no código)

Para defense in depth e cobrir o caso "alguém esqueceu de passar pelo PDP":

- **Policy tags + dynamic data masking** em todas as colunas PII listadas em `agents/vendas-linx/src/agent/context/schema.md` §7 e `agents/devolucoes/.../schema.md` §1.3:
  - Taxonomy: `azzas/confidencial/pii_alta` (CPF, e-mail, telefone, credenciais), `azzas/confidencial/pii_funcionario` (matrícula, nome, vendedor), `azzas/confidencial/financeiro` (PRECO_CUSTO, margem).
  - Masking rule default: `DEFAULT_MASKING_VALUE`. Override por grupo (Fine-Grained Reader) só para personas explícitas.
- **Authorized datasets** (Fase 1.5, opcional): `silver_linx_curado` com views já filtradas/mascaradas; agentes leem só do dataset curado. Reduz superfície de SQL livre.

### Audit estruturado (Fase 1)

Estender `mcp_core/audit.py` (já existe, default 90 dias) para registrar por chamada:

```
{
  conversation_id, exec_email, aad_groups,
  agent_domain, tool_name, prompt_hash,
  policy_decision: { allowed_brands, allowed_channels, columns_blocked },
  sql_executed_hash, sql_executed,
  bq_job_id, rows_returned_count,
  columns_returned: [...],   # nomes, NÃO valores
  ts
}
```

**Nunca logar linhas** — recriaria PII no audit.

### Modo shadow (rollout seguro)

Flag `MCP_POLICY_MODE = shadow | enforce` (default `shadow` por 2 semanas):
- `shadow`: PDP roda, decisão é logada, mas SQL **não** é alterado. Permite calibrar policies vendo "o que rejeitaria".
- `enforce`: injeção real de filtros + bloqueio.

---

## Arquivos críticos a modificar (Fase 1)

### Novos

- `packages/mcp-core/src/mcp_core/policy/__init__.py` — fachada do PDP.
- `packages/mcp-core/src/mcp_core/policy/loader.py` — lê `policies.yaml` com TTL (mesmo padrão do `allowlist.py`).
- `packages/mcp-core/src/mcp_core/policy/evaluator.py` — `evaluate(claims, request) → PolicyDecision` (função pura, testável).
- `packages/mcp-core/src/mcp_core/policy/injector.py` — wrapping de SQL com WHERE de marca/canal; valida colunas vs blocklist.
- `packages/mcp-core/config/policies.yaml` — mapeamento `group → escopo` (versionado).
- `packages/mcp-core/config/policy_table_mappings.yaml` — `tabela → {coluna_marca, coluna_canal}` (versionado).
- `packages/mcp-core/tests/test_policy_evaluator.py` — testes de união de grupos, deny default, coringa.
- `packages/mcp-core/tests/test_policy_injector.py` — testes de wrap correto, deny em tabela não mapeada, blocklist de colunas.

### Modificados

- `packages/mcp-core/src/mcp_core/jwt_tokens.py` — incluir `groups` (claim do AAD) no payload validado e propagado.
- `packages/mcp-core/src/mcp_core/auth_middleware.py` — anexar `PolicyDecision` ao request context após autenticação.
- `packages/mcp-core/src/mcp_core/bq_client.py` — `run_query` aceita `policy_decision`; chama `injector` antes de submeter; labela job com `brand_scope`; modo `shadow` vs `enforce` via env.
- `packages/mcp-core/src/mcp_core/audit.py` — campos novos (`aad_groups`, `policy_decision`, `columns_returned`).
- `packages/mcp-core/src/mcp_core/settings.py` — adicionar `MCP_POLICY_MODE` e `MCP_POLICIES_PATH` ao `_ENV_OVERRIDES`.
- `agents/vendas-linx/config/settings.toml` e `agents/devolucoes/config/settings.toml` — referência ao `policies.yaml` (path ou URL).
- `agents/*/config/allowed_execs.json` — **mantém para fallback**, mas o padrão passa a ser groups; documentar deprecação gradual.
- `CLAUDE.md` — adicionar seção "Governança de dados — modelo de policy" com referência aos eixos Marca/Canal e à fonte de verdade (AAD groups).

### GCP (fora do repo)

- Criar **taxonomy de policy tags** no Data Catalog (`azzas/confidencial/pii_alta`, `pii_funcionario`, `financeiro`).
- Aplicar tags às colunas listadas em `schema.md` §7 e `devolucoes/schema.md` §1.3.
- Criar grupos no Azure AD: `bq-{marca}-analyst`, `bq-ecom-director`, `bq-varejo-director`, `bq-superadmin` (TI).

### Reuso de utilitários existentes

- **`AllowlistChecker` (TTL de 30s, JSON+env)** em `allowlist.py`: replicar exatamente o padrão para `PolicyLoader` — não inventar mecanismo novo de reload.
- **`BqClient._check_allowed_datasets`**: já faz dry-run e inspeciona referenced tables — `injector` deve reusar essa inspeção, não duplicar.
- **`audit.py`** com `retention_days` configurável: estender colunas, não criar tabela paralela.
- **`TokenIssuer` + JWKS validator**: já valida `tid` (tenant) e `iss`; só precisa expor o claim `groups` que já vem do AAD.

---

## Verification

### Testes unitários (rodar antes de qualquer enforcement)

```bash
cd packages/mcp-core && pytest tests/test_policy_evaluator.py tests/test_policy_injector.py -v
```

Cobertura mínima:
- União de escopos de múltiplos grupos.
- Deny por default quando usuário não casa nenhum grupo.
- Coringa `*` em brands/channels.
- Wrap SQL produz query equivalente quando escopo é `*` (não-regressão).
- Wrap SQL bloqueia tabela não mapeada.
- Blocklist de colunas detecta `PRECO_CUSTO` em SELECT * via dry-run.

### Teste de integração (SA dev contra dataset de teste)

```bash
cd packages/mcp-core && pytest tests/integration/test_policy_e2e.py -v
```

Cenários:
- Usuário Farm-only roda query de "vendas por marca" → recebe só FARM.
- Usuário Farm-only roda query referenciando `RL_DESTINO IN ('1','2')` → marca '1' (Animale) some no resultado (filtro injetado vence).
- Usuário sem grupo qualquer → request rejeitado com motivo claro.

### Modo shadow (2 semanas em prod)

1. Deploy com `MCP_POLICY_MODE=shadow`.
2. Inspecionar `audit.db` diariamente: contar quantas chamadas teriam sido bloqueadas e quais colunas teriam sido mascaradas.
3. Ajustar `policies.yaml` até a taxa de "false deny" (usuário legítimo bloqueado) for ~0.
4. Anunciar para usuários, virar `MCP_POLICY_MODE=enforce`.

### Validação BigQuery nativa

- Logar com identidade sem permissão `Fine-Grained Reader` na tag `pii_alta` → query retornando `cpf_cliente` retorna `XXX` (não bytes reais).
- Verificar via Cloud Audit Logs que `exec_email` e `brand_scope` aparecem nas job labels para amostra de execuções.

### Regressão dos agentes

```bash
cd agents/vendas-linx && pytest -v
cd agents/devolucoes && pytest -v
```

Garantir que a chamada normal de tools continua funcionando para `bq-superadmin` (escopo `*`), espelhando o comportamento atual.

---

## Fora de escopo (Fase 1)

Coisas que **não** entram agora, mas têm gatilho documentado para entrar nas Fases 2/3:

- Tipo de filial (próprio × franquia) e Região como eixos — só com sinal organizacional claro.
- Service-account impersonation por persona (Fase 2).
- OPA/Cedar como motor de policies (Fase 2 se policies passarem de ~30 regras).
- Semantic layer (Fase 3, condicional a divergência de KPIs entre agentes).
- UI de admin no portal para editar policies (Fase 2 — hoje, edita via PR).

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| AAD não retornar `groups` no token (limite de 200 grupos no JWT) | Usar Microsoft Graph para buscar grupos quando o claim vier truncado; cachear por sessão |
| Wrap de SQL quebrar queries com CTEs já existentes | Detectar via parse leve (sqlglot opcional na Fase 1, obrigatório na 2); fallback para deny + log se não conseguir wrap seguro |
| Usuário legítimo bloqueado em produção | Modo shadow obrigatório por 2 semanas; canal direto para reportar false deny; rollback via flag |
| Policies viram bagunça com 50+ entradas | Lint script obrigatório no CI; convenção de nome de grupo padronizada (`bq-<marca>-<role>`) |
| LLM tentar burlar via prompt ("ignore o filtro") | Filtro é injetado pelo PEP no servidor, **fora** do contexto do LLM — impossível por design |
