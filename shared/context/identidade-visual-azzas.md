---
tipo: nota
data: 2026-03-30
tags: [design, identidade-visual, referencia]
---

# Identidade Visual - BU Fashion & Lifestyle (Azzas 2154)

Referência extraída do template oficial `template-azzas.pptx` (22 slides analisados visualmente). Usar como base para qualquer entrega visual: reports HTML, dashboards, slides e frontends.

---

## Paleta de Cores

A identidade é extremamente contida: preto, branco, tons de azul e neutros quentes. Sem cores vibrantes.

### Neutros (base de tudo)

| Token | Hex | Nome | Uso |
|-------|-----|------|-----|
| `--ink` | `#000000` | Preto | Texto principal, fundos hero/cover, overlays |
| `--ink-soft` | `#595959` | Cinza escuro | Texto secundário, captions |
| `--ink-faint` | `#999999` | Cinza médio | Labels, metadados, placeholders |
| `--surface` | `#FFFFFF` | Branco | Fundo principal, texto sobre escuro |
| `--surface-warm` | `#E8E8E4` | Bege quente | Fundo de slides de conteúdo |
| `--surface-cream` | `#F9F6EA` | Creme | Fundo editorial, destaque suave |

### Azuis (a única família de cor do template)

| Token | Hex | Nome | Uso |
|-------|-----|------|-----|
| `--navy` | `#274566` | Navy escuro | Fundo de slides, destaque principal |
| `--steel` | `#3D5A73` | Steel blue | Fundo alternativo, elementos de ênfase |
| `--blue-soft` | `#A1C6ED` | Azul powder | Fundos suaves, gradientes, backgrounds claros |
| `--blue-light` | `#C5D9ED` | Azul claro | Gradientes, hover states |

### Funcionais (para dashboards e UIs - derivadas da paleta)

| Token | Hex | Nome | Uso |
|-------|-----|------|-----|
| `--status-active` | `#274566` | Navy | Status ativo, confirmado |
| `--status-pending` | `#B5AFA8` | Warm gray | Pendente, aguardando |
| `--overlay` | `rgba(0,0,0,0.35)` | Overlay escuro | Sobre fotografias com texto |

---

## Tipografia

### Fontes

| Papel | Família | Google Fonts |
|-------|---------|-------------|
| **Principal** | Red Hat Display | `Red+Hat+Display:wght@300;400;600` |
| **Editorial/Acento** | Playfair Display | `Playfair+Display:ital,wght@0,400;0,700;1,400` |
| **Fallback** | Arial, sans-serif | Sistema |

### Hierarquia de Tamanhos

| Nível | Fonte | Peso | Tamanho | Estilo |
|-------|-------|------|---------|--------|
| H1 - Título principal | Red Hat Display | Regular (400) | 3.5-4rem | Pode ser ALL CAPS |
| H2 - Subtítulo editorial | Playfair Display | Regular (400) | 1.25rem | Itálico |
| H3 - Seção | Red Hat Display | SemiBold (600) | 1.5rem | - |
| Body | Red Hat Display | Regular (400) | 1.125rem | - |
| Body Light | Red Hat Display | Light (300) | 1.125rem | Para textos longos |
| Caption | Red Hat Display | Light (300) | 0.875rem | `--ink-soft` |
| Label/Tag | Red Hat Display | SemiBold (600) | 0.75rem | ALL CAPS, letter-spacing |

---

## CSS Variables (Design Tokens)

Copiar direto no `:root` de qualquer projeto HTML:

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
  --status-active:  #274566;
  --status-pending: #B5AFA8;
  --overlay:        rgba(0, 0, 0, 0.35);

  /* Tipografia */
  --font-primary:   'Red Hat Display', Arial, sans-serif;
  --font-editorial: 'Playfair Display', Georgia, serif;

  /* Tamanhos */
  --text-h1:    clamp(2.5rem, 4vw, 4rem);
  --text-h2:    1.25rem;
  --text-h3:    1.5rem;
  --text-body:  1.125rem;
  --text-small: 0.875rem;
  --text-xs:    0.75rem;

  /* Pesos */
  --weight-light:    300;
  --weight-regular:  400;
  --weight-semibold: 600;

  /* Espaçamento */
  --space-xs:  0.25rem;
  --space-sm:  0.5rem;
  --space-md:  1rem;
  --space-lg:  2rem;
  --space-xl:  4rem;

  /* Bordas */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 16px;

  /* Sombras */
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.08);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.10);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.14);
}
```

---

## HTML Head (Google Fonts)

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Red+Hat+Display:wght@300;400;600&display=swap" rel="stylesheet">
```

