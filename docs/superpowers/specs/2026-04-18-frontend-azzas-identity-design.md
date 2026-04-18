---
data: 2026-04-18
tipo: spec
tags: [frontend, design, identidade-visual]
---

# Redesign de Frontend — Identidade Azzas 2154

Alinha os dois arquivos HTML do projeto (`index.html` e `dashboard_farm_ecomm.html`) à identidade visual descrita em `identidade-visual-azzas.md`. Abordagem escolhida: **redesign editorial** — troca de tokens (cores + fontes) + componentes refinados + hero/seções editoriais no estilo dos slides Azzas.

## Escopo

Dois arquivos:

1. `index.html` — portal SPA com autenticação MSAL e biblioteca de análises
2. `dashboard_farm_ecomm.html` — dashboard standalone de produto/ecommerce Farm

**Fora de escopo:**

- Qualquer mudança na lógica JS (MSAL flow, fetch de library, canvas do sparkline, IntersectionObserver, etc)
- `library/*.json`, `api/*`, `middleware.js`, `vercel.json`
- Outros dashboards ou análises que ainda serão criadas (a identidade vira referência para eles)

## Decisões de identidade

### Paleta (exclui todas as cores vibrantes atuais)

| Aplicação | Token | Hex |
|---|---|---|
| Texto principal / fundos hero fortes | `--ink` | `#000000` |
| Texto secundário | `--ink-soft` | `#595959` |
| Metadados, labels esmaecidos | `--ink-faint` | `#999999` |
| Fundo principal claro | `--surface` | `#FFFFFF` |
| Fundo warm (filtros, bordas) | `--surface-warm` | `#E8E8E4` |
| Fundo editorial (biblioteca) | `--surface-cream` | `#F9F6EA` |
| Destaque principal, status ativo | `--navy` | `#274566` |
| Destaque secundário | `--steel` | `#3D5A73` |
| Powder accent (gráficos, links) | `--blue-soft` | `#A1C6ED` |
| Gradientes, hover | `--blue-light` | `#C5D9ED` |
| Neutro warm (badge muted) | `--status-pending` | `#B5AFA8` |

Removidos: `#0d1a0d`, `#152315`, `#3a8a3a`, `#4caf50`, `#66bb6a`, `#e8f5e8` (todo o tema verde do `index.html`). `#0F1F18`, `#162820`, `#1C3228`, `#F2E8D5`, `#D9A84E`, `#D9604A`, `#6DA882` (todo o tema do `dashboard_farm_ecomm.html`).

### Tipografia

Ambos os arquivos passam a usar apenas duas famílias:

- **Red Hat Display** (300/400/600) — fonte principal (UI, labels, valores)
- **Playfair Display** (400/700 + 400 itálico) — editorial/acento (subtítulos, nomes de produto, hero values grandes, insights)

Google Fonts preconnect + link com os dois pesos.

Removidas: system fonts do `index.html` e `Cormorant Garamond` / `DM Mono` / `Instrument Sans` do dashboard.

### Regras gerais aplicadas

- Hierarquia via **peso**, não cor: light (300) < regular (400) < semibold (600)
- **ALL CAPS com letter-spacing** só em labels, eyebrows, nomes de brand/categoria
- Nenhuma cor vibrante nos gráficos: sparkline e barras passam a usar powder blue (`#A1C6ED`)
- Alertas via **contraste** (preto sólido, peso 600) em vez de vermelho/coral
- Status positivo via **powder blue**, não verde

---

## `index.html` — redesign editorial

### Estrutura (mantida)

- `#loading` (tela de autenticação)
- `#library-view` (navbar + filtros + grid de cards) — adicionar **hero**
- `#analysis-view` (barra com botão voltar + iframe)

### Mudanças visuais

**Body:** fundo `--surface-cream` (`#F9F6EA`), fonte `--font-primary`, cor `--ink`.

**`#loading`:** fundo creme, spinner em borda `--navy`, texto em `--ink-soft`.

**Navbar (`header`):**
- Fundo `--ink` (preto), cor `--surface` (branco)
- Brand `<h1>`: texto **"Azzas 2154"** em Red Hat Display semibold, uppercase, letter-spacing 0.15em, `font-size: 1rem`
- `#user-email` em `rgba(255,255,255,0.5)`, Red Hat Display 300, 0.75rem

