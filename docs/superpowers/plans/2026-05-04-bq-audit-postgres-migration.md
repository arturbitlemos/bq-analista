# BQ Audit — Postgres Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate BQ query audit logs from ephemeral SQLite (wiped on Railway redeploy) to Neon Postgres, fix three silent error paths in `consultar_bq`, and update the admin page to query Postgres directly with a Chart.js usage graph.

**Architecture:** `PgAuditLog` in `audit.py` writes fire-and-forget to the existing `mcp_core.db` pool. `server_factory.py` selects `PgAuditLog` when `DATABASE_URL` is present in env (already set on Railway), falling back to `AuditLog` (SQLite) for local dev. The portal's `handleBqStats` drops the fan-out HTTP calls and queries Postgres directly with a `?days=` window.

**Tech Stack:** asyncpg (via existing `mcp_core.db` pool), Neon Postgres, Chart.js 4.4.3 (CDN), Neon serverless JS driver (already used by portal), pytest-asyncio (already in project).

**Deploy order:** agents (Railway) before portal (Vercel). The migration must be applied to the Neon DB before the first agent deploy.

---

## File Map

| File | Change |
|---|---|
| `packages/mcp-core/migrations/0002_create_bq_audit.sql` | Create |
| `packages/mcp-core/tests/conftest.py` | Modify — add `bq_audit` to TRUNCATE list |
| `packages/mcp-core/src/mcp_core/settings.py` | Modify — `database_url` field + `_ENV_OVERRIDES` entry |
| `packages/mcp-core/tests/test_settings.py` | Modify — 2 new tests |
| `packages/mcp-core/src/mcp_core/audit.py` | Modify — add `PgAuditLog` class |
| `packages/mcp-core/tests/test_audit.py` | Create |
| `packages/mcp-core/src/mcp_core/server_factory.py` | Modify — audit selection, `asyncio.create_task`, error paths |
| `packages/mcp-core/src/mcp_core/api_routes.py` | Modify — remove `/api/admin/bq-stats` + `audit_db_path` param |
| `packages/mcp-core/tests/test_bq_stats_endpoint.py` | Delete |
| `packages/mcp-core/tests/test_api_routes.py` | Create — 404 check for removed endpoint |
| `portal/api/admin/[action].js` | Modify — `handleBqStats` rewrite |
| `portal/admin.html` | Modify — BQ Stats first, chart, time selector, states |

---

## Task 1: SQL Migration + conftest

**Files:**
- Create: `packages/mcp-core/migrations/0002_create_bq_audit.sql`
- Modify: `packages/mcp-core/tests/conftest.py`

- [ ] **Step 1: Create the migration file**

```sql
-- packages/mcp-core/migrations/0002_create_bq_audit.sql
CREATE TABLE IF NOT EXISTS bq_audit (
  id            BIGSERIAL PRIMARY KEY,
  ts            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  exec_email    TEXT NOT NULL,
  agent         TEXT NOT NULL,
  tool          TEXT NOT NULL,
  sql           TEXT,
  bytes_scanned BIGINT  DEFAULT 0,
  row_count     INT     DEFAULT 0,
  duration_ms   INT     DEFAULT 0,
  result        TEXT    NOT NULL,
  error         TEXT
);
CREATE INDEX IF NOT EXISTS idx_bq_audit_ts   ON bq_audit (ts);
CREATE INDEX IF NOT EXISTS idx_bq_audit_exec ON bq_audit (exec_email);
```

- [ ] **Step 2: Apply migration to production and test databases**

Apply to the Neon DB that Railway agents use (same as `DATABASE_URL`):
```bash
psql "$DATABASE_URL" -f packages/mcp-core/migrations/0002_create_bq_audit.sql
```

Also apply to the test database used by the test suite:
```bash
psql "$DATABASE_URL_TEST" -f packages/mcp-core/migrations/0002_create_bq_audit.sql
```

If `psql` is unavailable, run the SQL through the Neon console or `neon sql`.

- [ ] **Step 3: Add `bq_audit` to conftest TRUNCATE**

Open `packages/mcp-core/tests/conftest.py`. The file currently reads:

```python
import os
import pytest
import pytest_asyncio
from mcp_core import db


@pytest_asyncio.fixture
async def db_pool():
    """Initialize pool and TRUNCATE tables before/after each test.

    NOTE: tests assume serial execution. Don't use pytest-xdist (-n) — TRUNCATE
    is destructive and parallel tests collide. If we need parallelism later,
    migrate to pytest-postgresql with ephemeral DB per worker.
    """
    if "DATABASE_URL_TEST" not in os.environ:
        pytest.skip("DATABASE_URL_TEST not set")
    os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_TEST"]
    await db.init_pool()
    pool = db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE analyses, audit_log RESTART IDENTITY CASCADE")
    yield
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE analyses, audit_log RESTART IDENTITY CASCADE")
    await db.close_pool()
```

Change both TRUNCATE statements to include `bq_audit`:

```python
await conn.execute("TRUNCATE analyses, audit_log, bq_audit RESTART IDENTITY CASCADE")
```

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/migrations/0002_create_bq_audit.sql packages/mcp-core/tests/conftest.py
git commit -m "feat(audit): create bq_audit Postgres table + update test truncate"
```

---

## Task 2: `AuditSettings.database_url` + `_ENV_OVERRIDES`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/settings.py`
- Modify: `packages/mcp-core/tests/test_settings.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/mcp-core/tests/test_settings.py`:

```python
def test_database_url_env_sets_audit_database_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DATABASE_URL in env populates settings.audit.database_url."""
    toml = tmp_path / "settings.toml"
    toml.write_text(
        '[server]\nhost="0.0.0.0"\nport=3000\ndomain="d"\n'
        '[bigquery]\nproject_id="p"\nmax_bytes_billed=1\n'
        'query_timeout_s=60\nmax_rows=100\nallowed_datasets=["x"]\n'
        '[github]\nrepo_path="/r"\nbranch="main"\n'
        'author_name="bot"\nauthor_email="bot@x.com"\n'
        '[auth]\njwt_issuer="i"\naccess_token_ttl_s=1\nrefresh_token_ttl_s=1\n'
        '[audit]\ndb_path="/a"\nretention_days=1\n'
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://neon/testdb")
    s = load_settings(toml)
    assert s.audit.database_url == "postgresql://neon/testdb"


def test_audit_database_url_is_none_when_env_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When DATABASE_URL is not set, settings.audit.database_url is None."""
    toml = tmp_path / "settings.toml"
    toml.write_text(
        '[server]\nhost="0.0.0.0"\nport=3000\ndomain="d"\n'
        '[bigquery]\nproject_id="p"\nmax_bytes_billed=1\n'
        'query_timeout_s=60\nmax_rows=100\nallowed_datasets=["x"]\n'
        '[github]\nrepo_path="/r"\nbranch="main"\n'
        'author_name="bot"\nauthor_email="bot@x.com"\n'
        '[auth]\njwt_issuer="i"\naccess_token_ttl_s=1\nrefresh_token_ttl_s=1\n'
        '[audit]\ndb_path="/a"\nretention_days=1\n'
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = load_settings(toml)
    assert s.audit.database_url is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/mcp-core
python -m pytest tests/test_settings.py::test_database_url_env_sets_audit_database_url tests/test_settings.py::test_audit_database_url_is_none_when_env_absent -v
```

Expected: FAIL — `AuditSettings has no field 'database_url'` (ValidationError or AttributeError)

- [ ] **Step 3: Add `database_url` to `AuditSettings` and `_ENV_OVERRIDES`**

In `packages/mcp-core/src/mcp_core/settings.py`:

```python
class AuditSettings(BaseModel):
    db_path: str
    retention_days: int = 90
    database_url: str | None = None
```

Add entry to `_ENV_OVERRIDES` (format is 3-tuple `(env_var, section, field)`). Note: `DATABASE_URL` intentionally deviates from the `MCP_*` prefix convention because Railway provides it with this exact name:

```python
_ENV_OVERRIDES: tuple[tuple[str, str, str], ...] = (
    ("MCP_BQ_PROJECT_ID", "bigquery", "project_id"),
    ("MCP_BQ_BILLING_PROJECT_ID", "bigquery", "billing_project_id"),
    ("MCP_GITHUB_AUTHOR_EMAIL", "github", "author_email"),
    ("MCP_GITHUB_AUTHOR_NAME", "github", "author_name"),
    ("MCP_GITHUB_BRANCH", "github", "branch"),
    ("DATABASE_URL", "audit", "database_url"),
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_settings.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/settings.py packages/mcp-core/tests/test_settings.py
git commit -m "feat(settings): add audit.database_url field and DATABASE_URL env override"
```

---

## Task 3: `PgAuditLog` in `audit.py`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/audit.py`
- Create: `packages/mcp-core/tests/test_audit.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/mcp-core/tests/test_audit.py`:

```python
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_core.audit import PgAuditLog


@asynccontextmanager
async def _fake_pool(mock_conn):
    """Minimal asyncpg pool context manager for testing."""
    mock_pool = MagicMock()

    @asynccontextmanager
    async def acquire():
        yield mock_conn

    mock_pool.acquire = acquire
    yield mock_pool


async def test_pg_audit_log_record_executes_insert():
    """record() calls conn.execute with an INSERT INTO bq_audit statement."""
    mock_conn = AsyncMock()
    async with _fake_pool(mock_conn) as mock_pool:
        with patch("mcp_core.db.get_pool", return_value=mock_pool):
            audit = PgAuditLog(agent_name="test-agent")
            await audit.record(
                exec_email="user@soma.com",
                tool="consultar_bq",
                sql="SELECT 1",
                bytes_scanned=1024,
                row_count=5,
                duration_ms=200,
                result="ok",
                error=None,
            )

    mock_conn.execute.assert_called_once()
    sql_stmt = mock_conn.execute.call_args[0][0]
    assert "INSERT INTO bq_audit" in sql_stmt
    positional = mock_conn.execute.call_args[0]
    assert "user@soma.com" in positional
    assert "test-agent" in positional
    assert "consultar_bq" in positional
    assert "ok" in positional


async def test_pg_audit_log_record_passes_all_fields():
    """record() passes all 9 value fields in the correct order."""
    mock_conn = AsyncMock()
    async with _fake_pool(mock_conn) as mock_pool:
        with patch("mcp_core.db.get_pool", return_value=mock_pool):
            audit = PgAuditLog(agent_name="ciclo-agent")
            await audit.record(
                exec_email="a@soma.com",
                tool="consultar_bq",
                sql="SELECT 2",
                bytes_scanned=2048,
                row_count=10,
                duration_ms=350,
                result="error",
                error="bq_execution: quota exceeded",
            )

    positional = mock_conn.execute.call_args[0]
    # $1=exec_email $2=agent $3=tool $4=sql $5=bytes $6=rows $7=duration $8=result $9=error
    assert positional[1] == "a@soma.com"
    assert positional[2] == "ciclo-agent"
    assert positional[3] == "consultar_bq"
    assert positional[4] == "SELECT 2"
    assert positional[5] == 2048
    assert positional[6] == 10
    assert positional[7] == 350
    assert positional[8] == "error"
    assert positional[9] == "bq_execution: quota exceeded"


async def test_pg_audit_log_record_swallows_db_errors(caplog):
    """record() catches DB exceptions and logs them without re-raising."""
    mock_conn = AsyncMock()
    mock_conn.execute.side_effect = RuntimeError("connection pool exhausted")
    async with _fake_pool(mock_conn) as mock_pool:
        with patch("mcp_core.db.get_pool", return_value=mock_pool):
            audit = PgAuditLog(agent_name="test-agent")
            with caplog.at_level(logging.ERROR, logger="mcp_core.audit"):
                await audit.record(
                    exec_email="user@soma.com",
                    tool="consultar_bq",
                    sql=None,
                    bytes_scanned=0,
                    row_count=0,
                    duration_ms=0,
                    result="error",
                    error="some error",
                )
    # Must not raise; must log the failure
    assert any("bq_audit" in r.message for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd packages/mcp-core
python -m pytest tests/test_audit.py -v
```

