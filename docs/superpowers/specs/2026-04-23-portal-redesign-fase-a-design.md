# Portal Redesign — Fase A

**Data:** 2026-04-23
**Escopo:** redesign do portal `bq-analista.vercel.app` focado em descoberta de onboarding, alinhamento visual à marca Azzas 2154, organização da library de análises pra escalar a 100-300 items por analista, e página de sucesso de autenticação do DXT (aba que abre no browser após login).

**Fora do escopo (Fase B, futuro):** análises replicáveis/parametrizáveis — re-execução com novos períodos/parâmetros pela UI. Brainstorm separado.

---

## Contexto

- 80% dos usuários são analistas (publicam e leem análises dos colegas); 20% execs (leem link específico).
- Library hoje: `portal/library/<domain>/<email>.json` (privada) + `portal/library/<domain>/public.json` (pública).
- Arquivos HTML em `portal/analyses/<domain>/<email>/<filename>.html` e `portal/analyses/<domain>/public/<filename>.html`.
- Publicação: agente MCP chama `publicar_dashboard` → grava HTML + `prepend_entry` no library JSON + commit/push → Vercel redeploya.
- Onboarding existe em `portal/onboarding.html` mas sem link de entrada em lugar nenhum, e com visual desalinhado (fonte Apple system, azul `#0071e3` em vez da paleta navy).
- Brand tokens canônicos em `shared/context/identidade-visual-azzas.md`: Navy `#274566`, Steel `#3D5A73`, Powder blue `#A1C6ED`, Light `#C5D9ED`, Cream `#F9F6EA`, Bege `#E8E8E4`. Fontes: Red Hat Display (primária) + Playfair Display italic (editorial).

---

## Decisões de UX

### Navegação principal

**Tabs horizontais no topo do conteúdo:**

| Tab | Conteúdo | Count badge |
|-----|----------|-------------|
| **Minhas** (default) | Análises publicadas pelo usuário logado em qualquer agente, não arquivadas | nº de itens |
| **Time** | Todas as análises públicas de qualquer autor em qualquer agente, não arquivadas pelo usuário | nº de itens |
| **Arquivadas** | Itens que o usuário arquivou (sejam suas ou do time) | nº de itens |

**Cross-domain:** a library é agregada — análises aparecem independente de qual agente as publicou (Vendas Linx, Devoluções, ou agentes futuros). Cada card indica o agente de origem na linha de meta.

**Busca:** input de texto abaixo das tabs, procura em `title`, `description`, `tags` e `brand` da tab ativa. Case-insensitive, match por substring.

**Facets (dropdowns) ao lado da busca:**
- **Agente** — lista distinct dos agentes presentes (Vendas Linx / Devoluções / ...)
- **Marca** — lista distinct de `brand` dos items da tab ativa
- **Período** — agrupadores: "Últimos 7 dias" / "Últimos 30 dias" / "Este trimestre" / "Este ano" / "Tudo"
- **Ordem** — "Mais recente" (default) / "Mais antiga" / "Título A→Z"

Filtros são aditivos (AND entre facets, tab define o universo).

### Arquivamento

- **Soft hide pessoal.** Arquivar não deleta o HTML nem remove do `library.json` — grava a ação em `localStorage` (per-user, per-browser) ou, melhor, num campo `archived_by: [email]` no próprio library entry via futura chamada de API.
- **Decisão da Fase A:** começar com `localStorage` (zero backend novo). Key: `azzas_archived`, valor: array de `{id, archivedAt}`.
- **Comportamento:** arquivar algo remove da tab "Minhas"/"Time" e adiciona à "Arquivadas". Ação "Restaurar" reverte.
- **Escopo:** só o próprio usuário vê o efeito. Nada é escondido de outros.

### Ações no card

Clicar no card (fora do menu) abre a análise no **iframe fullscreen existente** (mantém comportamento atual do `index.html`, preserva contexto de tab/busca/scroll ao fechar).

Menu `⋯` no canto superior direito do thumbnail abre dropdown com ações que variam por visibilidade:

