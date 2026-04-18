from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitOps:
    repo_path: Path
    author_name: str
    author_email: str
    branch: str = "main"
    push: bool = False  # set True in prod via settings

    def _run(self, *args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.repo_path), *args],
            stderr=subprocess.STDOUT,
        ).decode()

    def commit_paths(self, paths: list[Path], message: str) -> str:
        rel = [str(p.relative_to(self.repo_path)) for p in paths]
        self._run("add", "--", *rel)
        env_args = [
            "-c", f"user.name={self.author_name}",
            "-c", f"user.email={self.author_email}",
            "commit", "-m", message,
        ]
        self._run(*env_args)
        sha = self._run("rev-parse", "HEAD").strip()
        if self.push:
            self._run("push", "origin", self.branch)
        return sha
