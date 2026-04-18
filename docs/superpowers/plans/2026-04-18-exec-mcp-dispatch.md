# Exec MCP Dispatch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MCP server (Python) that executives query via Claude Team (mobile) to run BigQuery analyses and publish dashboards to the `bq-analista` Vercel portal, gated by Azure AD OAuth + allowlist.

**Architecture:** Python 3.13 MCP server using the official `mcp` Python SDK (FastMCP), running in a Docker container on a Mac mini under `launchd`, exposed via Cloudflare Tunnel. Exposes 4 tools (`get_context`, `consultar_bq`, `listar_analises`, `publicar_dashboard`). Auth: Azure AD auth-code flow via a `mcp-login` CLI, 30-min JWTs with refresh. Writes scoped to `analyses/<exec_email>/` and `library/<exec_email>.json`. Audit to local SQLite.

**Tech Stack:** Python 3.13, `mcp` SDK (FastMCP), `google-cloud-bigquery`, `msal` (Azure AD), `PyGithub` or `GitPython`, `PyJWT`, `pydantic`, `pytest`, Docker, launchd, Cloudflare Tunnel.

**Spec:** `docs/superpowers/specs/2026-04-18-exec-mcp-dispatch-design.md`

**Locked-in decisions (from spec section 8):**

1. **Runtime**: Python 3.13 + official `mcp` SDK (FastMCP). Rationale: `google-cloud-bigquery` is native; `msal` is Microsoft's official Python lib for Azure AD.
2. **Progress streaming**: MCP-native `progressNotification` via `Context.report_progress()` on each tool. No custom SSE.
3. **HTML template**: reuse existing `analyses/artur.lemos@somagrupo.com.br/*.html` as template shape. MCP emits a lean HTML (single file, inline CSS) following the same structure; no exec-specific template system in MVP.
4. **Audit retention**: 90 days local SQLite with cron-triggered cleanup job. SIEM shipping deferred to backlog.
5. **Initial allowlist**: `config/allowed_execs.json` starts with just `artur.lemos@somagrupo.com.br` for dogfooding. Real execs added via PR on rollout day.

**Phase breakdown:**

- Phase 0 — Scaffolding + test harness
- Phase 1 — `get_context` tool (simplest, proves scaffolding works)
- Phase 2 — `consultar_bq` tool + SQL validator
- Phase 3 — `publicar_dashboard` tool + git integration
- Phase 4 — `listar_analises` tool
- Phase 5 — Auth layer (Azure AD + allowlist + `mcp-login` CLI)
- Phase 6 — Audit log + anomaly alerts
- Phase 7 — Infrastructure (Dockerfile + launchd + Cloudflare Tunnel)
- Phase 8 — Production verification + Claude Team connector registration

Each phase ends in a commit and is independently useful. Integration deploy only happens after Phase 7.

---

## Phase 0: Scaffolding + test harness

### Task 0.1: Create `mcp-server` subdirectory and Python project

**Files:**
- Create: `mcp-server/pyproject.toml`
- Create: `mcp-server/.python-version`
- Create: `mcp-server/src/mcp_exec/__init__.py`
- Create: `mcp-server/tests/__init__.py`
- Create: `mcp-server/README.md`

- [ ] **Step 1: Create directory structure**

Run from repo root:
```bash
mkdir -p mcp-server/src/mcp_exec mcp-server/tests mcp-server/config
touch mcp-server/src/mcp_exec/__init__.py mcp-server/tests/__init__.py
```

- [ ] **Step 2: Write pyproject.toml**

Create `mcp-server/pyproject.toml`:
```toml
[project]
name = "mcp-exec"
version = "0.1.0"
description = "MCP server for executive BigQuery dispatch at Azzas"
requires-python = ">=3.13"
dependencies = [
  "mcp>=1.2.0",
  "google-cloud-bigquery>=3.25",
  "google-auth>=2.34",
  "msal>=1.31",
  "PyJWT[crypto]>=2.9",
  "GitPython>=3.1",
  "pydantic>=2.9",
  "sqlalchemy>=2.0",
  "httpx>=0.27",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-mock>=3.14",
  "ruff>=0.6",
]

[project.scripts]
mcp-exec-server = "mcp_exec.server:main"
mcp-login = "mcp_exec.cli_login:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Write `.python-version`**

```
3.13
```

- [ ] **Step 4: Write minimal README for the subproject**

Create `mcp-server/README.md`:
```markdown
# mcp-exec

Python MCP server that lets Azzas executives run BigQuery analyses and publish dashboards via Claude Team on mobile.

See `docs/superpowers/specs/2026-04-18-exec-mcp-dispatch-design.md` for the full architecture.

## Dev

```bash
cd mcp-server
uv sync --all-extras
uv run pytest
```
```

- [ ] **Step 5: Install deps and verify empty test suite runs**

```bash
cd mcp-server && uv sync --all-extras && uv run pytest -v
```
Expected: `no tests ran in 0.XXs` — no errors.

- [ ] **Step 6: Commit**

```bash
git add mcp-server/
git commit -m "feat(mcp): scaffold Python project structure for exec dispatch server"
```

---

### Task 0.2: Add `.gitignore` entries + config placeholder

**Files:**
- Modify: `mcp-server/.gitignore` (create)
- Create: `mcp-server/config/allowed_execs.example.json`
- Create: `mcp-server/config/settings.example.toml`

- [ ] **Step 1: Write `mcp-server/.gitignore`**

```
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/

# Local secrets & state
config/allowed_execs.json
config/settings.toml
.env
.env.local
audit.db
audit.db-journal
```

- [ ] **Step 2: Write `config/allowed_execs.example.json`**

```json
{
  "allowed_emails": [
    "artur.lemos@somagrupo.com.br"
  ],
  "notes": "Copy to allowed_execs.json and edit. Emails must match Azure AD upn exactly."
}
```

- [ ] **Step 3: Write `config/settings.example.toml`**

```toml
[server]
host = "0.0.0.0"
port = 3000

[bigquery]
project_id = "soma-online-refined"
max_bytes_billed = 5000000000  # 5GB
query_timeout_s = 60
max_rows = 100000
allowed_datasets = ["soma_online_refined"]

[github]
repo_path = "/app/repo"
branch = "main"
author_name = "mcp-exec-bot"
author_email = "mcp@azzas.com.br"

[auth]
jwt_issuer = "mcp-exec-azzas"
access_token_ttl_s = 1800   # 30 min
refresh_token_ttl_s = 2592000  # 30 days

[audit]
db_path = "/var/mcp/audit.db"
retention_days = 90
```

- [ ] **Step 4: Commit**

```bash
git add mcp-server/.gitignore mcp-server/config/
git commit -m "chore(mcp): ignore local secrets/state, add example config files"
```

---

### Task 0.3: Settings loader with pydantic

**Files:**
- Create: `mcp-server/src/mcp_exec/settings.py`
- Create: `mcp-server/tests/test_settings.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_settings.py`:
```python
from pathlib import Path

import pytest

from mcp_exec.settings import Settings, load_settings


def test_loads_example_settings(tmp_path: Path) -> None:
    toml = tmp_path / "settings.toml"
    toml.write_text(
        '[server]\nhost="0.0.0.0"\nport=3000\n'
        '[bigquery]\nproject_id="p"\nmax_bytes_billed=5000000000\n'
        'query_timeout_s=60\nmax_rows=100000\nallowed_datasets=["d"]\n'
        '[github]\nrepo_path="/r"\nbranch="main"\n'
        'author_name="bot"\nauthor_email="bot@x.com"\n'
        '[auth]\njwt_issuer="iss"\naccess_token_ttl_s=1800\nrefresh_token_ttl_s=2592000\n'
        '[audit]\ndb_path="/var/x.db"\nretention_days=90\n'
    )
    s = load_settings(toml)
    assert isinstance(s, Settings)
    assert s.server.port == 3000
    assert s.bigquery.max_bytes_billed == 5_000_000_000
    assert s.audit.retention_days == 90


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_settings(tmp_path / "missing.toml")
```

- [ ] **Step 2: Run to see it fail**

```bash
cd mcp-server && uv run pytest tests/test_settings.py -v
```
Expected: ImportError (`mcp_exec.settings` doesn't exist).

- [ ] **Step 3: Implement settings loader**

Create `mcp-server/src/mcp_exec/settings.py`:
```python
from __future__ import annotations

import tomllib
from pathlib import Path
from pydantic import BaseModel, Field


class ServerSettings(BaseModel):
    host: str
    port: int


class BigQuerySettings(BaseModel):
    project_id: str
    max_bytes_billed: int
    query_timeout_s: int
    max_rows: int
    allowed_datasets: list[str]


class GithubSettings(BaseModel):
    repo_path: str
    branch: str = "main"
    author_name: str
    author_email: str


class AuthSettings(BaseModel):
    jwt_issuer: str
    access_token_ttl_s: int
    refresh_token_ttl_s: int


class AuditSettings(BaseModel):
    db_path: str
    retention_days: int = 90


class Settings(BaseModel):
    server: ServerSettings
    bigquery: BigQuerySettings
    github: GithubSettings
    auth: AuthSettings
    audit: AuditSettings


def load_settings(path: Path) -> Settings:
    if not path.exists():
        raise FileNotFoundError(f"settings file not found: {path}")
    data = tomllib.loads(path.read_text())
    return Settings.model_validate(data)
```

- [ ] **Step 4: Run tests pass**

```bash
cd mcp-server && uv run pytest tests/test_settings.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/mcp_exec/settings.py mcp-server/tests/test_settings.py
git commit -m "feat(mcp): typed settings loader (server/bq/github/auth/audit)"
```

---

## Phase 1: `get_context` tool

Goal: prove the FastMCP scaffold works by exposing a simple read-only tool that returns repo docs.

### Task 1.1: Bootstrap FastMCP server with `get_context`

**Files:**
- Create: `mcp-server/src/mcp_exec/server.py`
- Create: `mcp-server/src/mcp_exec/context_loader.py`
- Create: `mcp-server/tests/test_context_loader.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_context_loader.py`:
```python
from pathlib import Path

from mcp_exec.context_loader import load_exec_context


def test_concatenates_known_docs(tmp_path: Path) -> None:
    (tmp_path / "schema.md").write_text("# Schema\nTable A")
    (tmp_path / "business-rules.md").write_text("# Rules\nRule 1")
    (tmp_path / "SKILL.md").write_text("# Skill\nKPI formula")

    ctx = load_exec_context(repo_root=tmp_path)

    assert "# Schema" in ctx.text
    assert "# Rules" in ctx.text
    assert "# Skill" in ctx.text
    assert ctx.allowed_tables == ["soma_online_refined.refined_captacao"]