| Ação | Item público | Item privado (só autor vê) |
|------|--------------|---------------------------|
| Copiar link | ✓ | — (link privado dá 403 pros outros) |
| Tornar pública | — | ✓ (já existe via `/api/share`) |
| Arquivar / Restaurar | ✓ | ✓ |

**Feedback ao copiar link:** toast curto ("Link copiado" + ícone de check) no canto inferior por 2s. Toast é inline na página (não depende de lib de notificações). Menu fecha ao clicar.

Sem "renomear" ou "editar metadata" nesta fase — isso é Fase B.

### Entrada pro onboarding

**Link permanente no header:** "Instalar no Claude ↗"

- Visível em todas as páginas do portal
- Aponta pra `/onboarding`
- Marcado `active` quando a URL é `/onboarding`

Sem banner, sem profile dropdown, sem CTA empty-state. Um único ponto de entrada, sempre visível, nunca dismissable.

### Layout visual (marca aplicada)

**Header (todas as páginas):**
- Fundo branco, borda inferior sutil
- Logo à esquerda: `AZZAS <em>análises</em>` — "AZZAS" em Red Hat Display 600, "análises" em Playfair italic
- Navegação à direita: "Análises" (link pra `/`), "Instalar no Claude ↗" (link pra `/onboarding`)
- Chip de usuário: fundo bege quente (`--surface-warm`), email exibido

**Hero da library (só em `/`):**
- Fundo creme (`--surface-cream`)
- Título grande em Red Hat Display 400, 28px: "Minhas análises" / "Análises do time" / "Arquivadas"
- Subtítulo editorial em Playfair italic com contagens e metadata: "42 publicadas · 8 arquivadas · última há 2 dias"

**Cards da library:**
- Background branco, borda sutil
- Thumb com gradiente derivado da marca (Navy/Steel/Blue-soft/Cream — rotação determinística por brand string, sem imagem ainda)
- Chip de marca (ALL CAPS, Red Hat 600, 9px, letter-spacing) sobre o thumb
- Menu `⋯` sobre o thumb
- Corpo: título (Red Hat 600, 13px), meta line com formato `<AGENTE> · <período> · <recência>` onde o nome do agente vem em Red Hat 600 10px uppercase cor `--steel` como primeiro elemento (ink-faint, 11px no resto), descrição (ink-soft, 11px), tags como chips bege (ALL CAPS, 9px)

**Onboarding hero:**
- Fundo navy sólido
- Eyebrow: "AZZAS 2154 · CLAUDE DESKTOP" (ALL CAPS, Red Hat 600, azul-powder sobre navy)
- Título em Red Hat 400, ~44px, branco: "Análises onde você já está conversando."
- Editorial em Playfair italic, azul claro: "Uma extensão. Seu BigQuery. Sua identidade corporativa."
- Parágrafo curto
- CTA: botão branco com texto navy, "Baixar Azzas MCP v{X} ↓"
- Sub-texto: plataforma + última atualização

**Onboarding seções:**
- Background branco ou bege quente (alternando)
- Section heading ALL CAPS, letter-spacing, ink-faint, 11px ("INSTALAÇÃO", "O QUE VOCÊ GANHA", "PROBLEMAS COMUNS")
- Passos de instalação em `<ol>` com numeração Playfair italic (decimal-leading-zero), grid 2 colunas
- Agentes em cards com left-border navy, fundo creme
- Troubleshooting em parágrafos curtos com `<strong>` pra perguntas