Expected: FAIL — `ImportError: cannot import name 'PgAuditLog' from 'mcp_core.audit'`

- [ ] **Step 3: Add `PgAuditLog` to `audit.py`**

Add to `packages/mcp-core/src/mcp_core/audit.py`. Append after the existing `AuditLog` class:

```python
import asyncio
import logging

logger = logging.getLogger(__name__)


class PgAuditLog:
    def __init__(self, agent_name: str) -> None:
        self._agent_name = agent_name

    async def record(
        self, *, exec_email: str, tool: str, sql: str | None,
        bytes_scanned: int, row_count: int, duration_ms: int,
        result: str, error: str | None,
    ) -> None:
        try:
            from mcp_core import db
            async with db.get_pool().acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO bq_audit
                      (exec_email, agent, tool, sql, bytes_scanned,
                       row_count, duration_ms, result, error)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    exec_email, self._agent_name, tool, sql,
                    bytes_scanned, row_count, duration_ms, result, error,
                )
        except Exception:
            logger.error("bq_audit insert failed", exc_info=True)
```

The top of `audit.py` should also have `import logging`. If the current file doesn't have it (it doesn't), add it:

```python
from __future__ import annotations

import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_audit.py -v
```

Expected: all 3 PASS

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/audit.py packages/mcp-core/tests/test_audit.py
git commit -m "feat(audit): add PgAuditLog — fire-and-forget writes to Postgres bq_audit"
```

---

## Task 4: `server_factory.py` — Audit Selection + Error Paths

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py`

This task has three sub-changes:
1. Add `import asyncio` (currently missing from imports)
2. Import `PgAuditLog` and update `_get_audit()` to select based on `settings.audit.database_url`
3. Wrap all `_get_audit().record(...)` calls in `asyncio.create_task()`
4. Add `record()` calls to the three currently-silent error paths in `consultar_bq`

> **Note on testing:** The audit selection logic and `consultar_bq` error path fixes live inside the `build_mcp_app` closure, making them hard to unit test without instrumenting the closure. Coverage comes from Task 3's `PgAuditLog` tests (behaviour) + Task 2's settings tests (selection condition) + code review of the error-path additions.

- [ ] **Step 1: Add `asyncio` to imports**

In `packages/mcp-core/src/mcp_core/server_factory.py`, find the stdlib import block (lines 1-14) and add `asyncio`:

```python
from __future__ import annotations

import asyncio
import contextlib
import functools
import hashlib
import json
import os
import re
import subprocess
import time as _time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal, cast
```

- [ ] **Step 2: Import `PgAuditLog` alongside `AuditLog`**

Find line 22:
```python
from mcp_core.audit import AuditLog
```

Replace with:
```python
from mcp_core.audit import AuditLog, PgAuditLog
```

- [ ] **Step 3: Update `_get_audit()` to select based on `database_url`**

Find the `_get_audit()` function inside `build_mcp_app` (currently around line 126-131):

```python
_audit: AuditLog | None = None

def _get_audit() -> AuditLog:
    nonlocal _audit
    if _audit is None:
        settings = _load_cached_state().settings
        _audit = AuditLog(db_path=Path(settings.audit.db_path))
    return _audit
```

Replace with:

```python
_audit: AuditLog | PgAuditLog | None = None

def _get_audit() -> AuditLog | PgAuditLog:
    nonlocal _audit
    if _audit is None:
        settings = _load_cached_state().settings
        if settings.audit.database_url:
            _audit = PgAuditLog(agent_name=agent_name)
        else:
            _audit = AuditLog(db_path=Path(settings.audit.db_path))
    return _audit
```

`agent_name` is available here because `_get_audit` is defined inside the `build_mcp_app(agent_name: str, ...)` closure.

- [ ] **Step 4: Rewrite `consultar_bq` with fire-and-forget and error recording**

Find `consultar_bq` (currently around lines 232-265). Replace the entire function body:

```python
@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True})
async def consultar_bq(sql: str, ctx: Context) -> dict[str, object]:
    """Run a SELECT query against BigQuery. Only SELECT/WITH is accepted.
    Returns rows, bytes_billed, bytes_processed."""
    exec_email = _current_email(ctx)
    start = _time.time()
    await ctx.report_progress(progress=0.0, total=1.0, message="validating query...")

    try:
        validate_readonly_sql(sql)
    except SqlValidationError as e:
        asyncio.create_task(_get_audit().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=f"sql_validation: {e}",
        ))
        return {"error": f"sql_validation: {e}"}

    await ctx.report_progress(progress=0.2, total=1.0, message="checking dataset access...")
    client = _load_cached_state().bq_client

    try:
        result = client.run_query(sql=sql, exec_email=exec_email)
    except DatasetNotAllowedError as e:
        asyncio.create_task(_get_audit().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=f"dataset_not_allowed: {e}",
        ))
        return {"error": f"dataset_not_allowed: {e}"}
    except Exception as e:
        asyncio.create_task(_get_audit().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=0, row_count=0,
            duration_ms=int((_time.time() - start) * 1000),
            result="error", error=f"bq_execution: {e}",
        ))
        return {"error": f"bq_execution: {e}"}

    duration_ms = int((_time.time() - start) * 1000)
    await ctx.report_progress(progress=1.0, total=1.0, message="query complete")
    asyncio.create_task(_get_audit().record(
        exec_email=exec_email, tool="consultar_bq", sql=sql,
        bytes_scanned=cast(int, result.bytes_processed or 0),
        row_count=result.row_count,
        duration_ms=duration_ms,
        result="ok", error=None,
    ))
    return {
        "rows": result.rows,
        "row_count": result.row_count,
        "bytes_billed": result.bytes_billed,
        "bytes_processed": result.bytes_processed,
        "truncated": result.truncated,
    }
```

- [ ] **Step 5: Run the existing server_factory tests**

```bash
cd packages/mcp-core
python -m pytest tests/test_server_factory.py -v
```

Expected: all existing tests PASS (tool registration tests don't exercise audit paths)

- [ ] **Step 6: Commit**

```bash
git add packages/mcp-core/src/mcp_core/server_factory.py
git commit -m "feat(server_factory): use PgAuditLog when DATABASE_URL set; record all consultar_bq error paths"
```

---

## Task 5: Remove `/api/admin/bq-stats` from `api_routes.py`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/api_routes.py`
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py` (call-site update)
- Delete: `packages/mcp-core/tests/test_bq_stats_endpoint.py`
- Create: `packages/mcp-core/tests/test_api_routes.py`

- [ ] **Step 1: Write a test for the removed endpoint returning 404**

Create `packages/mcp-core/tests/test_api_routes.py`:

```python
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_core.api_routes import register_api_routes
from mcp_core.auth_middleware import AuthContext


def _make_app() -> TestClient:
    app = FastAPI()
    register_api_routes(
        app,
        auth_ctx=MagicMock(spec=AuthContext),
        bq_factory=MagicMock(),
        blob_factory=MagicMock(),
    )
    return TestClient(app)


def test_bq_stats_endpoint_removed():
    """/api/admin/bq-stats must not exist after removing the SQLite fan-out."""
    client = _make_app()
    resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 404


def test_healthz_still_present():
    """/healthz must still respond after api_routes cleanup."""
    from unittest.mock import AsyncMock, patch as async_patch
    app = FastAPI()
    register_api_routes(
        app,
        auth_ctx=MagicMock(spec=AuthContext),
        bq_factory=MagicMock(),
        blob_factory=MagicMock(),
    )
    client = TestClient(app)
    with patch("mcp_core.api_routes.db") as mock_db:
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=MagicMock(fetchval=AsyncMock(return_value=1)))
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = client.get("/healthz")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd packages/mcp-core
python -m pytest tests/test_api_routes.py::test_bq_stats_endpoint_removed -v
```

Expected: FAIL — endpoint currently returns 200, not 404. (The `test_healthz_still_present` test will likely also fail due to `audit_db_path` kwarg — that's expected until Step 3.)

- [ ] **Step 3: Remove the endpoint and `audit_db_path` from `api_routes.py`**

Open `packages/mcp-core/src/mcp_core/api_routes.py`.

**Remove these imports** (no longer needed after removing SQLite endpoint):
```python
import sqlite3
import time
```

**Update `register_api_routes` signature** — remove `audit_db_path`:

```python
def register_api_routes(
    app: FastAPI,
    *,
    auth_ctx: AuthContext,
    bq_factory,
    blob_factory,
) -> None:
    """Register refresh route + /healthz on the given FastAPI app."""
```

**Delete the entire `/api/admin/bq-stats` endpoint** — remove from `@app.get("/api/admin/bq-stats")` through the closing `}` of the `return` statement (lines 109–174 in the original file).

The file after editing should contain only: imports, `_RefreshBody`, `_bearer_token`, `register_api_routes` with `/healthz` and `/api/refresh/{analysis_id}`.

- [ ] **Step 4: Update the call site in `server_factory.py`**

Find the `register_api_routes` call in `server_factory.py` (around line 630):

```python
register_api_routes(
    auth_app,
    auth_ctx=api_auth_ctx,
    bq_factory=lambda: _load_cached_state().bq_client,
    blob_factory=lambda: BlobClient(),
    audit_db_path=settings.audit.db_path,
)
```

Replace with (remove the `audit_db_path` kwarg):

```python
register_api_routes(
    auth_app,
    auth_ctx=api_auth_ctx,
    bq_factory=lambda: _load_cached_state().bq_client,
    blob_factory=lambda: BlobClient(),
)
```

- [ ] **Step 5: Delete the old test file**

```bash
git rm packages/mcp-core/tests/test_bq_stats_endpoint.py
```

- [ ] **Step 6: Run all mcp-core tests**

```bash
cd packages/mcp-core
python -m pytest tests/ -v
```

Expected: all PASS. Notably `test_bq_stats_endpoint_removed` and `test_healthz_still_present` should now pass.

- [ ] **Step 7: Commit**

```bash
git add packages/mcp-core/src/mcp_core/api_routes.py \
        packages/mcp-core/src/mcp_core/server_factory.py \
        packages/mcp-core/tests/test_api_routes.py
