# Portal Azzas Análises — Auditoria UI/UX (2026-05-15)

Branch: `feat/portal-uiux-audit` · Método: Playwright (Chrome) headless, cookie de sessão HMAC mintado a partir de `SESSION_SECRET`, MSAL mockado para destravar a biblioteca logada. Viewports: desktop 1440×900 e mobile 390×844.

## Critério de sucesso

1. **Funcional**: 4 fluxos (login → library+filtros → abrir análise → admin/onboarding/dicionário) sem bug funcional.
2. **Performance**: Lighthouse mobile ≥ 90 perf / ≥ 95 a11y / ≥ 95 best-practices na home.
3. **UX/Negócio**: Nielsen + heurísticas de portal de BI. Cada achado classificado por impacto. Alto impacto → commit com antes/depois.
4. **Stop**: parar quando só sobrar P2/P3 cosmético.

## Tese de negócio

O produto é uma biblioteca de BI cujo valor é "abrir e ver o número rápido, confiar nele, e querer voltar". Os gargalos competitivos hoje não são de features — são de **momentos de confiança**: a porta de entrada (login sem marca), o momento de valor (abrir dashboard = tela branca), e os estados de falha (texto preto cru). Um portal interno que parece frágil nesses três momentos perde adoção mesmo com dados bons por trás.

## Achados priorizados

