"""Clone or sync the monorepo at container startup using GitHub App auth.

Run as: `python -m mcp_core.clone_repo`

Env vars:
  GITHUB_APP_ID            (required)
  GITHUB_APP_PRIVATE_KEY   (required, PEM text)
  GITHUB_REPO              (required, owner/name format)
  MCP_REPO_ROOT            (optional, default /app/repo)
  MCP_GITHUB_BRANCH        (optional, default main)

If the required env vars are not all present, the script exits 0 without
doing anything, so local/dev runs that don't need git push keep working.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from mcp_core.git_ops import mint_installation_token


def main() -> int:
    app_id = os.environ.get("GITHUB_APP_ID")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    repo = os.environ.get("GITHUB_REPO")
    if not (app_id and private_key and repo):
        print("[clone_repo] GITHUB_APP_ID/GITHUB_APP_PRIVATE_KEY/GITHUB_REPO not set; skipping clone")
        return 0

    target = Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))
    branch = os.environ.get("MCP_GITHUB_BRANCH", "main")

    # Normalize PEM: some hosts store newlines as literal '\n'.
    if "\\n" in private_key and "\n" not in private_key:
        private_key = private_key.replace("\\n", "\n")

    try:
        token = mint_installation_token(app_id, private_key)
    except Exception as e:
        print(f"[clone_repo] GitHub App auth failed: {e}. Server will boot but publicar_dashboard won't push.")
        return 0
    auth_url = f"https://x-access-token:{token}@github.com/{repo}.git"

    target.mkdir(parents=True, exist_ok=True)
    if (target / ".git").exists():
        print(f"[clone_repo] syncing {target} from origin/{branch}")
        subprocess.check_call(["git", "-C", str(target), "remote", "set-url", "origin", auth_url])
        subprocess.check_call(["git", "-C", str(target), "fetch", "origin", branch])
        subprocess.check_call(["git", "-C", str(target), "reset", "--hard", f"origin/{branch}"])
    else:
        print(f"[clone_repo] cloning {repo} into {target}")
        subprocess.check_call(["git", "clone", "--branch", branch, auth_url, str(target)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