def test_missing_docs_raises(tmp_path: Path) -> None:
    import pytest
    with pytest.raises(FileNotFoundError):
        load_exec_context(repo_root=tmp_path)
```

- [ ] **Step 2: Run test, see it fail**

```bash
cd mcp-server && uv run pytest tests/test_context_loader.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement context_loader**

Create `mcp-server/src/mcp_exec/context_loader.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DOCS = ["schema.md", "business-rules.md", "SKILL.md"]
ALLOWED_TABLES = ["soma_online_refined.refined_captacao"]


@dataclass
class ExecContext:
    text: str
    allowed_tables: list[str]


def load_exec_context(repo_root: Path) -> ExecContext:
    parts: list[str] = []
    for doc in DOCS:
        p = repo_root / doc
        if not p.exists():
            raise FileNotFoundError(f"required doc missing: {p}")
        parts.append(f"<!-- {doc} -->\n{p.read_text()}")
    return ExecContext(text="\n\n".join(parts), allowed_tables=list(ALLOWED_TABLES))
```

- [ ] **Step 4: Run tests pass**

```bash
cd mcp-server && uv run pytest tests/test_context_loader.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Wire into FastMCP server**

Create `mcp-server/src/mcp_exec/server.py`:
```python
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_exec.context_loader import load_exec_context
from mcp_exec.settings import load_settings

mcp = FastMCP("mcp-exec-azzas")


def _repo_root() -> Path:
    # Repo is mounted into container at /app/repo in prod; dev uses MCP_REPO_ROOT env.
    return Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))


@mcp.tool()
def get_context() -> dict:
    """Return concatenated docs (schema.md, business-rules.md, SKILL.md) plus allowed tables.

    Call once at session start to prime Claude with the analytics context.
    """
    ctx = load_exec_context(_repo_root())
    return {"text": ctx.text, "allowed_tables": ctx.allowed_tables}


def main() -> None:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    # Load once to fail fast if settings are bad; server doesn't use them yet.
    load_settings(settings_path)
    mcp.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Smoke-test the server locally**

```bash
cd mcp-server && MCP_REPO_ROOT=$(pwd)/.. MCP_SETTINGS=$(pwd)/config/settings.example.toml \
  uv run python -c "from mcp_exec.server import get_context; print(get_context()['allowed_tables'])"
```
Expected: `['soma_online_refined.refined_captacao']`

- [ ] **Step 7: Commit**

```bash
git add mcp-server/src/mcp_exec/server.py mcp-server/src/mcp_exec/context_loader.py mcp-server/tests/test_context_loader.py
git commit -m "feat(mcp): FastMCP scaffold + get_context tool"
```

---

## Phase 2: `consultar_bq` tool + SQL validator

### Task 2.1: SQL validator (reject non-SELECT)

**Files:**
- Create: `mcp-server/src/mcp_exec/sql_validator.py`
- Create: `mcp-server/tests/test_sql_validator.py`

- [ ] **Step 1: Write the failing tests**

Create `mcp-server/tests/test_sql_validator.py`:
```python
import pytest

from mcp_exec.sql_validator import SqlValidationError, validate_readonly_sql


def test_accepts_select() -> None:
    validate_readonly_sql("SELECT 1")
    validate_readonly_sql("SELECT * FROM `p.d.t` WHERE x = 1")


def test_accepts_with_cte() -> None:
    validate_readonly_sql("WITH a AS (SELECT 1) SELECT * FROM a")


def test_rejects_ddl() -> None:
    for s in [
        "CREATE TABLE x AS SELECT 1",
        "DROP TABLE x",
        "ALTER TABLE x ADD COLUMN y INT64",
        "TRUNCATE TABLE x",
    ]:
        with pytest.raises(SqlValidationError):
            validate_readonly_sql(s)


def test_rejects_dml() -> None:
    for s in [
        "INSERT INTO x VALUES (1)",
        "UPDATE x SET y = 1",
        "DELETE FROM x",
        "MERGE INTO x ...",
    ]:
        with pytest.raises(SqlValidationError):
            validate_readonly_sql(s)


def test_rejects_multi_statement() -> None:
    with pytest.raises(SqlValidationError):
        validate_readonly_sql("SELECT 1; SELECT 2")


def test_rejects_scripting() -> None:
    for s in ["DECLARE x INT64 DEFAULT 0; SELECT x", "BEGIN SELECT 1; END"]:
        with pytest.raises(SqlValidationError):
            validate_readonly_sql(s)


def test_strips_comments_before_check() -> None:
    validate_readonly_sql("-- a comment\nSELECT 1")
    validate_readonly_sql("/* block */ SELECT 1")
```

- [ ] **Step 2: Run tests, see them fail**

```bash
cd mcp-server && uv run pytest tests/test_sql_validator.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement validator**

Create `mcp-server/src/mcp_exec/sql_validator.py`:
```python
from __future__ import annotations

import re


class SqlValidationError(ValueError):
    pass


_BANNED_STARTS = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP",
    "ALTER", "TRUNCATE", "GRANT", "REVOKE", "CALL", "BEGIN",
    "DECLARE", "SET", "EXECUTE", "EXPORT",
)
_ALLOWED_STARTS = ("SELECT", "WITH")


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql.strip()


def validate_readonly_sql(sql: str) -> None:
    """Allow only SELECT / WITH single-statement queries. Raise on anything else."""
    cleaned = _strip_comments(sql).rstrip(";").strip()
    if not cleaned:
        raise SqlValidationError("empty SQL")
    if ";" in cleaned:
        raise SqlValidationError("multi-statement SQL not allowed")
    head = cleaned.split(None, 1)[0].upper()
    if head in _BANNED_STARTS:
        raise SqlValidationError(f"statement type not allowed: {head}")
    if head not in _ALLOWED_STARTS:
        raise SqlValidationError(f"only SELECT/WITH allowed, got: {head}")
```

- [ ] **Step 4: Run tests pass**

```bash
cd mcp-server && uv run pytest tests/test_sql_validator.py -v
```
Expected: all tests green.

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/mcp_exec/sql_validator.py mcp-server/tests/test_sql_validator.py
git commit -m "feat(mcp): SQL validator restricts tools to SELECT/WITH single statement"
```

---

### Task 2.2: BigQuery client wrapper with labels + limits

**Files:**
- Create: `mcp-server/src/mcp_exec/bq_client.py`
- Create: `mcp-server/tests/test_bq_client.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_bq_client.py`:
```python
from unittest.mock import MagicMock

from mcp_exec.bq_client import BqClient
from mcp_exec.settings import BigQuerySettings


def _settings() -> BigQuerySettings:
    return BigQuerySettings(
        project_id="test-project",
        max_bytes_billed=5_000_000_000,
        query_timeout_s=60,
        max_rows=100_000,
        allowed_datasets=["soma_online_refined"],
    )


def test_run_query_applies_labels_and_limits() -> None:
    fake_bq = MagicMock()
    fake_job = MagicMock()
    fake_job.total_bytes_billed = 1234
    fake_job.total_bytes_processed = 5678
    fake_job.result.return_value = iter([{"col": 1}, {"col": 2}])
    fake_bq.query.return_value = fake_job

    client = BqClient(settings=_settings(), bq=fake_bq)
    result = client.run_query(
        sql="SELECT 1 AS col",
        exec_email="exec@azzas.com.br",
    )

    assert result.row_count == 2
    assert result.bytes_billed == 1234
    # job_config passed with label + limit
    job_config = fake_bq.query.call_args.kwargs["job_config"]
    assert job_config.maximum_bytes_billed == 5_000_000_000
    assert job_config.labels == {
        "exec_email": "exec_azzas_com_br",
        "source": "mcp_dispatch",
    }
    assert job_config.dry_run is False


def test_run_query_truncates_rows_at_max() -> None:
    fake_bq = MagicMock()
    fake_job = MagicMock()
    fake_job.total_bytes_billed = 0
    fake_job.total_bytes_processed = 0
    fake_job.result.return_value = iter([{"i": i} for i in range(5)])
    fake_bq.query.return_value = fake_job

    s = _settings()
    s = s.model_copy(update={"max_rows": 3})
    client = BqClient(settings=s, bq=fake_bq)
    result = client.run_query("SELECT 1", exec_email="e@x.com")
    assert len(result.rows) == 3
    assert result.truncated is True
```

- [ ] **Step 2: Run test, see it fail**

```bash
cd mcp-server && uv run pytest tests/test_bq_client.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement BqClient**

Create `mcp-server/src/mcp_exec/bq_client.py`:
```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from google.cloud import bigquery

from mcp_exec.settings import BigQuerySettings


def _label_sanitize(email: str) -> str:
    # GCP labels: lowercase letters, numbers, dashes, underscores; max 63 chars.
    return re.sub(r"[^a-z0-9_-]", "_", email.lower())[:63]


class _BqLike(Protocol):
    def query(self, sql: str, job_config: Any) -> Any: ...


@dataclass
class QueryResult:
    rows: list[dict]
    row_count: int
    bytes_billed: int
    bytes_processed: int
    truncated: bool = False


@dataclass
class BqClient:
    settings: BigQuerySettings
    bq: _BqLike = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.bq is None:
            self.bq = bigquery.Client(project=self.settings.project_id)

    def run_query(self, sql: str, exec_email: str) -> QueryResult:
        cfg = bigquery.QueryJobConfig(
            dry_run=False,
            use_query_cache=True,
            maximum_bytes_billed=self.settings.max_bytes_billed,
            labels={
                "exec_email": _label_sanitize(exec_email),
                "source": "mcp_dispatch",
            },
        )
        job = self.bq.query(sql, job_config=cfg)
        rows: list[dict] = []
        truncated = False
        for i, row in enumerate(job.result(timeout=self.settings.query_timeout_s)):
            if i >= self.settings.max_rows:
                truncated = True
                break
            rows.append(dict(row))
        return QueryResult(
            rows=rows,
            row_count=len(rows),
            bytes_billed=job.total_bytes_billed or 0,
            bytes_processed=job.total_bytes_processed or 0,
            truncated=truncated,
        )
```

- [ ] **Step 4: Run tests pass**

```bash
cd mcp-server && uv run pytest tests/test_bq_client.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/mcp_exec/bq_client.py mcp-server/tests/test_bq_client.py
git commit -m "feat(mcp): BigQuery client wrapper with exec_email labels and limits"
```

---

### Task 2.3: Wire `consultar_bq` tool with progress reporting

**Files:**
- Modify: `mcp-server/src/mcp_exec/server.py`
- Create: `mcp-server/tests/test_consultar_bq.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_consultar_bq.py`:
```python
from unittest.mock import MagicMock, patch