**Página de sucesso de auth (loopback `127.0.0.1:878X/cb`):**
- HTML autocontido, servido pelo DXT local após o callback OAuth — tem que funcionar online (Google Fonts via CDN) e parecer da marca
- Dois estados: **sucesso** (query string tem `access`) e **erro** (query string tem `error`)
- **Sucesso:** fundo creme, logo "AZZAS *análises*" no topo, ícone de check em navy (SVG inline, 48px), headline em Red Hat 400 ~32px "Login concluído", editorial em Playfair italic "Bem-vindo, {email}.", sub "Você já pode fechar esta aba e voltar pro Claude Desktop.", pequeno countdown "Fechando em 3s..." (opcional, fecha via `window.close()` — só funciona se a aba foi aberta por outro tab, senão expira o countdown sem fechar)
- **Erro:** fundo creme, mesmo logo, ícone ⚠ em navy, headline "Login não concluído", mensagem humana baseada no código de erro: `wrong_tenant` → "Você não está no tenant corporativo Azzas.", `invalid_code` → "A autorização expirou ou falhou.", qualquer outro → o `error_description` se houver, ou "Algo deu errado."; sub "Volte pro Claude Desktop e tente novamente. Se persistir, contate ai.labs@somagrupo.com.br."
- Mesmo tratamento tipográfico do `/onboarding`. Nenhum link externo nem botão — usuário fecha manualmente ou via auto-close

---

## Arquitetura e arquivos

### Arquivos a editar

| Arquivo | Mudança |
|---------|---------|
| `portal/index.html` | Refatoração completa: header com link onboarding, tabs (Minhas/Time/Arquivadas), busca, facets, grid de cards, arquivamento via localStorage. Mantém MSAL/auth flow existente. |
| `portal/onboarding.html` | Refatoração completa: aplica design tokens navy+cream+Playfair, hero escuro, passos em grid, agentes em cards, header igual ao `/`. |
| `portal/vercel.json` | Já tem rewrite `/onboarding` → `/onboarding.html` (feito em commit anterior). Sem mudança. |
| `portal/middleware.js` | Sem mudança — `/onboarding` já passa pelo check de sessão. |
| `packages/mcp-core/src/mcp_core/library.py` | Adiciona campo `author_email: str` em `LibraryEntry`. Necessário pra distinguir "Minhas" de "Time" quando tudo cai em public.json (modo `MCP_FORCE_PUBLIC=1`). |
| `packages/mcp-core/src/mcp_core/server_factory.py` | `publicar_dashboard` passa `author_email=exec_email` ao criar `LibraryEntry`. |
| `packages/mcp-core/tests/test_library.py` | Atualiza teste pra cobrir o novo campo. |
| `packages/mcp-client-dxt/src/auth.ts` | Troca a string `<h1>Pronto!</h1>...` inline (linha ~88) por uma função `renderCallbackPage(params)` que retorna HTML rebrandado. Função em novo arquivo `packages/mcp-client-dxt/src/callback-page.ts` pra isolar HTML do código de rede. |
| `packages/mcp-client-dxt/src/callback-page.ts` | **Novo.** Exporta `renderCallbackPage(params: LoopbackParams): string` — produz HTML autocontido com marca Azzas pra sucesso ou erro. |
| `packages/mcp-client-dxt/src/__tests__/callback-page.test.ts` | **Novo.** Snapshot ou asserção de presença: quando `params.error` setado → contém headline "Login não concluído" e a mensagem traduzida; quando `params.access` setado → contém headline "Login concluído" e o email. |

### Arquivos a criar

Nenhum. Manter CSS inline nas duas páginas HTML (segue o padrão atual, YAGNI de extrair stylesheet).

### Tokens compartilhados

Copiar bloco `:root` de `shared/context/identidade-visual-azzas.md` literalmente pros dois HTMLs. Sem build step novo. Quando os dois arquivos divergirem, aceitar o custo — ambos dependem da referência canônica em `shared/context/`.

### LocalStorage contract

```js
// Key: 'azzas_archived'
// Value (JSON array):
[
  { "id": "farm-produto-ecomm-2026-04-18", "archivedAt": "2026-04-23T15:00:00Z" },
  { "id": "maria-filo-cambios-2026-04-10", "archivedAt": "2026-04-22T09:30:00Z" }
]
```

Leitura e escrita em helpers no próprio `index.html`:
- `getArchived(): Set<string>` — retorna set de ids
- `isArchived(id): bool`
- `archive(id)` / `unarchive(id)` — manipulam localStorage, disparam re-render

---

## Fluxo de dados

