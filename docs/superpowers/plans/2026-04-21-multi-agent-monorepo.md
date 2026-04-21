# Multi-Agent Monorepo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganizar o repo em um monorepo com `packages/mcp-core/` compartilhado, `agents/<domain>/` isolados por domínio, `portal/` para o frontend Vercel, e `shared/context/` para princípios e dimensões comuns.

**Architecture:** O `mcp-server/` atual é dividido em `packages/mcp-core/` (infraestrutura compartilhada: auth, audit, BQ, SQL validator) e `agents/vendas-linx/` (configuração + contexto específico). O frontend Vercel move para `portal/`. Novos agentes são criados via `scripts/new-agent.sh`.

**Tech Stack:** Python 3.13, uv workspaces, FastMCP, Google Cloud BigQuery, PyJWT, Railway, Vercel

---

## Notas de arquitetura

- **`/health`** já existe em `auth_routes.py` — sem alteração necessária no Dockerfile health check.
- **`dev_server.py`** importa `from mcp_exec.server import mcp` (módulo-level). Na nova estrutura `mcp` é retornado por `build_mcp_app()` e não existe como módulo. **Não copiar** para mcp-core — é obsoleto. Dev mode usa `MCP_DEV_EXEC_EMAIL` com o servidor normal.
- **`alerts.py`** e **`bridge.py`** são seguros de copiar — só importam módulos que também serão movidos.
- **`PyJWKClient`** (Azure token validation) deve ser instanciado uma vez e cacheado — não por request.
- **`uv.lock`** deve ser regenerado após criar o workspace e após cada novo agente.

---

## Checkpoint de produção

Ao concluir a **Fase 3 (Task 15)**, o agente `vendas-linx` está rodando na nova estrutura com comportamento idêntico ao atual. **Valide em produção antes de continuar para a Fase 4.** As fases 4+ adicionam features de segurança e não bloqueiam o agente funcionar.

---

## Mapa de arquivos

### Criados
- `pyproject.toml` — workspace uv raiz
- `.dockerignore` — evita copiar node_modules, .git, etc.
- `packages/mcp-core/pyproject.toml`
- `packages/mcp-core/src/mcp_core/__init__.py`
- `packages/mcp-core/src/mcp_core/server_factory.py` — novo
- `packages/mcp-core/tests/` — testes migrados + novos
- `shared/context/analyst-principles.md`
- `shared/context/pii-rules.md`
- `shared/context/identidade-visual-azzas.md`
- `shared/context/TEMPLATE.md`
- `shared/context/dimensions/produto.md`
- `shared/context/dimensions/filiais.md`
- `shared/context/dimensions/colecao.md`
- `agents/vendas-linx/pyproject.toml`
- `agents/vendas-linx/Dockerfile`
- `agents/vendas-linx/scripts/entrypoint.sh`
- `agents/vendas-linx/railway.toml`
- `agents/vendas-linx/config/settings.toml`
- `agents/vendas-linx/config/allowed_execs.json`
- `agents/vendas-linx/src/agent/__init__.py`
- `agents/vendas-linx/src/agent/server.py`
- `agents/vendas-linx/src/agent/context/schema.md`
- `agents/vendas-linx/src/agent/context/business-rules.md`
- `agents/vendas-linx/src/agent/context/SKILL.md`
- `agents/vendas-linx/tests/__init__.py`
- `agents/vendas-linx/tests/test_server.py`
- `scripts/new-agent.sh`

### Modificados
- `packages/mcp-core/src/mcp_core/settings.py` — adiciona `domain` em `ServerSettings`
- `packages/mcp-core/src/mcp_core/sandbox.py` — paths com `domain`
- `packages/mcp-core/src/mcp_core/bq_client.py` — enforcement via dry-run + timeout
- `packages/mcp-core/src/mcp_core/context_loader.py` — dual-path (shared + agent)
- `packages/mcp-core/src/mcp_core/auth_middleware.py` — Azure SSO passthrough + PyJWKClient cache
- `CLAUDE.md` — seção "Como criar um novo agente"

### Distribuição de testes migrados

| Arquivo atual (`mcp-server/tests/`) | Destino |
|---|---|
| `test_allowlist.py` | `packages/mcp-core/tests/` |
| `test_audit.py` | `packages/mcp-core/tests/` |
| `test_auth_middleware.py` | `packages/mcp-core/tests/` |
| `test_auth_routes.py` | `packages/mcp-core/tests/` |
| `test_azure_auth.py` | `packages/mcp-core/tests/` |
| `test_bq_client.py` | `packages/mcp-core/tests/` |
| `test_context_loader.py` | `packages/mcp-core/tests/` |
| `test_git_ops.py` | `packages/mcp-core/tests/` |
| `test_jwt_tokens.py` | `packages/mcp-core/tests/` |
| `test_library.py` | `packages/mcp-core/tests/` |
| `test_sandbox.py` | `packages/mcp-core/tests/` |
| `test_settings.py` | `packages/mcp-core/tests/` |
| `test_sql_validator.py` | `packages/mcp-core/tests/` |
| `test_alerts.py` | `packages/mcp-core/tests/` |
| `test_cli_login.py` | `packages/mcp-core/tests/` |
| `test_consultar_bq.py` | `agents/vendas-linx/tests/` — testa tool específica |
| `test_listar_analises.py` | `agents/vendas-linx/tests/` — testa tool específica |
| `test_publicar_dashboard.py` | `agents/vendas-linx/tests/` — testa tool específica |

`test_sandbox.py` migra para mcp-core mas será **substituído** pela versão nova (com `domain`) no Task 6.

### Movidos (sem alteração de conteúdo)
- `mcp-server/src/mcp_exec/*.py` (exceto `server.py` e `dev_server.py`) → `packages/mcp-core/src/mcp_core/`
- `analyst principles.md` → `shared/context/analyst-principles.md`
- `schema.md` → `agents/vendas-linx/src/agent/context/schema.md`
- `business-rules.md` → `agents/vendas-linx/src/agent/context/business-rules.md`
- `SKILL.md` → `agents/vendas-linx/src/agent/context/SKILL.md`
- `index.html`, `api/`, `public/`, `middleware.js`, `msal-init.js`, `package.json`, `package-lock.json`, `vercel.json` → `portal/`
- `queries/` → `portal/queries/`
- `library/*.json` → `portal/library/vendas-linx/*.json`
- `analyses/<email>/` → `portal/analyses/vendas-linx/<email>/`

### Não copiados (obsoletos)
- `mcp-server/src/mcp_exec/server.py` — substituído por `server_factory.py` + `agents/*/server.py`
- `mcp-server/src/mcp_exec/dev_server.py` — obsoleto; dev mode usa `MCP_DEV_EXEC_EMAIL`

### Deletados (após validação em produção)
- `mcp-server/` — inteiro
- Arquivos de contexto na raiz (`analyst principles.md`, `schema.md`, etc.)
- Arquivos de frontend na raiz (`index.html`, `api/`, etc.)

---

## Fase 1: Workspace + mcp-core scaffold

### Task 1: Criar workspace uv raiz e .dockerignore

**Files:**
- Create: `pyproject.toml`
- Create: `.dockerignore`

- [ ] **Step 1: Criar `pyproject.toml` na raiz**

```toml
[tool.uv.workspace]
members = ["packages/mcp-core", "agents/*"]
```

- [ ] **Step 2: Criar `.dockerignore` na raiz**

```
.git
.github
.DS_Store
node_modules
__pycache__
*.pyc
*.pyo
.pytest_cache
.mypy_cache
.venv
.worktrees
docs/
analyses/
library/
*.html
*.db
.env
.env.*
mcp-server/
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml .dockerignore
git commit -m "chore: add uv workspace root and .dockerignore"
```

---

### Task 2: Criar estrutura do pacote mcp-core

**Files:**
- Create: `packages/mcp-core/pyproject.toml`
- Create: `packages/mcp-core/src/mcp_core/__init__.py`
- Create: `packages/mcp-core/tests/__init__.py`

- [ ] **Step 1: Criar diretórios**

```bash
mkdir -p packages/mcp-core/src/mcp_core
mkdir -p packages/mcp-core/tests
touch packages/mcp-core/src/mcp_core/__init__.py
touch packages/mcp-core/tests/__init__.py
```

- [ ] **Step 2: Criar `packages/mcp-core/pyproject.toml`**

```toml
[project]
name = "mcp-core"
version = "0.1.0"
description = "Shared MCP infrastructure for Azzas analytics agents"
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
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "pytest-mock>=3.14",
  "ruff>=0.6",
  "mypy>=1.20",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/mcp_core"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Gerar lockfile do workspace**

```bash
uv lock
```

Esperado: `uv.lock` criado ou atualizado na raiz do repo.

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/ uv.lock
git commit -m "chore: scaffold mcp-core package and generate workspace lockfile"
```

---

### Task 3: Copiar módulos de mcp_exec para mcp_core

**Files:**
- Copy: módulos de `mcp-server/src/mcp_exec/` → `packages/mcp-core/src/mcp_core/`

Não copiar `server.py` (substituído por `server_factory.py`) nem `dev_server.py` (obsoleto).

- [ ] **Step 1: Copiar todos os módulos válidos**

```bash
for mod in allowlist audit auth_middleware auth_routes azure_auth \
            bq_client bridge cli_login context_loader git_ops \
            jwt_tokens library sandbox settings sql_validator alerts; do
  cp "mcp-server/src/mcp_exec/${mod}.py" "packages/mcp-core/src/mcp_core/${mod}.py"
done
```

- [ ] **Step 2: Substituir imports `mcp_exec` → `mcp_core` (dois comandos separados)**