from mcp_exec.server import consultar_bq_impl
from mcp_exec.bq_client import QueryResult


@patch("mcp_exec.server._build_bq_client")
def test_rejects_non_select(build_mock) -> None:
    build_mock.return_value = MagicMock()
    result = consultar_bq_impl(sql="DELETE FROM x", exec_email="e@x.com", progress=None)
    assert result["error"].startswith("sql_validation:")


@patch("mcp_exec.server._build_bq_client")
def test_happy_path_returns_rows(build_mock) -> None:
    fake = MagicMock()
    fake.run_query.return_value = QueryResult(
        rows=[{"col": 1}], row_count=1, bytes_billed=10, bytes_processed=20
    )
    build_mock.return_value = fake

    out = consultar_bq_impl(sql="SELECT 1 AS col", exec_email="e@x.com", progress=None)
    assert out["row_count"] == 1
    assert out["rows"] == [{"col": 1}]
    assert out["bytes_billed"] == 10


@patch("mcp_exec.server._build_bq_client")
def test_progress_callback_invoked(build_mock) -> None:
    fake = MagicMock()
    fake.run_query.return_value = QueryResult(rows=[], row_count=0, bytes_billed=0, bytes_processed=0)
    build_mock.return_value = fake

    calls: list[str] = []
    consultar_bq_impl(sql="SELECT 1", exec_email="e@x.com", progress=calls.append)
    assert any("querying BigQuery" in c for c in calls)
```

- [ ] **Step 2: Extend server.py with the tool**

Modify `mcp-server/src/mcp_exec/server.py`, add below `get_context`:
```python
from typing import Callable, Optional

from mcp_exec.bq_client import BqClient
from mcp_exec.sql_validator import SqlValidationError, validate_readonly_sql


def _build_bq_client() -> BqClient:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    settings = load_settings(settings_path)
    return BqClient(settings=settings.bigquery)


def consultar_bq_impl(
    sql: str,
    exec_email: str,
    progress: Optional[Callable[[str], None]],
) -> dict:
    try:
        validate_readonly_sql(sql)
    except SqlValidationError as e:
        return {"error": f"sql_validation: {e}"}

    client = _build_bq_client()
    if progress:
        progress("querying BigQuery...")
    try:
        result = client.run_query(sql=sql, exec_email=exec_email)
    except Exception as e:  # noqa: BLE001
        return {"error": f"bq_execution: {e}"}
    return {
        "rows": result.rows,
        "row_count": result.row_count,
        "bytes_billed": result.bytes_billed,
        "bytes_processed": result.bytes_processed,
        "truncated": result.truncated,
    }


@mcp.tool()
async def consultar_bq(sql: str, ctx) -> dict:
    """Run a SELECT query against BigQuery.

    Only SELECT / WITH single-statement SQL is accepted.
    Returns rows (capped) plus bytes_billed / bytes_processed.
    """
    exec_email = _current_exec_email(ctx)

    def report(msg: str) -> None:
        # FastMCP Context.report_progress accepts an int; we also log the message.
        ctx.info(msg)

    return consultar_bq_impl(sql=sql, exec_email=exec_email, progress=report)


def _current_exec_email(ctx) -> str:
    # Stub until Phase 5 wires real Azure AD auth. Always returns the test exec.
    return os.environ.get("MCP_DEV_EXEC_EMAIL", "artur.lemos@somagrupo.com.br")
```

- [ ] **Step 3: Run tests pass**

```bash
cd mcp-server && uv run pytest tests/test_consultar_bq.py -v
```
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add mcp-server/src/mcp_exec/server.py mcp-server/tests/test_consultar_bq.py
git commit -m "feat(mcp): expose consultar_bq tool with SQL validation + progress reporting"
```

---

## Phase 3: `publicar_dashboard` tool + git integration

### Task 3.1: Path sandbox (reject writes outside exec scope)

**Files:**
- Create: `mcp-server/src/mcp_exec/sandbox.py`
- Create: `mcp-server/tests/test_sandbox.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_sandbox.py`:
```python
from pathlib import Path

import pytest

from mcp_exec.sandbox import PathSandboxError, exec_analysis_path, exec_library_path


def test_analysis_path_is_under_exec_dir(tmp_path: Path) -> None:
    p = exec_analysis_path(repo_root=tmp_path, exec_email="fulano@x.com", filename="foo.html")
    expected = tmp_path / "analyses" / "fulano@x.com" / "foo.html"
    assert p == expected


def test_rejects_traversal(tmp_path: Path) -> None:
    for bad in ["../foo.html", "foo/../../bar.html", "/etc/passwd"]:
        with pytest.raises(PathSandboxError):
            exec_analysis_path(repo_root=tmp_path, exec_email="fulano@x.com", filename=bad)


def test_rejects_non_html(tmp_path: Path) -> None:
    with pytest.raises(PathSandboxError):
        exec_analysis_path(repo_root=tmp_path, exec_email="fulano@x.com", filename="foo.sh")


def test_library_path(tmp_path: Path) -> None:
    p = exec_library_path(repo_root=tmp_path, exec_email="fulano@x.com")
    assert p == tmp_path / "library" / "fulano@x.com.json"


def test_library_rejects_weird_email(tmp_path: Path) -> None:
    for bad in ["../x", "x/y", "x\n"]:
        with pytest.raises(PathSandboxError):
            exec_library_path(repo_root=tmp_path, exec_email=bad)
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_sandbox.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement sandbox**

Create `mcp-server/src/mcp_exec/sandbox.py`:
```python
from __future__ import annotations

import re
from pathlib import Path

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class PathSandboxError(ValueError):
    pass


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.fullmatch(email):
        raise PathSandboxError(f"invalid exec_email: {email!r}")


def _ensure_inside(base: Path, target: Path) -> None:
    base_abs = base.resolve()
    target_abs = target.resolve()
    try:
        target_abs.relative_to(base_abs)
    except ValueError as e:
        raise PathSandboxError(f"path escapes sandbox: {target}") from e


def exec_analysis_path(repo_root: Path, exec_email: str, filename: str) -> Path:
    _validate_email(exec_email)
    if not filename.endswith(".html"):
        raise PathSandboxError("only .html files allowed in analyses/")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise PathSandboxError(f"invalid filename: {filename!r}")
    base = repo_root / "analyses" / exec_email
    target = base / filename
    _ensure_inside(base, target)
    return target


def exec_library_path(repo_root: Path, exec_email: str) -> Path:
    _validate_email(exec_email)
    base = repo_root / "library"
    target = base / f"{exec_email}.json"
    _ensure_inside(base, target)
    return target
```

- [ ] **Step 4: Tests pass**

```bash
cd mcp-server && uv run pytest tests/test_sandbox.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/mcp_exec/sandbox.py mcp-server/tests/test_sandbox.py
git commit -m "feat(mcp): path sandbox rejects traversal + non-html writes"
```

---

### Task 3.2: Library JSON updater

**Files:**
- Create: `mcp-server/src/mcp_exec/library.py`
- Create: `mcp-server/tests/test_library.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_library.py`:
```python
import json
from pathlib import Path

from mcp_exec.library import LibraryEntry, prepend_entry


def test_creates_library_json_if_missing(tmp_path: Path) -> None:
    lib = tmp_path / "lib.json"
    entry = LibraryEntry(
        id="abc", title="T", brand="FARM", date="2026-04-18",
        link="/analyses/x@y.com/abc.html", description="d", tags=["ytd"],
        filename="abc.html",
    )
    prepend_entry(lib, entry)
    saved = json.loads(lib.read_text())
    assert saved[0]["id"] == "abc"
    assert saved[0]["link"].startswith("/analyses/")


def test_prepends_to_existing_list(tmp_path: Path) -> None:
    lib = tmp_path / "lib.json"
    lib.write_text(json.dumps([{"id": "old"}]))
    entry = LibraryEntry(
        id="new", title="T", brand="B", date="2026-04-18",
        link="/x", description="d", tags=[], filename="new.html",
    )
    prepend_entry(lib, entry)
    saved = json.loads(lib.read_text())
    assert [s["id"] for s in saved] == ["new", "old"]
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_library.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement library updater**

Create `mcp-server/src/mcp_exec/library.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class LibraryEntry:
    id: str
    title: str
    brand: str
    date: str
    link: str
    description: str
    tags: list[str]
    filename: str


def prepend_entry(library_path: Path, entry: LibraryEntry) -> None:
    library_path.parent.mkdir(parents=True, exist_ok=True)
    if library_path.exists():
        existing = json.loads(library_path.read_text() or "[]")
        if not isinstance(existing, list):
            raise ValueError(f"library file is not a JSON array: {library_path}")
    else:
        existing = []
    existing.insert(0, asdict(entry))
    library_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Tests pass**

```bash
cd mcp-server && uv run pytest tests/test_library.py -v
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/mcp_exec/library.py mcp-server/tests/test_library.py
git commit -m "feat(mcp): library.json prepend helper"
```

---

### Task 3.3: Git wrapper (add/commit/push)

**Files:**
- Create: `mcp-server/src/mcp_exec/git_ops.py`
- Create: `mcp-server/tests/test_git_ops.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_git_ops.py`:
```python
import subprocess
from pathlib import Path

import pytest

from mcp_exec.git_ops import GitOps


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
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_git_ops.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement GitOps**

Create `mcp-server/src/mcp_exec/git_ops.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess


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
```

- [ ] **Step 4: Tests pass**

```bash
cd mcp-server && uv run pytest tests/test_git_ops.py -v
```
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add mcp-server/src/mcp_exec/git_ops.py mcp-server/tests/test_git_ops.py
git commit -m "feat(mcp): git ops wrapper with pinned author/email"
```

---

### Task 3.4: Wire `publicar_dashboard` tool

**Files:**
- Modify: `mcp-server/src/mcp_exec/server.py`
- Create: `mcp-server/tests/test_publicar_dashboard.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_publicar_dashboard.py`:
```python
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
    # committed
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
```

- [ ] **Step 2: Extend server.py**

Add to `mcp-server/src/mcp_exec/server.py`:
```python
import hashlib
from datetime import datetime, timezone

from mcp_exec.git_ops import GitOps
from mcp_exec.library import LibraryEntry, prepend_entry
from mcp_exec.sandbox import PathSandboxError, exec_analysis_path, exec_library_path


