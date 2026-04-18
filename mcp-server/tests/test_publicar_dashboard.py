import json
import subprocess
from pathlib import Path

import pytest

from mcp_exec.server import publicar_dashboard_impl


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "seed@x.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "seed"], check=True)
    (tmp_path / "seed.txt").write_text("s")
    subprocess.run(["git", "-C", str(tmp_path), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "seed"], check=True)
    return tmp_path


def test_publishes_and_updates_library(repo: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_REPO_ROOT", str(repo))
    monkeypatch.setenv("MCP_SETTINGS", str(Path(__file__).parent.parent / "config" / "settings.example.toml"))

    out = publicar_dashboard_impl(
        title="Canal × Marca YTD",
        brand="FARM",
        period="YTD 2026",
        description="desc",
        html_content="<html><body>hi</body></html>",
        tags=["ytd", "canal"],
        exec_email="fulano@somagrupo.com.br",
        progress=None,
    )

    assert out["link"].startswith("/analyses/fulano@somagrupo.com.br/")
    assert (repo / "analyses" / "fulano@somagrupo.com.br").exists()
    lib = json.loads((repo / "library" / "fulano@somagrupo.com.br.json").read_text())
    assert lib[0]["title"] == "Canal × Marca YTD"
    log = subprocess.check_output(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"]
    ).decode()
    assert "fulano@somagrupo.com.br" in log


def test_rejects_bad_email(repo: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_REPO_ROOT", str(repo))
    monkeypatch.setenv("MCP_SETTINGS", str(Path(__file__).parent.parent / "config" / "settings.example.toml"))
    out = publicar_dashboard_impl(
        title="x", brand="y", period="z", description="w",
        html_content="<html/>", tags=[],
        exec_email="../../etc/passwd", progress=None,
    )
    assert out["error"].startswith("path_sandbox:")