```bash
find packages/mcp-core/src/mcp_core -name "*.py" \
  -exec sed -i '' 's/from mcp_exec\./from mcp_core./g' {} +

find packages/mcp-core/src/mcp_core -name "*.py" \
  -exec sed -i '' 's/import mcp_exec\./import mcp_core./g' {} +
```

> **Linux (Railway/Docker):** remover o `''` após `-i` em ambos os comandos.

- [ ] **Step 3: Verificar que nenhum `mcp_exec` sobrou**

```bash
grep -r "mcp_exec" packages/mcp-core/src/
```

Esperado: nenhuma saída.

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/src/
git commit -m "chore: copy mcp_exec modules to mcp_core, update imports"
```

---

### Task 4: Migrar e distribuir testes

**Files:**
- Copy: testes para `packages/mcp-core/tests/` e `agents/vendas-linx/tests/` conforme tabela no mapa de arquivos acima.

- [ ] **Step 1: Copiar testes para mcp-core**

```bash
for t in test_allowlist test_audit test_auth_middleware test_auth_routes \
          test_azure_auth test_bq_client test_context_loader test_git_ops \
          test_jwt_tokens test_library test_sandbox test_settings \
          test_sql_validator test_alerts test_cli_login; do
  cp "mcp-server/tests/${t}.py" "packages/mcp-core/tests/${t}.py"
done
```

- [ ] **Step 2: Criar `agents/vendas-linx/tests/` e copiar testes específicos de tool**

```bash
mkdir -p agents/vendas-linx/tests
touch agents/vendas-linx/tests/__init__.py
for t in test_consultar_bq test_listar_analises test_publicar_dashboard; do
  cp "mcp-server/tests/${t}.py" "agents/vendas-linx/tests/${t}.py"
done
```

- [ ] **Step 3: Atualizar imports nos testes do mcp-core**

```bash
find packages/mcp-core/tests -name "*.py" \
  -exec sed -i '' 's/from mcp_exec\./from mcp_core./g' {} +

find packages/mcp-core/tests -name "*.py" \
  -exec sed -i '' 's/import mcp_exec\./import mcp_core./g' {} +
```

- [ ] **Step 4: Atualizar imports nos testes do agente**

```bash
find agents/vendas-linx/tests -name "*.py" \
  -exec sed -i '' 's/from mcp_exec\./from mcp_core./g' {} +

find agents/vendas-linx/tests -name "*.py" \
  -exec sed -i '' 's/import mcp_exec\./import mcp_core./g' {} +
```

- [ ] **Step 5: Instalar e rodar testes do mcp-core**

```bash
cd packages/mcp-core
uv sync
uv run pytest -x -q 2>&1 | head -50
```

Esperado: os testes que não dependem de `server.py` passam. Testes que importam `mcp_exec.server` vão falhar — **anote quais são** e remova temporariamente (esses serão reescritos nos Tasks 10-12).

- [ ] **Step 6: Commit**

```bash
git add packages/mcp-core/tests/ agents/vendas-linx/tests/
git commit -m "chore: distribute tests to mcp-core and vendas-linx agent"
```

---

## Fase 2: Novas features no mcp-core

### Task 5: Adicionar `domain` ao Settings

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/settings.py`
- Modify: `packages/mcp-core/tests/test_settings.py`

- [ ] **Step 1: Escrever testes falhando**

Adicionar ao final de `packages/mcp-core/tests/test_settings.py`:

```python
import pytest
from pydantic import ValidationError
from mcp_core.settings import Settings, load_settings


def test_server_settings_requires_domain():
    with pytest.raises(ValidationError):
        Settings.model_validate({
            "server": {"host": "0.0.0.0", "port": 3000},  # domain ausente
            "bigquery": {
                "project_id": "p", "max_bytes_billed": 1,
                "query_timeout_s": 60, "max_rows": 100, "allowed_datasets": ["d"],
            },
            "github": {
                "repo_path": "/r", "branch": "main",
                "author_name": "x", "author_email": "x@y.com",
            },
            "auth": {
                "jwt_issuer": "x", "access_token_ttl_s": 1800,
                "refresh_token_ttl_s": 2592000,
            },
            "audit": {"db_path": "./a.db", "retention_days": 90},
        })


def test_settings_domain_loads_from_toml(tmp_path):
    toml = tmp_path / "settings.toml"
    toml.write_text("""\
[server]
host = "0.0.0.0"
port = 3000
domain = "vendas-linx"

[bigquery]
project_id = "proj"
max_bytes_billed = 5000000000
query_timeout_s = 60
max_rows = 100000
allowed_datasets = ["silver_linx"]

[github]
repo_path = "/app/repo"
branch = "main"
author_name = "Bot"
author_email = "bot@x.com"

[auth]
jwt_issuer = "mcp-exec-azzas"
access_token_ttl_s = 1800
refresh_token_ttl_s = 2592000

[audit]
db_path = "./audit.db"
retention_days = 90
""")
    s = load_settings(toml)
    assert s.server.domain == "vendas-linx"
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
cd packages/mcp-core
uv run pytest tests/test_settings.py::test_server_settings_requires_domain -v
```

Esperado: FAIL — `ServerSettings` não tem campo `domain`.

- [ ] **Step 3: Adicionar `domain` ao `ServerSettings` e `_settings_from_env`**

Em `packages/mcp-core/src/mcp_core/settings.py`:

Substituir a classe `ServerSettings`:
```python
class ServerSettings(BaseModel):
    host: str
    port: int
    domain: str  # routes analyses/<domain>/ and library/<domain>/ paths
```

Em `_settings_from_env`, dentro de `ServerSettings(...)`, adicionar:
```python
    domain=os.environ["MCP_DOMAIN"],
```

Atualizar o comentário do campo `allowed_datasets` em `BigQuerySettings`:
```python
    allowed_datasets: list[str]  # enforced via BQ dry-run in bq_client._check_allowed_datasets
```

- [ ] **Step 4: Rodar testes**

```bash
uv run pytest tests/test_settings.py -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/settings.py packages/mcp-core/tests/test_settings.py
git commit -m "feat(mcp-core): add domain field to ServerSettings"
```

---

### Task 6: Atualizar sandbox.py com domain nos paths

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/sandbox.py`
- Modify: `packages/mcp-core/tests/test_sandbox.py`

- [ ] **Step 1: Escrever testes falhando**

Substituir o conteúdo de `packages/mcp-core/tests/test_sandbox.py`:

```python
import pytest
from pathlib import Path
from mcp_core.sandbox import exec_analysis_path, exec_library_path, PathSandboxError


def test_analysis_path_includes_domain(tmp_path):
    path = exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "report.html")
    assert path == tmp_path / "analyses" / "vendas-linx" / "user@soma.com.br" / "report.html"


def test_library_path_includes_domain(tmp_path):
    path = exec_library_path(tmp_path, "vendas-linx", "user@soma.com.br")
    assert path == tmp_path / "library" / "vendas-linx" / "user@soma.com.br.json"


def test_analysis_path_blocks_path_traversal(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "../escape.html")


def test_analysis_path_blocks_subdirectory_in_filename(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "sub/file.html")


def test_invalid_email_rejected(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "not-an-email", "file.html")


def test_invalid_domain_rejected(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "Domain With Spaces", "user@soma.com.br", "file.html")


def test_non_html_rejected(tmp_path):
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "file.csv")
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_sandbox.py -v
```

Esperado: FAIL — assinatura atual não tem `domain`.

- [ ] **Step 3: Reescrever `sandbox.py`**

Substituir o conteúdo de `packages/mcp-core/src/mcp_core/sandbox.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")  # min 1 char, lowercase, hyphens ok


class PathSandboxError(ValueError):
    pass


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.fullmatch(email):
        raise PathSandboxError(f"invalid exec_email: {email!r}")


def _validate_domain(domain: str) -> None:
    if not _DOMAIN_RE.fullmatch(domain):
        raise PathSandboxError(f"invalid domain: {domain!r}")


