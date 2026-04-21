from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SHARED_DOCS = [
    "analyst-principles.md",
    "pii-rules.md",
    "identidade-visual-azzas.md",
    "TEMPLATE.md",
]

AGENT_DOCS = [
    "schema.md",
    "business-rules.md",
    "SKILL.md",
]

SKILL_ALLOWLIST = {"product-photos"}


@dataclass
class ExecContext:
    text: str
    allowed_tables: list[str]


def load_exec_context(agent_root: Path, shared_root: Path) -> ExecContext:
    """
    Merge two context layers:
    1. shared_root/ — analyst-principles, pii-rules, dimensions/*.md
    2. agent_root/context/ — schema.md, business-rules.md, SKILL.md

    Skills are loaded from <repo_root>/.claude/skills/ where repo_root
    is derived as shared_root.parent.parent (shared/context → repo root).
    """
    sections: list[tuple[str, str]] = []

    # Shared docs (optional — missing files are silently skipped)
    for doc in SHARED_DOCS:
        p = shared_root / doc
        if p.exists():
            sections.append((f"shared/{doc}", p.read_text()))

    # Shared dimensions
    dims_dir = shared_root / "dimensions"
    if dims_dir.exists():
        for dim in sorted(dims_dir.glob("*.md")):
            sections.append((f"shared/dimensions/{dim.name}", dim.read_text()))

    # Agent-specific context (optional)
    ctx_dir = agent_root / "context"
    for doc in AGENT_DOCS:
        p = ctx_dir / doc
        if p.exists():
            sections.append((doc, p.read_text()))

    # Skills from repo root .claude/skills/
    # shared_root = <repo_root>/shared/context → repo_root = shared_root.parent.parent
    repo_root = shared_root.parent.parent
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
    ] + [f"- `{name}`" for name, _ in sections]

    parts = ["\n".join(toc_lines)] + [f"<!-- {name} -->\n{body}" for name, body in sections]
    return ExecContext(text="\n\n".join(parts), allowed_tables=[])
