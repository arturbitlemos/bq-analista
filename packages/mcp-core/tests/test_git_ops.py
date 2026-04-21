import subprocess
from pathlib import Path

import pytest

from mcp_core.git_ops import GitOps


@pytest.fixture
def empty_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "seed@x.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "seed"], check=True)
    seed = tmp_path / "seed.txt"
    seed.write_text("seed")
    subprocess.run(["git", "-C", str(tmp_path), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "seed"], check=True)
    return tmp_path


def test_commit_author_and_message(empty_repo: Path) -> None:
    (empty_repo / "analyses").mkdir()
    (empty_repo / "analyses" / "a.html").write_text("<html/>")
    git = GitOps(
        repo_path=empty_repo,
        author_name="mcp-exec-bot",
        author_email="mcp@azzas.com.br",
    )
    git.commit_paths(
        paths=[empty_repo / "analyses" / "a.html"],
        message="análise dispatched para exec@x.com",
    )
    log = subprocess.check_output(
        ["git", "-C", str(empty_repo), "log", "-1", "--format=%an|%ae|%s"]
    ).decode().strip()
    assert log == "mcp-exec-bot|mcp@azzas.com.br|análise dispatched para exec@x.com"