def _ensure_inside(base: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(base.resolve())
    except ValueError as e:
        raise PathSandboxError(f"path escapes sandbox: {target}") from e


def exec_analysis_path(repo_root: Path, domain: str, exec_email: str, filename: str) -> Path:
    _validate_domain(domain)
    _validate_email(exec_email)
    if not filename.endswith(".html") or len(filename) <= len(".html"):
        raise PathSandboxError("only non-empty .html files allowed in analyses/")
    if "/" in filename or "\\" in filename or ".." in filename:
        raise PathSandboxError(f"invalid filename: {filename!r}")
    base = repo_root / "analyses" / domain / exec_email
    target = base / filename
    _ensure_inside(base, target)
    return target


def exec_library_path(repo_root: Path, domain: str, exec_email: str) -> Path:
    _validate_domain(domain)
    _validate_email(exec_email)
    base = repo_root / "library" / domain
    target = base / f"{exec_email}.json"
    _ensure_inside(base, target)
    return target
```

- [ ] **Step 4: Rodar testes**

```bash
uv run pytest tests/test_sandbox.py -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/sandbox.py packages/mcp-core/tests/test_sandbox.py
git commit -m "feat(mcp-core): add domain to sandbox paths"
```

---

### Task 7: Enforcement de allowed_datasets via BQ dry-run

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/bq_client.py`
- Modify: `packages/mcp-core/tests/test_bq_client.py`

- [ ] **Step 1: Escrever testes falhando**

Adicionar ao final de `packages/mcp-core/tests/test_bq_client.py`:

```python
import pytest
from unittest.mock import MagicMock, call
from mcp_core.bq_client import BqClient, DatasetNotAllowedError
from mcp_core.settings import BigQuerySettings


def _settings(allowed: list[str]) -> BigQuerySettings:
    return BigQuerySettings(
        project_id="proj",
        max_bytes_billed=5_000_000_000,
        query_timeout_s=60,
        max_rows=100,
        allowed_datasets=allowed,
    )


def _table_ref(dataset_id: str):
    ref = MagicMock()
    ref.dataset_id = dataset_id
    return ref


def test_dry_run_blocks_unauthorized_dataset():
    mock_bq = MagicMock()
    dry_job = MagicMock()
    dry_job.referenced_tables = [_table_ref("silver_ecomm")]
    mock_bq.query.return_value = dry_job

    client = BqClient(settings=_settings(["silver_linx"]), bq=mock_bq)
    with pytest.raises(DatasetNotAllowedError, match="silver_ecomm"):
        client.run_query("SELECT 1", exec_email="user@soma.com.br")

    # Must NOT have executed a real query after a dry-run failure
    assert mock_bq.query.call_count == 1


def test_dry_run_allows_authorized_dataset():
    mock_bq = MagicMock()
    dry_job = MagicMock()
    dry_job.referenced_tables = [_table_ref("silver_linx")]

    real_job = MagicMock()
    real_job.result.return_value = iter([])
    real_job.total_bytes_billed = 100
    real_job.total_bytes_processed = 200

    mock_bq.query.side_effect = [dry_job, real_job]

    client = BqClient(settings=_settings(["silver_linx"]), bq=mock_bq)
    result = client.run_query("SELECT 1", exec_email="user@soma.com.br")
    assert result.bytes_billed == 100
    assert mock_bq.query.call_count == 2


def test_dry_run_first_call_has_dry_run_true():
    from google.cloud import bigquery as bq_mod
    mock_bq = MagicMock()
    dry_job = MagicMock()
    dry_job.referenced_tables = [_table_ref("silver_linx")]
    real_job = MagicMock()
    real_job.result.return_value = iter([])
    real_job.total_bytes_billed = 0
    real_job.total_bytes_processed = 0
    mock_bq.query.side_effect = [dry_job, real_job]

    client = BqClient(settings=_settings(["silver_linx"]), bq=mock_bq)
    client.run_query("SELECT 1", exec_email="user@soma.com.br")

    first_cfg = mock_bq.query.call_args_list[0][1]["job_config"]
    assert first_cfg.dry_run is True
    assert first_cfg.use_query_cache is False


def test_dry_run_query_without_tables_is_allowed():
    # SELECT 1 has no referenced tables — allowed regardless of allowed_datasets
    mock_bq = MagicMock()
    dry_job = MagicMock()
    dry_job.referenced_tables = []  # no tables referenced
    real_job = MagicMock()
    real_job.result.return_value = iter([])
    real_job.total_bytes_billed = 0
    real_job.total_bytes_processed = 0
    mock_bq.query.side_effect = [dry_job, real_job]

    client = BqClient(settings=_settings(["silver_linx"]), bq=mock_bq)
    result = client.run_query("SELECT 1", exec_email="user@soma.com.br")
    assert result.row_count == 0
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_bq_client.py -v -k "dry_run"
```

Esperado: FAIL — `DatasetNotAllowedError` não existe.

- [ ] **Step 3: Atualizar `bq_client.py`**

Após os imports existentes, adicionar:

```python
class DatasetNotAllowedError(ValueError):
    pass
```

Adicionar método `_check_allowed_datasets` à classe `BqClient`:

```python
    def _check_allowed_datasets(self, sql: str) -> None:
        """Run BQ dry-run to extract referenced datasets; raise if any is not allowed."""
        cfg = bigquery.QueryJobConfig(
            dry_run=True,
            use_query_cache=False,
            maximum_bytes_billed=self.settings.max_bytes_billed,
        )
        job = self.bq.query(sql, job_config=cfg)
        # job.result() is not needed for dry-run; referenced_tables is populated immediately
        for table_ref in job.referenced_tables:
            if table_ref.dataset_id not in self.settings.allowed_datasets:
                raise DatasetNotAllowedError(
                    f"dataset '{table_ref.dataset_id}' not in allowed_datasets "
                    f"{self.settings.allowed_datasets}"
                )
```

Atualizar o início de `run_query`:

```python
    def run_query(self, sql: str, exec_email: str) -> QueryResult:
        self._check_allowed_datasets(sql)  # raises DatasetNotAllowedError if unauthorized
        cfg = bigquery.QueryJobConfig(
            # ... resto igual
```

- [ ] **Step 4: Rodar todos os testes do bq_client**

```bash
uv run pytest tests/test_bq_client.py -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/bq_client.py packages/mcp-core/tests/test_bq_client.py
git commit -m "feat(mcp-core): enforce allowed_datasets via BQ dry-run"
```

---

### Task 8: Azure SSO passthrough no auth_middleware

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/auth_middleware.py`
- Modify: `packages/mcp-core/tests/test_auth_middleware.py`

O `PyJWKClient` faz HTTP ao Azure. Para não criar uma nova instância por request, ele é armazenado em `AuthContext` e reutilizado entre chamadas.

- [ ] **Step 1: Escrever testes falhando**

Adicionar ao final de `packages/mcp-core/tests/test_auth_middleware.py`:

```python
import time
import jwt as pyjwt
import pytest
from unittest.mock import MagicMock, patch
from mcp_core.auth_middleware import AuthContext, AuthError, extract_exec_email

TENANT_ID = "test-tenant"
CLIENT_ID = "test-client"


def _azure_token(email: str, expired: bool = False) -> str:
    now = int(time.time())
    return pyjwt.encode(
        {
            "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
            "aud": CLIENT_ID,
            "preferred_username": email,
            "exp": now - 10 if expired else now + 3600,
            "iat": now,
        },
        "secret",
        algorithm="HS256",
    )


def _make_ctx(allowed: list[str]) -> AuthContext:
    issuer = MagicMock()
    issuer.issuer = "mcp-exec-azzas"
    issuer.verify_access.side_effect = Exception("should not be called for Azure tokens")
    allowlist = MagicMock()
    allowlist.is_allowed.side_effect = lambda e: e in allowed
    return AuthContext(
        issuer=issuer,
        allowlist=allowlist,
        azure_tenant_id=TENANT_ID,
        azure_client_id=CLIENT_ID,
    )


def test_azure_token_accepted_when_on_allowlist():
    token = _azure_token("user@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    with patch("mcp_core.auth_middleware._validate_azure_signature", return_value=None):
        email = extract_exec_email(token, ctx)
    assert email == "user@soma.com.br"


def test_azure_token_rejected_when_not_on_allowlist():
    token = _azure_token("other@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    with patch("mcp_core.auth_middleware._validate_azure_signature", return_value=None):
        with pytest.raises(AuthError, match="not_on_allowlist"):
            extract_exec_email(token, ctx)


def test_unknown_issuer_rejected():
    token = pyjwt.encode(
        {"iss": "https://evil.example.com", "exp": int(time.time()) + 3600},
        "secret",
        algorithm="HS256",
    )
    ctx = _make_ctx([])
    with pytest.raises(AuthError, match="unknown token issuer"):
        extract_exec_email(token, ctx)


def test_azure_passthrough_not_configured_raises():
    token = _azure_token("user@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    ctx.azure_tenant_id = ""  # not configured
    with pytest.raises(AuthError, match="not configured"):
        extract_exec_email(token, ctx)


def test_jwks_client_reused_across_calls():
    """PyJWKClient should not be instantiated on every call."""
    token = _azure_token("user@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    with patch("mcp_core.auth_middleware._validate_azure_signature", return_value=None) as mock_v:
        extract_exec_email(token, ctx)
        extract_exec_email(token, ctx)
    # _validate_azure_signature is called twice but should use cached ctx
    assert mock_v.call_count == 2
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_auth_middleware.py -v -k "azure"
```

Esperado: FAIL — `AuthContext` não tem campos Azure.

- [ ] **Step 3: Reescrever `auth_middleware.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import jwt as pyjwt

from mcp_core.allowlist import Allowlist
from mcp_core.jwt_tokens import TokenError, TokenIssuer


class AuthError(RuntimeError):
    pass


@dataclass
class AuthContext:
    issuer: TokenIssuer
    allowlist: Allowlist
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    # PyJWKClient cached here — one HTTP fetch per process, not per request
    _jwks_client: object = field(default=None, init=False, repr=False)

    def _get_jwks_client(self) -> pyjwt.PyJWKClient:
        if self._jwks_client is None:
            jwks_uri = (
                f"https://login.microsoftonline.com"
                f"/{self.azure_tenant_id}/discovery/v2.0/keys"
            )
            self._jwks_client = pyjwt.PyJWKClient(
                jwks_uri, cache_jwk_set=True, lifespan=300
            )
        return self._jwks_client  # type: ignore[return-value]


def _peek_iss(token: str) -> str:
    """Decode `iss` claim without verifying the signature."""
    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
        return str(payload.get("iss", ""))
    except Exception as e:
        raise AuthError(f"malformed token: {e}") from e


def _validate_azure_signature(token: str, ctx: AuthContext) -> None:
    """Verify Azure AD token signature and audience using cached JWKS."""
    signing_key = ctx._get_jwks_client().get_signing_key_from_jwt(token)
    pyjwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=ctx.azure_client_id,
    )


def _extract_azure_email(token: str) -> str:
    payload = pyjwt.decode(token, options={"verify_signature": False})
    email = payload.get("preferred_username") or payload.get("upn") or ""
    if not email:
        raise AuthError("azure token missing preferred_username/upn claim")
    return cast(str, email)


def extract_exec_email(token: str, ctx: AuthContext) -> str:
    iss = _peek_iss(token)

    if iss == ctx.issuer.issuer:
        # Internal JWT issued by this server
        try:
            claims = ctx.issuer.verify_access(token)
        except TokenError as e:
            raise AuthError(f"invalid_token: {e}") from e
        email = cast(str, claims["email"])

    elif "login.microsoftonline.com" in iss:
        # Azure AD SSO passthrough — frontend sends its own token directly
        if not ctx.azure_tenant_id or not ctx.azure_client_id:
            raise AuthError("azure passthrough not configured on this agent")
        _validate_azure_signature(token, ctx)
        email = _extract_azure_email(token)

    else:
        raise AuthError(f"unknown token issuer: {iss!r}")

    if not ctx.allowlist.is_allowed(email):
        raise AuthError(f"not_on_allowlist: {email}")
    return email
```

- [ ] **Step 4: Rodar testes**

```bash
uv run pytest tests/test_auth_middleware.py -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/auth_middleware.py packages/mcp-core/tests/test_auth_middleware.py
git commit -m "feat(mcp-core): add Azure SSO passthrough with cached PyJWKClient"
```

---

### Task 9: context_loader dual-path (shared + agent)

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/context_loader.py`
- Modify: `packages/mcp-core/tests/test_context_loader.py`

- [ ] **Step 1: Escrever testes falhando**

Substituir `packages/mcp-core/tests/test_context_loader.py`:

```python
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
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_context_loader.py -v
```

Esperado: FAIL — assinatura `load_exec_context(repo_root)` diferente da nova.

- [ ] **Step 3: Reescrever `context_loader.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SHARED_DOCS = [
    "analyst-principles.md",
    "pii-rules.md",
    "identidade-visual-azzas.md",
    "TEMPLATE.md",
]

AGENT_DOCS = [
    "schema.md",
    "business-rules.md",
    "SKILL.md",
]

SKILL_ALLOWLIST = {"product-photos"}


@dataclass
class ExecContext:
    text: str
    allowed_tables: list[str]


def load_exec_context(agent_root: Path, shared_root: Path) -> ExecContext:
    """
    Merge two context layers:
    1. shared_root/ — analyst-principles, pii-rules, dimensions/*.md
    2. agent_root/context/ — schema.md, business-rules.md, SKILL.md

    Skills are loaded from <repo_root>/.claude/skills/ where repo_root
    is derived as shared_root.parent.parent (shared/context → repo root).
    """
    sections: list[tuple[str, str]] = []

    # Shared docs (optional — missing files are silently skipped)
    for doc in SHARED_DOCS:
        p = shared_root / doc
        if p.exists():
            sections.append((f"shared/{doc}", p.read_text()))

    # Shared dimensions
    dims_dir = shared_root / "dimensions"
    if dims_dir.exists():
        for dim in sorted(dims_dir.glob("*.md")):
            sections.append((f"shared/dimensions/{dim.name}", dim.read_text()))

    # Agent-specific context (optional)
    ctx_dir = agent_root / "context"
    for doc in AGENT_DOCS:
        p = ctx_dir / doc
        if p.exists():
            sections.append((doc, p.read_text()))

    # Skills from repo root .claude/skills/
    # shared_root = <repo_root>/shared/context → repo_root = shared_root.parent.parent
    repo_root = shared_root.parent.parent
    skills_dir = repo_root / ".claude" / "skills"
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            if skill_md.parent.name not in SKILL_ALLOWLIST:
                continue
            rel = str(skill_md.relative_to(repo_root))
            sections.append((rel, skill_md.read_text()))

    toc_lines = [
        "# Analytics Context",
        "",
        "Este bloco contém TODAS as regras e referências que você precisa. "
        "Skills listadas abaixo são padrões documentais aplicados inline — "
        "NÃO são ferramentas MCP separadas e não devem ser buscadas via tool_search.",
        "",
        "## Seções incluídas",
    ] + [f"- `{name}`" for name, _ in sections]

    parts = ["\n".join(toc_lines)] + [f"<!-- {name} -->\n{body}" for name, body in sections]
    return ExecContext(text="\n\n".join(parts), allowed_tables=[])
```

- [ ] **Step 4: Rodar testes**

```bash
uv run pytest tests/test_context_loader.py -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/context_loader.py packages/mcp-core/tests/test_context_loader.py
git commit -m "feat(mcp-core): context_loader accepts shared_root + agent_root"
```

---

### Task 10: Criar server_factory.py

**Files:**
- Create: `packages/mcp-core/src/mcp_core/server_factory.py`
- Create: `packages/mcp-core/tests/test_server_factory.py`

`_get_auth_context()` é cacheado com `lru_cache` para evitar instanciar `PyJWKClient` a cada request.

- [ ] **Step 1: Escrever testes**

```python
# packages/mcp-core/tests/test_server_factory.py
import os
import pytest
from unittest.mock import patch


ENV = {
    "MCP_PUBLIC_HOST": "test.example.com",
    "MCP_JWT_SECRET": "testsecret123456789012345678901",
    "MCP_AZURE_TENANT_ID": "tenant-id",
    "MCP_AZURE_CLIENT_ID": "client-id",
    "MCP_AZURE_CLIENT_SECRET": "client-secret",
}


def test_build_mcp_app_returns_app_and_main():
    with patch.dict(os.environ, ENV):
        from mcp_core.server_factory import build_mcp_app
        app, main = build_mcp_app(agent_name="test-agent")
    assert app is not None
    assert callable(main)


def test_build_mcp_app_registers_base_tools():
    with patch.dict(os.environ, ENV):
        from mcp_core.server_factory import build_mcp_app
        app, _ = build_mcp_app(agent_name="test-agent")
    # FastMCP stores tools in _tool_manager._tools dict
    registered = set(app._tool_manager._tools.keys())
    assert {"get_context", "consultar_bq", "publicar_dashboard", "listar_analises"}.issubset(registered)


def test_build_mcp_app_raises_without_jwt_secret():
    env_no_secret = {k: v for k, v in ENV.items() if k != "MCP_JWT_SECRET"}
    with patch.dict(os.environ, env_no_secret, clear=False):
        os.environ.pop("MCP_JWT_SECRET", None)
        from mcp_core.server_factory import build_mcp_app
        # build_mcp_app itself doesn't fail — _get_auth_context() fails at request time
        # but main() should fail if MCP_JWT_SECRET is absent
        _, main = build_mcp_app(agent_name="test-agent")
        with pytest.raises((RuntimeError, KeyError)):
            main()  # tries to read MCP_JWT_SECRET
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_server_factory.py::test_build_mcp_app_returns_app_and_main -v
```

Esperado: FAIL — `server_factory` não existe.

- [ ] **Step 3: Criar `server_factory.py`**

```python
# packages/mcp-core/src/mcp_core/server_factory.py
from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import os
import re
import subprocess
import time as _time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, cast

import uvicorn
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.streamable_http_manager import TransportSecuritySettings as _TSS

from mcp_core.allowlist import Allowlist
from mcp_core.audit import AuditLog
from mcp_core.auth_middleware import AuthContext, AuthError, extract_exec_email
from mcp_core.auth_routes import build_auth_app
from mcp_core.azure_auth import AzureAuth
from mcp_core.bq_client import BqClient, DatasetNotAllowedError
from mcp_core.context_loader import load_exec_context
from mcp_core.git_ops import GitOps
from mcp_core.jwt_tokens import TokenIssuer
from mcp_core.library import LibraryEntry, prepend_entry
from mcp_core.sandbox import PathSandboxError, exec_analysis_path, exec_library_path
from mcp_core.settings import load_settings
from mcp_core.sql_validator import SqlValidationError, validate_readonly_sql


def _repo_root() -> Path:
    return Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))


def _settings_path() -> Path:
    return Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "analise"


def build_mcp_app(agent_name: str) -> tuple[FastMCP, Callable]:
    """
    Build a FastMCP app with the 4 base tools registered.

    Returns (app, main):
    - app:  FastMCP instance — use @app.tool() to add domain-specific tools
    - main: callable entrypoint — use as if __name__ == '__main__': main()

    All configuration is read from env vars and /app/config/settings.toml at runtime.
    """
    public_host = os.environ.get("MCP_PUBLIC_HOST", "localhost")

    mcp = FastMCP(
        agent_name,
        transport_security=_TSS(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                public_host,
                f"{public_host}:443",
                "localhost",
                "localhost:8080",
                "127.0.0.1",
            ],
            allowed_origins=[
                f"https://{public_host}",
                "https://claude.ai",
            ],
        ),
    )

    # ── Internal singletons ────────────────────────────────────────────────

    _audit: AuditLog | None = None

    def _get_audit() -> AuditLog:
        nonlocal _audit
        if _audit is None:
            settings = load_settings(_settings_path())
            _audit = AuditLog(db_path=Path(settings.audit.db_path))
        return _audit

    # lru_cache(1) caches the AuthContext across requests so PyJWKClient is reused
    @functools.lru_cache(maxsize=1)
    def _get_auth_context() -> AuthContext:
        settings = load_settings(_settings_path())
        secret = os.environ.get("MCP_JWT_SECRET")
        if not secret:
            raise RuntimeError(
                "MCP_JWT_SECRET environment variable is required. "
                "Generate with: openssl rand -hex 32"
            )
        issuer = TokenIssuer(
            secret=secret,
            issuer=settings.auth.jwt_issuer,
            access_ttl_s=settings.auth.access_token_ttl_s,
            refresh_ttl_s=settings.auth.refresh_token_ttl_s,
        )
        allowlist = Allowlist(
            path=Path(os.environ.get("MCP_ALLOWLIST", "/app/config/allowed_execs.json"))
        )
        return AuthContext(
            issuer=issuer,
            allowlist=allowlist,
            azure_tenant_id=os.environ.get("MCP_AZURE_TENANT_ID", ""),
            azure_client_id=os.environ.get("MCP_AZURE_CLIENT_ID", ""),
        )

    def _current_email(ctx: Context) -> str:
        if os.environ.get("MCP_DEV_EXEC_EMAIL"):
            return os.environ["MCP_DEV_EXEC_EMAIL"]
        headers = getattr(ctx.request_context.request, "headers", {}) or {}
        auth = headers.get("authorization") or headers.get("Authorization") or ""
        if not auth.lower().startswith("bearer "):
            raise AuthError("missing bearer token")
        token = auth.split(None, 1)[1].strip()
        return extract_exec_email(token=token, ctx=_get_auth_context())

    def _build_bq_client() -> BqClient:
        settings = load_settings(_settings_path())
        return BqClient(settings=settings.bigquery)

    # ── Base tool: get_context ─────────────────────────────────────────────
    @mcp.tool()
    def get_context(ctx: Context) -> dict[str, object]:
        """Return merged context: shared principles + agent schema + business rules.
        Call once at session start to prime Claude with domain knowledge."""
        _current_email(ctx)
        settings = load_settings(_settings_path())
        repo_root = _repo_root()
        domain = settings.server.domain
        shared_root = repo_root / "shared" / "context"
        agent_root = repo_root / "agents" / domain / "src" / "agent"
        loaded = load_exec_context(agent_root=agent_root, shared_root=shared_root)
        return {"text": loaded.text, "allowed_tables": loaded.allowed_tables}

    # ── Base tool: consultar_bq ────────────────────────────────────────────
    @mcp.tool()
    async def consultar_bq(sql: str, ctx: Context) -> dict[str, object]:
        """Run a SELECT query against BigQuery. Only SELECT/WITH is accepted.
        Returns rows, bytes_billed, bytes_processed."""
        exec_email = _current_email(ctx)
        start = _time.time()
        await ctx.report_progress(progress=0.0, total=1.0, message="validating query...")
        try:
            validate_readonly_sql(sql)
        except SqlValidationError as e:
            return {"error": f"sql_validation: {e}"}
        await ctx.report_progress(progress=0.2, total=1.0, message="checking dataset access...")
        client = _build_bq_client()
        try:
            result = client.run_query(sql=sql, exec_email=exec_email)
        except DatasetNotAllowedError as e:
            return {"error": f"dataset_not_allowed: {e}"}
        except Exception as e:
            return {"error": f"bq_execution: {e}"}
        duration_ms = int((_time.time() - start) * 1000)
        await ctx.report_progress(progress=1.0, total=1.0, message="query complete")
        _get_audit().record(
            exec_email=exec_email, tool="consultar_bq", sql=sql,
            bytes_scanned=cast(int, result.bytes_processed or 0),
            row_count=result.row_count,
            duration_ms=duration_ms,
            result="ok", error=None,
        )
        return {
            "rows": result.rows,
            "row_count": result.row_count,
            "bytes_billed": result.bytes_billed,
            "bytes_processed": result.bytes_processed,
            "truncated": result.truncated,
        }

    # ── Base tool: publicar_dashboard ─────────────────────────────────────
    @mcp.tool()
    async def publicar_dashboard(
        title: str, brand: str, period: str,
        description: str, html_content: str,
        tags: list[str], ctx: Context,
    ) -> dict[str, object]:
        """Publish an HTML dashboard to the exec's sandbox and update the library."""
        exec_email = _current_email(ctx)
        settings = load_settings(_settings_path())
        repo_root = _repo_root()
        domain = settings.server.domain

        today = datetime.now(timezone.utc).date().isoformat()
        short_hash = hashlib.sha1(
            f"{exec_email}{title}{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:8]
        slug = _slugify(title)
        filename = f"{slug}-{today}-{short_hash}.html"

        try:
            analysis_path = exec_analysis_path(repo_root, domain, exec_email, filename)
            library_path = exec_library_path(repo_root, domain, exec_email)
        except PathSandboxError as e:
            return {"error": f"path_sandbox: {e}"}

        await ctx.report_progress(progress=0.0, total=1.0, message="rendering dashboard...")
        analysis_path.parent.mkdir(parents=True, exist_ok=True)
        analysis_path.write_text(html_content)

        entry_id = f"{slug}-{short_hash}"
        link = f"/analyses/{domain}/{exec_email}/{filename}"
        library_path.parent.mkdir(parents=True, exist_ok=True)
        prepend_entry(
            library_path,
            LibraryEntry(
                id=entry_id, title=title, brand=brand, date=today,
                link=link, description=description, tags=tags, filename=filename,
            ),
        )

        await ctx.report_progress(progress=0.5, total=1.0, message="publishing to git...")
        git = GitOps(
            repo_path=repo_root,
            author_name=settings.github.author_name,
            author_email=settings.github.author_email,
            branch=settings.github.branch,
            push=os.environ.get("MCP_GIT_PUSH", "0") == "1",
        )
        try:
            sha = git.commit_paths(
                paths=[analysis_path, library_path],
                message=f"análise dispatched para {exec_email}: {title}",
            )
        except subprocess.CalledProcessError as e:
            output = e.output.decode(errors="replace") if e.output else str(e)
            return {"error": f"git_commit: {output.strip()}"}

        await ctx.report_progress(progress=1.0, total=1.0, message="dashboard published")
        return {"id": entry_id, "link": link, "published_at": today, "commit_sha": sha}

    # ── Base tool: listar_analises ─────────────────────────────────────────
    @mcp.tool()
    async def listar_analises(escopo: str, ctx: Context) -> dict[str, object]:
        """List analyses. escopo: 'mine' (own sandbox) or 'public' (shared library)."""
        exec_email = _current_email(ctx)
        settings = load_settings(_settings_path())
        repo_root = _repo_root()
        domain = settings.server.domain
        email_key = exec_email if escopo == "mine" else "public"
        lib = repo_root / "library" / domain / f"{email_key}.json"
        if not lib.exists():
            return {"items": []}
        try:
            data = json.loads(lib.read_text() or "[]")
        except json.JSONDecodeError as e:
            return {"error": f"library_parse: {e}"}
        return {"items": data}

    # ── main() entrypoint ──────────────────────────────────────────────────
    def main() -> None:
        settings = load_settings(_settings_path())
        azure = AzureAuth(
            tenant_id=os.environ["MCP_AZURE_TENANT_ID"],
            client_id=os.environ["MCP_AZURE_CLIENT_ID"],
            client_secret=os.environ["MCP_AZURE_CLIENT_SECRET"],
            redirect_uri=os.environ.get(
                "MCP_AZURE_REDIRECT_URI",
                f"https://{os.environ.get('MCP_PUBLIC_HOST', 'localhost')}/auth/callback",
            ),
        )
        secret = os.environ["MCP_JWT_SECRET"]
        issuer = TokenIssuer(
            secret=secret,
            issuer=settings.auth.jwt_issuer,
            access_ttl_s=settings.auth.access_token_ttl_s,
            refresh_ttl_s=settings.auth.refresh_token_ttl_s,
        )
        allowlist = Allowlist(
            path=Path(os.environ.get("MCP_ALLOWLIST", "/app/config/allowed_execs.json"))
        )

        @contextlib.asynccontextmanager
        async def lifespan(app):
            async with mcp.session_manager.run():
                yield

        auth_app = build_auth_app(
            azure=azure, issuer=issuer, allowlist=allowlist, lifespan=lifespan
        )
        auth_app.mount("/", mcp.streamable_http_app())
        port = int(os.environ.get("PORT", settings.server.port))
        uvicorn.run(auth_app, host=settings.server.host, port=port)

    return mcp, main
```

- [ ] **Step 4: Rodar testes**

```bash
uv run pytest tests/test_server_factory.py -v
```

Esperado: PASS.

- [ ] **Step 5: Rodar todos os testes do mcp-core**

```bash
uv run pytest -x -q
```

Esperado: sem regressões.

- [ ] **Step 6: Commit**

```bash
git add packages/mcp-core/src/mcp_core/server_factory.py packages/mcp-core/tests/test_server_factory.py
git commit -m "feat(mcp-core): add server_factory with 4 base tools and cached auth context"
```

---

## Fase 3: Migrar vendas-linx

### Task 11: Criar estrutura do agente vendas-linx

**Files:**
- Create: `agents/vendas-linx/pyproject.toml`
- Create: `agents/vendas-linx/config/settings.toml`
- Create: `agents/vendas-linx/config/allowed_execs.json`
- Create: `agents/vendas-linx/src/agent/__init__.py`

- [ ] **Step 1: Criar diretórios**

```bash
mkdir -p agents/vendas-linx/config
mkdir -p agents/vendas-linx/src/agent/context
mkdir -p agents/vendas-linx/scripts
touch agents/vendas-linx/src/agent/__init__.py
```

- [ ] **Step 2: Criar `agents/vendas-linx/pyproject.toml`**

```toml
[project]
name = "agent-vendas-linx"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["mcp-core"]

[project.scripts]
agent-server = "agent.server:main"

[tool.uv.sources]
mcp-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/agent"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Criar `agents/vendas-linx/config/settings.toml`**

```toml
[server]
host = "0.0.0.0"
port = 3000
domain = "vendas-linx"

[bigquery]
project_id = "soma-pipeline-prd"
max_bytes_billed = 5000000000
query_timeout_s = 60
max_rows = 100000
allowed_datasets = ["silver_linx"]

[github]
repo_path = "/app/repo"
branch = "main"
author_name = "Artur Lemos"
author_email = "abitlemos@gmail.com"

[auth]
jwt_issuer = "mcp-exec-azzas"
access_token_ttl_s = 1800
refresh_token_ttl_s = 2592000

[audit]
db_path = "/var/mcp/audit.db"
retention_days = 90
```

- [ ] **Step 4: Copiar `allowed_execs.json`**

```bash
cp mcp-server/config/allowed_execs.json agents/vendas-linx/config/
```

- [ ] **Step 5: Mover arquivos de contexto**

```bash
cp schema.md         agents/vendas-linx/src/agent/context/schema.md
cp business-rules.md agents/vendas-linx/src/agent/context/business-rules.md
cp SKILL.md          agents/vendas-linx/src/agent/context/SKILL.md
```

- [ ] **Step 6: Regenerar lockfile do workspace**

```bash
cd /caminho/para/raiz/do/repo
uv lock
```

- [ ] **Step 7: Commit**

```bash
git add agents/vendas-linx/ uv.lock
git commit -m "chore(vendas-linx): scaffold agent structure, config, and context"
```

---

### Task 12: Criar server.py e testes do agente

**Files:**
- Create: `agents/vendas-linx/src/agent/server.py`
- Create: `agents/vendas-linx/tests/__init__.py`
- Create: `agents/vendas-linx/tests/test_server.py`

- [ ] **Step 1: Criar `agents/vendas-linx/src/agent/server.py`**

```python
from mcp_core.server_factory import build_mcp_app

# Herda as 4 ferramentas base: get_context, consultar_bq, publicar_dashboard, listar_analises
app, main = build_mcp_app(agent_name="mcp-exec-vendas-linx")

# Adicione ferramentas específicas do domínio vendas-linx aqui, se necessário.

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Criar `agents/vendas-linx/tests/test_server.py`**

Testa que o agente importa corretamente e registra as ferramentas base.
Os testes de `test_consultar_bq.py`, `test_listar_analises.py` e `test_publicar_dashboard.py`
(copiados no Task 4) precisarão ser atualizados para importar de `mcp_core` — verificar e corrigir imports nesses arquivos agora.

```python
import os
import pytest
from unittest.mock import patch

ENV = {
    "MCP_PUBLIC_HOST": "test.example.com",
    "MCP_JWT_SECRET": "testsecret123456789012345678901",
    "MCP_AZURE_TENANT_ID": "tenant-id",
    "MCP_AZURE_CLIENT_ID": "client-id",
    "MCP_AZURE_CLIENT_SECRET": "client-secret",
}


def test_agent_imports_and_builds():
    with patch.dict(os.environ, ENV):
        from agent.server import app, main
    assert app is not None
    assert callable(main)


def test_agent_has_base_tools():
    with patch.dict(os.environ, ENV):
        from agent.server import app
    registered = set(app._tool_manager._tools.keys())
    assert {"get_context", "consultar_bq", "publicar_dashboard", "listar_analises"}.issubset(registered)


def test_agent_has_no_extra_tools_by_default():
    """vendas-linx has no domain-specific tools beyond the 4 base ones."""
    with patch.dict(os.environ, ENV):
        from agent.server import app
    registered = set(app._tool_manager._tools.keys())
    assert registered == {"get_context", "consultar_bq", "publicar_dashboard", "listar_analises"}
```

- [ ] **Step 3: Instalar e rodar testes**

```bash
cd agents/vendas-linx
uv sync
uv run pytest tests/test_server.py -v
```

Esperado: PASS.

- [ ] **Step 4: Commit**

```bash
git add agents/vendas-linx/src/agent/server.py agents/vendas-linx/tests/
git commit -m "feat(vendas-linx): add agent server using server_factory"
```

---

### Task 13: Dockerfile, entrypoint e railway.toml

**Files:**
- Create: `agents/vendas-linx/scripts/entrypoint.sh`
- Create: `agents/vendas-linx/Dockerfile`
- Create: `agents/vendas-linx/railway.toml`

**Paths em produção:**
- Código Python: `/app/agents/vendas-linx/` (baked no Docker)
- Config: `/app/config/settings.toml` (copiado de `agents/vendas-linx/config/` durante build)
- Repo clonado: `/app/repo/` (entrypoint clona em runtime)
- `MCP_SETTINGS=/app/config/settings.toml` (default, sem mudança)
- `MCP_REPO_ROOT=/app/repo` (default, sem mudança)

- [ ] **Step 1: Criar `agents/vendas-linx/scripts/entrypoint.sh`**

```bash
#!/bin/bash
set -e

# Clone or update the monorepo (provides shared/context + agents/*/context + analyses + library)
if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPO" ]; then
    if [ ! -d "/app/repo/.git" ]; then
        git clone "https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" /app/repo
    else
        git -C /app/repo pull --ff-only
    fi
fi

exec uv run python -m agent.server
```

```bash
chmod +x agents/vendas-linx/scripts/entrypoint.sh
```

- [ ] **Step 2: Criar `agents/vendas-linx/Dockerfile`**

Build context = raiz do repo (precisa do `pyproject.toml` do workspace e `packages/mcp-core/`).

```dockerfile
# Build context MUST be the repo root.
# Railway: Dockerfile path = agents/vendas-linx/Dockerfile, Build context = .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv --no-cache-dir

# Copy workspace root + mcp-core + this agent (explicit paths avoid copying unnecessary dirs)
COPY pyproject.toml uv.lock ./
COPY packages/mcp-core/ packages/mcp-core/
COPY agents/vendas-linx/ agents/vendas-linx/

# Install agent and its mcp-core dependency via uv workspace
WORKDIR /app/agents/vendas-linx
RUN uv sync --frozen

# Stage config to /app/config (default MCP_SETTINGS path)
RUN mkdir -p /app/config && cp -r /app/agents/vendas-linx/config/. /app/config/

COPY agents/vendas-linx/scripts/entrypoint.sh /app/scripts/entrypoint.sh

RUN useradd -m -u 1000 mcp \
    && mkdir -p /var/mcp /app/repo \
    && chown -R mcp:mcp /app /var/mcp \
    && chmod +x /app/scripts/entrypoint.sh
USER mcp

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:3000/health', timeout=5).raise_for_status()"

EXPOSE 3000

CMD ["/app/scripts/entrypoint.sh"]
```

- [ ] **Step 3: Criar `agents/vendas-linx/railway.toml`**

```toml
[build]
builder = "dockerfile"
dockerfilePath = "agents/vendas-linx/Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

- [ ] **Step 4: Testar build Docker localmente**

```bash
docker build -f agents/vendas-linx/Dockerfile -t agent-vendas-linx-test .
```

Esperado: build conclui sem erro.

```bash
docker run --rm \
  -e MCP_PUBLIC_HOST=localhost \
  -e MCP_JWT_SECRET=dev-secret-12345678901234567890 \
  -e MCP_AZURE_TENANT_ID=tenant \
  -e MCP_AZURE_CLIENT_ID=client \
  -e MCP_AZURE_CLIENT_SECRET=secret \
  -e MCP_DEV_EXEC_EMAIL=test@test.com \
  -p 3001:3000 \
  agent-vendas-linx-test
```

Esperado: servidor sobe na porta 3001. O repo não é clonado (sem `GITHUB_TOKEN`) — normal em teste local.

- [ ] **Step 5: Verificar `/health`**

Com o container rodando:

```bash
curl -s http://localhost:3001/health
```

Esperado: `{"status":"ok"}`.

- [ ] **Step 6: Commit**

```bash
git add agents/vendas-linx/Dockerfile agents/vendas-linx/scripts/ agents/vendas-linx/railway.toml
git commit -m "chore(vendas-linx): add Dockerfile, entrypoint, and railway.toml"
```

---

### Task 14: Teste de integração local com MCP SDK

Usa o cliente Python do MCP SDK (mesmo protocolo que Claude.ai usa) em vez de curl.

**Files:**
- Create: `agents/vendas-linx/tests/test_integration.py`

- [ ] **Step 1: Criar `test_integration.py`**

```python
"""
Integration test — requires the agent server to be running locally.
Start the server before running:

  MCP_DEV_EXEC_EMAIL=test@test.com \
  MCP_JWT_SECRET=dev-secret \
  MCP_REPO_ROOT=/tmp/test-repo \
  uv run python -m agent.server

Then run: uv run pytest tests/test_integration.py -v -m integration
"""
import os
import pytest

pytestmark = pytest.mark.integration  # skip unless -m integration


@pytest.fixture
def mcp_url():
    return os.environ.get("MCP_TEST_URL", "http://localhost:3000/mcp")


@pytest.fixture
def headers():
    token = os.environ.get("MCP_TEST_TOKEN", "")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


@pytest.mark.asyncio
async def test_health_endpoint(mcp_url):
    import httpx
    base = mcp_url.replace("/mcp", "")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{base}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_get_context_returns_text(mcp_url, headers):
    from mcp.client.streamable_http import streamable_http_client
    from mcp.client.session import ClientSession

    async with streamable_http_client(mcp_url, headers=headers) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool("get_context", {})
    assert result.content
    text = result.content[0].text if hasattr(result.content[0], "text") else str(result.content[0])
    assert "Analytics Context" in text


@pytest.mark.asyncio
async def test_unauthorized_dataset_blocked(mcp_url, headers):
    from mcp.client.streamable_http import streamable_http_client
    from mcp.client.session import ClientSession

    async with streamable_http_client(mcp_url, headers=headers) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(
                "consultar_bq",
                {"sql": "SELECT 1 FROM `soma-pipeline-prd.silver_ecomm.VENDAS` LIMIT 1"},
            )
    content_text = str(result.content)
    assert "dataset_not_allowed" in content_text
```

- [ ] **Step 2: Rodar os testes unitários (integration pulados por padrão)**

```bash
uv run pytest agents/vendas-linx/tests/ -v -m "not integration"
```

Esperado: PASS para testes unitários. Integration skippados.

- [ ] **Step 3: Rodar integração com servidor local (quando disponível)**

```bash
# Terminal 1:
cd agents/vendas-linx
MCP_DEV_EXEC_EMAIL=test@test.com \
MCP_JWT_SECRET=dev-secret-12345678901234 \
MCP_REPO_ROOT=../../portal \
uv run python -m agent.server

# Terminal 2:
uv run pytest tests/test_integration.py -v -m integration
```

Esperado: health e get_context passam. O teste de dataset bloqueado confirma o enforcement.

- [ ] **Step 4: Commit**

```bash
git add agents/vendas-linx/tests/test_integration.py
git commit -m "test(vendas-linx): add integration tests using MCP SDK client"
```

---

> ## ✅ CHECKPOINT DE PRODUÇÃO
>
> Antes de continuar: atualize o Railway service existente — Dockerfile path = `agents/vendas-linx/Dockerfile`, build context = `.` (raiz). Adicione as variáveis `GITHUB_TOKEN`, `GITHUB_REPO` e `MCP_DOMAIN=vendas-linx`. Faça o deploy e valide `/health` + `get_context` em produção. Só então avance para a Fase 4.

---

## Fase 4: Shared context e portal

### Task 15: Criar shared/context/

**Files:**
- Create: `shared/context/analyst-principles.md`
- Create: `shared/context/pii-rules.md`
- Create: `shared/context/identidade-visual-azzas.md`
- Create: `shared/context/TEMPLATE.md`
- Create: `shared/context/dimensions/produto.md`
- Create: `shared/context/dimensions/filiais.md`
- Create: `shared/context/dimensions/colecao.md`

- [ ] **Step 1: Criar diretórios**

```bash
mkdir -p shared/context/dimensions
```

- [ ] **Step 2: Mover docs existentes**

```bash
cp "analyst principles.md" shared/context/analyst-principles.md
cp identidade-visual-azzas.md shared/context/identidade-visual-azzas.md
cp TEMPLATE.md shared/context/TEMPLATE.md
```

- [ ] **Step 3: Extrair pii-rules.md do CLAUDE.md**

Criar `shared/context/pii-rules.md` com o conteúdo da seção `## Proteção de Dados Pessoais (PII)` do `CLAUDE.md`. Copiar do início da seção `## Proteção` até antes da linha `## Regra de ouro`.

```bash
# Verificar o intervalo de linhas:
grep -n "## Proteção\|## Regra de ouro" CLAUDE.md
# Usar o intervalo correto abaixo (ajuste os números):
sed -n '7,90p' CLAUDE.md > shared/context/pii-rules.md
```

Abrir o arquivo e confirmar que o conteúdo está correto.

- [ ] **Step 4: Criar placeholders de dimensões**

```bash
printf '# Dimensão Produto\n\nCompartilhada entre todos os agentes.\nDocumente aqui as colunas de `PRODUTOS`, `PRODUTOS_PRECOS`, `PRODUTO_CORES`, `PRODUTOS_TAMANHOS`.\n' \
  > shared/context/dimensions/produto.md

printf '# Dimensão Filiais\n\nCompartilhada entre todos os agentes.\nDocumente aqui as colunas de `FILIAIS`, `LOJAS_REDE`, `LOJAS_PREVISAO_VENDAS`.\n' \
  > shared/context/dimensions/filiais.md

printf '# Dimensão Coleção\n\n(A definir — preencher com schema real antes de criar agentes que usem esta dimensão.)\n' \
  > shared/context/dimensions/colecao.md
```

- [ ] **Step 5: Commit**

```bash
git add shared/
git commit -m "chore: create shared/context with principles, pii-rules, and dimension stubs"
```

---

### Task 16: Mover frontend para portal/

**Files:**
- Move: `index.html`, `api`, `public`, `middleware.js`, `msal-init.js`, `package.json`, `package-lock.json`, `vercel.json`, `queries/` → `portal/`

- [ ] **Step 1: Criar diretório portal/**

```bash
mkdir -p portal
```

- [ ] **Step 2: Mover arquivos (sem trailing slash no source)**

```bash
git mv index.html     portal/index.html
git mv middleware.js  portal/middleware.js
git mv msal-init.js   portal/msal-init.js
git mv package.json   portal/package.json
git mv vercel.json    portal/vercel.json
git mv api            portal/api
git mv public         portal/public
git mv queries        portal/queries
```

Se `package-lock.json` existir na raiz:
```bash
git mv package-lock.json portal/package-lock.json
```

- [ ] **Step 3: Verificar se `vercel.json` tem paths que precisam de ajuste**

```bash
cat portal/vercel.json
```

Se houver rewrites ou routes que referenciam caminhos relativos (ex: `/api/...`), confirmar que continuam corretos após o move. Routes internas ao `portal/` não mudam.

- [ ] **Step 4: Mover `analyses/` e `library/`**

```bash
git mv analyses portal/analyses
git mv library  portal/library
```

- [ ] **Step 5: Commit**

```bash
git add portal/
git commit -m "chore: move frontend and data dirs to portal/"
```

---

### Task 17: Migrar library/ e analyses/ para estrutura de domínio

**Files:**
- Move: `portal/library/*.json` → `portal/library/vendas-linx/*.json`
- Move: `portal/analyses/<email>/` → `portal/analyses/vendas-linx/<email>/`

- [ ] **Step 1: Criar subdiretórios de domínio**

```bash
mkdir -p portal/library/vendas-linx
mkdir -p portal/analyses/vendas-linx
```

- [ ] **Step 2: Mover arquivos de library**

```bash
for f in portal/library/*.json; do
  [ -f "$f" ] && git mv "$f" portal/library/vendas-linx/
done
```

- [ ] **Step 3: Mover diretórios de analyses**

```bash
shopt -s nullglob
for d in portal/analyses/*/; do
  dirname=$(basename "$d")
  # Skip 'vendas-linx' (já no lugar), 'public' (diretório especial)
  if [ "$dirname" != "vendas-linx" ] && [ "$dirname" != "public" ]; then
    git mv "portal/analyses/$dirname" "portal/analyses/vendas-linx/$dirname"
  fi
done
shopt -u nullglob
```

- [ ] **Step 4: Verificar estrutura**

```bash
find portal/library portal/analyses -maxdepth 3 -not -path '*/.git*'
```

Esperado:
```
portal/library/vendas-linx/artur.lemos@somagrupo.com.br.json
portal/library/vendas-linx/public.json
portal/analyses/vendas-linx/<email>/...
```

- [ ] **Step 5: Commit**

```bash
git add portal/
git commit -m "chore: migrate library/ and analyses/ to domain subdirectory vendas-linx"
```

---

### Task 18: Reconfigurar Vercel

- [ ] **Step 1: Atualizar Root Directory no painel Vercel**

Acessar: Vercel → projeto `bq-analista` → Settings → General → Root Directory → definir como `portal`.

Isso causa redeploy automático.

- [ ] **Step 2: Verificar que o deploy conclui sem erro**

Aguardar o deploy e confirmar no painel que está "Ready".

- [ ] **Step 3: Verificar analyses existentes**

Acessar uma URL de análise publicada anteriormente e confirmar que carrega:
```
https://bq-analista.vercel.app/analyses/vendas-linx/<email>/<arquivo>.html
```

---

## Fase 5: Tooling e cleanup

### Task 19: Criar scripts/new-agent.sh

**Files:**
- Create: `scripts/new-agent.sh`

O script usa Python para substituições de texto (cross-platform, sem depender de `sed -i ''` macOS vs Linux).

- [ ] **Step 1: Criar o script**

```bash
mkdir -p scripts
```

```bash
cat > scripts/new-agent.sh << 'SCRIPT'
#!/usr/bin/env bash
# Usage: scripts/new-agent.sh <domain>
# Creates a new agent from the current vendas-linx agent as reference.
# Requirements: bash, python3 (for cross-platform string substitution)

set -euo pipefail

DOMAIN="${1:?Usage: new-agent.sh <domain>}"
AGENT_DIR="agents/$DOMAIN"
REF_DIR="agents/vendas-linx"
REPO_ROOT="$(git rev-parse --show-toplevel)"

cd "$REPO_ROOT"

if [ -d "$AGENT_DIR" ]; then
  echo "ERROR: $AGENT_DIR already exists" >&2
  exit 1
fi

# Validate domain format (lowercase, hyphens ok, no spaces)
if ! echo "$DOMAIN" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
  echo "ERROR: domain must be lowercase letters, digits, or hyphens (e.g. vendas-ecomm)" >&2
  exit 1
fi

echo "Creating agent: $DOMAIN (from $REF_DIR)"
cp -r "$REF_DIR" "$AGENT_DIR"

# Cross-platform string substitution via Python
python3 - "$AGENT_DIR" "$DOMAIN" << 'PYEOF'
import sys, re
from pathlib import Path

agent_dir = Path(sys.argv[1])
domain = sys.argv[2]

def replace_in_file(path: Path, old: str, new: str):
    content = path.read_text()
    if old in content:
        path.write_text(content.replace(old, new))

# pyproject.toml: update name
replace_in_file(agent_dir / "pyproject.toml", 'name = "agent-vendas-linx"', f'name = "agent-{domain}"')

# settings.toml: update domain and clear allowed_datasets
settings = agent_dir / "config" / "settings.toml"
content = settings.read_text()
content = content.replace('domain = "vendas-linx"', f'domain = "{domain}"')
content = re.sub(
    r'allowed_datasets\s*=\s*\[.*?\]',
    'allowed_datasets = []  # REQUIRED: set the datasets for this domain',
    content,
)
settings.write_text(content)

print(f"  ✓ pyproject.toml: name updated")
print(f"  ✓ settings.toml: domain={domain}, allowed_datasets cleared")
PYEOF

# Clear sensitive/domain-specific files
echo '{"allowed_emails": []}' > "$AGENT_DIR/config/allowed_execs.json"

printf '# Schema — %s\n\nDocumente aqui as tabelas do domínio %s.\n\nSiga o protocolo PII do CLAUDE.md antes de escrever qualquer coluna.\n' \
  "$DOMAIN" "$DOMAIN" > "$AGENT_DIR/src/agent/context/schema.md"

printf '# Business Rules — %s\n\nDocumente aqui as regras de negócio do domínio %s.\n' \
  "$DOMAIN" "$DOMAIN" > "$AGENT_DIR/src/agent/context/business-rules.md"

# Clear audit db if it was copied
rm -f "$AGENT_DIR/audit.db" "$AGENT_DIR"/*.db

echo ""
echo "Agent created at $AGENT_DIR"
echo ""
echo "Next steps:"
echo "  1. config/settings.toml      — set allowed_datasets"
echo "  2. config/allowed_execs.json — add authorized emails"
echo "  3. src/agent/context/schema.md         — document tables (PII first!)"
echo "  4. src/agent/context/business-rules.md — document rules"
echo "  5. uv lock  (from repo root)"
echo "  6. See CLAUDE.md 'Como criar um novo agente' for Railway setup"
SCRIPT

chmod +x scripts/new-agent.sh
```

- [ ] **Step 2: Testar o script**

```bash
scripts/new-agent.sh atacado
```

Verificar:
```bash
grep "domain" agents/atacado/config/settings.toml
# Esperado: domain = "atacado"

cat agents/atacado/config/allowed_execs.json
# Esperado: {"allowed_emails": []}

grep "allowed_datasets" agents/atacado/config/settings.toml
# Esperado: allowed_datasets = []  # REQUIRED: ...

grep "name" agents/atacado/pyproject.toml
# Esperado: name = "agent-atacado"
```

- [ ] **Step 3: Testar validação de domain inválido**

```bash
scripts/new-agent.sh "Domain Inválido" 2>&1 | grep ERROR
# Esperado: ERROR: domain must be lowercase...
```

- [ ] **Step 4: Deletar agente de teste**

```bash
rm -rf agents/atacado
```

- [ ] **Step 5: Commit**

```bash
git add scripts/new-agent.sh
git commit -m "chore: add cross-platform new-agent.sh scaffold script"
```

---

### Task 20: Atualizar CLAUDE.md com guia de novo agente

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Adicionar seção ao final do `CLAUDE.md`**

Abrir `CLAUDE.md` e adicionar após o conteúdo existente:

````markdown
---

## Como criar um novo agente

> **Pré-requisito:** a migração inicial (`mcp-server/` → `packages/mcp-core/` + `agents/vendas-linx/`) deve estar concluída. Verifique que `uv sync` roda sem erro na raiz do repo.
>
> Antes de começar: saiba responder — quais datasets do BigQuery esse agente acessa? Quem pode usar? Quais são as regras de negócio específicas?

**Passo 0 — Gere o agente**

```bash
scripts/new-agent.sh <seu-dominio>
```

Não use `cp -r` — o script garante cópia do estado atual, limpa configs sensíveis, e valida o nome do domínio.

**Passo 1 — Edite os arquivos obrigatórios**

| Arquivo | O que mudar |
|---|---|
| `config/settings.toml` | `allowed_datasets` — datasets BQ permitidos |
| `config/allowed_execs.json` | Emails autorizados neste agente |
| `src/agent/context/schema.md` | Tabelas, colunas, PKs, joins canônicos |
| `src/agent/context/business-rules.md` | Regras de negócio específicas |
| `src/agent/server.py` | Ferramentas extras do domínio (pode ficar vazio) |

**Dimensões compartilhadas:** se produto, filial ou coleção aparecem no schema, referencie `shared/context/dimensions/` — não duplique conteúdo.

**PII:** classifique cada coluna antes de escrever o schema. Colunas PII não entram. Dúvida → Protocolo de Recusa.

**Passo 2 — Atualize o lockfile e teste localmente**

```bash
# Na raiz do repo:
uv lock

# Credenciais GCP (obrigatório para acessar BigQuery):
gcloud auth application-default login

# Subir o agente em dev mode:
cd agents/<seu-dominio>
uv sync
MCP_DEV_EXEC_EMAIL=seu@somagrupo.com.br \
MCP_JWT_SECRET=dev-secret \
MCP_REPO_ROOT=../../portal \
uv run python -m agent.server
```

Verifique três coisas:
1. `GET http://localhost:3000/health` retorna `{"status":"ok"}`
2. `get_context` retorna schema do domínio + princípios compartilhados
3. Query em dataset fora de `allowed_datasets` retorna erro `dataset_not_allowed` **sem** `billed_bytes` nos logs

**Passo 3 — Escreva testes**

- Bug no core (auth, BQ, SQL validator) → `packages/mcp-core/tests/`
- Comportamento do agente → `agents/<dominio>/tests/`

Use `agents/vendas-linx/tests/` como referência.

**Passo 4 — Configure o Railway service**

1. Crie novo service no Railway apontando para este repo
2. Build: Dockerfile path = `agents/<dominio>/Dockerfile`, build context = `.`
3. Variáveis de ambiente:

| Variável | Instrução |
|---|---|
| `MCP_JWT_SECRET` | `openssl rand -hex 32` — **nunca reutilize de outro agente** |
| `MCP_PUBLIC_HOST` | URL gerada pelo Railway após o primeiro deploy |
| `MCP_AZURE_TENANT_ID` | Mesmo dos outros agentes |
| `MCP_AZURE_CLIENT_ID` | Mesmo dos outros agentes |
| `MCP_AZURE_CLIENT_SECRET` | Mesmo dos outros agentes |
| `GITHUB_TOKEN` | Token com permissão de push ao repo |
| `GITHUB_REPO` | `arturlemos/bq-analista` |
| `MCP_GIT_PUSH` | `1` |

4. Após Railway gerar a URL, atualize `MCP_PUBLIC_HOST` e faça redeploy.

**Passo 5 — Emita token para o usuário**

```bash
# No Railway shell ou localmente apontando para o service:
curl -H "x-admin-key: $MCP_ADMIN_KEY" \
  "https://<MCP_PUBLIC_HOST>/auth/issue-token?email=usuario@somagrupo.com.br&days=365"
```

**Passo 6 — Registre no Claude.ai**

- URL: `https://<MCP_PUBLIC_HOST>/mcp`
- Header: `Authorization: Bearer <token>`
- Confirme com `get_context` que o contexto do domínio está chegando.

**O que NÃO fazer**

- Não use `cp -r` — use `scripts/new-agent.sh`
- Não reimplemente auth, audit ou SQL validation no agente — mude no `mcp-core`
- Não duplique dimensões compartilhadas — referencie `shared/context/dimensions/`
- Não reutilize `MCP_JWT_SECRET` entre agentes
- Não suba sem validar enforcement de `allowed_datasets` (Passo 2, item 3)
````

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add new agent creation guide to CLAUDE.md"
```

---

### Task 21: Deletar mcp-server/ e cleanup de raiz

> **Só execute após validar o agente `vendas-linx` em produção rodando a partir de `agents/vendas-linx/`.**

- [ ] **Step 1: Verificar que nada mais referencia mcp-server/**

```bash
grep -r "mcp-server\|mcp_exec" . \
  --include="*.py" --include="*.toml" --include="*.sh" \
  --include="*.yml" --include="*.json" \
  --exclude-dir=".git" --exclude-dir="mcp-server"
```

Esperado: nenhuma referência ativa fora de `mcp-server/` em si.

- [ ] **Step 2: Deletar mcp-server/**

```bash
git rm -r mcp-server/
```

- [ ] **Step 3: Deletar arquivos de contexto movidos da raiz**

```bash
git rm "analyst principles.md" schema.md business-rules.md SKILL.md
git rm identidade-visual-azzas.md TEMPLATE.md
```

Verificar se ainda existem (podem já ter sido movidos em tarefas anteriores):
```bash
ls analyst\ principles.md schema.md business-rules.md SKILL.md 2>/dev/null || echo "already moved"
```

- [ ] **Step 4: Deletar arquivos de frontend movidos para portal/**

```bash
# Verificar o que ainda está na raiz
ls index.html middleware.js msal-init.js package.json package-lock.json vercel.json 2>/dev/null
git rm index.html middleware.js msal-init.js package.json vercel.json 2>/dev/null || true
git rm package-lock.json 2>/dev/null || true
```

- [ ] **Step 5: Commit final**

```bash
git add -A
git commit -m "chore: remove mcp-server/ and root-level files after migration"
```

---

## Verificação final

- [ ] `uv sync` na raiz do repo roda sem erro
- [ ] `cd packages/mcp-core && uv run pytest -q` — todos os testes passam
- [ ] `cd agents/vendas-linx && uv run pytest -q -m "not integration"` — todos passam
- [ ] `docker build -f agents/vendas-linx/Dockerfile -t test .` — conclui sem erro
- [ ] `curl http://localhost:<port>/health` → `{"status":"ok"}`
- [ ] Agente responde em produção Railway (health + get_context)
- [ ] Portal Vercel carrega em produção
- [ ] `scripts/new-agent.sh atacado && rm -rf agents/atacado` — sem erro
- [ ] `scripts/new-agent.sh "Bad Domain" 2>&1 | grep ERROR` — rejeita nome inválido