### Load inicial (`/`)

1. Middleware valida sessão → passa através.
2. Página bota loader, chama `/api/mcp/agents` (já existe) pra obter a lista de agentes. Cada agente tem `name` (slug, ex: `vendas-linx`) e `label` (ex: `Vendas Linx`). O `name` é o diretório em `portal/library/<name>/`.
3. Pra cada agente na lista, dispara em paralelo: `fetch('/library/<agent.name>/<email>.json')` + `fetch('/library/<agent.name>/public.json')`. Falhas individuais (404 se o arquivo ainda não existe) são tratadas como array vazio, não erro.
4. Ao carregar cada item, anexa `agent: { name, label }` e `source: "private" | "public"` pra saber de onde veio. Merge em `allItems` único.
5. Dedupe por `id`. Se o mesmo id aparece em privado e público, prioriza o privado.
6. Lê `localStorage['azzas_archived']` → `archivedIds`.
7. Classifica cada item como "mine" ou "team":
   - `mine` = `source === "private"` OU (`source === "public"` E `item.author_email === currentEmail`)
   - `team` = `source === "public"` E `item.author_email !== currentEmail`
   - Fallback (pra items antigos sem `author_email`): considera `mine` se `item.filename` começa com o slug do email do usuário atual; senão `team`.
8. Calcula counts (excluindo arquivados):
   - `mine` count, `team` count, `archived` count (todos independente de classificação mine/team)
9. Renderiza tab ativa (default: `mine`).

### Filtros

- **Tab:** muda universo de items.
- **Busca:** filtra por substring em `title + description + tags.join(' ') + brand` (case-insensitive).
- **Agente:** filtra por `item.agent.name === selectedAgent`.
- **Marca:** filtra por `item.brand === selectedBrand`.
- **Período:** filtra por `item.date` (usa `Date.parse`) contra janela relativa a hoje.
- **Ordem:** sort final.

Re-render roda em cliente sem chamar backend de novo.

### Ações no card

- **Abrir:** abre no iframe fullscreen existente (mantém comportamento do `index.html`). Não troca de URL.
- **Copiar link:** `navigator.clipboard.writeText(window.location.origin + item.link)` → toast "Link copiado" 2s. Só aparece em items com `source === "public"`.
- **Tornar pública:** chama `/api/share` existente. Só aparece em items com `source === "private"`. Após sucesso, recarrega a library.
- **Arquivar:** `archive(item.id)` → remove da view atual com animação curta (opcional), incrementa count da tab Arquivadas.
- **Restaurar:** inverso.

### Onboarding

- Idêntico ao existente: fetch `/api/mcp/version` e `/api/mcp/agents` pra popular versão e lista de agentes.
- Ribbon de "nova versão disponível" mantém a lógica atual (`localStorage['mcp_last_known_version']`).

---

## Estados especiais

### Empty states

- **Minhas sem items:** "Você ainda não publicou nenhuma análise." + link pra "Como publicar?" (README / docs).
- **Time sem items:** "O time ainda não publicou nada público."
- **Arquivadas vazia:** "Nada arquivado."
- **Busca sem match:** "Nenhuma análise encontrada pra '<query>' nesta tab."

### Loading

- Skeleton grid (3 cards de placeholder cinza claro) enquanto o fetch não volta. Sem spinner.

### Erros

- Fetch do library falha: banner discreto no topo em bege quente, "Não consegui carregar a library. Tente atualizar a página."

---

## Responsivo

- **Desktop (≥ 900px):** grid 3 colunas, header horizontal.
- **Tablet (600-900px):** grid 2 colunas, header horizontal.
- **Mobile (< 600px):** grid 1 coluna, header empilha (logo em cima, nav embaixo compacta). Facets (Agente/Marca/Período/Ordem) colapsam num botão único "Filtros ▾" que abre um **bottom sheet** (modal slide-up ocupando bottom 70% da tela) com os 4 selects empilhados. Botão "Aplicar" fecha o sheet e atualiza a grid. Sheet fecha ao clicar fora ou na área cinza no topo.
- **Onboarding:** hero pilha, passos viram 1 coluna, agentes pilham.

