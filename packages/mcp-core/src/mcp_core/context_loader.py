from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DOCS = [
    "schema.md",
    "business-rules.md",
    "SKILL.md",
    "identidade-visual-azzas.md",
    "TEMPLATE.md",
]
# Skills relevantes ao fluxo de análise. Skills não listadas aqui são ignoradas
# mesmo que estejam em .claude/skills/ (evita poluição por imports genéricos).
SKILL_ALLOWLIST = {"product-photos"}
ALLOWED_TABLES = [
    "soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO",
    "soma-pipeline-prd.silver_linx.PRODUTOS",
    "soma-pipeline-prd.silver_linx.PRODUTOS_PRECOS",
    "soma-pipeline-prd.silver_linx.PRODUTO_CORES",
    "soma-pipeline-prd.silver_linx.PRODUTOS_TAMANHOS",
    "soma-pipeline-prd.silver_linx.FILIAIS",
    "soma-pipeline-prd.silver_linx.LOJAS_REDE",
    "soma-pipeline-prd.silver_linx.LOJAS_PREVISAO_VENDAS",
    "soma-pipeline-prd.silver_linx.ANMN_ESTOQUE_HISTORICO_PROD",
]


@dataclass
class ExecContext:
    text: str
    allowed_tables: list[str]


def load_exec_context(repo_root: Path) -> ExecContext:
    sections: list[tuple[str, str]] = []
    for doc in DOCS:
        p = repo_root / doc
        if not p.exists():
            raise FileNotFoundError(f"required doc missing: {p}")
        sections.append((doc, p.read_text()))

    skills_dir = repo_root / ".claude" / "skills"
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            if skill_md.parent.name not in SKILL_ALLOWLIST:
                continue
            rel = str(skill_md.relative_to(repo_root))
            sections.append((rel, skill_md.read_text()))

    toc_lines = [
        "# Analytics Context",
        "",
        "Este bloco contém TODAS as regras e referências que você precisa. "
        "Skills listadas abaixo são padrões documentais aplicados inline — "
        "NÃO são ferramentas MCP separadas e não devem ser buscadas via tool_search.",
        "",
        "## Seções incluídas",
    ]
    for name, _ in sections:
        toc_lines.append(f"- `{name}`")
    toc = "\n".join(toc_lines)

    parts = [toc] + [f"<!-- {name} -->\n{body}" for name, body in sections]
    return ExecContext(text="\n\n".join(parts), allowed_tables=list(ALLOWED_TABLES))
