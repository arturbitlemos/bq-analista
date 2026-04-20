from pathlib import Path

from mcp_exec.context_loader import load_exec_context


def test_concatenates_known_docs(tmp_path: Path) -> None:
    (tmp_path / "schema.md").write_text("# Schema\nTable A")
    (tmp_path / "business-rules.md").write_text("# Rules\nRule 1")
    (tmp_path / "SKILL.md").write_text("# Skill\nKPI formula")
    (tmp_path / "identidade-visual-azzas.md").write_text("# Identity")
    (tmp_path / "TEMPLATE.md").write_text("# Template")

    ctx = load_exec_context(repo_root=tmp_path)

    assert "# Schema" in ctx.text
    assert "# Rules" in ctx.text
    assert "# Skill" in ctx.text
    assert any("silver_linx" in t for t in ctx.allowed_tables)


def test_missing_docs_raises(tmp_path: Path) -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        load_exec_context(repo_root=tmp_path)
