from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Allowlist:
    path: Path
    _emails: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            raw = os.environ.get("MCP_ALLOWED_EMAILS", "")
            self._emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
            return
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"allowlist JSON is malformed at {self.path}: {e}") from e
        self._emails = {e.lower() for e in data.get("allowed_emails", [])}

    def is_allowed(self, email: str) -> bool:
        return email.lower() in self._emails