| ID | Impacto | Achado | Heurística |
|----|---------|--------|------------|
| U1 | **ALTO** | Abrir análise = iframe em branco, zero feedback. É o momento de maior valor do produto. | Visibilidade do status (Nielsen #1) |
| U2 | **ALTO** | Sem tela de login com marca. Logged-out vê spinner cru → redirect instantâneo pro Microsoft. Zero marca/contexto/confiança. | Reconhecimento, confiança, branding |
| U3 | **ALTO** | Estado de erro catastrófico: falha no `/api/config` mostra "Erro: Failed to load Azure config" em texto preto, sem marca, sem retry. | Recuperação de erro (Nielsen #9) |
| U4 | MÉD-ALTO | Skeletons da library não resolvem se agentes lentos; counts piscam 0→N; erro de reload esvazia o grid. | Visibilidade, performance percebida |
| U5 | MÉDIO | Aba default é "Minhas". Usuário novo (zero análises) cai num beco vazio em vez de ver o valor (públicas do time). | Ativação first-run |
| U6 | MÉDIO | Empty states são uma frase cinza sem CTA. "Minhas" vazio cita a extensão mas não linka pro /onboarding. Funil de ativação furado. | Affordance, funil |
| F2 | MÉDIO | Página admin renderiza chrome inteiro + erros vermelhos pra não-admin, e dispara fetches antes de checar acesso. | Prevenção de erro, gating |
| U7 | MÉDIO | Header mobile espremido: marca + 3 links + chip de email sem colapsar. | Responsivo |
| U8 | BAIXO-MÉD | A11y: tabs sem `aria-selected`, iframe sem anúncio de loading, `--ink-faint #999` falha contraste AA. | Acessibilidade |
| U9 | BAIXO | "Instalar no Claude" (nav) vs título da página de onboarding — naming inconsistente. | Consistência |

## Escopo desta rodada (implementado)

Alto impacto + alavancagem barata: **U1, U2, U3, U4, U6, F2** e **U5** (decisão de produto reversível: cair em "Público" quando "Minhas" está vazio no first-run). U7/U8/U9 ficam como P2 priorizados no relatório final.

## Resultado (verificado via Playwright + Lighthouse)

| Critério | Meta | Resultado |
|----------|------|-----------|
| Lighthouse perf (home, mobile) | ≥ 90 | **93–94** (FCP 3.1s → 1.0s) |
| Lighthouse a11y | ≥ 95 | **100** |
| Lighthouse best-practices | ≥ 95 | **100** |
| Fluxos funcionais (sweep desktop+mobile) | 0 bug | **0 pageerror, todos navOk** |

Implementado e verificado com antes/depois (`scripts/uiux-audit/screenshots/{pre,post}.*`):
U1 overlay de loading no iframe · U2 tela de login com marca · U3 erro com marca + retry · U4 erro de library in-grid · U5 first-run cai em Público · U6 empty state com CTA · U8 aria-selected + contraste AA · F2 admin gate limpo · perf: fontes non-render-blocking.

### Pendentes (P2/P3 — não bloqueiam)

- **U7** header mobile espremido (marca + 3 links + chip sem colapsar) — refator de layout, maior.
- **U9** naming "Instalar no Claude" vs título da página de onboarding.
- **F3** probe `/api/admin/analytics` loga 403 no console pra não-admin (ruído de devtools, não visível ao usuário; some-lo exigiria mexer na API).
- i18n: `state-error` ainda mostra "Failed to load Azure config" (mensagem técnica do throw) em inglês.
- LCP ~3s no `vercel dev` é cold-start do dev server; em prod `/` é HTML estático no CDN. Reavaliar com Lighthouse contra a URL de produção.

## Rodada 2 — Dashboards dentro do iframe (o produto em si)

Auditadas 3 análises reais (Farm devolução / Azzas YTD / Maria Filó tamanho) em desktop+mobile via `dashboards.mjs`. São HTMLs **bespoke** gerados pelo Claude a cada análise (não pelo `exec_template.py`, que está desativado p/ entrega inline). Logo o leverage está na **guidance de geração**, não em arquivos individuais.

| ID | Impacto | Achado |
|----|---------|--------|
| D1 | **ALTO** | `SKILL.md` manda "tema **verde escuro**" — contradiz o guia canônico `identidade-visual-azzas.md` (navy/azul, **sem verde**, sem cor vibrante). Dashboards saem off-brand e inconsistentes. |
| D2 | **ALTO** | Zero guidance de layout responsivo. Azzas-YTD trava numa coluna ~400px no desktop 1440px (~70% da tela vazia); Farm usa a largura. Inconsistência que mata credibilidade pra executivo no laptop. |
| D3 | MÉD-ALTO | Sem piso de fonte pra dados: 284 nós sub-11px no Azzas-YTD — tabela densa ilegível. |
| D4 | MÉDIO | `SKILL.md` aponta "padrão visual dos dashboards existentes" (referência circular que perpetua o drift) em vez do guia canônico. |
| D5 | MÉDIO | Tier de dado inconsistente: Maria Filó com 0 labels ✅📊🔶❓ — viola a Prime Directive do `analyst-principles.md`. Não reforçado no momento de gerar o HTML. |

**Correção (atinge todas as análises futuras):** seção "Layout & Responsividade" + piso de legibilidade + reforço de tier no `identidade-visual-azzas.md` (injetado em todo `get_context`); e correção do `SKILL.md` (remove "verde escuro", aponta pro guia canônico, exige o contrato responsivo). Os 3 dashboards existentes vivem no Blob, bespoke — tratados como legado; o ganho é na guidance.

## Rodada 3 — Colaboração + Onboarding (funil de ativação)

Exercitados via Playwright (`collab.mjs`) os fluxos de kebab → share modal → refresh modal (desktop+mobile) e auditado o onboarding. Modais bem desenhados (bottom-sheet no mobile, contexto claro, feedback via toast, trata erro) — funcionam sem pageerror.

| ID | Impacto | Achado → Correção |
|----|---------|-------------------|
| C1 | **MÉD-ALTO** | "Tornar pública" no kebab era 1 clique sem confirmação, visualmente igual a "Copiar link" — misclique expõe dado de produção pro grupo inteiro. → Confirmação explícita antes de tornar pública (tornar privada de volta não precisa). |
| O1 | **MÉD-ALTO** | Onboarding mostrava "última atualização: \<hoje\>" via `new Date()` — sempre a data de hoje, mentira que corrói confiança. → Removido; sub-cta agora diz "grátis pra contas @somagrupo.com.br". |
| O2 | MÉDIO | CTA primário mostrava "Baixar Azzas MCP v— ↓" / "v?" no load/falha. → Texto limpo enquanto carrega, versão anexada quando resolve. |
| O3 | MÉDIO | Hero abstrato ("faça perguntas aos dados"), sem mostrar valor. → Callout "Você pergunta → recebe pronto" com query de exemplo concreta (conversão). |
| O5 | BAIXO | Emoji de tier inconsistente (📈) vs canônico (📊). → Corrigido. |
| O6 | BAIXO | `--ink-faint #999` (contraste AA) — mesmo fix do portal. → `#767676`. |

Verificado: collab-post sem pageerror, fluxos intactos; onboarding desktop+mobile navOk, zero erro. Before/after: `screenshots/collab-pre.*` e `ob-post.onboarding.*`.

**Pendente (decisão de produto, P2):** O4 — Passo 2 (skill) é co-igual ao Passo 1 mas opcional e técnico (jargão pra exec); dois CTAs de download competindo. Reestruturar como progressive disclosure precisa de call de produto.

## Rodada 4 — P2/P3

| ID | Achado → Correção | Verificação |
|----|-------------------|-------------|
| U7 | Header mobile espremido: email full-width quebrava o layout, nav ragged. → CSS-only: nav vira faixa própria organizada, chip de email truncado (ellipsis, `max-width:46vw`), alvos de toque maiores. | Sweep mobile 390px: header limpo, 0 regressão. |
| U9 | `onboarding.html` `<title>` era "Azzas MCP — Onboarding" — quebrava o padrão "Azzas 2154 — \<Página\>" e não batia com o nav "Instalar no Claude". → `Azzas 2154 — Instalar no Claude`. | — |
| i18n | `msal-init.js` lançava "Failed to load Azure config" (inglês) que vazava pro card de erro com marca. → Mensagem em PT acionável. | — |

Sweep `p23-post`: 10 páginas, **0 regressões**, deep-dive (busca/abrir análise) intacto, zero pageerror.

**Removido após validação do usuário:** o bypass dev-only de MSAL (commit dropado) era só auxílio de navegação local; não faz parte do produto.

### Backlog remanescente (não acionável nesta rodada)

- **O4** (decisão de produto): Passo 2 (skill) no onboarding é co-igual ao Passo 1 mas opcional/técnico; dois CTAs de download competem. Reestruturar como progressive disclosure precisa de call de produto — não implementado unilateralmente.
- **F3**: probe `/api/admin/analytics` loga 403 no console pra não-admin. Ruído de devtools, não visível ao usuário; suprimir exigiria mudar a API — custo > benefício.
- **Lighthouse em produção**: só mensurável após deploy (as mudanças ainda não estão em `bq-analista.vercel.app`). Rodar pós-merge.

## Nota de ambiente (não é bug de produto)

`vercel env pull` deixou `portal/.env.local` sem `AZURE_CLIENT_ID/TENANT_ID`, então `/api/config` dava 500 no dev local e a SPA nunca bootava. Corrigido localmente (env não versionado). Vale alinhar o `vercel env pull` / documentar no README de dev local.