git commit -m "feat(api_routes): remove /api/admin/bq-stats SQLite endpoint; data now in Postgres"
```

---

## Task 6: Portal API — `handleBqStats` Rewrite

**Files:**
- Modify: `portal/api/admin/[action].js`

- [ ] **Step 1: Replace `handleBqStats`**

Open `portal/api/admin/[action].js`. The current `handleBqStats` function (lines 78–159) fans out via HTTP to each agent. Replace the entire function with the Postgres-direct version:

```js
async function handleBqStats(res, days) {
  const sql = getSql()

  const [totals, byUser, byDay, recentErrors, lastSeenByAgent] = await Promise.all([
    sql`
      SELECT COUNT(*)                                                     AS total_calls,
             SUM(CASE WHEN result = 'error' THEN 1 ELSE 0 END)           AS total_errors,
             SUM(bytes_scanned)                                           AS total_bytes_scanned,
             COUNT(DISTINCT exec_email)                                   AS distinct_users
      FROM bq_audit
      WHERE ts >= NOW() - make_interval(days => ${days})
    `.catch(() => null),

    sql`
      SELECT exec_email,
             COUNT(*)                                              AS total_calls,
             SUM(CASE WHEN result = 'error' THEN 1 ELSE 0 END)   AS errors,
             SUM(bytes_scanned)                                   AS total_bytes,
             ROUND(AVG(duration_ms))                             AS avg_duration_ms,
             MODE() WITHIN GROUP (ORDER BY agent)                AS top_agent
      FROM bq_audit
      WHERE ts >= NOW() - make_interval(days => ${days})
      GROUP BY exec_email
      ORDER BY total_calls DESC
    `.catch(() => null),

    sql`
      SELECT DATE_TRUNC('day', ts)::date AS day,
             exec_email,
             COUNT(*)                   AS n
      FROM bq_audit
      WHERE ts >= NOW() - make_interval(days => ${days})
      GROUP BY 1, 2
      ORDER BY 1
    `.catch(() => null),

    sql`
      SELECT ts, exec_email, agent, tool,
             LEFT(sql, 200) AS sql_preview,
             error, bytes_scanned
      FROM bq_audit
      WHERE result = 'error'
        AND ts >= NOW() - make_interval(days => ${days})
      ORDER BY ts DESC
      LIMIT 20
    `.catch(() => null),

    sql`
      SELECT agent, MAX(ts) AS last_seen
      FROM bq_audit
      GROUP BY agent
      ORDER BY agent
    `.catch(() => null),
  ])

  res.setHeader('cache-control', 'private, no-store')
  return res.status(200).json({
    totals: totals?.[0] ?? {},
    by_user: byUser ?? [],
    by_day: byDay ?? [],
    recent_errors: recentErrors ?? [],
    last_seen_by_agent: lastSeenByAgent ?? [],
  })
}
```

- [ ] **Step 2: Update the `days` parsing and router call**

Find the `module.exports` handler function (lines 161–173). Update `action === 'bq-stats'` to extract and validate `days`:

```js
module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'method not allowed' })

  const cookie = parseCookie(req.headers.cookie || '', 'session')
  const email = cookie ? verifySession(cookie, process.env.SESSION_SECRET) : null
  if (!email) return res.status(401).json({ error: 'not authenticated' })
  if (!isAdmin(email, process.env.ADMIN_EMAILS)) return res.status(403).json({ error: 'forbidden' })

  const { action } = req.query
  if (action === 'analytics') return handleAnalytics(res)
  if (action === 'bq-stats') {
    const days = Math.max(1, Math.min(90, parseInt(req.query.days, 10) || 30))
    return handleBqStats(res, days)
  }
  return res.status(404).json({ error: 'not found' })
}
```

- [ ] **Step 3: Remove unused imports**

The new `handleBqStats` no longer uses `mintProxyJwt` or `MANIFEST`. Remove these two lines from the top of the file if they are not used by any other function:

```js
// Remove these if unused:
const { mintProxyJwt } = require('../_helpers/proxy_jwt')
const { MANIFEST } = require('../mcp/_helpers/manifest')
```

Check the rest of the file first — if `handleAnalytics` does not use them either, delete both import lines.

- [ ] **Step 4: Manual test**

Deploy or run locally with `vercel dev`. Then:

1. Open `/admin` — should load without error
2. Open DevTools → Network → `/api/admin/bq-stats` — verify 200 with JSON containing `totals`, `by_user`, `by_day`, `recent_errors`, `last_seen_by_agent`
3. Try `?days=7`, `?days=90` — verify different counts
4. Try `?days=abc` — should default to 30 (no 500)
5. Try `?days=999` — should clamp to 90

- [ ] **Step 5: Commit**

```bash
git add portal/api/admin/[action].js
git commit -m "feat(portal/admin): replace bq-stats fan-out with direct Postgres queries"
```

---

## Task 7: Admin Page UI

**Files:**
- Modify: `portal/admin.html`

This task rewrites the BQ-stats rendering section of `admin.html`. The analytics section (`handleAnalytics` data) stays structurally unchanged.

- [ ] **Step 1: Add Chart.js CDN and mount-point div**

Find the closing `</style>` tag in `<head>`. After it, add:

```html
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
```

Find `<main><div id="root"><p class="msg">Carregando…</p></div></main>` and replace with two separate mount points:

```html
<main>
  <div id="bq-root"><p class="msg">Carregando BQ stats…</p></div>
  <div id="analytics-root"><p class="msg">Carregando analytics do portal…</p></div>
