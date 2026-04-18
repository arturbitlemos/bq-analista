import json
from pathlib import Path

import pytest

from mcp_exec.server import listar_analises_impl


def _seed(repo: Path, email: str, items: list[dict]) -> None:
    lib = repo / "library" / f"{email}.json"
    lib.parent.mkdir(parents=True, exist_ok=True)
    lib.write_text(json.dumps(items))


def test_scope_mine_returns_exec_library(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_REPO_ROOT", str(tmp_path))
    _seed(tmp_path, "e@x.com", [{"id": "a", "title": "T", "link": "/x"}])
    out = listar_analises_impl(escopo="mine", exec_email="e@x.com")
    assert out["items"][0]["id"] == "a"


def test_scope_public_returns_public_library(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_REPO_ROOT", str(tmp_path))
    _seed(tmp_path, "public", [{"id": "p", "title": "Pub", "link": "/p"}])
    out = listar_analises_impl(escopo="public", exec_email="e@x.com")
    assert out["items"][0]["id"] == "p"


def test_missing_library_returns_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_REPO_ROOT", str(tmp_path))
    out = listar_analises_impl(escopo="mine", exec_email="nobody@x.com")
    assert out["items"] == []


def test_invalid_escopo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_REPO_ROOT", str(tmp_path))
    out = listar_analises_impl(escopo="everyone", exec_email="e@x.com")
    assert "error" in out