def _slugify(title: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "analise"


def publicar_dashboard_impl(
    *,
    title: str,
    brand: str,
    period: str,
    description: str,
    html_content: str,
    tags: list[str],
    exec_email: str,
    progress,
) -> dict:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    settings = load_settings(settings_path)
    repo_root = _repo_root()

    today = datetime.now(timezone.utc).date().isoformat()
    short_hash = hashlib.sha1(
        f"{exec_email}{title}{datetime.now(timezone.utc).isoformat()}".encode()
    ).hexdigest()[:8]
    slug = _slugify(title)
    filename = f"{slug}-{today}-{short_hash}.html"

    try:
        analysis_path = exec_analysis_path(repo_root, exec_email, filename)
        library_path = exec_library_path(repo_root, exec_email)
    except PathSandboxError as e:
        return {"error": f"path_sandbox: {e}"}

    if progress:
        progress("rendering dashboard...")
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.write_text(html_content)

    entry_id = f"{slug}-{short_hash}"
    link = f"/analyses/{exec_email}/{filename}"
    prepend_entry(
        library_path,
        LibraryEntry(
            id=entry_id, title=title, brand=brand, date=today,
            link=link, description=description, tags=tags, filename=filename,
        ),
    )

    if progress:
        progress("publishing to Vercel...")
    git = GitOps(
        repo_path=repo_root,
        author_name=settings.github.author_name,
        author_email=settings.github.author_email,
        branch=settings.github.branch,
        push=os.environ.get("MCP_GIT_PUSH", "0") == "1",
    )
    sha = git.commit_paths(
        paths=[analysis_path, library_path],
        message=f"análise dispatched para {exec_email}: {title}",
    )
    return {
        "id": entry_id,
        "link": link,
        "published_at": today,
        "commit_sha": sha,
    }


@mcp.tool()
async def publicar_dashboard(
    title: str,
    brand: str,
    period: str,
    description: str,
    html_content: str,
    tags: list[str],
    ctx,
) -> dict:
    """Publish an HTML dashboard to the exec's analysis sandbox + update library."""
    return publicar_dashboard_impl(
        title=title, brand=brand, period=period, description=description,
        html_content=html_content, tags=tags,
        exec_email=_current_exec_email(ctx),
        progress=lambda m: ctx.info(m),
    )
```

- [ ] **Step 3: Tests pass**

```bash
cd mcp-server && uv run pytest tests/test_publicar_dashboard.py -v
```
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add mcp-server/src/mcp_exec/server.py mcp-server/tests/test_publicar_dashboard.py
git commit -m "feat(mcp): publicar_dashboard writes sandbox + library + git commit"
```

---

## Phase 4: `listar_analises` tool

### Task 4.1: Implement listar_analises

**Files:**
- Modify: `mcp-server/src/mcp_exec/server.py`
- Create: `mcp-server/tests/test_listar_analises.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_listar_analises.py`:
```python
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
```

- [ ] **Step 2: Extend server.py**

Add to `mcp-server/src/mcp_exec/server.py`:
```python
import json


def listar_analises_impl(escopo: str, exec_email: str) -> dict:
    if escopo not in {"mine", "public"}:
        return {"error": "escopo must be 'mine' or 'public'"}
    repo_root = _repo_root()
    email_key = exec_email if escopo == "mine" else "public"
    lib = repo_root / "library" / f"{email_key}.json"
    if not lib.exists():
        return {"items": []}
    data = json.loads(lib.read_text() or "[]")
    return {"items": data}


@mcp.tool()
async def listar_analises(escopo: str, ctx) -> dict:
    """List analyses. escopo: 'mine' (own sandbox) or 'public' (shared library)."""
    return listar_analises_impl(escopo=escopo, exec_email=_current_exec_email(ctx))
```

- [ ] **Step 3: Tests pass**

```bash
cd mcp-server && uv run pytest tests/test_listar_analises.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add mcp-server/src/mcp_exec/server.py mcp-server/tests/test_listar_analises.py
git commit -m "feat(mcp): listar_analises tool for mine/public scope"
```

---

## Phase 5: Azure AD auth layer + `mcp-login` CLI + allowlist

### Task 5.1: Allowlist loader

**Files:**
- Create: `mcp-server/src/mcp_exec/allowlist.py`
- Create: `mcp-server/tests/test_allowlist.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_allowlist.py`:
```python
from pathlib import Path

from mcp_exec.allowlist import Allowlist


def test_email_in_list(tmp_path: Path) -> None:
    f = tmp_path / "a.json"
    f.write_text('{"allowed_emails": ["a@x.com", "B@X.COM"]}')
    al = Allowlist(path=f)
    assert al.is_allowed("a@x.com")
    assert al.is_allowed("A@X.com")  # case-insensitive
    assert al.is_allowed("b@x.com")
    assert not al.is_allowed("c@x.com")


def test_reload_picks_up_new_emails(tmp_path: Path) -> None:
    f = tmp_path / "a.json"
    f.write_text('{"allowed_emails": ["a@x.com"]}')
    al = Allowlist(path=f)
    assert not al.is_allowed("b@x.com")
    f.write_text('{"allowed_emails": ["a@x.com", "b@x.com"]}')
    al.reload()
    assert al.is_allowed("b@x.com")
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_allowlist.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement allowlist**

Create `mcp-server/src/mcp_exec/allowlist.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Allowlist:
    path: Path
    _emails: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        data = json.loads(self.path.read_text())
        self._emails = {e.lower() for e in data.get("allowed_emails", [])}

    def is_allowed(self, email: str) -> bool:
        return email.lower() in self._emails
```

- [ ] **Step 4: Tests pass + commit**

```bash
cd mcp-server && uv run pytest tests/test_allowlist.py -v
git add mcp-server/src/mcp_exec/allowlist.py mcp-server/tests/test_allowlist.py
git commit -m "feat(mcp): allowlist loader (reloadable, case-insensitive)"
```

---

### Task 5.2: Azure AD token exchange helper

**Files:**
- Create: `mcp-server/src/mcp_exec/azure_auth.py`
- Create: `mcp-server/tests/test_azure_auth.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_azure_auth.py`:
```python
from unittest.mock import MagicMock, patch

import pytest

from mcp_exec.azure_auth import AzureAuthError, AzureAuth


def _cfg() -> dict:
    return {"tenant_id": "t", "client_id": "c", "client_secret": "s", "redirect_uri": "http://localhost:8765"}


def test_exchange_code_extracts_email() -> None:
    fake_msal = MagicMock()
    fake_msal.acquire_token_by_authorization_code.return_value = {
        "access_token": "aad_tok",
        "id_token_claims": {"preferred_username": "e@x.com", "upn": "e@x.com"},
        "expires_in": 3600,
    }
    with patch("mcp_exec.azure_auth.msal.ConfidentialClientApplication", return_value=fake_msal):
        az = AzureAuth(**_cfg())
        out = az.exchange_code(code="abc")
        assert out.email == "e@x.com"
        assert out.aad_access_token == "aad_tok"


def test_exchange_code_no_email_raises() -> None:
    fake = MagicMock()
    fake.acquire_token_by_authorization_code.return_value = {"error": "bad"}
    with patch("mcp_exec.azure_auth.msal.ConfidentialClientApplication", return_value=fake):
        az = AzureAuth(**_cfg())
        with pytest.raises(AzureAuthError):
            az.exchange_code(code="abc")
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_azure_auth.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement AzureAuth**

Create `mcp-server/src/mcp_exec/azure_auth.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

import msal


class AzureAuthError(RuntimeError):
    pass


@dataclass
class AzureTokenInfo:
    email: str
    aad_access_token: str
    expires_in_s: int


@dataclass
class AzureAuth:
    tenant_id: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = ("User.Read",)

    def _app(self) -> msal.ConfidentialClientApplication:
        return msal.ConfidentialClientApplication(
            client_id=self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )

    def authorization_url(self, state: str) -> str:
        return self._app().get_authorization_request_url(
            scopes=list(self.scopes),
            state=state,
            redirect_uri=self.redirect_uri,
        )

    def exchange_code(self, code: str) -> AzureTokenInfo:
        result = self._app().acquire_token_by_authorization_code(
            code=code,
            scopes=list(self.scopes),
            redirect_uri=self.redirect_uri,
        )
        if "access_token" not in result:
            raise AzureAuthError(f"azure ad returned no access_token: {result.get('error_description', result)}")
        claims = result.get("id_token_claims", {})
        email = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
        if not email:
            raise AzureAuthError("no email claim in id_token")
        return AzureTokenInfo(
            email=email,
            aad_access_token=result["access_token"],
            expires_in_s=int(result.get("expires_in", 3600)),
        )
```

- [ ] **Step 4: Tests pass + commit**

```bash
cd mcp-server && uv run pytest tests/test_azure_auth.py -v
git add mcp-server/src/mcp_exec/azure_auth.py mcp-server/tests/test_azure_auth.py
git commit -m "feat(mcp): Azure AD auth-code token exchange helper"
```

---

### Task 5.3: JWT issuer + verifier (MCP's own tokens)

**Files:**
- Create: `mcp-server/src/mcp_exec/jwt_tokens.py`
- Create: `mcp-server/tests/test_jwt_tokens.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_jwt_tokens.py`:
```python
import time

import pytest

from mcp_exec.jwt_tokens import TokenExpiredError, TokenInvalidError, TokenIssuer


def test_issue_and_verify() -> None:
    iss = TokenIssuer(secret="s", issuer="mcp-test", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    claims = iss.verify_access(pair.access_token)
    assert claims["email"] == "e@x.com"
    assert claims["kind"] == "access"


def test_access_token_expires() -> None:
    iss = TokenIssuer(secret="s", issuer="i", access_ttl_s=1, refresh_ttl_s=10)
    pair = iss.issue(email="e@x.com")
    time.sleep(2)
    with pytest.raises(TokenExpiredError):
        iss.verify_access(pair.access_token)


def test_tampered_token_rejected() -> None:
    iss = TokenIssuer(secret="s", issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    tampered = pair.access_token[:-2] + ("AA" if pair.access_token[-2:] != "AA" else "BB")
    with pytest.raises(TokenInvalidError):
        iss.verify_access(tampered)


def test_refresh_issues_new_access() -> None:
    iss = TokenIssuer(secret="s", issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    new_access = iss.refresh(pair.refresh_token)
    claims = iss.verify_access(new_access)
    assert claims["email"] == "e@x.com"


def test_refresh_rejects_access_token() -> None:
    iss = TokenIssuer(secret="s", issuer="i", access_ttl_s=60, refresh_ttl_s=120)
    pair = iss.issue(email="e@x.com")
    with pytest.raises(TokenInvalidError):
        iss.refresh(pair.access_token)
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_jwt_tokens.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement TokenIssuer**

Create `mcp-server/src/mcp_exec/jwt_tokens.py`:
```python
from __future__ import annotations

import time
from dataclasses import dataclass

import jwt


class TokenError(RuntimeError):
    pass


class TokenExpiredError(TokenError):
    pass


class TokenInvalidError(TokenError):
    pass


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_at: int


@dataclass
class TokenIssuer:
    secret: str
    issuer: str
    access_ttl_s: int
    refresh_ttl_s: int
    alg: str = "HS256"

    def _encode(self, kind: str, email: str, ttl: int) -> tuple[str, int]:
        now = int(time.time())
        exp = now + ttl
        payload = {
            "iss": self.issuer,
            "sub": email,
            "email": email,
            "kind": kind,
            "iat": now,
            "exp": exp,
        }
        return jwt.encode(payload, self.secret, algorithm=self.alg), exp

    def issue(self, email: str) -> TokenPair:
        access, exp = self._encode("access", email, self.access_ttl_s)
        refresh, _ = self._encode("refresh", email, self.refresh_ttl_s)
        return TokenPair(access_token=access, refresh_token=refresh, expires_at=exp)

    def _decode(self, token: str) -> dict:
        try:
            return jwt.decode(token, self.secret, algorithms=[self.alg], issuer=self.issuer)
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredError("token expired") from e
        except jwt.InvalidTokenError as e:
            raise TokenInvalidError(str(e)) from e

    def verify_access(self, token: str) -> dict:
        claims = self._decode(token)
        if claims.get("kind") != "access":
            raise TokenInvalidError("not an access token")
        return claims

    def refresh(self, refresh_token: str) -> str:
        claims = self._decode(refresh_token)
        if claims.get("kind") != "refresh":
            raise TokenInvalidError("not a refresh token")
        access, _ = self._encode("access", claims["email"], self.access_ttl_s)
        return access
```

- [ ] **Step 4: Tests pass + commit**

```bash
cd mcp-server && uv run pytest tests/test_jwt_tokens.py -v
git add mcp-server/src/mcp_exec/jwt_tokens.py mcp-server/tests/test_jwt_tokens.py
git commit -m "feat(mcp): JWT access+refresh token issuer/verifier"
```

---

### Task 5.4: Auth HTTP endpoints (`/auth/token`, `/auth/refresh`, `/auth/start`)

**Files:**
- Create: `mcp-server/src/mcp_exec/auth_routes.py`
- Create: `mcp-server/tests/test_auth_routes.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_auth_routes.py`:
```python
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from mcp_exec.allowlist import Allowlist
from mcp_exec.auth_routes import build_auth_app
from mcp_exec.azure_auth import AzureTokenInfo
from mcp_exec.jwt_tokens import TokenIssuer


def _app(allowlist_emails: list[str]) -> TestClient:
    azure = MagicMock()
    azure.authorization_url.return_value = "https://login.microsoftonline.com/fake"
    azure.exchange_code.return_value = AzureTokenInfo(
        email="exec@azzas.com.br", aad_access_token="aad", expires_in_s=3600
    )
    issuer = TokenIssuer(secret="s", issuer="mcp", access_ttl_s=60, refresh_ttl_s=120)

    import tempfile, json
    from pathlib import Path
    tmp = Path(tempfile.mkstemp(suffix=".json")[1])
    tmp.write_text(json.dumps({"allowed_emails": allowlist_emails}))

    return TestClient(
        build_auth_app(azure=azure, issuer=issuer, allowlist=Allowlist(path=tmp))
    )


def test_start_redirects_to_azure() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/start", follow_redirects=False)
    assert r.status_code == 302
    assert "microsoftonline.com" in r.headers["location"]


def test_callback_returns_tokens_for_allowed_exec() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/callback?code=abc&state=xyz")
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert r.json()["refresh_token"]


def test_callback_rejects_unauthorized_exec() -> None:
    c = _app(["other@azzas.com.br"])
    r = c.get("/auth/callback?code=abc&state=xyz")
    assert r.status_code == 403


def test_refresh_returns_new_access() -> None:
    c = _app(["exec@azzas.com.br"])
    r = c.get("/auth/callback?code=abc&state=xyz")
    refresh = r.json()["refresh_token"]
    r2 = c.post("/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 200
    assert r2.json()["access_token"]
```

- [ ] **Step 2: Add FastAPI + uvicorn to deps**

Edit `mcp-server/pyproject.toml`, add to `dependencies`:
```toml
"fastapi>=0.115",
"uvicorn[standard]>=0.30",
```
And to `optional-dependencies.dev`:
```toml
"httpx>=0.27",  # already in deps; confirm FastAPI TestClient works
```

Run `uv sync --all-extras`.

- [ ] **Step 3: Implement auth_routes**

Create `mcp-server/src/mcp_exec/auth_routes.py`:
```python
from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from mcp_exec.allowlist import Allowlist
from mcp_exec.azure_auth import AzureAuth, AzureAuthError
from mcp_exec.jwt_tokens import TokenInvalidError, TokenIssuer


def build_auth_app(
    *,
    azure: AzureAuth,
    issuer: TokenIssuer,
    allowlist: Allowlist,
) -> FastAPI:
    app = FastAPI()

    @app.get("/auth/start")
    def start() -> RedirectResponse:
        state = secrets.token_urlsafe(16)
        return RedirectResponse(azure.authorization_url(state=state), status_code=302)

    @app.get("/auth/callback")
    def callback(code: str, state: str | None = None) -> JSONResponse:
        try:
            info = azure.exchange_code(code=code)
        except AzureAuthError as e:
            raise HTTPException(status_code=400, detail=f"azure_auth: {e}")
        if not allowlist.is_allowed(info.email):
            raise HTTPException(status_code=403, detail=f"not on allowlist: {info.email}")
        pair = issuer.issue(email=info.email)
        return JSONResponse({
            "access_token": pair.access_token,
            "refresh_token": pair.refresh_token,
            "expires_at": pair.expires_at,
            "email": info.email,
        })

    @app.post("/auth/refresh")
    async def refresh(req: Request) -> JSONResponse:
        body = await req.json()
        try:
            access = issuer.refresh(body["refresh_token"])
        except TokenInvalidError as e:
            raise HTTPException(status_code=401, detail=str(e))
        return JSONResponse({"access_token": access})

    return app
```

- [ ] **Step 4: Tests pass + commit**

```bash
cd mcp-server && uv run pytest tests/test_auth_routes.py -v
git add mcp-server/src/mcp_exec/auth_routes.py mcp-server/tests/test_auth_routes.py mcp-server/pyproject.toml
git commit -m "feat(mcp): /auth/{start,callback,refresh} routes gated by allowlist"
```

---

### Task 5.5: MCP tool-call auth middleware (bearer token → exec_email)

**Files:**
- Modify: `mcp-server/src/mcp_exec/server.py`
- Create: `mcp-server/src/mcp_exec/auth_middleware.py`
- Create: `mcp-server/tests/test_auth_middleware.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_auth_middleware.py`:
```python
import pytest

from mcp_exec.allowlist import Allowlist
from mcp_exec.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_exec.jwt_tokens import TokenIssuer


def _ctx(tmp_path, allowed: list[str]) -> AuthContext:
    import json
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"allowed_emails": allowed}))
    return AuthContext(
        issuer=TokenIssuer(secret="s", issuer="mcp", access_ttl_s=60, refresh_ttl_s=120),
        allowlist=Allowlist(path=f),
    )


