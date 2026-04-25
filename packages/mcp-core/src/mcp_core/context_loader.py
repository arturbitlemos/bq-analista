from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SHARED_DOCS = [
    "analyst-principles.md",
    "pii-rules.md",
    "identidade-visual-azzas.md",
    "TEMPLATE.md",
]

# schema.md and business-rules.md are loaded on-demand via describe_table / get_business_rules
AGENT_DOCS = ["SKILL.md"]

SKILL_ALLOWLIST = {"product-photos"}


@dataclass
class ExecContext:
    text: str
    allowed_tables: list[str]


def parse_table_index(schema_text: str) -> list[str]:
    """Extract UPPER_CASE table names from backtick-quoted names in section headers."""
    names: list[str] = []
    seen: set[str] = set()
    for line in schema_text.splitlines():
        if re.match(r"^#{2,4}\s+", line):
            for name in re.findall(r"`([A-Z][A-Z0-9_]+)`", line):
                if name not in seen:
                    seen.add(name)
                    names.append(name)
    return names


def extract_table_section(schema_text: str, table_name: str) -> str | None:
    """Return the schema.md section that documents table_name, or None if not found."""
    target = f"`{table_name.upper()}`"
    lines = schema_text.splitlines()
    start: int | None = None
    start_level = 0
    for i, line in enumerate(lines):
        if start is None:
            m = re.match(r"^(#{2,4})\s+", line)
            if m and target in line:
                start, start_level = i, len(m.group(1))
        else:
            m = re.match(r"^(#{2,4})\s+", line)
            if m and len(m.group(1)) <= start_level:
                return "\n".join(lines[start:i])
    if start is not None:
        return "\n".join(lines[start:])
    return None


def load_exec_context(agent_root: Path, shared_root: Path) -> ExecContext:
    """
    Lightweight context for get_context tool:
    - Shared principles, PII rules, and dimensions
    - Compact table index (names only) from schema.md
    - Agent SKILL.md if present

    Full table schemas → describe_table(table_name)
    Business rules    → get_business_rules()
    """
    sections: list[tuple[str, str]] = []

    for doc in SHARED_DOCS:
        p = shared_root / doc
        if p.exists():
            sections.append((f"shared/{doc}", p.read_text()))

    dims_dir = shared_root / "dimensions"
    if dims_dir.exists():
        for dim in sorted(dims_dir.glob("*.md")):
            sections.append((f"shared/dimensions/{dim.name}", dim.read_text()))

    # Table index — compact list of table names, not full schema
    schema_path = agent_root / "context" / "schema.md"
    allowed_tables: list[str] = []
    if schema_path.exists():
        schema_text = schema_path.read_text()
        allowed_tables = parse_table_index(schema_text)
        if allowed_tables:
            index_lines = [
                "## Tabelas disponíveis",
                "",
                "Use `describe_table(table_name)` para schema completo (colunas, tipos, PII, joins).",
                "Use `get_business_rules()` para regras de negócio e SQL canônico.",
                "",
            ] + [f"- `{t}`" for t in allowed_tables]
            sections.append(("schema/table-index", "\n".join(index_lines)))

    # Agent-specific docs (SKILL.md only; schema.md and business-rules.md are on-demand)
    ctx_dir = agent_root / "context"
    for doc in AGENT_DOCS:
        p = ctx_dir / doc
        if p.exists():
            sections.append((doc, p.read_text()))

    # Skills from repo root .claude/skills/
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
        "Este bloco contém princípios, regras de PII e índice de tabelas. "
        "Para schema completo de uma tabela use describe_table(). "
        "Para regras de negócio use get_business_rules().",
        "",
        "## Seções incluídas",
    ] + [f"- `{name}`" for name, _ in sections]

    parts = ["\n".join(toc_lines)] + [f"<!-- {name} -->\n{body}" for name, body in sections]
    return ExecContext(text="\n\n".join(parts), allowed_tables=allowed_tables)
