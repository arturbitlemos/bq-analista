from pathlib import Path
import pytest
from mcp_core.context_loader import (
    load_exec_context,
    parse_table_index,
    extract_table_section,
)

SAMPLE_SCHEMA = """\
# Schema Reference

## 1. Vendas — `TB_VENDAS`

Full path: `proj.dataset.TB_VENDAS`

| Coluna | Tipo |
|---|---|
| DATA_VENDA | DATE |
| VALOR_PAGO | NUMERIC |

## 2. Produto — dimensão

### 2.1 `PRODUTOS` (master do produto)

Full path: `proj.dataset.PRODUTOS`

| Coluna | Tipo |
|---|---|
| PRODUTO | STRING |

### 2.2 `PRODUTOS_PRECOS` (preços por tabela)

Full path: `proj.dataset.PRODUTOS_PRECOS`

| Coluna | Tipo |
|---|---|
| PRODUTO | STRING |
| PRECO1 | STRING |

## 3. Filiais — `FILIAIS`

Full path: `proj.dataset.FILIAIS`
"""


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
    (ctx / "schema.md").write_text(SAMPLE_SCHEMA)
    (ctx / "business-rules.md").write_text("# Business Rules\n\nRegra 1.")
    return agent


# ── load_exec_context ─────────────────────────────────────────────────────────

def test_loads_shared_docs(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Principles" in result.text
    assert "# PII" in result.text


def test_loads_shared_dimensions(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Produto" in result.text
    assert "# Filiais" in result.text


def test_table_index_present_not_full_schema(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    # Table index (compact list) is present
    assert "`TB_VENDAS`" in result.text
    assert "`PRODUTOS`" in result.text
    # Full schema content is NOT dumped into the blob
    assert "DATA_VENDA" not in result.text
    assert "VALOR_PAGO" not in result.text


def test_business_rules_not_in_context_blob(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Business Rules" not in result.text


def test_principles_appear_before_table_index(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert result.text.index("# Principles") < result.text.index("`TB_VENDAS`")


def test_allowed_tables_populated(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "TB_VENDAS" in result.allowed_tables
    assert "PRODUTOS" in result.allowed_tables
    assert "FILIAIS" in result.allowed_tables


def test_missing_optional_docs_dont_raise(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert result.text  # non-empty


def test_skills_loaded_from_repo_root(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    repo_root = shared.parent.parent
    skill_dir = repo_root / ".claude" / "skills" / "product-photos"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Product Photos Skill")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Product Photos Skill" in result.text


# ── parse_table_index ─────────────────────────────────────────────────────────

def test_parse_table_index_extracts_all_tables():
    tables = parse_table_index(SAMPLE_SCHEMA)
    assert "TB_VENDAS" in tables
    assert "PRODUTOS" in tables
    assert "PRODUTOS_PRECOS" in tables
    assert "FILIAIS" in tables


def test_parse_table_index_no_duplicates():
    tables = parse_table_index(SAMPLE_SCHEMA)
    assert len(tables) == len(set(tables))


def test_parse_table_index_empty_schema():
    assert parse_table_index("# No tables here") == []


# ── extract_table_section ─────────────────────────────────────────────────────

def test_extract_top_level_section():
    section = extract_table_section(SAMPLE_SCHEMA, "TB_VENDAS")
    assert section is not None
    assert "TB_VENDAS" in section
    assert "DATA_VENDA" in section
    assert "VALOR_PAGO" in section
    # Should not bleed into the next section
    assert "PRODUTOS" not in section


def test_extract_nested_section():
    section = extract_table_section(SAMPLE_SCHEMA, "PRODUTOS")
    assert section is not None
    assert "PRODUTOS" in section
    assert "proj.dataset.PRODUTOS" in section
    # Should not include PRODUTOS_PRECOS content
    assert "PRECO1" not in section


def test_extract_last_section_in_file():
    section = extract_table_section(SAMPLE_SCHEMA, "FILIAIS")
    assert section is not None
    assert "FILIAIS" in section


def test_extract_unknown_table_returns_none():
    assert extract_table_section(SAMPLE_SCHEMA, "TABELA_INEXISTENTE") is None


def test_extract_case_insensitive():
    section = extract_table_section(SAMPLE_SCHEMA, "tb_vendas")
    assert section is not None
    assert "TB_VENDAS" in section
