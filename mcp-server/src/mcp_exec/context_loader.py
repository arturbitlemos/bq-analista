from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DOCS = ["schema.md", "business-rules.md", "SKILL.md"]
ALLOWED_TABLES = ["soma_online_refined.refined_captacao"]


@dataclass
class ExecContext:
    text: str
    allowed_tables: list[str]


def load_exec_context(repo_root: Path) -> ExecContext:
    parts: list[str] = []
    for doc in DOCS:
        p = repo_root / doc
        if not p.exists():
            raise FileNotFoundError(f"required doc missing: {p}")
        parts.append(f"<!-- {doc} -->\n{p.read_text()}")
    return ExecContext(text="\n\n".join(parts), allowed_tables=list(ALLOWED_TABLES))
