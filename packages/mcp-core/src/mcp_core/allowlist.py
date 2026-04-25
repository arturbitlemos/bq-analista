from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

_RELOAD_TTL_S = 30


@dataclass
class Allowlist:
    path: Path
    _emails: set[str] = field(default_factory=set, init=False)
    _last_reload: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        if not self.path.exists():
            raw = os.environ.get("MCP_ALLOWED_EMAILS", "")
            self._emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
        else:
            try:
                data = json.loads(self.path.read_text())
            except json.JSONDecodeError as e:
                raise ValueError(f"allowlist JSON is malformed at {self.path}: {e}") from e
            self._emails = {e.lower() for e in data.get("allowed_emails", [])}
        self._last_reload = time.monotonic()

    def is_allowed(self, email: str) -> bool:
        if time.monotonic() - self._last_reload > _RELOAD_TTL_S:
            try:
                self.reload()
            except Exception:
                # Reload failure (mid-deploy file write, malformed JSON) must
                # not lock everyone out — keep using the previously cached
                # allowlist and back off so we don't retry every request.
                self._last_reload = time.monotonic()
        return email.lower() in self._emails
