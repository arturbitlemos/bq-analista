from pathlib import Path
import pytest
from mcp_core.context_loader import load_exec_context


def _make_shared(root: Path) -> Path:
    shared = root / "shared" / "context"
    shared.mkdir(parents=True)
    (shared / "analyst-principles.md").write_text("# Principles")
    (shared / "pii-rules.md").write_text("# PII")
    dims = shared / "dimensions"
    dims.mkdir()
    (dims / "produto.md").write_text("# Produto")
    (dims / "filiais.md").write_text("# Filiais")
    return shared


def _make_agent(root: Path, domain: str) -> Path:
    agent = root / "agents" / domain / "src" / "agent"
    ctx = agent / "context"
    ctx.mkdir(parents=True)
    (ctx / "schema.md").write_text("# Schema vendas-linx")
    (ctx / "business-rules.md").write_text("# Business Rules")
    return agent


def test_loads_shared_and_agent_context(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Principles" in result.text
    assert "# PII" in result.text
    assert "# Schema vendas-linx" in result.text
    assert "# Business Rules" in result.text


def test_loads_shared_dimensions(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Produto" in result.text
    assert "# Filiais" in result.text


def test_shared_appears_before_agent(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert result.text.index("# Principles") < result.text.index("# Schema vendas-linx")


def test_missing_optional_docs_dont_raise(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    # SKILL.md is optional — should not raise if missing
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert result.text  # non-empty


def test_skills_loaded_from_repo_root(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    # Create a skill in the repo root .claude/skills/
    repo_root = shared.parent.parent  # tmp_path
    skill_dir = repo_root / ".claude" / "skills" / "product-photos"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Product Photos Skill")

    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Product Photos Skill" in result.text