</main>
```

Add CSS for the time selector and chart container at the bottom of `<style>`:

```css
.time-btns { display: flex; gap: 8px; margin-bottom: 16px; }
.time-btn { padding: 4px 14px; border: 1px solid #e4e4e7; border-radius: 6px; background: #fff; cursor: pointer; font-size: .875rem; }
.time-btn.active { background: #18181b; color: #fff; border-color: #18181b; }
.chart-wrap { background: #fff; border: 1px solid #e4e4e7; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.chart-controls { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
select.user-select { font-size: .875rem; padding: 4px 8px; border: 1px solid #e4e4e7; border-radius: 6px; }
.agent-status { background: #fff; border: 1px solid #e4e4e7; border-radius: 8px; padding: 16px; margin-bottom: 16px; font-size: .875rem; }
.agent-status-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #f4f4f5; }
.agent-status-row:last-child { border-bottom: none; }
```

- [ ] **Step 2: Replace the render script**

Find `<script type="module">` and replace the entire script block (from `<script type="module">` to `</script>`) with the following:

```html
<script type="module">
  function escHtml(str) {
    return String(str ?? '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
  }

  function fmt(n) { return Number(n ?? 0).toLocaleString('pt-BR') }

  function fmtBytes(b) {
    b = Number(b ?? 0)
    if (b >= 1e12) return (b / 1e12).toFixed(1) + ' TB'
    if (b >= 1e9)  return (b / 1e9).toFixed(1) + ' GB'
    if (b >= 1e6)  return (b / 1e6).toFixed(1) + ' MB'
    if (b >= 1e3)  return (b / 1e3).toFixed(1) + ' KB'
    return b + ' B'
  }

  function fmtDate(ts) {
    const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' }) +
      ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
  }

  function fmtRelative(isoTs) {
    if (!isoTs) return 'Nunca'
    const diffMs = Date.now() - new Date(isoTs).getTime()
    const mins = Math.floor(diffMs / 60000)
    if (mins < 60) return `há ${mins}m`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `há ${hrs}h`
    return fmtDate(isoTs)
  }

  function badge(action) {
    const safe = escHtml(action)
    const cls = ['publish','refresh','share','archive','login_failed'].includes(action) ? action : ''
    return `<span class="badge ${cls}">${safe}</span>`
  }

  async function fetchJson(url) {
    const res = await fetch(url, { credentials: 'include' })
    if (res.status === 401) { location.href = '/'; throw new Error('unauthorized') }
    if (res.status === 403) throw new Error('forbidden')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  }

  // ── BQ Stats section ──────────────────────────────────────────────────────

  let _activeDays = 30
  let _chart = null
  let _byDay = []

  function selectDays(n) {
    _activeDays = n
    document.querySelectorAll('.time-btn').forEach(b => {
      b.classList.toggle('active', Number(b.dataset.days) === n)
    })
    renderBqStats(n)
  }

  function buildChartDataset(selectedEmail) {
    const rows = selectedEmail === '__all__'
      ? _byDay
      : _byDay.filter(r => r.exec_email === selectedEmail)
    const dayMap = {}
    for (const row of rows) {
      dayMap[row.day] = (dayMap[row.day] || 0) + Number(row.n)
    }
    const labels = Object.keys(dayMap).sort()
    return {
      labels,
      datasets: [{
        label: selectedEmail === '__all__' ? 'Total de queries' : selectedEmail,
        data: labels.map(d => dayMap[d]),
        tension: 0.3,
        fill: false,
        borderColor: '#2563eb',
        backgroundColor: '#2563eb',
        pointRadius: 3,
      }]
    }
  }

  function drawChart(selectedEmail) {
    if (_chart) { _chart.destroy(); _chart = null }
    const canvas = document.getElementById('bq-chart')
    if (!canvas) return
    _chart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: buildChartDataset(selectedEmail),
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { ticks: { maxTicksLimit: 10 } },
          y: { beginAtZero: true, ticks: { precision: 0 } }
        },
        plugins: { legend: { display: false } }
      }
    })
  }

  async function renderBqStats(days) {
    const root = document.getElementById('bq-root')
    root.innerHTML = `
      <p class="section-title">Queries BigQuery</p>
      <div class="time-btns">
        <button class="time-btn${days===7?' active':''}" data-days="7" onclick="selectDays(7)">7d</button>
        <button class="time-btn${days===30?' active':''}" data-days="30" onclick="selectDays(30)">30d</button>
        <button class="time-btn${days===90?' active':''}" data-days="90" onclick="selectDays(90)">90d</button>
      </div>
      <p class="msg">Carregando…</p>`

    let bq
    try {
      bq = await fetchJson(`/api/admin/bq-stats?days=${days}`)
    } catch (e) {
      root.innerHTML = `
        <p class="section-title">Queries BigQuery</p>
        <div class="time-btns">
          <button class="time-btn${days===7?' active':''}" data-days="7" onclick="selectDays(7)">7d</button>
          <button class="time-btn${days===30?' active':''}" data-days="30" onclick="selectDays(30)">30d</button>
          <button class="time-btn${days===90?' active':''}" data-days="90" onclick="selectDays(90)">90d</button>
        </div>
        <p class="msg error">Erro ao carregar BQ stats: ${escHtml(e.message)}
          <button onclick="renderBqStats(${days})" style="margin-left:8px;padding:2px 8px;cursor:pointer">Tentar novamente</button>
        </p>`
      return
    }

    _byDay = bq.by_day || []
    const t = bq.totals || {}
    const emails = [...new Set(_byDay.map(r => r.exec_email))].sort()

    const hasData = Number(t.total_calls) > 0

    let html = `
      <p class="section-title">Queries BigQuery — últimos ${days}d</p>
      <div class="time-btns">
        <button class="time-btn${days===7?' active':''}" data-days="7" onclick="selectDays(7)">7d</button>
        <button class="time-btn${days===30?' active':''}" data-days="30" onclick="selectDays(30)">30d</button>
        <button class="time-btn${days===90?' active':''}" data-days="90" onclick="selectDays(90)">90d</button>
      </div>`

    if (!hasData) {
      html += `<p class="msg" style="background:#fff;border-radius:8px;border:1px solid #e4e4e7">
        Sem queries registradas nos últimos ${days}d.</p>`
      root.innerHTML = html
      return
    }

    html += `<div class="cards">
      <div class="card"><div class="label">Total de queries</div><div class="value">${fmt(t.total_calls)}</div></div>
      <div class="card"><div class="label">Erros</div>
        <div class="value${Number(t.total_errors) > 0 ? ' warn' : ''}">${fmt(t.total_errors)}</div>
      </div>
      <div class="card"><div class="label">Bytes escaneados</div>
        <div class="value" style="font-size:1.25rem">${fmtBytes(t.total_bytes_scanned)}</div>
      </div>
      <div class="card"><div class="label">Usuários ativos</div><div class="value">${fmt(t.distinct_users)}</div></div>
    </div>`

    html += `<div class="chart-wrap">
      <div class="chart-controls">
        <span style="font-size:.8rem;font-weight:600;color:#52525b">USO NO TEMPO</span>
        <select id="bq-user-select" class="user-select">
          <option value="__all__">Todos os usuários</option>
          ${emails.map(e => `<option value="${escHtml(e)}">${escHtml(e)}</option>`).join('')}
        </select>
      </div>
      <div style="height:200px"><canvas id="bq-chart"></canvas></div>
    </div>`

    if (bq.by_user?.length) {
      html += `<p class="section-title">Por usuário</p>
      <table><thead><tr>
        <th>Email</th><th>Queries</th><th>Erros</th><th>Bytes</th><th>Avg ms</th><th>Agent principal</th>
      </tr></thead><tbody>`
      for (const u of bq.by_user) {
        html += `<tr>
          <td>${escHtml(u.exec_email)}</td>
          <td>${fmt(u.total_calls)}</td>
          <td class="${Number(u.errors) > 0 ? 'err-text' : ''}">${fmt(u.errors)}</td>
          <td>${fmtBytes(u.total_bytes)}</td>
          <td>${fmt(u.avg_duration_ms)}</td>
          <td><code>${escHtml(u.top_agent ?? '—')}</code></td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    if (bq.recent_errors?.length) {
      html += `<p class="section-title">Erros recentes</p>
      <table><thead><tr>
        <th>Quando</th><th>Usuário</th><th>Agent</th><th>SQL (preview)</th><th>Erro</th>
      </tr></thead><tbody>`
      for (const e of bq.recent_errors) {
        html += `<tr>
          <td>${escHtml(fmtDate(e.ts))}</td>
          <td>${escHtml(e.exec_email)}</td>
          <td><code>${escHtml(e.agent ?? '—')}</code></td>
          <td><code>${escHtml(e.sql_preview ?? '—')}</code></td>
          <td class="err-text">${escHtml(e.error ?? '—')}</td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    if (bq.last_seen_by_agent?.length) {
      html += `<p class="section-title">Último registro por agent</p>
      <div class="agent-status">`
      for (const row of bq.last_seen_by_agent) {
        html += `<div class="agent-status-row">
          <code>${escHtml(row.agent)}</code>
          <span style="color:#71717a">${escHtml(fmtRelative(row.last_seen))}</span>
        </div>`
      }
      html += `</div>`
    } else {
      html += `<p class="section-title">Último registro por agent</p>
        <p class="msg" style="background:#fff;border-radius:8px;border:1px solid #e4e4e7">Sem registros.</p>`
    }

    root.innerHTML = html

    // Chart.js initialisation — must run after innerHTML is set
    if (_chart) { _chart.destroy(); _chart = null }
    drawChart('__all__')
    const sel = document.getElementById('bq-user-select')
    if (sel) sel.addEventListener('change', () => drawChart(sel.value))
  }

  // ── Analytics section (portal events) ─────────────────────────────────────

  async function renderAnalytics() {
    const root = document.getElementById('analytics-root')
    let a
    try {
      a = await fetchJson('/api/admin/analytics')
    } catch (e) {
      if (e.message === 'unauthorized') return
      if (e.message === 'forbidden') {
        document.getElementById('bq-root').innerHTML = '<p class="msg error">⛔ Acesso restrito.</p>'
        root.innerHTML = ''
        return
      }
      root.innerHTML = `<p class="msg error">Erro ao carregar analytics: ${escHtml(e.message)}</p>`
      return
    }

    let html = ''

    if (a.summary) {
      const s = a.summary
      html += `<p class="section-title">Últimos 30 dias — Portal</p><div class="cards">
        <div class="card"><div class="label">Publicações</div><div class="value">${fmt(s.total_publishes)}</div></div>
        <div class="card"><div class="label">Refreshes</div><div class="value">${fmt(s.total_refreshes)}</div></div>
        <div class="card"><div class="label">Compartilhamentos</div><div class="value">${fmt(s.total_shares)}</div></div>
        <div class="card"><div class="label">Arquivamentos</div><div class="value">${fmt(s.total_archives)}</div></div>
        <div class="card"><div class="label">Usuários únicos</div><div class="value">${fmt(s.distinct_users)}</div></div>
        <div class="card"><div class="label">Logins falhos</div>
          <div class="value${Number(s.total_login_failures) > 0 ? ' warn' : ''}">${fmt(s.total_login_failures)}</div>
        </div>
      </div>`
    }

    if (a.by_action_by_day?.length) {
      const days = {}
      for (const row of a.by_action_by_day) {
        const day = row.day
        if (!days[day]) days[day] = { publish: 0, refresh: 0, share: 0, archive: 0 }
        days[day][row.action] = Number(row.n)
      }
      html += `<p class="section-title">Tendência — últimos 14 dias</p>
      <table><thead><tr>
        <th>Dia</th><th>Publicações</th><th>Refreshes</th><th>Compartilhamentos</th><th>Arquivamentos</th>
      </tr></thead><tbody>`
      for (const [day, counts] of Object.entries(days).sort().reverse()) {
        html += `<tr>
          <td>${escHtml(day)}</td>
          <td>${fmt(counts.publish)}</td>
          <td>${fmt(counts.refresh)}</td>
          <td>${fmt(counts.share)}</td>
          <td>${fmt(counts.archive)}</td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    if (a.top_users?.length) {
      html += `<p class="section-title">Usuários mais ativos (portal, 30d)</p>
      <table><thead><tr><th>Email</th><th>Ações</th></tr></thead><tbody>`
      for (const u of a.top_users) {
        html += `<tr><td>${escHtml(u.actor_email)}</td><td>${fmt(u.n)}</td></tr>`
      }
      html += `</tbody></table>`
    }

    if (a.top_analyses?.length) {
      html += `<p class="section-title">Análises mais acessadas (refresh + share, 30d)</p>
      <table><thead><tr><th>Título</th><th>ID</th><th>Acessos</th></tr></thead><tbody>`
      for (const r of a.top_analyses) {
        html += `<tr>
          <td>${escHtml(r.title ?? '—')}</td>
          <td><code>${escHtml(r.analysis_id)}</code></td>
          <td>${fmt(r.n)}</td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    if (a.recent_activity?.length) {
      html += `<p class="section-title">Atividade recente (30d)</p>
      <table><thead><tr><th>Quando</th><th>Usuário</th><th>Ação</th><th>Analysis ID</th></tr></thead><tbody>`
      for (const ev of a.recent_activity) {
        html += `<tr>
          <td>${escHtml(fmtDate(ev.occurred_at))}</td>
          <td>${escHtml(ev.actor_email)}</td>
          <td>${badge(ev.action)}</td>
          <td><code>${escHtml(ev.analysis_id ?? '—')}</code></td>
        </tr>`
      }
      html += `</tbody></table>`
    }

    root.innerHTML = html || '<p class="msg">Nenhum dado de portal disponível.</p>'
  }

  // ── Boot ───────────────────────────────────────────────────────────────────
  // BQ stats loads first (most important section), analytics loads in parallel
  renderBqStats(_activeDays)
  renderAnalytics()

  // Make selectDays accessible from inline onclick
  window.selectDays = selectDays
  window.renderBqStats = renderBqStats
</script>
```

- [ ] **Step 2: Run the full Python test suite to confirm no regressions**

```bash
cd packages/mcp-core
python -m pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 3: Manual test in browser**

Run `vercel dev` or open the deployed preview URL and navigate to `/admin`.

Check:
1. BQ Stats section loads first (above portal analytics)
2. Cards show total queries, errors, bytes (formatted e.g. "1.2 GB"), active users
3. "7d / 30d / 90d" buttons are visible; active button is highlighted; clicking changes data
4. Line chart appears with "Todos os usuários" selected by default
5. Dropdown lists each `exec_email` seen in the data
6. Selecting a specific email filters the chart to that user's query volume
7. "Por usuário" table has an "Agent principal" column
8. "Erros recentes" table shows Agent + SQL preview columns
9. "Último registro por agent" shows each agent name + relative time
10. Simulate API failure: temporarily break the URL → error message + "Tentar novamente" button appears
11. Portal analytics section still loads correctly below BQ stats

- [ ] **Step 4: Commit**

```bash
git add portal/admin.html
git commit -m "feat(admin): BQ stats first, Chart.js usage graph, time selector, error states"
```
