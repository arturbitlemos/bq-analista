from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import jwt
import requests


@dataclass
class GitOps:
    repo_path: Path
    author_name: str
    author_email: str
    branch: str = "main"
    push: bool = False  # set True in prod via settings
    github_app_id: str | None = None
    github_app_private_key: str | None = None

    def _get_github_token(self) -> str | None:
        if not self.github_app_id or not self.github_app_private_key:
            return None
        now = int(time.time())
        payload = {
            "iat": now,
            "exp": now + 600,
            "iss": self.github_app_id,
        }
        app_jwt = jwt.encode(
            payload, self.github_app_private_key, algorithm="RS256"
        )
        resp = requests.post(
            "https://api.github.com/app/installations",
            headers={"Authorization": f"Bearer {app_jwt}"},
        )
        resp.raise_for_status()
        installations = resp.json()
        org_install = next(
            (i for i in installations if i["account"]["type"] == "Organization"),
            None,
        )
        if not org_install:
            raise RuntimeError("No organization installation found for GitHub App")
        install_id = org_install["id"]
        resp = requests.post(
            f"https://api.github.com/app/installations/{install_id}/access_tokens",
            headers={"Authorization": f"Bearer {app_jwt}"},
        )
        resp.raise_for_status()
        return resp.json()["token"]

    def _run(self, *args: str, **kwargs) -> str:
        cmd = ["git", "-C", str(self.repo_path), *args]
        env = os.environ.copy()
        if self.github_app_id and self.github_app_private_key:
            token = self._get_github_token()
            env["GIT_CREDENTIALS"] = f"https://x-access-token:{token}@github.com"
        return subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, env=env, **kwargs
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
