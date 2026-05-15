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

## Nota de ambiente (não é bug de produto)

`vercel env pull` deixou `portal/.env.local` sem `AZURE_CLIENT_ID/TENANT_ID`, então `/api/config` dava 500 no dev local e a SPA nunca bootava. Corrigido localmente (env não versionado). Vale alinhar o `vercel env pull` / documentar no README de dev local.