def test_valid_token_returns_email(tmp_path) -> None:
    actx = _ctx(tmp_path, ["e@x.com"])
    token = actx.issuer.issue("e@x.com").access_token
    email = extract_exec_email(token=token, ctx=actx)
    assert email == "e@x.com"


def test_invalid_token_raises(tmp_path) -> None:
    actx = _ctx(tmp_path, ["e@x.com"])
    with pytest.raises(AuthError):
        extract_exec_email(token="nope", ctx=actx)


def test_removed_from_allowlist_raises(tmp_path) -> None:
    actx = _ctx(tmp_path, [])  # empty allowlist
    token = actx.issuer.issue("e@x.com").access_token
    with pytest.raises(AuthError):
        extract_exec_email(token=token, ctx=actx)
```

- [ ] **Step 2: Implement auth_middleware**

Create `mcp-server/src/mcp_exec/auth_middleware.py`:
```python
from __future__ import annotations

from dataclasses import dataclass

from mcp_exec.allowlist import Allowlist
from mcp_exec.jwt_tokens import TokenError, TokenIssuer


class AuthError(RuntimeError):
    pass


@dataclass
class AuthContext:
    issuer: TokenIssuer
    allowlist: Allowlist


def extract_exec_email(token: str, ctx: AuthContext) -> str:
    try:
        claims = ctx.issuer.verify_access(token)
    except TokenError as e:
        raise AuthError(f"invalid_token: {e}") from e
    email = claims["email"]
    if not ctx.allowlist.is_allowed(email):
        raise AuthError(f"not_on_allowlist: {email}")
    return email
```

- [ ] **Step 3: Wire middleware into server `_current_exec_email`**

Modify `mcp-server/src/mcp_exec/server.py` — replace the stub `_current_exec_email`:
```python
from mcp_exec.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_exec.allowlist import Allowlist
from mcp_exec.jwt_tokens import TokenIssuer


def _auth_context() -> AuthContext:
    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    settings = load_settings(settings_path)
    secret = os.environ["MCP_JWT_SECRET"]
    issuer = TokenIssuer(
        secret=secret,
        issuer=settings.auth.jwt_issuer,
        access_ttl_s=settings.auth.access_token_ttl_s,
        refresh_ttl_s=settings.auth.refresh_token_ttl_s,
    )
    allowlist = Allowlist(path=Path(os.environ.get("MCP_ALLOWLIST", "/app/config/allowed_execs.json")))
    return AuthContext(issuer=issuer, allowlist=allowlist)


def _current_exec_email(ctx) -> str:
    # In dev, allow override via env var for tests.
    if os.environ.get("MCP_DEV_EXEC_EMAIL"):
        return os.environ["MCP_DEV_EXEC_EMAIL"]

    # Pull Bearer token from MCP request headers.
    headers = getattr(ctx.request_context.request, "headers", {}) or {}
    auth = headers.get("authorization") or headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    token = auth.split(None, 1)[1].strip()
    return extract_exec_email(token=token, ctx=_auth_context())
```

- [ ] **Step 4: Tests pass + commit**

```bash
cd mcp-server && uv run pytest tests/test_auth_middleware.py -v
git add mcp-server/src/mcp_exec/auth_middleware.py mcp-server/src/mcp_exec/server.py mcp-server/tests/test_auth_middleware.py
git commit -m "feat(mcp): bearer token middleware resolves exec_email from JWT"
```

---

### Task 5.6: `mcp-login` CLI (browser-based OAuth dance)

**Files:**
- Create: `mcp-server/src/mcp_exec/cli_login.py`
- Create: `mcp-server/tests/test_cli_login.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_cli_login.py`:
```python
import json
from pathlib import Path
from unittest.mock import patch

