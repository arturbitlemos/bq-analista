from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import jwt
import requests


def mint_installation_token(app_id: str, private_key: str) -> str:
    """Mint a short-lived installation access token for the GitHub App.

    Picks the first Organization installation available."""
    # Normalize PEM: some hosts store newlines as literal '\n'.
    if "\\n" in private_key and "\n" not in private_key:
        private_key = private_key.replace("\\n", "\n")
    private_key = private_key.strip()
    now = int(time.time())
    app_jwt = jwt.encode(
        {"iat": now - 30, "exp": now + 540, "iss": str(app_id)},
        private_key,
        algorithm="RS256",
    )
    resp = requests.get(
        "https://api.github.com/app/installations",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
        },
    )
    if not resp.ok:
        raise RuntimeError(f"github {resp.status_code} on /app/installations: {resp.text[:300]}")
    org = next(
        (i for i in resp.json() if i["account"]["type"] == "Organization"),
        None,
    )
    if not org:
        raise RuntimeError("No organization installation found for GitHub App")
    resp = requests.post(
        f"https://api.github.com/app/installations/{org['id']}/access_tokens",
        headers={"Authorization": f"Bearer {app_jwt}"},
    )
    resp.raise_for_status()
    return resp.json()["token"]


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
        return mint_installation_token(self.github_app_id, self.github_app_private_key)

    def _run(self, *args: str, **kwargs) -> str:
        return subprocess.check_output(
            ["git", "-C", str(self.repo_path), *args],
            stderr=subprocess.STDOUT,
            **kwargs,
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
            if self.github_app_id and self.github_app_private_key:
                token = self._get_github_token()
                # Fetch remote URL and reconstruct with token credentials
                remote_url = self._run("config", "--get", "remote.origin.url").strip()
                # Transform https://github.com/owner/repo → https://x-access-token:TOKEN@github.com/owner/repo
                if remote_url.startswith("https://github.com/"):
                    auth_url = f"https://x-access-token:{token}@github.com/{remote_url.split('github.com/', 1)[1]}"
                    self._run("push", auth_url, f"HEAD:{self.branch}")
                else:
                    # Fallback for SSH or other URL schemes
                    self._run("push", "origin", self.branch)
            else:
                self._run("push", "origin", self.branch)
        return sha