---

## Padrões de Componentes

### Hero / Cover (foto + overlay + texto branco)

```css
.hero {
  position: relative;
  background: var(--ink);
  color: var(--surface);
  padding: var(--space-xl);
}

.hero-title {
  font-family: var(--font-primary);
  font-size: var(--text-h1);
  font-weight: var(--weight-regular);
  letter-spacing: 0.02em;
}

.hero-subtitle {
  font-family: var(--font-editorial);
  font-size: var(--text-h2);
  font-weight: var(--weight-regular);
  font-style: italic;
  opacity: 0.7;
}
```

### Seção (divisória com fundo navy)

```css
.section-divider {
  background: var(--navy);
  color: var(--surface);
  padding: var(--space-xl);
  text-align: center;
}

.section-divider h2 {
  font-family: var(--font-primary);
  font-size: var(--text-h1);
  font-weight: var(--weight-regular);
}

.section-divider em {
  font-family: var(--font-editorial);
  font-style: italic;
}
```

### Card de Conteúdo

```css
.card {
  background: var(--surface);
  border: 1px solid var(--surface-warm);
  border-radius: var(--radius-md);
  padding: var(--space-lg);
}

.card-title {
  font-family: var(--font-primary);
  font-weight: var(--weight-semibold);
  font-size: var(--text-h3);
  color: var(--ink);
}

.card-body {
  font-family: var(--font-primary);
  font-weight: var(--weight-light);
  font-size: var(--text-body);
  color: var(--ink-soft);
  line-height: 1.6;
}
```

### Tag / Badge

```css
.tag {
  font-family: var(--font-primary);
  font-size: var(--text-xs);
  font-weight: var(--weight-semibold);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-sm);
}

.tag--navy  { background: #27456612; color: var(--navy); }
.tag--steel { background: #3D5A7312; color: var(--steel); }
.tag--muted { background: #B5AFA812; color: var(--status-pending); }
```

### Header / Navbar

```css
.navbar {
  background: var(--ink);
  color: var(--surface);
  padding: var(--space-md) var(--space-lg);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.navbar-brand {
  font-family: var(--font-primary);
  font-weight: var(--weight-semibold);
  font-size: var(--text-h3);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
```

---

## Diretrizes Gerais

1. **Paleta restrita** - A identidade usa essencialmente preto, branco e azuis. Não introduzir cores vibrantes (sem verde, roxo, laranja, etc).
2. **Fotografia como protagonista** - Slides são dominados por fotos full-bleed. Em UIs, usar imagens de alta qualidade.
3. **Overlay escuro sobre fotos** - Sempre que houver texto sobre imagem, aplicar overlay (35% opacidade).
4. **Navy como cor de destaque** - O azul navy (#274566) é a principal cor "não-neutra". Usar para seções de destaque, status ativos, links.
5. **Powder blue para fundos suaves** - O azul claro (#A1C6ED) aparece em gradientes e fundos de conteúdo.
6. **Hierarquia via peso, não cor** - Light (300) vs Regular (400) vs SemiBold (600) cria contraste suficiente.
7. **Máximo 2 fontes** - Red Hat Display (principal) + Playfair Display (editorial/itálico).
8. **ALL CAPS com parcimônia** - Apenas para labels, eyebrows e títulos de impacto. Nunca em corpo de texto.
9. **Minimalismo** - Muito espaço em branco. Menos elementos, mais respiro.

---

## Padrões de Fundo dos Slides

| Tipo de slide | Fundo | Texto |
|---------------|-------|-------|
| Cover/Capa | Foto full-bleed + overlay | Branco |
| Seção | Foto ou Navy sólido | Branco |
| Conteúdo claro | Bege (#E8E8E4) ou Creme | Preto |
| Conteúdo azul | Powder blue (#A1C6ED) | Preto |
| Conteúdo escuro | Navy (#274566) | Branco |
| Dados/Métricas | Preto sólido | Branco |

---

*Fonte: template-azzas.pptx / template-azzas.pdf (22 slides analisados em 2026-03-30)*
