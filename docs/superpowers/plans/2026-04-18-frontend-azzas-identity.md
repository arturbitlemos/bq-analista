# Redesign de Frontend — Identidade Azzas 2154 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Realinhar `index.html` (portal) e `dashboard_farm_ecomm.html` (dashboard) à identidade Azzas 2154, trocando paleta e fontes, adicionando hero no portal e preservando toda a lógica JS existente.

**Architecture:** Dois arquivos HTML standalone; cada um tem `<style>` inline com `:root` de tokens. Redesign acontece em duas frentes paralelas por arquivo — tokens + componentes. Sem mudança de estrutura JS (MSAL, canvas, IntersectionObserver). Spec de referência: `docs/superpowers/specs/2026-04-18-frontend-azzas-identity-design.md`.

**Tech Stack:** HTML5, CSS variables, Google Fonts (Red Hat Display + Playfair Display), Canvas 2D (sparkline preservado), MSAL (preservado).

**Verificação:** Não há suíte de testes. Cada task termina com abertura do arquivo no browser e checagem visual descrita. O servidor do visual companion ainda está rodando em `http://localhost:56966` e pode ser usado para comparar contra os mockups aprovados (`mockup-index-v2.html` e `mockup-dashboard-v2.html`).

---

## File Structure

Só dois arquivos são modificados (nenhum novo):

- `/Users/arturlemos/Documents/bq-analista/index.html` — portal SPA; `:root` substituído, navbar/hero/filtros/grid/analysis-view reestilizados
- `/Users/arturlemos/Documents/bq-analista/dashboard_farm_ecomm.html` — dashboard standalone; `:root` substituído, header/hero/KPIs/gráficos/insights/footer reestilizados

Tasks 1–3 mexem em `index.html`. Tasks 4–7 mexem em `dashboard_farm_ecomm.html`. Ordem linear — pode-se pular entre os dois, mas cada arquivo é internamente sequencial.

---

## Task 1: `index.html` — tokens, fonts, navbar e loading

**Files:**
- Modify: `/Users/arturlemos/Documents/bq-analista/index.html` (lines 3–13 head, 13–22 `:root`, 23–48 body/loading, 53–67 header)

- [ ] **Step 1: Adicionar preconnect e link do Google Fonts no `<head>`**

Abrir `index.html`. Logo após `<title>Farm Group Analytics</title>` (linha 6) e antes do `<script src="https://alcdn.msauth.net/...">` (linha 7), inserir:

```html
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Red+Hat+Display:wght@300;400;600&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Substituir `:root` inteiro pelos tokens Azzas**

Substituir o bloco `:root { --bg: #0d1a0d; ... --accent: #66bb6a; }` (linhas 13–22 aproximadas) por:

```css
    :root {
      /* Neutros */
      --ink:            #000000;
      --ink-soft:       #595959;
      --ink-faint:      #999999;
      --surface:        #FFFFFF;
      --surface-warm:   #E8E8E4;
      --surface-cream:  #F9F6EA;

      /* Azuis */
      --navy:           #274566;
      --steel:          #3D5A73;
      --blue-soft:      #A1C6ED;
      --blue-light:     #C5D9ED;

      /* Funcionais */
      --status-pending: #B5AFA8;

      /* Tipografia */
      --font-primary:   'Red Hat Display', Arial, sans-serif;
      --font-editorial: 'Playfair Display', Georgia, serif;
    }
```

- [ ] **Step 3: Atualizar `body` e `#loading`**

Substituir a regra `body { ... }` (linhas 24–29) e `#loading { ... }` + `.spinner { ... }` (linhas 32–48) por:

```css
    body {
      background: var(--surface-cream);
      color: var(--ink);
      font-family: var(--font-primary);
      min-height: 100vh;
    }

    #loading {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100vh;
      flex-direction: column;
      gap: 16px;
      color: var(--ink-soft);
    }
    .spinner {
      width: 32px; height: 32px;
      border: 3px solid var(--surface-warm);
      border-top-color: var(--navy);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
```

- [ ] **Step 4: Atualizar `header` (navbar)**

Substituir as regras `header { ... }`, `header h1 { ... }` e `#user-email { ... }` (linhas 53–67) por:

```css
    header {
      background: var(--ink);
      color: var(--surface);
      padding: 16px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
    }
    header h1 {
      font-family: var(--font-primary);
      font-size: 1rem;
      font-weight: 600;
      letter-spacing: 0.15em;
      text-transform: uppercase;
      color: var(--surface);
      flex: 1;
    }
    #user-email {
      font-size: 0.75rem;
      font-weight: 300;
      color: rgba(255, 255, 255, 0.5);
    }
```

- [ ] **Step 5: Trocar o texto da brand no HTML**

Na linha `<h1>Farm Group Analytics</h1>` (≈ linha 209), substituir por:

```html
    <h1>Azzas 2154</h1>
```

- [ ] **Step 6: Verificar visualmente**

Abrir `index.html` no browser. Esperado:
- Fundo creme (`#F9F6EA`) — não mais verde escuro
- Navbar preta com "AZZAS 2154" em branco uppercase com espaçamento largo
- Spinner de loading em navy (vai ser visível brevemente antes do MSAL redirect)
- Nenhum erro 404 nas fontes no DevTools → Network

- [ ] **Step 7: Commit**

```bash
git add index.html
git commit -m "style(index): tokens Azzas, Red Hat + Playfair, navbar preta"
```

---

## Task 2: `index.html` — hero novo e filtros

**Files:**
- Modify: `/Users/arturlemos/Documents/bq-analista/index.html` (linhas 69–90 filters/chips, HTML body do library-view)

- [ ] **Step 1: Adicionar CSS do hero**

Imediatamente após a regra `#user-email { ... }` (já atualizada na Task 1), antes de `.filters { ... }`, inserir:

```css
    .hero {
      background: var(--navy);
      color: var(--surface);
      padding: 3rem 2rem;
      text-align: center;
    }
    .hero-eyebrow {
      font-family: var(--font-primary);
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--blue-soft);
      margin-bottom: 0.85rem;
    }
    .hero-title {
      font-family: var(--font-primary);
      font-weight: 400;
      font-size: clamp(2rem, 4vw, 3rem);
      letter-spacing: 0.03em;
      line-height: 1.1;
    }
```

- [ ] **Step 2: Substituir CSS de `.filters` e `.chip`**

Substituir as regras `.filters { ... }`, `.chip { ... }` e `.chip:hover, .chip.active { ... }` (linhas 69–90) por:

```css
    .filters {
      padding: 0.85rem 1.5rem;
      background: var(--surface-warm);
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    }
    .chip {
      font-family: var(--font-primary);
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 0.3rem 0.8rem;
      border-radius: 4px;
      background: transparent;
      border: 1px solid rgba(39, 69, 102, 0.25);
      color: var(--ink-soft);
      cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover {
      border-color: var(--navy);
      color: var(--navy);
    }
    .chip.active {
      background: var(--navy);
      color: var(--surface);
      border-color: var(--navy);
    }
```

- [ ] **Step 3: Adicionar o HTML do hero dentro de `#library-view`**

Localizar o bloco:

```html
<div id="library-view">
  <header>
    <h1>Azzas 2154</h1>
    <span id="user-email"></span>
  </header>
  <div class="filters" id="filters">
```

Entre `</header>` e `<div class="filters" id="filters">`, inserir:

```html
  <section class="hero">
    <div class="hero-eyebrow">Biblioteca de Análises</div>
    <h2 class="hero-title">Inteligência de Negócio</h2>
  </section>
```

- [ ] **Step 4: Verificar visualmente**

Abrir `index.html`. Esperado:
- Entre navbar e filtros, bloco navy centralizado com "BIBLIOTECA DE ANÁLISES" (powder blue, pequeno, espaçado) e "Inteligência de Negócio" (branco, grande)
- Chips dos filtros em fundo bege sobre borda discreta; "Todas" ativa em fundo navy sólido

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "style(index): hero navy + filtros Azzas"
```

---

## Task 3: `index.html` — grid, cards e analysis view

**Files:**
- Modify: `/Users/arturlemos/Documents/bq-analista/index.html` (linhas 92–197 grid/card/tag/analysis)

- [ ] **Step 1: Substituir `#grid` e `.card` e filhos**

Substituir as regras de `#grid { ... }`, `.card { ... }`, `.card:hover { ... }`, `.card-brand { ... }`, `.card-title { ... }`, `.card-period { ... }`, `.card-desc { ... }`, `.card-footer { ... }`, `.tag { ... }`, `.badge-public { ... }` e `#empty { ... }` (linhas 92–164) por:

```css
    #grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
      padding: 24px;
    }

    .card {
      background: var(--surface);
      border: 1px solid var(--surface-warm);
      border-radius: 8px;
      padding: 16px;
      cursor: pointer;
      transition: border-color 0.15s, transform 0.1s;
    }
    .card:hover {
      border-color: var(--navy);
      transform: translateY(-2px);
    }
    .card-brand {
      font-family: var(--font-primary);
      font-size: 0.65rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      color: var(--navy);
      text-transform: uppercase;
      margin-bottom: 0.4rem;
    }
    .card-title {
      font-family: var(--font-primary);
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--ink);
      margin-bottom: 0.25rem;
      line-height: 1.3;
    }
    .card-period {
      font-family: var(--font-primary);
      font-size: 0.75rem;
      font-weight: 400;
      color: var(--ink-faint);
      margin-bottom: 0.5rem;
    }
    .card-desc {
      font-family: var(--font-primary);
      font-size: 0.8rem;
      font-weight: 300;
      color: var(--ink-soft);
      line-height: 1.5;
      margin-bottom: 0.75rem;
    }
    .card-footer {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      flex-wrap: wrap;
    }
    .tag {
      background: rgba(39, 69, 102, 0.07);
      color: var(--navy);
      font-family: var(--font-primary);
      font-size: 0.65rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
    }
    .badge-public {
      margin-left: auto;
      font-family: var(--font-primary);
      font-size: 0.6rem;
      font-weight: 600;
      color: var(--steel);
      border: 1px solid var(--blue-soft);
      border-radius: 4px;
      padding: 0.1rem 0.4rem;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    #empty {
      grid-column: 1/-1;
      text-align: center;
      padding: 60px 0;
      color: var(--ink-faint);
      font-family: var(--font-editorial);
      font-style: italic;
    }
```

- [ ] **Step 2: Remover `#`s do rendering de tags**

Nos templates dentro do JS (linha ≈ 376 `${(a.tags ?? []).map(t => \`<span class="tag">#${t}</span>\`).join('')}`), trocar `#${t}` por apenas `${t}`:

```javascript
        ${(a.tags ?? []).map(t => `<span class="tag">${t}</span>`).join('')}
```

Motivo: tags no novo visual são uppercase com espaçamento — prefixo `#` vira ruído visual.

Idem para os chips (linha ≈ 336):

```javascript
    btn.textContent = t
```

(substituir `btn.textContent = \`#${t}\`` por `btn.textContent = t`)

- [ ] **Step 3: Substituir CSS de `#analysis-view`, `.analysis-bar`, `#back-btn`, `#analysis-crumb`, `#analysis-iframe`**

Substituir o bloco inteiro (linhas ≈ 166–197) por:

```css
    #analysis-view {
      display: none;
      flex-direction: column;
      height: 100vh;
    }
    .analysis-bar {
      background: var(--ink);
      color: var(--surface);
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      padding: 10px 20px;
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
    #back-btn {
      background: none;
      border: 1px solid rgba(255, 255, 255, 0.2);
      color: var(--surface);
      font-family: var(--font-primary);
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s;
    }
    #back-btn:hover {
      border-color: var(--blue-soft);
      color: var(--blue-soft);
    }
    #analysis-crumb {
      font-family: var(--font-editorial);
      font-style: italic;
      font-size: 0.9rem;
      color: rgba(255, 255, 255, 0.7);
    }
    #analysis-iframe {
      flex: 1;
      border: none;
      background: var(--surface);
    }
```

- [ ] **Step 4: Atualizar mensagem de erro do loading**

Na função `init()`, substituir:

```javascript
    document.getElementById('loading').innerHTML =
      `<p style="color:#ef5350">Erro: ${err.message}</p>`
```

por:

```javascript
    document.getElementById('loading').innerHTML =
      `<p style="color:var(--ink); font-family:var(--font-editorial); font-style:italic;">Erro: ${err.message}</p>`
```

- [ ] **Step 5: Verificar visualmente**

Abrir `index.html`. Esperado:
- Grid de cards sobre fundo creme; cards brancos com borda bege quente
- Brand em navy uppercase; título em preto; tags em navy com fundo suave
- Clicar um card abre o iframe com barra preta + botão "← BIBLIOTECA" em branco e breadcrumb em Playfair itálico
- Voltar volta pra biblioteca
- Grepar por `#3a8a3a`, `#66bb6a`, `#0d1a0d`, `#152315`, `var(--green)`, `var(--accent)` no arquivo: zero ocorrências

Comando de verificação:

```bash
grep -nE '#(3a8a3a|66bb6a|0d1a0d|152315|2a4a2a|4caf50|8aaf8a|e8f5e8)|var\(--(green|accent|bg|text-muted|text)\b' index.html
```

Esperado: sem saída.

- [ ] **Step 6: Commit**

```bash
git add index.html
git commit -m "style(index): cards, tags e analysis view alinhados à identidade"
```

---

## Task 4: `dashboard_farm_ecomm.html` — tokens, fonts, header, hero e KPIs

**Files:**
- Modify: `/Users/arturlemos/Documents/bq-analista/dashboard_farm_ecomm.html` (linhas 7–40 head/body, 42–172 header/hero/KPIs)

- [ ] **Step 1: Substituir o link do Google Fonts**

Substituir a linha 9:

```html
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=DM+Mono:wght@300;400;500&family=Instrument+Sans:wght@300;400;500&display=swap" rel="stylesheet" />
```

por:

```html
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Red+Hat+Display:wght@300;400;600&display=swap" rel="stylesheet" />
```

- [ ] **Step 2: Substituir `:root` inteiro**

Substituir o bloco `:root { --bg: #0F1F18; ... --font-sans: 'Instrument Sans', sans-serif; }` (linhas 14–28) por:

```css
    :root {
      /* Neutros */
      --ink:            #000000;
      --surface:        #FFFFFF;
      --surface-warm:   #E8E8E4;

      /* Azuis */
      --navy:           #274566;
      --steel:          #3D5A73;
      --blue-soft:      #A1C6ED;
      --blue-light:     #C5D9ED;

      /* Cor de fundo do dashboard e derivadas */
      --bg:             #274566;
      --card:           rgba(255, 255, 255, 0.04);
      --card-strong:    rgba(255, 255, 255, 0.05);
      --border:         rgba(255, 255, 255, 0.1);
      --border-strong:  rgba(255, 255, 255, 0.12);
      --on-bg:          #FFFFFF;
      --on-bg-dim:      rgba(255, 255, 255, 0.55);
      --on-bg-faint:    rgba(255, 255, 255, 0.35);

      /* Tipografia */
      --font-primary:   'Red Hat Display', Arial, sans-serif;
      --font-editorial: 'Playfair Display', Georgia, serif;
    }
```

- [ ] **Step 3: Atualizar `html` e `body`**

Substituir linhas 30–39 por:

```css
    html {
      background: var(--bg);
      color: var(--on-bg);
      font-family: var(--font-primary);
      font-size: 16px;
    }

    body {
      min-height: 100dvh;
      padding-bottom: 3rem;
      /* Noise sutil sobre o navy */
      background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='.03'/%3E%3C/svg%3E");
    }
```

- [ ] **Step 4: Atualizar `header`, `.logo`, `.header-meta`, `.header-label`, `.header-badge`**

Substituir as regras (linhas ≈ 42–85) por:

```css
    header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      padding: 2rem 1.25rem 0;
      animation: fadeUp .6s ease both;
    }

    .logo {
      font-family: var(--font-primary);
      font-size: 2.4rem;
      font-weight: 400;
      letter-spacing: 0.22em;
      color: var(--on-bg);
      line-height: 1;
      text-transform: uppercase;
    }

    .header-meta { text-align: right; }

    .header-label {
      font-family: var(--font-primary);
      font-size: 0.62rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--on-bg-dim);
      line-height: 1.6;
    }

    .header-badge {
      display: inline-block;
      margin-top: 0.45rem;
      background: var(--blue-soft);
      color: var(--navy);
      font-family: var(--font-primary);
      font-size: 0.6rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      padding: 0.3rem 0.6rem;
      border-radius: 4px;
      text-transform: uppercase;
    }
```

- [ ] **Step 5: Atualizar `.section-label` e `.divider`**

Substituir (linhas ≈ 87–102) por:

```css
    .section-label {
      font-family: var(--font-editorial);
      font-style: italic;
      font-weight: 400;
      font-size: 1rem;
      color: var(--on-bg-dim);
      letter-spacing: 0.02em;
      margin-bottom: 0.85rem;
    }

    .divider {
      height: 1px;
      background: var(--border);
      margin: 0 1.25rem;
    }
```

- [ ] **Step 6: Atualizar hero (`.hero`, `.hero-main-label`, `.hero-value`, `.hero-sub`, `.kpi-row`, `.kpi-card`, `.kpi-label`, `.kpi-value` e modificadores)**

Substituir (linhas ≈ 104–172) por:

```css
    .hero {
      padding: 2rem 1.25rem 1.5rem;
      animation: fadeUp .6s .1s ease both;
    }

    .hero-main-label {
      font-family: var(--font-primary);
      font-size: 0.6rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--blue-soft);
      margin-bottom: 0.5rem;
    }

    .hero-value {
      font-family: var(--font-editorial);
      font-style: italic;
      font-weight: 400;
      font-size: 3.8rem;
      color: var(--on-bg);
      line-height: 1;
      letter-spacing: -0.01em;
    }

    .hero-sub {
      font-family: var(--font-primary);
      font-weight: 300;
      font-size: 0.85rem;
      color: var(--on-bg-dim);
      margin-top: 0.55rem;
    }

    .kpi-row {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.75rem;
      margin-top: 1.5rem;
    }

    .kpi-card {
      background: var(--card-strong);
      border: 1px solid var(--border-strong);
      border-radius: 6px;
      padding: 0.9rem 1rem;
      transition: border-color 0.2s;
    }

    .kpi-card:active { border-color: var(--blue-soft); }

    .kpi-label {
      font-family: var(--font-primary);
      font-size: 0.58rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--on-bg-dim);
      margin-bottom: 0.4rem;
    }

    .kpi-value {
      font-family: var(--font-primary);
      font-size: 1.4rem;
      font-weight: 400;
      color: var(--on-bg);
      line-height: 1;
    }

    .kpi-value.accent { color: var(--blue-soft); }
    .kpi-value.alert  { color: var(--on-bg); font-weight: 600; }
```

- [ ] **Step 7: Verificar visualmente**

Abrir `dashboard_farm_ecomm.html`. Esperado:
- Fundo navy sólido com ruído imperceptível
- Logo "FARM" em Red Hat com letter-spacing muito aberto
- Badge de período em powder blue com texto navy
- "R$12,0M" em Playfair itálico gigante (ainda não tem a fonte renderizada? checar Network)
- 4 KPIs em cards semi-transparentes; "Ticket Médio" em powder blue; "Taxa de Desconto" em branco bold

- [ ] **Step 8: Commit**

```bash
git add dashboard_farm_ecomm.html
git commit -m "style(dashboard): tokens Azzas, header e hero editorial"
```

---

## Task 5: `dashboard_farm_ecomm.html` — sparkline (canvas) e labels de tendência

**Files:**
- Modify: `/Users/arturlemos/Documents/bq-analista/dashboard_farm_ecomm.html` (linhas ≈ 174–202 chart-wrap/trend, 747–817 canvas script)

- [ ] **Step 1: Atualizar `.chart-wrap` e `.trend-label`**

Substituir (linhas ≈ 174–202) por:

```css
    .section {
      padding: 1.5rem 1.25rem 0;
    }

    .chart-wrap {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 1.25rem 1rem 1rem;
      overflow: hidden;
      animation: fadeUp .6s .25s ease both;
    }

    .trend-labels {
      display: flex;
      justify-content: space-between;
      margin-top: 0.65rem;
    }

    .trend-label {
      font-family: var(--font-primary);
      font-size: 0.55rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--on-bg-dim);
      text-align: center;
      flex: 1;
    }

    .trend-label.peak {
      color: var(--blue-soft);
      font-weight: 600;
    }
```

- [ ] **Step 2: Atualizar cores dentro do script do sparkline**

No bloco `(function () { ... })();` do sparkline (linhas ≈ 747–817), fazer quatro substituições:

a. Substituir as duas linhas de gradient:

```javascript
      grad.addColorStop(0, 'rgba(109,168,130,.35)');
      grad.addColorStop(1, 'rgba(109,168,130,.0)');
```

por:

```javascript
      grad.addColorStop(0, 'rgba(161,198,237,.4)');
      grad.addColorStop(1, 'rgba(161,198,237,0)');
```

b. Substituir `ctx.strokeStyle = '#6DA882';` por:

```javascript
      ctx.strokeStyle = '#A1C6ED';
```

c. Substituir `ctx.fillStyle = '#D9A84E';` (cor do ponto de pico) por:

```javascript
      ctx.fillStyle = '#FFFFFF';
```

d. Substituir a definição da fonte e as cores dos labels:

```javascript
      ctx.font = `${9 * dpr / dpr}px 'DM Mono', monospace`;
```

por:

```javascript
      ctx.font = `10px 'Red Hat Display', sans-serif`;
```

e o array:

```javascript
      [[0, '#6DA882'], [peakIdx, '#D9A84E'], [n - 1, 'rgba(242,232,213,.55)']].forEach(([i, color]) => {
```

por:

```javascript
      [[0, 'rgba(255,255,255,.55)'], [peakIdx, '#A1C6ED'], [n - 1, 'rgba(255,255,255,.55)']].forEach(([i, color]) => {
```

- [ ] **Step 3: Verificar visualmente**

Abrir `dashboard_farm_ecomm.html`. Esperado:
- Linha do sparkline em powder blue
- Ponto de pico (quarta 15) com bolinha branca
- Label da terça-feira/pico em powder blue; demais em cinza claro
- Valores de R$ em Red Hat Display (não em DM Mono)

- [ ] **Step 4: Commit**

```bash
git add dashboard_farm_ecomm.html
git commit -m "style(dashboard): sparkline em powder blue com pico branco"
```

---

## Task 6: `dashboard_farm_ecomm.html` — categorias, top 10 e pills de desconto

**Files:**
- Modify: `/Users/arturlemos/Documents/bq-analista/dashboard_farm_ecomm.html` (linhas ≈ 204–356, 637 inline override)

- [ ] **Step 1: Atualizar `.groups-list` / `.group-row` / `.group-name` / `.group-stats` / `.bar-track` / `.bar-fill`**

Substituir (linhas ≈ 204–249) por:

```css
    .groups-list {
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
      animation: fadeUp .6s .3s ease both;
    }

    .group-row { display: flex; flex-direction: column; gap: 0.3rem; }

    .group-meta {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }

    .group-name {
      font-family: var(--font-primary);
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--on-bg);
    }

    .group-stats {
      font-family: var(--font-primary);
      font-size: 0.62rem;
      font-weight: 300;
      color: var(--on-bg-dim);
    }

    .bar-track {
      height: 4px;
      background: rgba(255, 255, 255, 0.07);
      border-radius: 2px;
      overflow: hidden;
    }

    .bar-fill {
      height: 100%;
      background: var(--blue-soft);
      border-radius: 2px;
      transform-origin: left;
      transform: scaleX(0);
      transition: transform 1s cubic-bezier(.22,1,.36,1);
    }
```

- [ ] **Step 2: Atualizar bloco Top 10 (products-list, product-row, rank, product-name, product-cor, product-bar-*, product-numbers, product-revenue, product-units)**

Substituir (linhas ≈ 251–342) por:

```css
    .products-list {
      display: flex;
      flex-direction: column;
      gap: 0;
      border: 1px solid var(--border);
      border-radius: 6px;
      overflow: hidden;
      animation: fadeUp .6s .35s ease both;
    }

    .product-row {
      display: grid;
      grid-template-columns: 1.8rem 1fr auto;
      align-items: start;
      gap: 0.6rem;
      padding: 0.9rem 1rem;
      border-bottom: 1px solid var(--border);
      background: var(--card-strong);
      transition: background 0.15s;
    }

    .product-row:last-child { border-bottom: none; }
    .product-row:active { background: rgba(255, 255, 255, 0.06); }

    .rank {
      font-family: var(--font-primary);
      font-size: 0.7rem;
      font-weight: 300;
      color: var(--on-bg-dim);
      padding-top: 0.15rem;
      text-align: right;
    }

    .rank.top3 { color: var(--blue-soft); font-weight: 600; }

    .product-info { display: flex; flex-direction: column; gap: 0.2rem; }

    .product-name {
      font-family: var(--font-editorial);
      font-size: 0.95rem;
      font-weight: 400;
      color: var(--on-bg);
      line-height: 1.3;
      letter-spacing: 0.01em;
    }

    .product-cor {
      font-family: var(--font-primary);
      font-size: 0.55rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--on-bg-dim);
      margin-top: 0.15rem;
    }

    .product-bar-wrap { margin-top: 0.4rem; }

    .product-bar-track {
      height: 2px;
      background: rgba(255, 255, 255, 0.07);
      border-radius: 1px;
      overflow: hidden;
    }

    .product-bar-fill {
      height: 100%;
      background: var(--blue-soft);
      border-radius: 1px;
      transform-origin: left;
      transform: scaleX(0);
      transition: transform 1.1s cubic-bezier(.22,1,.36,1);
    }

    .product-numbers {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 0.2rem;
      flex-shrink: 0;
    }

    .product-revenue {
      font-family: var(--font-primary);
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--blue-soft);
      white-space: nowrap;
    }

    .product-units {
      font-family: var(--font-primary);
      font-size: 0.62rem;
      font-weight: 300;
      color: var(--on-bg-dim);
      white-space: nowrap;
    }
```

- [ ] **Step 3: Atualizar `.discount-pill` e variantes**

Substituir (linhas ≈ 344–356) por:

```css
    .discount-pill {
      font-family: var(--font-primary);
      font-size: 0.55rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      padding: 0.18rem 0.45rem;
      border-radius: 3px;
      white-space: nowrap;
    }

    .disc-low  { background: rgba(161, 198, 237, 0.18); color: var(--blue-light); }
    .disc-mid  { background: rgba(181, 175, 168, 0.2);  color: var(--surface-warm); }
    .disc-high { background: var(--ink); color: var(--on-bg); }
```

- [ ] **Step 4: Remover os overrides inline de cores antigas nas product bars**

Na linha ≈ 589 (produto #4 sem cadastro):

```html
          <div class="product-bar-track"><div class="product-bar-fill" style="background:var(--cream-dim);"></div></div>
```

Trocar por:

```html
          <div class="product-bar-track"><div class="product-bar-fill" style="background: var(--on-bg-dim);"></div></div>
```

E na linha ≈ 637 (produto #7 Rio Antigo com override coral):

```html
          <div class="product-bar-track"><div class="product-bar-fill" style="background:var(--coral);"></div></div>
```

Trocar por (remove o override, volta pro default powder blue):

```html
          <div class="product-bar-track"><div class="product-bar-fill"></div></div>
```

- [ ] **Step 5: Verificar visualmente**

Abrir `dashboard_farm_ecomm.html`. Esperado:
- Barras de categoria em powder blue sólido (sem gradient)
- Top 10 com nomes de produto em Playfair itálico aparente
- Ranking top3 em powder blue bold; demais em cinza claro
- Pills: "-10,5%" em powder blue suave; "-18,7%" em warm gray; "-35,5%" em preto sólido com texto branco
- Animação de entrada das barras preservada (scroll até a seção)

- [ ] **Step 6: Commit**

```bash
git add dashboard_farm_ecomm.html
git commit -m "style(dashboard): categorias, top 10 e pills Azzas"
```

---

## Task 7: `dashboard_farm_ecomm.html` — insights e footer

**Files:**
- Modify: `/Users/arturlemos/Documents/bq-analista/dashboard_farm_ecomm.html` (linhas ≈ 358–373 footer CSS, 700–744 insights HTML, 737–744 footer HTML)

- [ ] **Step 1: Adicionar CSS das classes de insight**

Na seção de CSS, logo após a regra `.discount-pill` e variantes (final do bloco Top 10), antes de `/* ── FOOTER */`, adicionar:

```css
    /* ── INSIGHTS ───────────────────────────────────────────────── */
    .insights-list {
      display: flex;
      flex-direction: column;
      gap: 0.65rem;
    }

    .insight {
      background: var(--card);
      border: 1px solid var(--border);
      border-left: 3px solid rgba(255, 255, 255, 0.2);
      border-radius: 6px;
      padding: 0.9rem 1rem;
    }

    .insight.positive  { border-left-color: var(--blue-soft); }
    .insight.alert     { border-left-color: var(--on-bg); }
    .insight.highlight { border-left-color: var(--blue-light); }
    .insight.neutral   { border-left-color: rgba(255, 255, 255, 0.25); }

    .insight-label {
      font-family: var(--font-primary);
      font-size: 0.58rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 0.35rem;
    }

    .insight.positive  .insight-label { color: var(--blue-soft); }
    .insight.alert     .insight-label { color: var(--on-bg); }
    .insight.highlight .insight-label { color: var(--blue-light); }
    .insight.neutral   .insight-label { color: var(--on-bg-dim); }

    .insight-text {
      font-family: var(--font-editorial);
      font-weight: 400;
      font-size: 0.95rem;
      color: var(--on-bg);
      line-height: 1.5;
    }
```

- [ ] **Step 2: Reescrever o HTML da seção Insights**

Localizar o bloco (linhas ≈ 700–734):

```html
  <!-- INSIGHTS -->
  <section class="section" style="animation: fadeUp .6s .4s ease both; padding-bottom: 0;">
    <div class="section-label">Insights do período</div>
    <div style="display:flex; flex-direction:column; gap:.65rem;">

      <div style="background:var(--card); border:1px solid var(--border); border-left: 3px solid var(--sage); border-radius:6px; padding:.9rem 1rem;">
        <div style="font-family:var(--font-mono);font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;color:var(--sage);margin-bottom:.35rem;">Coleção dominante</div>
        <div style="font-family:var(--font-serif);font-size:.95rem;color:var(--cream);line-height:1.45;">
          <em>Jardim Majestoso</em> e <em>Voo em Flor</em> concentram 6 dos 10 produtos no ranking — sinal claro de sell-through saudável nessas coleções.
        </div>
      </div>
      ...
    </div>
  </section>
```

Substituir pelo bloco inteiro:

```html
  <!-- INSIGHTS -->
  <section class="section" style="animation: fadeUp .6s .4s ease both; padding-bottom: 0;">
    <div class="section-label">Insights do período</div>
    <div class="insights-list">

      <div class="insight positive">
        <div class="insight-label">Coleção dominante</div>
        <div class="insight-text">
          <em>Jardim Majestoso</em> e <em>Voo em Flor</em> concentram 6 dos 10 produtos no ranking — sinal claro de sell-through saudável nessas coleções.
        </div>
      </div>

      <div class="insight alert">
        <div class="insight-label">Alerta de desconto</div>
        <div class="insight-text">
          Vestido Longo Rio Antigo (#7) opera com 35,5% de desconto — quase o dobro da média do top 10. Investigar se é ação promocional planejada ou clearance.
        </div>
      </div>

      <div class="insight highlight">
        <div class="insight-label">Maior receita ≠ Mais vendido</div>
        <div class="insight-text">
          O produto #8 (Vestido Longo Voo em Flor var. 2) gerou R$133K com 220 peças (R$605/pç), superando o #1 em receita. Ticket alto com desconto controlado de 12,3%.
        </div>
      </div>

      <div class="insight neutral">
        <div class="insight-label">Produto sem cadastro</div>
        <div class="insight-text">
          Cód. 370480 aparece em 4º lugar (243 peças, R$78K) sem registro em <em>refined_produtos</em>. Verificar carga de cadastro no data warehouse.
        </div>
      </div>

    </div>
  </section>
```

- [ ] **Step 3: Atualizar `footer` e `.footer-note`**

Substituir as regras CSS (linhas ≈ 358–373) por:

```css
    /* ── FOOTER ──────────────────────────────────────────────────── */
    footer {
      padding: 2rem 1.25rem 0;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      animation: fadeUp .6s .5s ease both;
    }

    .footer-note {
      font-family: var(--font-primary);
      font-size: 0.6rem;
      font-weight: 300;
      color: var(--on-bg-faint);
      letter-spacing: 0.04em;
      line-height: 1.6;
    }
```

E o HTML do footer (linhas ≈ 737–744), substituir:

```html
  <footer>
    <div class="footer-note">
      Fonte: soma-dl-refined-online<br>
      soma_online_refined.refined_captacao<br>
      Gerado em 17/04/2026
    </div>
    <div style="font-family:var(--font-serif);font-style:italic;font-size:1.4rem;color:rgba(242,232,213,.15);">farm</div>
  </footer>
```

por:

```html
  <footer>
    <div class="footer-note">
      Fonte: soma-dl-refined-online<br>
      soma_online_refined.refined_captacao<br>
      Gerado em 17/04/2026
    </div>
    <div style="font-family: var(--font-editorial); font-style: italic; font-size: 1.4rem; color: rgba(255, 255, 255, 0.15);">farm</div>
  </footer>
```

- [ ] **Step 4: Atualizar media queries**

Localizar `@media (min-width: 600px)` (linha ≈ 382) — está correto, só garantir que o `.hero-value { font-size: 5rem; }` interno dele continue válido (Playfair itálico vai renderizar bem nesse tamanho).

Localizar `@media (min-width: 900px)` (linha ≈ 393) — nenhuma mudança necessária.

- [ ] **Step 5: Varredura final de cores e fontes antigas**

Executar:

```bash
grep -nE '#(0F1F18|162820|1C3228|F2E8D5|D9A84E|D9604A|6DA882)|Cormorant|DM Mono|Instrument Sans|var\(--(bg2|cream|cream-dim|gold|coral|sage|white|font-serif|font-mono|font-sans)\b' dashboard_farm_ecomm.html
```

Esperado: zero saídas. Se aparecerem, corrigir e refazer.

- [ ] **Step 6: Verificar visualmente**

Abrir `dashboard_farm_ecomm.html`. Esperado:
- Seção "Insights do período" renderiza 4 cards com border-left coloridos (powder blue / branco / azul claro / cinza)
- Labels em uppercase Red Hat; textos em Playfair itálico (os `<em>` ficam ainda mais destacados)
- Footer com nota em Red Hat 300 e marca "farm" decorativa em Playfair itálico baixo contraste
- Comparar lado-a-lado com `mockup-dashboard-v2.html` no browser companion

- [ ] **Step 7: Commit**

```bash
git add dashboard_farm_ecomm.html
git commit -m "style(dashboard): insights restylizados e footer alinhado"
```

---

## Encerramento

Após Task 7, os dois arquivos estão alinhados ao spec. Como checagem final:

- [ ] Rodar `git log --oneline -8` — esperar ver 6 commits com prefixo `style(...)` em ordem
- [ ] Abrir os dois arquivos em abas separadas no browser e comparar contra `mockup-index-v2.html` e `mockup-dashboard-v2.html` servidos pelo companion em `http://localhost:56966`
- [ ] Parar o servidor do companion:

```bash
/Users/arturlemos/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.7/skills/brainstorming/scripts/stop-server.sh /Users/arturlemos/Documents/bq-analista/.superpowers/brainstorm/36314-1776482692
```

Nenhuma ação de deploy necessária — os arquivos servem estáticos via Vercel do jeito que já estão.