**Hero (novo — entre navbar e filtros):**
- Fundo `--navy`, cor branca, `padding: 3rem 2rem`, `text-align: center`
- Eyebrow: `"BIBLIOTECA DE ANÁLISES"` em Red Hat Display semibold 600, 0.7rem, `--blue-soft`, letter-spacing 0.14em
- Título: `"Inteligência de Negócio"` em Red Hat Display 400, `var(--text-h1)`, letter-spacing 0.03em
- **Sem subtítulo** (produto é só a lib, não carrega contexto de negócio)

**Filtros:**
- Fundo `--surface-warm`, padding 0.85rem 1.5rem
- `.chip`: Red Hat Display 600, 0.7rem uppercase, letter-spacing 0.08em
  - Normal: borda `rgba(39,69,102,0.25)`, texto `--ink-soft`, fundo transparente
  - Hover/active: fundo `--navy`, texto branco, borda `--navy`

**Grid / biblioteca:**
- Fundo `--surface-cream` (herda do body)
- Label "N análises" acima do grid: Red Hat Display 600, uppercase, `--ink-faint`
- `.card`: fundo branco, borda `--surface-warm`, radius 8px
  - Hover: borda `--navy`
- `.card-brand`: Red Hat Display 600, 0.65rem uppercase, letter-spacing 0.1em, cor `--navy`
- `.card-title`: Red Hat Display 600, 0.95rem, cor `--ink`
- `.card-period`: Red Hat Display 400, 0.75rem, cor `--ink-faint`
- `.card-desc`: Red Hat Display 300, 0.8rem, cor `--ink-soft`, line-height 1.5
- `.tag`: fundo `rgba(39,69,102,0.07)`, cor `--navy`, Red Hat Display 600, 0.65rem uppercase
- `.badge-public`: cor `--steel`, borda `--blue-soft`, uppercase 0.6rem

**Analysis view (iframe):**
- `.analysis-bar`: fundo `--ink`, texto branco
- `#back-btn`: borda `rgba(255,255,255,0.2)`, texto branco, hover borda `--blue-soft`
- `#analysis-crumb`: cor `rgba(255,255,255,0.6)`
- iframe: fundo `--surface` (branco), sem borda

### JS — intocado

MSAL flow, `loadLibrary()`, `buildFilters()`, `renderGrid()`, `openAnalysis()` mantidos exatamente como estão. Apenas os templates HTML de `.card` e `.chip` podem receber classes adicionais se necessário (mas o esquema atual já funciona).

---

## `dashboard_farm_ecomm.html` — redesign editorial

### Estrutura (mantida integralmente)

- Header (logo FARM + label + badge de período)
- Hero (valor principal + 4 KPI cards)
- Tendência diária (sparkline canvas)
- Receita por categoria (barras)
- Top 10 produtos por peças vendidas
- **Insights do período** (4 cards com accent na borda esquerda)
- Footer

### Mudanças visuais

**Body / frame:** fundo `--navy` (`#274566`) no lugar do verde escuro. Tudo respira num único bloco escuro coerente.

**Header:**
- Logo `"FARM"`: Red Hat Display 400, letter-spacing 0.22em, uppercase — mantém peso visual grande mas com fonte correta
- `.header-label`: Red Hat Display 600, 0.62rem, letter-spacing 0.14em, uppercase, cor `rgba(255,255,255,0.55)`
- `.header-badge`: fundo `--blue-soft`, cor `--navy` (contraste alto), Red Hat 600 0.6rem uppercase

**Hero:**
- `.hero-main-label`: eyebrow Red Hat 600 uppercase, cor `--blue-soft`
- **`.hero-value`** (o "R$12,0M"): **Playfair Display itálico 400, 4.5rem, branco** — principal toque editorial da peça
- `.hero-sub`: Red Hat 300, 0.85rem, cor `rgba(255,255,255,0.6)`
- `.kpi-card`: fundo `rgba(255,255,255,0.05)`, borda `rgba(255,255,255,0.12)`
- `.kpi-label`: Red Hat 600, 0.58rem uppercase, `rgba(255,255,255,0.55)`
- `.kpi-value`: Red Hat 400, 1.4rem, branco
  - `.accent` → cor `--blue-soft`
  - `.alert` → cor branca **peso 600** (contraste via peso, não cor vibrante)

**Tendência diária (sparkline):**
- Canvas redesenhado:
  - Área sob a curva: gradiente `rgba(161,198,237,.4)` → transparente
  - Linha: stroke `--blue-soft`, lineWidth 1.5
  - Ponto de pico: círculo **branco** (`fill #fff`) raio 3.5
  - Labels de valor (primeiro/pico/último): Red Hat 10px, cores `rgba(255,255,255,.55)` nas pontas e `--blue-soft` no pico