---

## Não-objetivos explícitos

- **Não** implementar análises parametrizáveis (Fase B).
- **Não** implementar compartilhamento 1:1 que copia o arquivo pra pasta do email de destino (Fase B — depende de decisões sobre conflito de nome, public-ou-privado, notificação pro destinatário).
- **Não** criar sistema de favoritos/pins.
- **Não** criar coleções/pastas nomeadas pelo usuário.
- **Não** adicionar comentários, reações ou notificações.
- **Não** mudar o fluxo de auth (MSAL segue igual).
- **Não** extrair CSS pra stylesheet separado.
- **Não** persistir "arquivado" no backend — local apenas por enquanto.

Nota: o schema do `library.json` ganha um campo `author_email` (adição retrocompatível — entries antigas sem o campo caem no fallback por filename slug).

---

## Testes

### Manual QA

- Login flow continua funcionando (Azure AD → sessão → `/`).
- Tabs mudam o universo corretamente, counts batem.
- "Minhas" mostra análises que eu publiquei (validar com análise publicada via agente, com `author_email` preenchido).
- "Time" mostra análises de outros autores, não arquivadas pelo usuário atual.
- Busca filtra por título, descrição, tags E marca. "Nenhuma análise" aparece quando sem match.
- Facet de agente lista só agentes com items na tab ativa.
- Facet de marca lista só marcas presentes na tab ativa.
- Cards mostram agente na linha de meta no formato `AGENTE · período · recência`.
- Análises antigas (sem `author_email`) caem no fallback por filename slug.
- Clicar num card abre o iframe fullscreen; fechar volta pra library com tab/busca/scroll preservados.
- Menu do item público mostra "Copiar link" e o toast aparece ao copiar.
- Menu do item privado mostra "Tornar pública" (não mostra "Copiar link"). Clicar recarrega a library com o item agora público.
- Em mobile, botão "Filtros ▾" abre bottom sheet com os 4 selects; "Aplicar" fecha e filtra.
- Arquivar remove da tab atual, aparece em "Arquivadas", restaurar reverte.
- Link "Instalar no Claude ↗" leva pra `/onboarding`, fica marcado como `active` lá.
- `/onboarding` renderiza com hero navy, todos os elementos com a marca.
- Em mobile (≤ 375px), grid fica 1 coluna, header não quebra.
- Tela de sucesso do DXT: após login Azure, a aba que abre mostra tela rebrandada (check navy, "Login concluído", email), não mais "Pronto!" puro.
- Tela de erro do DXT: simular com um tenant errado → aba mostra variante de erro com mensagem humana + instrução de voltar pro Claude.

### Automático

- Atualiza `packages/mcp-core/tests/test_library.py` pra cobrir `author_email` no `LibraryEntry`.
- Nenhum teste novo pra frontend nesta fase — é redesign de páginas estáticas sem lógica de negócio nova. O workflow `vitest` existente do portal cobre os handlers da API, que não são tocados.

---

## Rollout

Três vetores de deploy, podem ir no mesmo push (pipelines rodam em paralelo):

1. **Agentes Railway** — `mcp-core` (library.py + server_factory.py + test) redeployam automático via GitHub Actions. Novas análises ganham `author_email`, antigas caem no fallback por filename.
2. **Portal Vercel** — `index.html` + `onboarding.html` + `vercel.json` redeployam automático. Usuários veem portal novo.
3. **DXT client** — `callback-page.ts` + alteração em `auth.ts` exigem rebuild do `.dxt` (bump de versão patch, `1.0.0` → `1.0.1`) e reinstall no Claude Desktop. Sem rebuild, usuários continuam vendo o "Pronto!" antigo (a tela é renderizada pelo processo Node local).

Zero mudança de infraestrutura (env vars, domínios, etc). DXT v1.0.1 pode ser disponibilizada no onboarding sem forçar — quem precisar ver a tela nova só após próxima instalação.