from mcp_exec.cli_login import save_credentials


def test_save_credentials_writes_600_file(tmp_path: Path) -> None:
    out = tmp_path / "creds.json"
    save_credentials(path=out, payload={"access_token": "a", "refresh_token": "r", "expires_at": 123, "email": "e@x.com"})
    data = json.loads(out.read_text())
    assert data["access_token"] == "a"
    mode = oct(out.stat().st_mode & 0o777)
    assert mode == "0o600"
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_cli_login.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement cli_login**

Create `mcp-server/src/mcp_exec/cli_login.py`:
```python
from __future__ import annotations

import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx


CREDS_DEFAULT = Path.home() / ".mcp" / "credentials.json"


def save_credentials(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    os.chmod(path, 0o600)


def _capture_code(port: int, timeout_s: int = 120) -> str:
    code_holder: dict[str, str] = {}
    stop_event = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            if "code" in params:
                code_holder["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>OK</h1><p>You can close this tab.</p>")
                stop_event.set()
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *args):  # noqa: D401, N802
            return  # silence default logging

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        if not stop_event.wait(timeout=timeout_s):
            httpd.shutdown()
            raise TimeoutError("OAuth callback not received")
        httpd.shutdown()
    return code_holder["code"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcp-login")
    parser.add_argument("--server", default=os.environ.get("MCP_SERVER_URL", "https://mcp-azzas.azzas.com.br"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--creds-path", type=Path, default=CREDS_DEFAULT)
    args = parser.parse_args()

    start_url = f"{args.server}/auth/start"
    print(f"Opening browser to {start_url}")
    webbrowser.open(start_url)
    try:
        code = _capture_code(port=args.port)
    except TimeoutError:
        print("timeout waiting for browser callback", file=sys.stderr)
        sys.exit(1)

    r = httpx.get(f"{args.server}/auth/callback", params={"code": code}, timeout=30)
    if r.status_code != 200:
        print(f"auth failed: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(2)
    save_credentials(args.creds_path, r.json())
    print(f"credentials saved to {args.creds_path}")
```

Note: The real Azure AD redirect_uri must be registered as `http://localhost:8765/` in Entra ID. Document in README.

- [ ] **Step 4: Tests pass + commit**

```bash
cd mcp-server && uv run pytest tests/test_cli_login.py -v
git add mcp-server/src/mcp_exec/cli_login.py mcp-server/tests/test_cli_login.py
git commit -m "feat(mcp): mcp-login CLI performs OAuth code grant and saves credentials"
```

---

## Phase 6: Audit log + anomaly alerts

### Task 6.1: SQLite audit writer

**Files:**
- Create: `mcp-server/src/mcp_exec/audit.py`
- Create: `mcp-server/tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_audit.py`:
```python
from pathlib import Path

from mcp_exec.audit import AuditLog


def test_record_and_query(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    log.record(
        exec_email="e@x.com", tool="consultar_bq",
        sql="SELECT 1", bytes_scanned=10, row_count=1,
        duration_ms=55, result="ok", error=None,
    )
    rows = log.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["exec_email"] == "e@x.com"
    assert rows[0]["tool"] == "consultar_bq"


def test_purge_older_than(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    log.record(exec_email="e", tool="t", sql=None, bytes_scanned=0, row_count=0,
               duration_ms=0, result="ok", error=None)
    deleted = log.purge_older_than_days(0)
    assert deleted == 1
    assert log.list_recent() == []
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_audit.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement audit**

Create `mcp-server/src/mcp_exec/audit.py`:
```python
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  exec_email TEXT NOT NULL,
  tool TEXT NOT NULL,
  sql TEXT,
  bytes_scanned INTEGER DEFAULT 0,
  row_count INTEGER DEFAULT 0,
  duration_ms INTEGER DEFAULT 0,
  result TEXT NOT NULL,
  error TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit (ts);