- Trend labels abaixo: Red Hat 600, 0.55rem uppercase, `rgba(255,255,255,.45)`; `.peak` em `--blue-soft`

**Receita por categoria:**
- `.chart-wrap`: fundo `rgba(255,255,255,0.04)`, borda `rgba(255,255,255,0.1)`
- `.group-name`: Red Hat 600, 0.72rem uppercase, letter-spacing 0.08em
- `.group-stats`: Red Hat 300, 0.65rem, `rgba(255,255,255,.55)`
- `.bar-fill`: background sólido `--blue-soft` (substitui o gradient sage→gold)
- Animação de entrada (IntersectionObserver) preservada

**Top 10 produtos:**
- `.products-list`: borda `rgba(255,255,255,0.1)`, fundo `rgba(255,255,255,0.03)`
- `.rank`: Red Hat 300, 0.7rem, `rgba(255,255,255,0.5)`
  - `.top3` → cor `--blue-soft`, peso 600
- `.product-name`: **Playfair Display 400, 0.95rem, branco** (toque editorial)
- `.product-cor`: Red Hat 600, 0.55rem uppercase, letter-spacing 0.1em, `rgba(255,255,255,0.45)`
- `.product-bar-fill`: background `--blue-soft` (remove sage e overrides coral inline)
- `.product-revenue`: Red Hat 600, 0.8rem, `--blue-soft`
- `.product-units`: Red Hat 300, 0.62rem, `rgba(255,255,255,0.5)`
- **`.discount-pill`** — sem mais coral/gold/sage:
  - `.disc-low`: fundo `rgba(161,198,237,0.18)`, cor `--blue-light`
  - `.disc-mid`: fundo `rgba(181,175,168,0.2)` (warm gray), cor `#E8E8E4`
  - `.disc-high`: fundo **preto sólido**, cor branca (alerta via contraste máximo)

**Insights do período (restaurado, restylizado):**
- `.insight`: fundo `rgba(255,255,255,0.04)`, borda `rgba(255,255,255,0.1)`, `border-left: 3px solid` variável
  - `.insight.positive` → border-left `--blue-soft`, label `--blue-soft`
  - `.insight.alert` → border-left **branco**, label branca (alerta via contraste máximo)
  - `.insight.highlight` → border-left `--blue-light`, label `--blue-light`
  - `.insight.neutral` → border-left `rgba(255,255,255,0.25)`, label `rgba(255,255,255,0.55)`
- `.insight-label`: Red Hat 600, 0.58rem uppercase, letter-spacing 0.12em
- `.insight-text`: **Playfair Display 400, 0.95rem**, branco, line-height 1.5

**Footer:**
- `.footer-note`: Red Hat 300, 0.6rem, `rgba(255,255,255,0.35)`
- Marca `"farm"` decorativa (canto direito): Playfair itálico 1.4rem, `rgba(255,255,255,0.15)`

### JS — intocado

Sparkline canvas function, IntersectionObserver de animação e data bindings (`data-pct`, `data-bar`) preservados. Apenas as cores de stroke/fill dentro do canvas script mudam (sage/gold → powder blue/branco).

---

## Validação

Não há test suite automatizada para o frontend. Verificação será manual:

1. Abrir `index.html` via Vercel dev ou servidor estático — fluxo MSAL → biblioteca → iframe continua funcional
2. Abrir `dashboard_farm_ecomm.html` direto no browser — sparkline renderiza, barras animam ao entrar em viewport
3. Inspecionar que não existe nenhuma ocorrência de cores removidas (`#3a8a3a`, `#6DA882`, `#D9A84E`, `#D9604A`, etc) em nenhum dos dois arquivos
4. Inspecionar que fontes Cormorant/DM Mono/Instrument Sans não aparecem em nenhum dos dois arquivos

## Riscos

- **MSAL redirectUri:** nenhuma mudança. O fluxo atual (`redirectUri: window.location.origin`) continua.
- **Legibilidade:** fundo navy com texto branco passa WCAG AA; powder blue sobre navy tem contraste ~4.2:1 — limítrofe, uso como accent (não body). Validação manual.
- **Sparkline pico branco:** branco sólido sobre navy pode destoar — se parecer "duro" demais, cair para `--blue-light` (#C5D9ED) como fallback.
