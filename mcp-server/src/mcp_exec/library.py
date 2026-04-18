from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class LibraryEntry:
    id: str
    title: str
    brand: str
    date: str
    link: str
    description: str
    tags: list[str]
    filename: str


def prepend_entry(library_path: Path, entry: LibraryEntry) -> None:
    library_path.parent.mkdir(parents=True, exist_ok=True)
    if library_path.exists():
        existing = json.loads(library_path.read_text() or "[]")
        if not isinstance(existing, list):
            raise ValueError(f"library file is not a JSON array: {library_path}")
    else:
        existing = []
    existing.insert(0, asdict(entry))
    library_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