CREATE INDEX IF NOT EXISTS idx_audit_exec ON audit (exec_email);
"""


@dataclass
class AuditLog:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as c:
            c.executescript(SCHEMA)

    def record(
        self, *, exec_email: str, tool: str, sql: str | None,
        bytes_scanned: int, row_count: int, duration_ms: int,
        result: str, error: str | None,
    ) -> None:
        with sqlite3.connect(self.db_path) as c:
            c.execute(
                "INSERT INTO audit (ts, exec_email, tool, sql, bytes_scanned, row_count, duration_ms, result, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), exec_email, tool, sql, bytes_scanned, row_count, duration_ms, result, error),
            )

    def list_recent(self, limit: int = 100) -> list[dict]:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory = sqlite3.Row
            cur = c.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def purge_older_than_days(self, days: int) -> int:
        cutoff = time.time() - days * 86400
        with sqlite3.connect(self.db_path) as c:
            cur = c.execute("DELETE FROM audit WHERE ts < ?", (cutoff,))
            return cur.rowcount
```

- [ ] **Step 4: Wire audit into tool wrappers**

Modify each tool in `server.py` to record audit on success/error. Example shape at the top of `server.py`:
```python
from mcp_exec.audit import AuditLog

_AUDIT: AuditLog | None = None


def _audit_log() -> AuditLog:
    global _AUDIT
    if _AUDIT is None:
        settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
        settings = load_settings(settings_path)
        _AUDIT = AuditLog(db_path=Path(settings.audit.db_path))
    return _AUDIT
```

Then wrap `consultar_bq_impl`, `publicar_dashboard_impl`, `listar_analises_impl` to record calls. For example in `consultar_bq`:
```python
@mcp.tool()
async def consultar_bq(sql: str, ctx) -> dict:
    exec_email = _current_exec_email(ctx)
    start = time.time()
    out = consultar_bq_impl(sql=sql, exec_email=exec_email, progress=lambda m: ctx.info(m))
    _audit_log().record(
        exec_email=exec_email, tool="consultar_bq", sql=sql,
        bytes_scanned=out.get("bytes_processed", 0),
        row_count=out.get("row_count", 0),
        duration_ms=int((time.time() - start) * 1000),
        result="ok" if "error" not in out else "error",
        error=out.get("error"),
    )
    return out
```

Do the same for `publicar_dashboard` (sql=None, bytes_scanned=0, row_count=0) and `listar_analises`.

- [ ] **Step 5: Tests pass + commit**

```bash
cd mcp-server && uv run pytest tests/test_audit.py -v
git add mcp-server/src/mcp_exec/audit.py mcp-server/src/mcp_exec/server.py mcp-server/tests/test_audit.py
git commit -m "feat(mcp): SQLite audit log captures every tool call with retention purge"
```

---

### Task 6.2: Anomaly detector script (run hourly)

**Files:**
- Create: `mcp-server/src/mcp_exec/alerts.py`
- Create: `mcp-server/tests/test_alerts.py`

- [ ] **Step 1: Write the failing test**

Create `mcp-server/tests/test_alerts.py`:
```python
import time
from pathlib import Path

from mcp_exec.alerts import detect_anomalies
from mcp_exec.audit import AuditLog


def test_detects_high_calls_per_hour(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    for _ in range(60):
        log.record(
            exec_email="busy@x.com", tool="consultar_bq", sql="SELECT 1",
            bytes_scanned=1, row_count=1, duration_ms=1, result="ok", error=None,
        )
    alerts = detect_anomalies(log, now=time.time())
    assert any(a["kind"] == "high_call_rate" and a["exec_email"] == "busy@x.com" for a in alerts)


def test_detects_huge_query(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    log.record(
        exec_email="e@x.com", tool="consultar_bq", sql="SELECT 1",
        bytes_scanned=11 * 1024**3, row_count=1, duration_ms=1, result="ok", error=None,
    )
    alerts = detect_anomalies(log, now=time.time())
    assert any(a["kind"] == "huge_query" for a in alerts)


def test_detects_error_rate(tmp_path: Path) -> None:
    log = AuditLog(db_path=tmp_path / "a.db")
    for i in range(20):
        log.record(
            exec_email="e@x.com", tool="consultar_bq", sql="SELECT 1",
            bytes_scanned=0, row_count=0, duration_ms=0,
            result="ok" if i < 10 else "error",
            error=None if i < 10 else "boom",
        )
    alerts = detect_anomalies(log, now=time.time())
    assert any(a["kind"] == "high_error_rate" for a in alerts)
```

- [ ] **Step 2: See it fail**

```bash
cd mcp-server && uv run pytest tests/test_alerts.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement alerts**

Create `mcp-server/src/mcp_exec/alerts.py`:
```python
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from mcp_exec.audit import AuditLog

HUGE_QUERY_THRESHOLD_BYTES = 10 * 1024**3
HIGH_CALL_RATE_PER_HOUR = 50
HIGH_ERROR_RATE_THRESHOLD = 0.05


def detect_anomalies(log: AuditLog, now: float | None = None) -> list[dict]:
    now = now or time.time()
    since = now - 3600
    alerts: list[dict] = []

    with sqlite3.connect(log.db_path) as c:
        c.row_factory = sqlite3.Row
        # huge queries
        for r in c.execute(
            "SELECT exec_email, bytes_scanned, sql FROM audit WHERE ts >= ? AND bytes_scanned > ?",
            (since, HUGE_QUERY_THRESHOLD_BYTES),
        ):
            alerts.append({
                "kind": "huge_query",
                "exec_email": r["exec_email"],
                "bytes_scanned": r["bytes_scanned"],
                "sql": r["sql"],
            })
        # high call rate per exec
        for r in c.execute(
            "SELECT exec_email, COUNT(*) as n FROM audit WHERE ts >= ? GROUP BY exec_email HAVING n > ?",
            (since, HIGH_CALL_RATE_PER_HOUR),
        ):
            alerts.append({"kind": "high_call_rate", "exec_email": r["exec_email"], "count": r["n"]})
        # error rate
        row = c.execute(
            "SELECT "
            "SUM(CASE WHEN result='error' THEN 1 ELSE 0 END) as errs, COUNT(*) as total "
            "FROM audit WHERE ts >= ?",
            (since,),
        ).fetchone()
        if row and row["total"] and (row["errs"] / row["total"]) > HIGH_ERROR_RATE_THRESHOLD:
            alerts.append({"kind": "high_error_rate", "rate": row["errs"] / row["total"], "total": row["total"]})
    return alerts


def run_cli() -> int:
    import os
    from mcp_exec.settings import load_settings
    settings = load_settings(Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml")))
    log = AuditLog(db_path=Path(settings.audit.db_path))
    alerts = detect_anomalies(log)
    if alerts:
        for a in alerts:
            print("ALERT", a)
        return 1
    return 0
```

- [ ] **Step 4: Tests pass + commit**

```bash
cd mcp-server && uv run pytest tests/test_alerts.py -v
git add mcp-server/src/mcp_exec/alerts.py mcp-server/tests/test_alerts.py
git commit -m "feat(mcp): anomaly detector (huge queries, high rate, high error rate)"
```

---

### Task 6.3: Retention purge cron entry

**Files:**
- Create: `mcp-server/scripts/purge_audit.py`
- Modify: `mcp-server/README.md` (document cron)

- [ ] **Step 1: Create script**

Create `mcp-server/scripts/purge_audit.py`:
```python
#!/usr/bin/env python3
"""Purge audit entries older than settings.audit.retention_days. Intended for daily cron."""
from __future__ import annotations

import os
from pathlib import Path

from mcp_exec.audit import AuditLog
from mcp_exec.settings import load_settings


def main() -> None:
    settings = load_settings(Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml")))
    log = AuditLog(db_path=Path(settings.audit.db_path))
    deleted = log.purge_older_than_days(settings.audit.retention_days)
    print(f"deleted {deleted} audit rows older than {settings.audit.retention_days}d")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update README with cron guidance**

Append to `mcp-server/README.md`:
```markdown

## Cron jobs

Host runs two cron jobs (via launchd `StartCalendarInterval` or a wrapper plist):

- **Hourly anomaly check**: `python -m mcp_exec.alerts`. Exit code 1 on alert.
- **Daily audit purge**: `python scripts/purge_audit.py`.

Plists live in `infra/launchd/` (see Phase 7).
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/scripts/ mcp-server/README.md
git commit -m "chore(mcp): purge_audit.py cron script + docs"
```

---

## Phase 7: Infrastructure (Dockerfile + launchd + Cloudflare Tunnel)

### Task 7.1: Dockerfile (matches spec 4.4)

**Files:**
- Create: `mcp-server/Dockerfile`
- Create: `mcp-server/requirements.txt`
- Create: `mcp-server/.dockerignore`

- [ ] **Step 1: Freeze requirements.txt from pyproject**

```bash
cd mcp-server && uv export --no-hashes --format requirements-txt -o requirements.txt
```

- [ ] **Step 2: Write `.dockerignore`**

Create `mcp-server/.dockerignore`:
```
.venv
.git
.pytest_cache
.ruff_cache
__pycache__
tests/
*.db
*.db-journal
config/allowed_execs.json
config/settings.toml
```

- [ ] **Step 3: Write Dockerfile**

Create `mcp-server/Dockerfile`:
```dockerfile
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/

RUN useradd -m -u 1000 mcp \
    && mkdir -p /var/mcp /app/repo /app/config \
    && chown -R mcp:mcp /app /var/mcp
USER mcp

ENV PYTHONPATH=/app/src

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:3000/health', timeout=5).raise_for_status()"

EXPOSE 3000

CMD ["python", "-m", "mcp_exec.server"]
```

- [ ] **Step 4: Add `/health` endpoint to the HTTP app**

Modify `mcp-server/src/mcp_exec/auth_routes.py` — add inside `build_auth_app`:
```python
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

(The same FastAPI app will serve auth + health; MCP protocol itself runs alongside.)

- [ ] **Step 5: Build image locally to verify it compiles**

```bash
cd mcp-server && docker build -t mcp-azzas:dev .
```
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add mcp-server/Dockerfile mcp-server/requirements.txt mcp-server/.dockerignore mcp-server/src/mcp_exec/auth_routes.py
git commit -m "feat(mcp): Dockerfile + /health endpoint; pin requirements.txt"
```

---

### Task 7.2: Combined HTTP + MCP entrypoint

**Files:**
- Modify: `mcp-server/src/mcp_exec/server.py`

- [ ] **Step 1: Update `main()` to run FastAPI (auth+health) alongside MCP**

Replace `main()` in `server.py` with:
```python
def main() -> None:
    import asyncio
    import uvicorn
    from mcp_exec.auth_routes import build_auth_app
    from mcp_exec.azure_auth import AzureAuth
    from mcp_exec.allowlist import Allowlist
    from mcp_exec.jwt_tokens import TokenIssuer

    settings_path = Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))
    settings = load_settings(settings_path)

    azure = AzureAuth(
        tenant_id=os.environ["MCP_AZURE_TENANT_ID"],
        client_id=os.environ["MCP_AZURE_CLIENT_ID"],
        client_secret=os.environ["MCP_AZURE_CLIENT_SECRET"],
        redirect_uri=os.environ.get("MCP_AZURE_REDIRECT_URI", "http://localhost:8765/"),
    )
    issuer = TokenIssuer(
        secret=os.environ["MCP_JWT_SECRET"],
        issuer=settings.auth.jwt_issuer,
        access_ttl_s=settings.auth.access_token_ttl_s,
        refresh_ttl_s=settings.auth.refresh_token_ttl_s,
    )
    allowlist = Allowlist(path=Path(os.environ.get("MCP_ALLOWLIST", "/app/config/allowed_execs.json")))

    auth_app = build_auth_app(azure=azure, issuer=issuer, allowlist=allowlist)

    # MCP streams over stdio by default; in server mode we mount into FastAPI via the SDK's ASGI integration.
    auth_app.mount("/mcp", mcp.sse_app())  # FastMCP exposes an SSE ASGI app

    uvicorn.run(auth_app, host=settings.server.host, port=settings.server.port)
```

- [ ] **Step 2: Smoke-run locally (dev only — without Azure secrets, just assert import works)**

```bash
cd mcp-server && uv run python -c "from mcp_exec.server import main; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add mcp-server/src/mcp_exec/server.py
git commit -m "feat(mcp): uvicorn entrypoint serves auth routes + MCP SSE on one port"
```

---

### Task 7.3: launchd plist + deploy script

**Files:**
- Create: `mcp-server/infra/launchd/com.azzas.mcp.plist`
- Create: `mcp-server/infra/launchd/com.azzas.mcp.alerts.plist`
- Create: `mcp-server/infra/launchd/com.azzas.mcp.purge.plist`
- Create: `mcp-server/infra/deploy.sh`

- [ ] **Step 1: Write MCP plist**

Create `mcp-server/infra/launchd/com.azzas.mcp.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.azzas.mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/docker</string>
        <string>run</string>
        <string>--rm</string>
        <string>--name</string><string>mcp-server</string>
        <string>-p</string><string>3000:3000</string>
        <string>-v</string><string>/Users/artur/bq-analista:/app/repo</string>
        <string>-v</string><string>/etc/mcp:/app/config:ro</string>
        <string>-v</string><string>/var/mcp:/var/mcp</string>
        <string>-e</string><string>MCP_SETTINGS=/app/config/settings.toml</string>
        <string>-e</string><string>MCP_ALLOWLIST=/app/config/allowed_execs.json</string>
        <string>-e</string><string>MCP_BQ_SA_KEY</string>
        <string>-e</string><string>MCP_GITHUB_PAT</string>
        <string>-e</string><string>MCP_AZURE_TENANT_ID</string>
        <string>-e</string><string>MCP_AZURE_CLIENT_ID</string>
        <string>-e</string><string>MCP_AZURE_CLIENT_SECRET</string>
        <string>-e</string><string>MCP_JWT_SECRET</string>
        <string>-e</string><string>MCP_GIT_PUSH=1</string>
        <string>mcp-azzas:latest</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>MCP_BQ_SA_KEY</key>
        <string>__set_via_keychain_wrapper__</string>
        <key>MCP_GITHUB_PAT</key>
        <string>__set_via_keychain_wrapper__</string>
        <key>MCP_AZURE_TENANT_ID</key>
        <string>__set_via_keychain_wrapper__</string>
        <key>MCP_AZURE_CLIENT_ID</key>
        <string>__set_via_keychain_wrapper__</string>
        <key>MCP_AZURE_CLIENT_SECRET</key>
        <string>__set_via_keychain_wrapper__</string>
        <key>MCP_JWT_SECRET</key>
        <string>__set_via_keychain_wrapper__</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>/var/log/mcp/stdout.log</string>
    <key>StandardErrorPath</key><string>/var/log/mcp/stderr.log</string>
</dict>
</plist>
```

Note: the `__set_via_keychain_wrapper__` placeholders are filled by `deploy.sh` that reads from `security find-generic-password` and rewrites the plist just before `launchctl load`. Hardcoded substitution in plist EnvironmentVariables does not evaluate shell — hence the wrapper.

- [ ] **Step 2: Write alerts plist (hourly)**

Create `mcp-server/infra/launchd/com.azzas.mcp.alerts.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.azzas.mcp.alerts</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/docker</string><string>exec</string>
        <string>mcp-server</string>
        <string>python</string><string>-m</string><string>mcp_exec.alerts</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key><string>/var/log/mcp/alerts.log</string>
    <key>StandardErrorPath</key><string>/var/log/mcp/alerts.err</string>
</dict>
</plist>
```

- [ ] **Step 3: Write purge plist (daily 03:00)**

Create `mcp-server/infra/launchd/com.azzas.mcp.purge.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.azzas.mcp.purge</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/docker</string><string>exec</string>
        <string>mcp-server</string>
        <string>python</string><string>scripts/purge_audit.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>3</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>/var/log/mcp/purge.log</string>
    <key>StandardErrorPath</key><string>/var/log/mcp/purge.err</string>
</dict>
</plist>
```

- [ ] **Step 4: Write deploy.sh**

Create `mcp-server/infra/deploy.sh`:
```bash
#!/usr/bin/env bash
# Rebuild image, render plist with secrets from Keychain, reload launchd service.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MCP_DIR="$SCRIPT_DIR/.."

echo "==> Building mcp-azzas:latest"
docker build -t mcp-azzas:latest "$MCP_DIR"

read_kc() {
  security find-generic-password -w -a mcp -s "$1" 2>/dev/null || {
    echo "missing Keychain entry: $1" >&2
    exit 1
  }
}

MCP_BQ_SA_KEY=$(read_kc bq_sa_key)
MCP_GITHUB_PAT=$(read_kc github_pat)
MCP_AZURE_TENANT_ID=$(read_kc azure_tenant_id)
MCP_AZURE_CLIENT_ID=$(read_kc azure_client_id)
MCP_AZURE_CLIENT_SECRET=$(read_kc azure_client_secret)
MCP_JWT_SECRET=$(read_kc jwt_secret)

TMP_PLIST=$(mktemp)
cp "$SCRIPT_DIR/launchd/com.azzas.mcp.plist" "$TMP_PLIST"
for k in MCP_BQ_SA_KEY MCP_GITHUB_PAT MCP_AZURE_TENANT_ID MCP_AZURE_CLIENT_ID MCP_AZURE_CLIENT_SECRET MCP_JWT_SECRET; do
  v=$(eval echo "\$$k")
  # escape plist special chars
  v_escaped=$(python3 -c "import sys,xml.sax.saxutils as x; print(x.escape(sys.argv[1]))" "$v")
  perl -0777 -i -pe "s/<key>$k<\\/key>\s*<string>__set_via_keychain_wrapper__<\\/string>/<key>$k<\\/key><string>$v_escaped<\\/string>/" "$TMP_PLIST"
done

DEST=~/Library/LaunchAgents/com.azzas.mcp.plist
launchctl unload "$DEST" 2>/dev/null || true
mv "$TMP_PLIST" "$DEST"
chmod 600 "$DEST"
launchctl load "$DEST"

echo "==> MCP loaded. Tail logs:"
echo "   tail -f /var/log/mcp/stderr.log"
```

Make executable:
```bash
chmod +x mcp-server/infra/deploy.sh
```

- [ ] **Step 5: Commit**

```bash
git add mcp-server/infra/
git commit -m "chore(mcp): launchd plists + deploy.sh pulling secrets from Keychain"
```

---

### Task 7.4: Cloudflare Tunnel config docs

**Files:**
- Create: `mcp-server/infra/cloudflare/README.md`
- Create: `mcp-server/infra/cloudflare/config.yml.example`

- [ ] **Step 1: Write config.yml.example**

Create `mcp-server/infra/cloudflare/config.yml.example`:
```yaml
# Rename to config.yml and run: cloudflared tunnel run mcp-azzas
tunnel: <TUNNEL_ID>
credentials-file: /Users/artur/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: mcp-azzas.<your-corp-domain>
    service: http://localhost:3000
    originRequest:
      noTLSVerify: false
  - service: http_status:404
```

- [ ] **Step 2: Write README**

Create `mcp-server/infra/cloudflare/README.md`:
```markdown
# Cloudflare Tunnel setup

1. Install `cloudflared` on the Mac mini: `brew install cloudflared`.
2. Authenticate: `cloudflared tunnel login` → browser flow.
3. Create tunnel: `cloudflared tunnel create mcp-azzas` (writes credentials JSON).
4. Copy `config.yml.example` → `~/.cloudflared/config.yml`, fill `<TUNNEL_ID>` and hostname.
5. DNS: `cloudflared tunnel route dns mcp-azzas mcp-azzas.<corp-domain>`.
6. Run as launchd service: `sudo cloudflared service install`.
7. In Cloudflare dashboard → Access → create application for this hostname, restrict by issuer/domain. Rate-limit 100/min per IP.

## WAF rules

Add a WAF rule: allow only `user-agent contains "Claude"` OR requests coming from `claude.ai` in the `Origin` header. This blocks direct scraping of the public URL.
```

- [ ] **Step 3: Commit**

```bash
git add mcp-server/infra/cloudflare/
git commit -m "docs(mcp): Cloudflare Tunnel setup guide + WAF notes"
```

---

## Phase 8: Production verification + connector registration

### Task 8.1: Manual integration test with local MCP client

**Files:**
- Create: `mcp-server/tests/integration/test_end_to_end.md`

- [ ] **Step 1: Write the runbook**

Create `mcp-server/tests/integration/test_end_to_end.md`:
```markdown
# End-to-end integration test (manual, run once before production rollout)

## Prereqs
- Mac mini has Docker running.
- Keychain has all 6 secrets set (see `infra/deploy.sh`).
- `/etc/mcp/settings.toml` and `/etc/mcp/allowed_execs.json` exist and contain `artur.lemos@somagrupo.com.br`.
- Cloudflare tunnel running, hostname resolves.

## Steps

1. **Deploy**: `bash mcp-server/infra/deploy.sh`
2. **Verify service up**: `curl https://mcp-azzas.<corp>/health` → `{"status":"ok"}`
3. **Login from analyst laptop**: `uv run --directory mcp-server mcp-login --server https://mcp-azzas.<corp>`
   - Browser opens → Azure AD login → "You can close this tab."
   - `~/.mcp/credentials.json` appears with `access_token`, `refresh_token`, `email`.
4. **Call `get_context`**: use `mcp-cli` or curl against `/mcp/tools/get_context` with `Authorization: Bearer <token>`. Expect concatenated docs.
5. **Call `consultar_bq`** with:
   ```sql
   SELECT COUNT(*) AS n FROM `soma_online_refined.refined_captacao` WHERE data_venda >= CURRENT_DATE()
   ```
   Expect `row_count: 1`, `bytes_billed > 0`.
6. **Call `publicar_dashboard`** with a small HTML blob. Expect commit on `main` and a file under `analyses/artur.lemos@somagrupo.com.br/`.
7. **Check BQ audit**: `SELECT labels FROM \`region-us\`.INFORMATION_SCHEMA.JOBS_BY_PROJECT WHERE creation_time >= CURRENT_TIMESTAMP() - INTERVAL 1 HOUR AND labels.source = 'mcp_dispatch'` → email present.
8. **Check SQLite audit**: `sqlite3 /var/mcp/audit.db "SELECT * FROM audit ORDER BY ts DESC LIMIT 5"` → three rows for the 3 tool calls.
9. **Invalid exec**: temporarily remove your email from allowlist → call `/auth/callback` → expect 403.
10. **Token expiry**: set `access_token_ttl_s=5`, log in, wait 10s, call tool → expect 401 with "run: mcp-login".

## Pass criteria
All 10 steps complete without manual intervention from outside the flow. Failure at any step blocks rollout.
```

- [ ] **Step 2: Commit**

```bash
git add mcp-server/tests/integration/
git commit -m "docs(mcp): end-to-end integration runbook"
```

---

### Task 8.2: Claude Team connector registration docs

**Files:**
- Create: `mcp-server/infra/claude-team/connector.md`

- [ ] **Step 1: Write connector doc**

Create `mcp-server/infra/claude-team/connector.md`:
```markdown
# Registering the MCP server in Claude Team (Azzas workspace)

## Owner action (admin)

1. Claude Team admin → Settings → Connectors → Add custom connector.
2. Name: `Azzas Analytics (BigQuery)`.
3. URL: `https://mcp-azzas.<corp-domain>/mcp` (SSE endpoint).
4. Auth: Custom — header `Authorization: Bearer ${MCP_TOKEN}`. The connector substitutes per-user tokens from each exec's `~/.mcp/credentials.json` via the MCP client extension. (If Claude Team doesn't support per-user bearer from connectors at rollout time, fall back to OAuth-2.0 client credentials path using the `/auth/start` redirect.)
5. System prompt (workspace-scoped):
   ```
   You have access to Azzas BigQuery analytics via 4 tools (get_context, consultar_bq, listar_analises, publicar_dashboard).
   On every session start: call get_context once to prime yourself with schema + business rules.
   Never invent numbers — if a field is missing, say so.
   After a successful consultar_bq, suggest publicar_dashboard if the exec may want a saved dashboard.
   ```
6. Scope: publish to the Execs group only (not entire workspace).

## Exec onboarding (per person)

Give them a one-page PDF with:
- `brew install` or direct binary for `mcp-login`.
- Run `mcp-login`, click through Azure AD SSO.
- Mention: token expires every 30 min; rerun `mcp-login` if you see "token expired".
- Sample queries they can paste into Claude:
  - "me dá venda da FARM ontem"
  - "resumo YTD por canal"
  - "lista minhas análises salvas"
```

- [ ] **Step 2: Commit**

```bash
git add mcp-server/infra/claude-team/
git commit -m "docs(mcp): Claude Team connector registration + exec onboarding"
```

---

### Task 8.3: Update top-level README with MCP context

**Files:**
- Modify: `README.md` (repo root)

- [ ] **Step 1: Add a pointer section**

Read current `README.md` first (since it's an existing file).

Append a section:
```markdown

## Exec dispatch via MCP (beta)

This repo also hosts a Python MCP server (`mcp-server/`) that lets Azzas executives run BigQuery analyses and publish dashboards to this portal directly from Claude Team on mobile, gated by Azure AD SSO + allowlist.

- Architecture spec: `docs/superpowers/specs/2026-04-18-exec-mcp-dispatch-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-18-exec-mcp-dispatch.md`
- MCP server code: `mcp-server/`

Running status: built but not yet connected to the Azzas workspace. Connect via `mcp-server/infra/claude-team/connector.md`.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: surface exec MCP dispatch in top-level README"
```

---

## Self-review summary

This plan covers all sections of the spec:

- **§4.1 Components**: Mac mini deploy (Task 7.3), MCP server (all of Phases 0–4), Cloudflare Tunnel (7.4), Claude Team connector (8.2), BigQuery labels (2.2), repo write scoping (3.1), Vercel auto-deploy (unchanged — covered by 3.3 push).
- **§4.2 Fluxo**: progress reporting is in 2.3 (consultar_bq) and 3.4 (publicar_dashboard); end-to-end covered in 8.1.
- **§4.3 Tools**: `get_context` (1.1), `consultar_bq` (2.3), `listar_analises` (4.1), `publicar_dashboard` (3.4).
- **§4.4 Infrastructure**: Dockerfile (7.1), launchd plists (7.3), Cloudflare (7.4).
- **§5.1 Auth**: Azure AD (5.2), JWT (5.3), auth routes (5.4), middleware (5.5), mcp-login CLI (5.6).
- **§5.2 BQ blast radius**: SA labels + bytes billed (2.2), SQL validator (2.1).
- **§5.3 Repo blast radius**: path sandbox (3.1), pinned commit author (3.3).
- **§5.4 Audit**: SQLite writer (6.1), anomaly detector (6.2), retention purge (6.3).
- **§5.5 Host**: launchd + Docker non-root user (7.1, 7.3).
- **§5.6 Edge**: Cloudflare Tunnel docs (7.4).
- **§5.7 Allowlist**: loader (5.1), wired into auth (5.4, 5.5).
- **§6 Progress feedback**: `ctx.info(...)` calls through all tools (Phases 2, 3, 4).
- **§9 Risks**: mitigated by design (TTL 30 min is in settings; SQL validator is in 2.1; keychain in 7.3; launchd KeepAlive in 7.3; SA label queries verified in 8.1).
- **§10 Success criteria**: verified in 8.1 runbook.

No placeholders, every step has code or exact commands, type names consistent (`BqClient`, `AuditLog`, `TokenIssuer`, `AuthContext`, `Allowlist`, `GitOps`, `LibraryEntry`) across the plan.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-18-exec-mcp-dispatch.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute in this session using `executing-plans`, batch with checkpoints.

Which approach do you want?
