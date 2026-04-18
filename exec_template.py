"""HTML template generator for executive dashboards.

Generates standalone HTML dashboards following Farm/Soma branding.
Reuses structure from existing analyses but parameterized for report-generator.
"""

from typing import Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class KPICard:
    label: str
    value: str
    accent: bool = False


@dataclass
class Section:
    title: str
    content: str  # Raw HTML content


@dataclass
class Insight:
    text: str
    type: str = "neutral"  # neutral, positive, alert, highlight


def generate_dashboard_html(
    title: str,
    brand: str,
    period: str,
    hero_label: str,
    hero_value: str,
    hero_sub: Optional[str] = None,
    kpis: Optional[list[KPICard]] = None,
    sections: Optional[list[Section]] = None,
    insights: Optional[list[Insight]] = None,
) -> str:
    """Generate complete HTML dashboard.

    Args:
        title: Dashboard title (e.g. "Análise de Produto")
        brand: Brand/company name (e.g. "FARM")
        period: Date period (e.g. "11–17 abr 2026")
        hero_label: Main KPI label (e.g. "Venda Líquida Total")
        hero_value: Main KPI value (e.g. "R$12,0M")
        hero_sub: Additional context below hero (e.g. "35.778 peças · ...")
        kpis: List of KPICard objects for the KPI row
        sections: List of Section objects for content
        insights: List of Insight objects for alerts

    Returns:
        Complete HTML string (single file, inlined CSS, ready to publish)
    """

    if kpis is None:
        kpis = []
    if sections is None:
        sections = []
    if insights is None:
        insights = []

    # Build KPI cards HTML
    kpi_cards_html = "".join(
        f'''
      <div class="kpi-card">
        <div class="kpi-label">{kpi.label}</div>
        <div class="kpi-value{'  accent' if kpi.accent else ''}">{kpi.value}</div>
      </div>
'''
        for kpi in kpis
    )

    # Build sections HTML
    sections_html = "".join(
        f'''
  <!-- {section.title.upper()} -->
  <section class="section">
    <h2 class="section-title">{section.title}</h2>
    {section.content}
  </section>
'''
        for section in sections
    )

    # Build insights HTML
    insights_html = "".join(
        f'''
    <div class="insight {insight.type}">
      <div class="insight-label">{insight.type.upper()}</div>
      <div class="insight-text">{insight.text}</div>
    </div>
'''
        for insight in insights
    )

    hero_sub_html = f'    <div class="hero-sub">{hero_sub}</div>' if hero_sub else ""

    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{brand} — {title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Red+Hat+Display:wght@300;400;600&display=swap" rel="stylesheet" />

  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
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
    }}

    html {{
      background: var(--bg);
      color: var(--on-bg);
      font-family: var(--font-primary);
      font-size: 16px;
    }}

    body {{
      min-height: 100dvh;
      padding-bottom: 3rem;
      background-image:
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)' opacity='.03'/%3E%3C/svg%3E");
    }}

    /* ── HEADER ──────────────────────────────────────────────────── */
    header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      padding: 2rem 1.25rem 0;
      animation: fadeUp .6s ease both;
    }}

    .logo {{
      font-family: var(--font-primary);
      font-size: 2.4rem;
      font-weight: 400;
      letter-spacing: 0.22em;
      color: var(--on-bg);
      line-height: 1;
      text-transform: uppercase;
    }}

    .header-meta {{ text-align: right; }}

    .header-label {{
      font-family: var(--font-primary);
      font-size: 0.62rem;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--on-bg-dim);
      line-height: 1.6;
    }}

    .header-badge {{
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
    }}

    /* ── HERO ────────────────────────────────────────────────────── */
    .hero {{
      padding: 1.25rem 1rem 1rem;
      animation: fadeUp .6s .1s ease both;
    }}

    .hero-main-label {{
      font-family: var(--font-primary);
      font-size: 0.62rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--on-bg-dim);
      margin-bottom: 0.5rem;
    }}

    .hero-value {{
      font-family: var(--font-editorial);
      font-size: 2.8rem;
      font-weight: 700;
      color: var(--on-bg);
      line-height: 1;
      margin-bottom: 0.3rem;
    }}

    .hero-sub {{
      font-family: var(--font-primary);
      font-size: 0.6rem;
      font-weight: 300;
      color: var(--on-bg-dim);
      letter-spacing: 0.05em;
      margin-bottom: 1.25rem;
    }}

    /* ── KPI ROW ─────────────────────────────────────────────────── */
    .kpi-row {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 0.6rem;
      margin-top: 1rem;
    }}

    .kpi-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.9rem;
      animation: fadeUp .6s .15s ease both;
    }}

    .kpi-label {{
      font-family: var(--font-primary);
      font-size: 0.55rem;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--on-bg-dim);
      margin-bottom: 0.4rem;
    }}

    .kpi-value {{
      font-family: var(--font-editorial);
      font-size: 1.4rem;
      font-weight: 700;
      color: var(--blue-light);
      line-height: 1;
    }}

    .kpi-value.accent {{
      color: var(--blue-soft);
    }}

    /* ── DIVIDER ─────────────────────────────────────────────────── */
    .divider {{
      height: 1px;
      background: var(--border);
      margin: 1.5rem 1.25rem 0;
    }}

    /* ── SECTION ─────────────────────────────────────────────────── */
    .section {{
      padding: 1.25rem 1rem 1rem;
      animation: fadeUp .6s .2s ease both;
    }}

    .section-title {{
      font-family: var(--font-primary);
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--on-bg);
      margin-bottom: 1rem;
    }}

    /* ── INSIGHTS ────────────────────────────────────────────────── */
    .insights-grid {{
      display: flex;
      flex-direction: column;
      gap: 0.8rem;
      animation: fadeUp .6s .4s ease both;
    }}

    .insight {{
      border-left: 3px solid;
      border-radius: 6px;
      padding: 0.9rem 1rem;
    }}

    .insight.positive  {{ border-left-color: var(--blue-soft); }}
    .insight.alert     {{ border-left-color: var(--on-bg); }}
    .insight.highlight {{ border-left-color: var(--blue-light); }}
    .insight.neutral   {{ border-left-color: rgba(255, 255, 255, 0.25); }}

    .insight-label {{
      font-family: var(--font-primary);
      font-size: 0.58rem;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-bottom: 0.35rem;
    }}

    .insight.positive  .insight-label {{ color: var(--blue-soft); }}
    .insight.alert     .insight-label {{ color: var(--on-bg); }}
    .insight.highlight .insight-label {{ color: var(--blue-light); }}
    .insight.neutral   .insight-label {{ color: var(--on-bg-dim); }}

    .insight-text {{
      font-family: var(--font-editorial);
      font-weight: 400;
      font-size: 0.95rem;
      color: var(--on-bg);
      line-height: 1.5;
    }}

    /* ── FOOTER ──────────────────────────────────────────────────── */
    footer {{
      padding: 2rem 1.25rem 0;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      animation: fadeUp .6s .5s ease both;
    }}

    .footer-note {{
      font-family: var(--font-primary);
      font-size: 0.6rem;
      font-weight: 300;
      color: var(--on-bg-faint);
      letter-spacing: 0.04em;
      line-height: 1.6;
    }}

    /* ── ANIMATIONS ──────────────────────────────────────────────── */
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to   {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── DESKTOP BREAKPOINT ──────────────────────────────────────── */
    @media (min-width: 600px) {{
      header {{ padding: 2.5rem 2rem 0; }}
      .logo {{ font-size: 3.2rem; }}
      .hero {{ padding: 2.5rem 2rem 2rem; }}
      .hero-value {{ font-size: 5rem; }}
      .kpi-row {{ grid-template-columns: repeat(4, 1fr); }}
      .section {{ padding: 2rem 2rem 0; }}
      .divider {{ margin: 0 2rem; }}
      footer {{ padding: 2rem 2rem 0; }}
    }}

    @media (min-width: 900px) {{
      body {{ max-width: 860px; margin: 0 auto; }}
    }}
  </style>
</head>
<body>

  <!-- HEADER -->
  <header>
    <div class="logo">{brand}</div>
    <div class="header-meta">
      <div class="header-label">{title}</div>
      <span class="header-badge">{period}</span>
    </div>
  </header>

  <!-- HERO -->
  <section class="hero">
    <div class="hero-main-label">{hero_label}</div>
    <div class="hero-value">{hero_value}</div>
{hero_sub_html}

    <div class="kpi-row">
{kpi_cards_html}
    </div>
  </section>

  <div class="divider"></div>

{sections_html}
  <div class="divider"></div>

  <!-- INSIGHTS -->
  <section class="section">
    <h2 class="section-title">Insights</h2>
    <div class="insights-grid">
{insights_html}
    </div>
  </section>

  <!-- FOOTER -->
  <footer>
    <div class="footer-note">
      Gerado {datetime.now().strftime('%d de %B de %Y às %H:%M')}<br>
      Dados: BigQuery · Analista: Claude · Vercel
    </div>
  </footer>

</body>
</html>'''

    return html
