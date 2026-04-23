# Portal Redesign — Fase A

**Data:** 2026-04-23
**Escopo:** redesign do portal `bq-analista.vercel.app` focado em descoberta de onboarding, alinhamento visual à marca Azzas 2154, e organização da library de análises pra escalar a 100-300 items por analista.

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
| **Minhas** (default) | Análises publicadas pelo usuário logado, não arquivadas | nº de itens |
| **Time** | Todas as análises públicas do domínio, de qualquer autor, não arquivadas pelo usuário | nº de itens |
| **Arquivadas** | Itens que o usuário arquivou (sejam suas ou do time) | nº de itens |

**Busca:** input de texto abaixo das tabs, procura em `title`, `description`, `tags` da tab ativa. Case-insensitive, match por substring.

**Facets (dropdowns) ao lado da busca:**
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

Menu `⋯` no canto superior direito do thumbnail abre dropdown com:

- **Abrir** (default ao clicar no card)
- **Copiar link** (URL absoluta da análise, pra mandar por Slack/email)
- **Arquivar** / **Restaurar**

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
- Corpo: título (Red Hat 600, 13px), meta (período + recência, ink-faint, 11px), descrição (ink-soft, 11px), tags como chips bege (ALL CAPS, 9px)

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

---

## Arquitetura e arquivos

### Arquivos a editar

| Arquivo | Mudança |
|---------|---------|
| `portal/index.html` | Refatoração completa: header com link onboarding, tabs (Minhas/Time/Arquivadas), busca, facets, grid de cards, arquivamento via localStorage. Mantém MSAL/auth flow existente. |
| `portal/onboarding.html` | Refatoração completa: aplica design tokens navy+cream+Playfair, hero escuro, passos em grid, agentes em cards, header igual ao `/`. |
| `portal/vercel.json` | Já tem rewrite `/onboarding` → `/onboarding.html` (feito em commit anterior). Sem mudança. |
| `portal/middleware.js` | Sem mudança — `/onboarding` já passa pelo check de sessão. |

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
2. Página bota loader, chama `/api/config` (mantém fluxo atual) pra obter `domain`.
3. `fetch('/library/<domain>/<email>.json')` + `fetch('/library/<domain>/public.json')` em paralelo.
4. Merge dos dois arrays em `allItems`. Dedupe por `id` (pode existir o mesmo id em ambos; prioriza o do email).
5. Lê `localStorage['azzas_archived']` → `archivedIds`.
6. Calcula counts:
   - `mine` = items de `email.json` não arquivados
   - `team` = items de `public.json` não arquivados
   - `archived` = items em qualquer lista que estão arquivados
7. Renderiza tab ativa (default: `mine`).

### Filtros

- **Tab:** muda universo de items.
- **Busca:** filtra por substring em `title+description+tags.join(' ')`.
- **Marca:** filtra por `item.brand === selectedBrand`.
- **Período:** filtra por `item.date` (usa `Date.parse`) contra janela relativa a hoje.
- **Ordem:** sort final.

Re-render roda em cliente sem chamar backend de novo.

### Ações no card

- **Abrir:** `window.location = item.link` (ou push de estado p/ iframe, mantém comportamento atual do `index.html`).
- **Copiar link:** `navigator.clipboard.writeText(window.location.origin + item.link)`.
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
- **Mobile (< 600px):** grid 1 coluna, header empilha (logo em cima, nav embaixo compacta). Facets viram sheet/bottom drawer ou colapsam em "Filtros ▾" único.
- **Onboarding:** hero pilha, passos viram 1 coluna, agentes pilham.

---

## Não-objetivos explícitos

- **Não** implementar análises parametrizáveis (Fase B).
- **Não** criar sistema de favoritos/pins.
- **Não** criar coleções/pastas nomeadas pelo usuário.
- **Não** adicionar comentários, reações ou notificações.
- **Não** mudar o schema do `library.json`.
- **Não** mudar o fluxo de auth (MSAL segue igual).
- **Não** extrair CSS pra stylesheet separado.
- **Não** persistir "arquivado" no backend — local apenas por enquanto.

---

## Testes

### Manual QA

- Login flow continua funcionando (Azure AD → sessão → `/`).
- Tabs mudam o universo corretamente, counts batem.
- Busca filtra e "Nenhuma análise" aparece quando sem match.
- Facet de marca lista só marcas presentes na tab ativa.
- Arquivar remove da tab atual, aparece em "Arquivadas", restaurar reverte.
- Link "Instalar no Claude ↗" leva pra `/onboarding`, fica marcado como `active` lá.
- `/onboarding` renderiza com hero navy, todos os elementos com a marca.
- Em mobile (≤ 375px), grid fica 1 coluna, header não quebra.

### Automático

- Nenhum teste automatizado novo nesta fase — é redesign de páginas estáticas sem lógica de negócio nova. O worklow `vitest` existente do portal cobre os handlers da API, que não são tocados.

---

## Rollout

Deploy direto pra produção via push em `main`. Single deploy — duas páginas HTML. Zero mudança de infraestrutura.
