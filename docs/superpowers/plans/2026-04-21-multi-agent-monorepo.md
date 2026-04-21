# Multi-Agent Monorepo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganizar o repo em um monorepo com `packages/mcp-core/` compartilhado, `agents/<domain>/` isolados por domínio, `portal/` para o frontend Vercel, e `shared/context/` para princípios e dimensões comuns.

**Architecture:** O `mcp-server/` atual é dividido em `packages/mcp-core/` (infraestrutura compartilhada: auth, audit, BQ, SQL validator) e `agents/vendas-linx/` (configuração + contexto específico do domínio). O frontend Vercel move para `portal/`. Novos agentes são criados via `scripts/new-agent.sh` e implantados como Railway services independentes.

**Tech Stack:** Python 3.13, uv workspaces, FastMCP, Google Cloud BigQuery, PyJWT, Railway, Vercel

---

## Checkpoint de produção

Ao concluir a **Fase 3 (Task 15)**, o agente `vendas-linx` está rodando na nova estrutura com comportamento idêntico ao atual. **Valide em produção antes de continuar para a Fase 4.** As fases 4+ adicionam novas features de segurança e não são bloqueantes para o agente funcionar.

---

## Mapa de arquivos

### Criados
- `pyproject.toml` — workspace uv raiz
- `packages/mcp-core/pyproject.toml`
- `packages/mcp-core/src/mcp_core/__init__.py`
- `packages/mcp-core/src/mcp_core/server_factory.py` — novo
- `packages/mcp-core/tests/` — testes migrados + novos
- `shared/context/analyst-principles.md` — movido da raiz
- `shared/context/pii-rules.md` — extraído do CLAUDE.md
- `shared/context/identidade-visual-azzas.md` — movido da raiz
- `shared/context/TEMPLATE.md` — movido da raiz
- `shared/context/dimensions/produto.md`
- `shared/context/dimensions/filiais.md`
- `shared/context/dimensions/colecao.md`
- `agents/vendas-linx/pyproject.toml`
- `agents/vendas-linx/Dockerfile`
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
- `packages/mcp-core/src/mcp_core/sandbox.py` — adiciona `domain` nos paths
- `packages/mcp-core/src/mcp_core/bq_client.py` — enforcement via dry-run
- `packages/mcp-core/src/mcp_core/context_loader.py` — dual-path (shared + agent)
- `packages/mcp-core/src/mcp_core/auth_middleware.py` — Azure SSO passthrough
- `CLAUDE.md` — adiciona seção "Como criar um novo agente"

### Movidos (sem alteração de conteúdo)
- `mcp-server/src/mcp_exec/*.py` → `packages/mcp-core/src/mcp_core/*.py`
- `mcp-server/tests/*.py` → `packages/mcp-core/tests/` (maioria) + `agents/vendas-linx/tests/` (específicos)
- `analyst principles.md` → `shared/context/analyst-principles.md`
- `schema.md` → `agents/vendas-linx/src/agent/context/schema.md`
- `business-rules.md` → `agents/vendas-linx/src/agent/context/business-rules.md`
- `SKILL.md` → `agents/vendas-linx/src/agent/context/SKILL.md`
- `index.html`, `api/`, `public/`, `middleware.js`, etc. → `portal/`
- `library/*.json` → `portal/library/vendas-linx/*.json`
- `analyses/<email>/` → `portal/analyses/vendas-linx/<email>/`

### Deletados
- `mcp-server/` — após validação em produção

---

## Fase 1: Workspace + mcp-core scaffold

### Task 1: Criar workspace uv raiz

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Criar pyproject.toml na raiz**

```toml
[tool.uv.workspace]
members = ["packages/mcp-core", "agents/*"]
```

- [ ] **Step 2: Verificar que uv reconhece o workspace**

```bash
uv sync --dry-run
```

Esperado: sem erro. Se `packages/mcp-core` não existir ainda, o erro será sobre membros ausentes — normal, continuar.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add uv workspace root"
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

[project.optional-dependencies]
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

- [ ] **Step 3: Criar `packages/mcp-core/src/mcp_core/__init__.py`** (vazio)

```bash
touch packages/mcp-core/src/mcp_core/__init__.py
touch packages/mcp-core/tests/__init__.py
```

- [ ] **Step 4: Commit**

```bash
git add packages/
git commit -m "chore: scaffold mcp-core package"
```

---

### Task 3: Copiar módulos de mcp_exec para mcp_core

**Files:**
- Copy: `mcp-server/src/mcp_exec/*.py` → `packages/mcp-core/src/mcp_core/`

- [ ] **Step 1: Copiar todos os módulos**

```bash
cp mcp-server/src/mcp_exec/allowlist.py      packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/audit.py          packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/auth_middleware.py packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/auth_routes.py    packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/azure_auth.py     packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/bq_client.py      packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/bridge.py         packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/cli_login.py      packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/context_loader.py packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/dev_server.py     packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/git_ops.py        packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/jwt_tokens.py     packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/library.py        packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/sandbox.py        packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/settings.py       packages/mcp-core/src/mcp_core/
cp mcp-server/src/mcp_exec/sql_validator.py  packages/mcp-core/src/mcp_core/
```

Não copie `server.py` — o agente terá o seu próprio.

- [ ] **Step 2: Substituir todos os imports `mcp_exec` → `mcp_core`**

```bash
find packages/mcp-core/src/mcp_core -name "*.py" \
  -exec sed -i '' 's/from mcp_exec\./from mcp_core./g' {} + \
  -exec sed -i '' 's/import mcp_exec\./import mcp_core./g' {} +
```

No Linux (Railway/Docker), remover o `''` após `-i`:
```bash
find packages/mcp-core/src/mcp_core -name "*.py" \
  -exec sed -i 's/from mcp_exec\./from mcp_core./g' {} + \
  -exec sed -i 's/import mcp_exec\./import mcp_core./g' {} +
```

- [ ] **Step 3: Verificar que nenhum `mcp_exec` sobrou**

```bash
grep -r "mcp_exec" packages/mcp-core/src/
```

Esperado: nenhuma saída.

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/src/
git commit -m "chore: copy mcp_exec modules into mcp_core, update imports"
```

---

### Task 4: Migrar testes para mcp-core

**Files:**
- Copy: `mcp-server/tests/` → `packages/mcp-core/tests/`

- [ ] **Step 1: Copiar todos os arquivos de teste**

```bash
cp mcp-server/tests/*.py packages/mcp-core/tests/
```

- [ ] **Step 2: Atualizar imports nos testes**

```bash
find packages/mcp-core/tests -name "*.py" \
  -exec sed -i '' 's/from mcp_exec\./from mcp_core./g' {} + \
  -exec sed -i '' 's/import mcp_exec\./import mcp_core./g' {} +
```

- [ ] **Step 3: Instalar o pacote e rodar os testes**

```bash
cd packages/mcp-core
uv sync
uv run pytest -x -q
```

Esperado: todos os testes existentes passam (ou falham pelos mesmos motivos que falhavam antes — não introduzir novas falhas).

- [ ] **Step 4: Commit**

```bash
git add packages/mcp-core/tests/
git commit -m "chore: migrate tests to mcp-core"
```

---

## Fase 2: Novas features no mcp-core

### Task 5: Adicionar `domain` ao Settings

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/settings.py`
- Modify: `packages/mcp-core/tests/test_settings.py`

- [ ] **Step 1: Escrever teste falhando**

Em `packages/mcp-core/tests/test_settings.py`, adicionar:

```python
def test_settings_domain_required_in_server():
    from mcp_core.settings import Settings
    import pytest
    with pytest.raises(Exception):  # ValidationError
        Settings.model_validate({
            "server": {"host": "0.0.0.0", "port": 3000},  # domain ausente
            "bigquery": {"project_id": "p", "max_bytes_billed": 1, "query_timeout_s": 60, "max_rows": 100, "allowed_datasets": ["d"]},
            "github": {"repo_path": "/r", "branch": "main", "author_name": "x", "author_email": "x@y.com"},
            "auth": {"jwt_issuer": "x", "access_token_ttl_s": 1800, "refresh_token_ttl_s": 2592000},
            "audit": {"db_path": "./a.db", "retention_days": 90},
        })

def test_settings_domain_loads_from_toml(tmp_path):
    from mcp_core.settings import load_settings
    toml = tmp_path / "settings.toml"
    toml.write_text("""
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
uv run pytest tests/test_settings.py -v
```

Esperado: FAIL — `ServerSettings` não tem campo `domain`.

- [ ] **Step 3: Adicionar `domain` ao `ServerSettings` e ao `_settings_from_env`**

Em `packages/mcp-core/src/mcp_core/settings.py`, substituir a classe `ServerSettings`:

```python
class ServerSettings(BaseModel):
    host: str
    port: int
    domain: str  # routes analyses/<domain>/ and library/<domain>/ paths
```

E em `_settings_from_env`, adicionar `domain` dentro de `ServerSettings(...)`:

```python
server=ServerSettings(
    host="0.0.0.0",
    port=port,
    domain=os.environ["MCP_DOMAIN"],  # required — set per agent in Railway
),
```

- [ ] **Step 4: Rodar testes e confirmar passe**

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

### Task 6: Atualizar sandbox.py para incluir domain nos paths

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/sandbox.py`
- Modify: `packages/mcp-core/tests/test_sandbox.py`

- [ ] **Step 1: Escrever testes falhando**

Em `packages/mcp-core/tests/test_sandbox.py`, adicionar:

```python
from pathlib import Path
from mcp_core.sandbox import exec_analysis_path, exec_library_path

def test_analysis_path_includes_domain(tmp_path):
    path = exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "report.html")
    assert path == tmp_path / "analyses" / "vendas-linx" / "user@soma.com.br" / "report.html"

def test_library_path_includes_domain(tmp_path):
    path = exec_library_path(tmp_path, "vendas-linx", "user@soma.com.br")
    assert path == tmp_path / "library" / "vendas-linx" / "user@soma.com.br.json"

def test_analysis_path_blocks_escape(tmp_path):
    import pytest
    from mcp_core.sandbox import PathSandboxError
    with pytest.raises(PathSandboxError):
        exec_analysis_path(tmp_path, "vendas-linx", "user@soma.com.br", "../escape.html")
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_sandbox.py -v
```

Esperado: FAIL — assinatura atual não tem `domain`.

- [ ] **Step 3: Atualizar `sandbox.py`**

Substituir o conteúdo de `packages/mcp-core/src/mcp_core/sandbox.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_DOMAIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


class PathSandboxError(ValueError):
    pass


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.fullmatch(email):
        raise PathSandboxError(f"invalid exec_email: {email!r}")


def _validate_domain(domain: str) -> None:
    if not _DOMAIN_RE.fullmatch(domain):
        raise PathSandboxError(f"invalid domain: {domain!r}")


def _ensure_inside(base: Path, target: Path) -> None:
    base_abs = base.resolve()
    target_abs = target.resolve()
    try:
        target_abs.relative_to(base_abs)
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

- [ ] **Step 4: Atualizar chamadas de `exec_analysis_path` e `exec_library_path` no server_factory (será criado em Task 10) — anotar como dependência.**

Por ora, verificar que os testes do sandbox passam:

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

Em `packages/mcp-core/tests/test_bq_client.py`, adicionar:

```python
import pytest
from unittest.mock import MagicMock, patch
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

def _make_table_ref(dataset_id: str):
    ref = MagicMock()
    ref.dataset_id = dataset_id
    return ref

def test_dry_run_blocks_unauthorized_dataset():
    mock_bq = MagicMock()
    dry_job = MagicMock()
    dry_job.referenced_tables = [_make_table_ref("silver_ecomm")]
    mock_bq.query.return_value = dry_job

    client = BqClient(settings=_settings(["silver_linx"]), bq=mock_bq)
    with pytest.raises(DatasetNotAllowedError, match="silver_ecomm"):
        client.run_query("SELECT 1", exec_email="user@soma.com.br")

def test_dry_run_allows_authorized_dataset():
    mock_bq = MagicMock()
    dry_job = MagicMock()
    dry_job.referenced_tables = [_make_table_ref("silver_linx")]

    real_job = MagicMock()
    real_job.result.return_value = iter([])
    real_job.total_bytes_billed = 100
    real_job.total_bytes_processed = 200

    # First call = dry-run, second call = real query
    mock_bq.query.side_effect = [dry_job, real_job]

    client = BqClient(settings=_settings(["silver_linx"]), bq=mock_bq)
    result = client.run_query("SELECT 1", exec_email="user@soma.com.br")
    assert result.bytes_billed == 100

def test_dry_run_called_with_dry_run_true():
    from google.cloud import bigquery as bq_mod
    mock_bq = MagicMock()
    dry_job = MagicMock()
    dry_job.referenced_tables = [_make_table_ref("silver_linx")]
    real_job = MagicMock()
    real_job.result.return_value = iter([])
    real_job.total_bytes_billed = 0
    real_job.total_bytes_processed = 0
    mock_bq.query.side_effect = [dry_job, real_job]

    client = BqClient(settings=_settings(["silver_linx"]), bq=mock_bq)
    client.run_query("SELECT 1", exec_email="user@soma.com.br")

    first_call_config = mock_bq.query.call_args_list[0][1]["job_config"]
    assert first_call_config.dry_run is True
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_bq_client.py -v -k "dry_run"
```

Esperado: FAIL — `DatasetNotAllowedError` não existe, dry-run não está implementado.

- [ ] **Step 3: Atualizar `bq_client.py`**

Adicionar após os imports existentes:

```python
class DatasetNotAllowedError(ValueError):
    pass
```

Adicionar método `_check_allowed_datasets` à classe `BqClient`:

```python
def _check_allowed_datasets(self, sql: str) -> None:
    cfg = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    job = self.bq.query(sql, job_config=cfg)
    for table_ref in job.referenced_tables:
        if table_ref.dataset_id not in self.settings.allowed_datasets:
            raise DatasetNotAllowedError(
                f"dataset '{table_ref.dataset_id}' not in allowed_datasets "
                f"{self.settings.allowed_datasets}"
            )
```

Atualizar o início de `run_query` para chamar o check:

```python
def run_query(self, sql: str, exec_email: str) -> QueryResult:
    self._check_allowed_datasets(sql)  # ← adicionar esta linha
    cfg = bigquery.QueryJobConfig(
        # ... resto igual ao atual
    )
```

Também atualizar o comentário em `settings.py` que dizia "Documentary only":

```python
allowed_datasets: list[str]  # enforced via BQ dry-run in bq_client._check_allowed_datasets
```

- [ ] **Step 4: Rodar testes**

```bash
uv run pytest tests/test_bq_client.py -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-core/src/mcp_core/bq_client.py packages/mcp-core/src/mcp_core/settings.py packages/mcp-core/tests/test_bq_client.py
git commit -m "feat(mcp-core): enforce allowed_datasets via BQ dry-run"
```

---

### Task 8: Azure SSO passthrough no auth_middleware

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/auth_middleware.py`
- Modify: `packages/mcp-core/tests/test_auth_middleware.py`

- [ ] **Step 1: Escrever testes falhando**

Em `packages/mcp-core/tests/test_auth_middleware.py`, adicionar:

```python
import time, jwt, pytest
from unittest.mock import MagicMock, patch
from mcp_core.auth_middleware import extract_exec_email, AuthContext, AuthError

TENANT_ID = "test-tenant-id"
CLIENT_ID = "test-client-id"

def _azure_token(email: str, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "iss": f"https://login.microsoftonline.com/{TENANT_ID}/v2.0",
        "aud": CLIENT_ID,
        "preferred_username": email,
        "exp": now - 10 if expired else now + 3600,
        "iat": now,
    }
    return jwt.encode(payload, "secret", algorithm="HS256")

def _make_ctx(allowed_emails: list[str]) -> AuthContext:
    issuer = MagicMock()
    issuer.issuer = "mcp-exec-azzas"
    issuer.verify_access.side_effect = Exception("should not be called for Azure tokens")
    allowlist = MagicMock()
    allowlist.is_allowed.side_effect = lambda e: e in allowed_emails
    return AuthContext(
        issuer=issuer,
        allowlist=allowlist,
        azure_tenant_id=TENANT_ID,
        azure_client_id=CLIENT_ID,
    )

def test_azure_token_accepted_when_on_allowlist():
    token = _azure_token("user@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    with patch("mcp_core.auth_middleware._validate_azure_token_signature", return_value=None):
        email = extract_exec_email(token, ctx)
    assert email == "user@soma.com.br"

def test_azure_token_rejected_when_not_on_allowlist():
    token = _azure_token("other@soma.com.br")
    ctx = _make_ctx(["user@soma.com.br"])
    with patch("mcp_core.auth_middleware._validate_azure_token_signature", return_value=None):
        with pytest.raises(AuthError, match="not_on_allowlist"):
            extract_exec_email(token, ctx)

def test_unknown_issuer_rejected():
    payload = {"iss": "https://evil.example.com", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, "secret", algorithm="HS256")
    ctx = _make_ctx([])
    with pytest.raises(AuthError, match="unknown token issuer"):
        extract_exec_email(token, ctx)
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_auth_middleware.py -v -k "azure"
```

Esperado: FAIL — `AuthContext` não tem campos Azure, `extract_exec_email` não detecta `iss`.

- [ ] **Step 3: Atualizar `auth_middleware.py`**

Substituir o conteúdo de `packages/mcp-core/src/mcp_core/auth_middleware.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

import jwt as pyjwt

from mcp_core.allowlist import Allowlist
from mcp_core.jwt_tokens import TokenError, TokenIssuer
from typing import cast


class AuthError(RuntimeError):
    pass


@dataclass
class AuthContext:
    issuer: TokenIssuer
    allowlist: Allowlist
    azure_tenant_id: str = ""
    azure_client_id: str = ""


def _decode_iss(token: str) -> str:
    """Peek at the `iss` claim without verifying the signature."""
    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
        return str(payload.get("iss", ""))
    except Exception as e:
        raise AuthError(f"malformed token: {e}") from e


def _validate_azure_token_signature(token: str, tenant_id: str, client_id: str) -> None:
    """Validate Azure AD token signature via JWKS endpoint."""
    jwks_uri = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    jwks_client = pyjwt.PyJWKClient(jwks_uri)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    pyjwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=client_id,
    )


def _extract_azure_email(token: str) -> str:
    payload = pyjwt.decode(token, options={"verify_signature": False})
    email = payload.get("preferred_username") or payload.get("upn") or ""
    if not email:
        raise AuthError("azure token missing preferred_username/upn claim")
    return cast(str, email)


def extract_exec_email(token: str, ctx: AuthContext) -> str:
    iss = _decode_iss(token)

    if iss == ctx.issuer.issuer:
        # Internal JWT issued by mcp-exec-azzas
        try:
            claims = ctx.issuer.verify_access(token)
        except TokenError as e:
            raise AuthError(f"invalid_token: {e}") from e
        email = cast(str, claims["email"])

    elif "login.microsoftonline.com" in iss:
        # Azure AD SSO passthrough — frontend sends token directly
        if not ctx.azure_tenant_id or not ctx.azure_client_id:
            raise AuthError("azure passthrough not configured on this agent")
        _validate_azure_token_signature(token, ctx.azure_tenant_id, ctx.azure_client_id)
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
git commit -m "feat(mcp-core): add Azure SSO passthrough to auth_middleware"
```

---

### Task 9: context_loader dual-path (shared + agent)

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/context_loader.py`
- Modify: `packages/mcp-core/tests/test_context_loader.py`

- [ ] **Step 1: Escrever testes falhando**

Em `packages/mcp-core/tests/test_context_loader.py`, adicionar:

```python
from pathlib import Path
from mcp_core.context_loader import load_exec_context

def _make_shared(tmp_path: Path) -> Path:
    shared = tmp_path / "shared" / "context"
    shared.mkdir(parents=True)
    (shared / "analyst-principles.md").write_text("# Principles")
    (shared / "pii-rules.md").write_text("# PII")
    dims = shared / "dimensions"
    dims.mkdir()
    (dims / "produto.md").write_text("# Produto")
    return shared

def _make_agent(tmp_path: Path, domain: str) -> Path:
    agent = tmp_path / "agents" / domain / "src" / "agent"
    ctx = agent / "context"
    ctx.mkdir(parents=True)
    (ctx / "schema.md").write_text("# Schema vendas-linx")
    (ctx / "business-rules.md").write_text("# Business Rules")
    return agent

def test_loads_both_shared_and_agent_context(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Principles" in result.text
    assert "# Schema vendas-linx" in result.text
    assert "# Business Rules" in result.text

def test_loads_shared_dimensions(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    assert "# Produto" in result.text

def test_shared_context_appears_before_agent_context(tmp_path):
    shared = _make_shared(tmp_path)
    agent = _make_agent(tmp_path, "vendas-linx")
    result = load_exec_context(agent_root=agent, shared_root=shared)
    principles_pos = result.text.index("# Principles")
    schema_pos = result.text.index("# Schema vendas-linx")
    assert principles_pos < schema_pos
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_context_loader.py -v
```

Esperado: FAIL — `load_exec_context` tem assinatura diferente (aceita só `repo_root`).

- [ ] **Step 3: Reescrever `context_loader.py`**

Substituir o conteúdo de `packages/mcp-core/src/mcp_core/context_loader.py`:

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
    Merge two layers:
    1. shared_root — analyst-principles, pii-rules, dimensions/*.md
    2. agent_root/context — schema.md, business-rules.md, SKILL.md
    """
    sections: list[tuple[str, str]] = []

    # Shared docs
    for doc in SHARED_DOCS:
        p = shared_root / doc
        if p.exists():
            sections.append((f"shared/{doc}", p.read_text()))

    # Shared dimensions
    dims_dir = shared_root / "dimensions"
    if dims_dir.exists():
        for dim in sorted(dims_dir.glob("*.md")):
            sections.append((f"shared/dimensions/{dim.name}", dim.read_text()))

    # Agent-specific context
    ctx_dir = agent_root / "context"
    for doc in AGENT_DOCS:
        p = ctx_dir / doc
        if p.exists():
            sections.append((doc, p.read_text()))

    # Agent-specific skills (from repo .claude/skills/)
    skills_dir = agent_root.parents[3] / ".claude" / "skills"
    if skills_dir.exists():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            if skill_md.parent.name not in SKILL_ALLOWLIST:
                continue
            rel = str(skill_md.relative_to(agent_root.parents[3]))
            sections.append((rel, skill_md.read_text()))

    toc_lines = [
        "# Analytics Context",
        "",
        "Este bloco contém TODAS as regras e referências que você precisa. "
        "Skills listadas abaixo são padrões documentais aplicados inline — "
        "NÃO são ferramentas MCP separadas e não devem ser buscadas via tool_search.",
        "",
        "## Seções incluídas",
    ]
    for name, _ in sections:
        toc_lines.append(f"- `{name}`")
    toc = "\n".join(toc_lines)

    parts = [toc] + [f"<!-- {name} -->\n{body}" for name, body in sections]

    # allowed_tables: derived from agent schema.md filenames (informational for Claude)
    allowed_tables: list[str] = []

    return ExecContext(text="\n\n".join(parts), allowed_tables=allowed_tables)
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

Este módulo é o que `agents/vendas-linx/src/agent/server.py` vai importar. Ele encapsula: configuração do FastMCP, transport security, Azure auth, lifespan, e registro das 4 ferramentas base.

- [ ] **Step 1: Escrever teste de integração mínimo**

```python
# packages/mcp-core/tests/test_server_factory.py
import os
import pytest
from unittest.mock import patch

def test_build_mcp_app_returns_app_and_main():
    with patch.dict(os.environ, {
        "MCP_PUBLIC_HOST": "test.example.com",
        "MCP_JWT_SECRET": "testsecret",
        "MCP_AZURE_TENANT_ID": "tenant",
        "MCP_AZURE_CLIENT_ID": "client",
        "MCP_AZURE_CLIENT_SECRET": "secret",
    }):
        from mcp_core.server_factory import build_mcp_app
        app, main = build_mcp_app(agent_name="test-agent")
    assert app is not None
    assert callable(main)

def test_build_mcp_app_raises_without_jwt_secret():
    env = {k: v for k, v in os.environ.items() if k != "MCP_JWT_SECRET"}
    env.pop("MCP_JWT_SECRET", None)
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises((RuntimeError, KeyError)):
            from importlib import reload
            import mcp_core.server_factory as sf
            reload(sf)
            sf.build_mcp_app(agent_name="test-agent")
```

- [ ] **Step 2: Rodar e confirmar falha**

```bash
uv run pytest tests/test_server_factory.py -v
```

Esperado: FAIL — `server_factory` não existe.

- [ ] **Step 3: Criar `server_factory.py`**

```python
# packages/mcp-core/src/mcp_core/server_factory.py
from __future__ import annotations

import contextlib
import os
import time as _time
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
from mcp_core.bq_client import BqClient, DatasetNotAllowedError, QueryResult
from mcp_core.context_loader import load_exec_context
from mcp_core.git_ops import GitOps
from mcp_core.jwt_tokens import TokenIssuer
from mcp_core.library import LibraryEntry, prepend_entry
from mcp_core.sandbox import PathSandboxError, exec_analysis_path, exec_library_path
from mcp_core.settings import load_settings
from mcp_core.sql_validator import SqlValidationError, validate_readonly_sql

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone


def _repo_root() -> Path:
    return Path(os.environ.get("MCP_REPO_ROOT", "/app/repo"))


def _settings_path() -> Path:
    return Path(os.environ.get("MCP_SETTINGS", "/app/config/settings.toml"))


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "analise"


def build_mcp_app(agent_name: str) -> tuple[FastMCP, Callable]:
    """
    Build the FastMCP app with the 4 base tools registered.

    Returns (app, main):
    - app: FastMCP instance — use @app.tool() to add domain-specific tools
    - main: callable — use as __main__ entrypoint
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

    _audit: AuditLog | None = None

    def _get_audit() -> AuditLog:
        nonlocal _audit
        if _audit is None:
            settings = load_settings(_settings_path())
            _audit = AuditLog(db_path=Path(settings.audit.db_path))
        return _audit

    def _get_auth_context() -> AuthContext:
        settings = load_settings(_settings_path())
        secret = os.environ.get("MCP_JWT_SECRET")
        if not secret:
            raise RuntimeError("MCP_JWT_SECRET environment variable is required")
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

    # ── Base tool: get_context ──────────────────────────────────────────────
    @mcp.tool()
    def get_context(ctx: Context) -> dict[str, object]:
        """Return merged context: shared principles + agent schema + business rules."""
        _current_email(ctx)
        settings = load_settings(_settings_path())
        repo_root = _repo_root()
        domain = settings.server.domain
        shared_root = repo_root / "shared" / "context"
        agent_root = repo_root / "agents" / domain / "src" / "agent"
        loaded = load_exec_context(agent_root=agent_root, shared_root=shared_root)
        return {"text": loaded.text, "allowed_tables": loaded.allowed_tables}

    # ── Base tool: consultar_bq ─────────────────────────────────────────────
    @mcp.tool()
    async def consultar_bq(sql: str, ctx: Context) -> dict[str, object]:
        """Run a SELECT query against BigQuery. Only SELECT/WITH is accepted."""
        exec_email = _current_email(ctx)
        start = _time.time()
        await ctx.report_progress(progress=0.0, total=1.0, message="querying BigQuery...")
        try:
            validate_readonly_sql(sql)
        except SqlValidationError as e:
            return {"error": f"sql_validation: {e}"}
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

    # ── Base tool: publicar_dashboard ──────────────────────────────────────
    @mcp.tool()
    async def publicar_dashboard(
        title: str, brand: str, period: str,
        description: str, html_content: str,
        tags: list[str], ctx: Context,
    ) -> dict[str, object]:
        """Publish an HTML dashboard to the exec's sandbox + update library."""
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
        prepend_entry(
            library_path,
            LibraryEntry(
                id=entry_id, title=title, brand=brand, date=today,
                link=link, description=description, tags=tags, filename=filename,
            ),
        )

        await ctx.report_progress(progress=0.5, total=1.0, message="publishing...")
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

    # ── main() ──────────────────────────────────────────────────────────────
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

        auth_app = build_auth_app(azure=azure, issuer=issuer, allowlist=allowlist, lifespan=lifespan)
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

Esperado: todos passam.

- [ ] **Step 6: Commit**

```bash
git add packages/mcp-core/src/mcp_core/server_factory.py packages/mcp-core/tests/test_server_factory.py
git commit -m "feat(mcp-core): add server_factory with 4 base tools"
```

---

## Fase 3: Migrar vendas-linx

### Task 11: Criar estrutura do agente vendas-linx

**Files:**
- Create: `agents/vendas-linx/pyproject.toml`
- Create: `agents/vendas-linx/config/settings.toml`
- Create: `agents/vendas-linx/config/allowed_execs.json`
- Create: `agents/vendas-linx/src/agent/__init__.py`
- Create: `agents/vendas-linx/src/agent/context/` (mover arquivos)

- [ ] **Step 1: Criar diretórios**

```bash
mkdir -p agents/vendas-linx/config
mkdir -p agents/vendas-linx/src/agent/context
mkdir -p agents/vendas-linx/tests
touch agents/vendas-linx/src/agent/__init__.py
touch agents/vendas-linx/tests/__init__.py
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

Copiar de `mcp-server/config/settings.toml` e adicionar `domain`:

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
db_path = "./audit.db"
retention_days = 90
```

- [ ] **Step 4: Copiar `allowed_execs.json`**

```bash
cp mcp-server/config/allowed_execs.json agents/vendas-linx/config/
```

- [ ] **Step 5: Mover arquivos de contexto**

```bash
cp schema.md           agents/vendas-linx/src/agent/context/schema.md
cp business-rules.md   agents/vendas-linx/src/agent/context/business-rules.md
cp SKILL.md            agents/vendas-linx/src/agent/context/SKILL.md
```

- [ ] **Step 6: Commit**

```bash
git add agents/vendas-linx/
git commit -m "chore(vendas-linx): scaffold agent structure with config and context"
```

---

### Task 12: Criar server.py do agente vendas-linx

**Files:**
- Create: `agents/vendas-linx/src/agent/server.py`
- Create: `agents/vendas-linx/tests/test_server.py`

- [ ] **Step 1: Criar `agents/vendas-linx/src/agent/server.py`**

```python
from mcp_core.server_factory import build_mcp_app

app, main = build_mcp_app(agent_name="mcp-exec-vendas-linx")

# Adicione ferramentas específicas do domínio vendas-linx abaixo, se necessário.
# O agente atual não requer ferramentas extras além das 4 base.

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Escrever teste de smoke do agente**

```python
# agents/vendas-linx/tests/test_server.py
import os
from unittest.mock import patch

def test_server_imports_and_builds():
    with patch.dict(os.environ, {
        "MCP_PUBLIC_HOST": "test.example.com",
        "MCP_JWT_SECRET": "testsecret",
        "MCP_AZURE_TENANT_ID": "tenant",
        "MCP_AZURE_CLIENT_ID": "client",
        "MCP_AZURE_CLIENT_SECRET": "secret",
    }):
        from agent.server import app, main
    assert app is not None
    assert callable(main)

def test_server_has_base_tools():
    with patch.dict(os.environ, {
        "MCP_PUBLIC_HOST": "test.example.com",
        "MCP_JWT_SECRET": "testsecret",
        "MCP_AZURE_TENANT_ID": "tenant",
        "MCP_AZURE_CLIENT_ID": "client",
        "MCP_AZURE_CLIENT_SECRET": "secret",
    }):
        from agent.server import app
    tool_names = {t.name for t in app.list_tools()}
    assert {"get_context", "consultar_bq", "publicar_dashboard", "listar_analises"}.issubset(tool_names)
```

- [ ] **Step 3: Instalar e rodar testes do agente**

```bash
cd agents/vendas-linx
uv sync
uv run pytest -v
```

Esperado: PASS.

- [ ] **Step 4: Commit**

```bash
git add agents/vendas-linx/src/agent/server.py agents/vendas-linx/tests/test_server.py
git commit -m "feat(vendas-linx): add agent server using server_factory"
```

---

### Task 13: Dockerfile, entrypoint e railway.toml do agente

**Context:** O setup atual do `mcp-server/` usa um `entrypoint.sh` que clona o repo git em `/app/repo` na inicialização. O código Python roda em `/app/`, config em `/app/config/`, e o repo com arquivos de contexto e analyses fica em `/app/repo/`. O novo Dockerfile para `agents/vendas-linx/` segue o mesmo padrão — apenas a origem do código Python muda.

**Files:**
- Create: `agents/vendas-linx/Dockerfile`
- Create: `agents/vendas-linx/scripts/entrypoint.sh`
- Create: `agents/vendas-linx/railway.toml`

- [ ] **Step 1: Criar `agents/vendas-linx/scripts/entrypoint.sh`**

```bash
#!/bin/bash
set -e

# Clone or update the monorepo into /app/repo (for shared context + analyses)
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

Build context é a raiz do repo (precisa do `pyproject.toml` do workspace e de `packages/mcp-core/`).

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

# Copy workspace root + shared packages + this agent
COPY pyproject.toml .
COPY packages/mcp-core/ packages/mcp-core/
COPY agents/vendas-linx/ agents/vendas-linx/

# Install agent and its mcp-core dependency via uv workspace
WORKDIR /app/agents/vendas-linx
RUN uv sync --frozen

# Stage config to /app/config (where MCP_SETTINGS points by default)
RUN mkdir -p /app/config && cp -r /app/agents/vendas-linx/config/. /app/config/

COPY agents/vendas-linx/scripts/entrypoint.sh /app/scripts/entrypoint.sh

RUN useradd -m -u 1000 mcp \
    && mkdir -p /var/mcp /app/repo \
    && chown -R mcp:mcp /app /var/mcp \
    && chmod +x /app/scripts/entrypoint.sh
USER mcp

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:3000/health', timeout=5).raise_for_status()"

EXPOSE 3000

CMD ["/app/scripts/entrypoint.sh"]
```

> **Paths em produção:**
> - Código Python: `/app/agents/vendas-linx/`
> - Config: `/app/config/settings.toml` (copiado do `agents/vendas-linx/config/`)
> - Repo clonado: `/app/repo/` (entrypoint clona na inicialização)
> - `MCP_SETTINGS=/app/config/settings.toml` (default, sem mudança)
> - `MCP_REPO_ROOT=/app/repo` (default, sem mudança)

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
docker run --rm \
  -e MCP_PUBLIC_HOST=localhost \
  -e MCP_JWT_SECRET=dev-secret \
  -e MCP_AZURE_TENANT_ID=tenant \
  -e MCP_AZURE_CLIENT_ID=client \
  -e MCP_AZURE_CLIENT_SECRET=secret \
  -e MCP_DEV_EXEC_EMAIL=test@test.com \
  -e MCP_DOMAIN=vendas-linx \
  -p 3001:3000 \
  agent-vendas-linx-test
```

Esperado: servidor sobe em porta 3001 sem erro. O repo não será clonado porque `GITHUB_TOKEN` não está definido — normal em teste local.

- [ ] **Step 5: Commit**

```bash
git add agents/vendas-linx/Dockerfile agents/vendas-linx/scripts/ agents/vendas-linx/railway.toml
git commit -m "chore(vendas-linx): add Dockerfile, entrypoint, and railway.toml"
```

---

### Task 14: Teste local completo do agente

- [ ] **Step 1: Subir agente em dev mode**

```bash
gcloud auth application-default login  # se ainda não autenticado

cd agents/vendas-linx
MCP_DEV_EXEC_EMAIL=seu@somagrupo.com.br \
MCP_JWT_SECRET=dev-secret \
MCP_REPO_ROOT=../../portal \
MCP_DOMAIN=vendas-linx \
MCP_SETTINGS=../../agents/vendas-linx/config/settings.toml \
uv run python -m agent.server
```

- [ ] **Step 2: Testar get_context via curl**

```bash
curl -s -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_context","arguments":{}},"id":1}'
```

Esperado: resposta com `text` contendo schema + princípios.

- [ ] **Step 3: Testar enforcement de dataset**

```bash
curl -s -X POST http://localhost:3000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"consultar_bq","arguments":{"sql":"SELECT 1 FROM soma-pipeline-prd.silver_ecomm.VENDAS LIMIT 1"}},"id":2}'
```

Esperado: erro `dataset_not_allowed: silver_ecomm` — sem `billed_bytes` nos logs.

- [ ] **Step 4: Commit (se necessário ajuste)**

```bash
git add -A
git commit -m "test(vendas-linx): verify local agent integration"
```

---

> ## ✅ CHECKPOINT DE PRODUÇÃO
>
> O agente `vendas-linx` está pronto para deploy na nova estrutura. Antes de continuar:
>
> 1. Atualize o Railway service existente: Dockerfile path = `agents/vendas-linx/Dockerfile`, build context = `.`
> 2. Adicione `MCP_DOMAIN=vendas-linx` às variáveis do service
> 3. Faça o deploy e valide que o agente responde em produção
> 4. Só então continue para a Fase 4

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

- [ ] **Step 2: Mover arquivos existentes**

```bash
cp "analyst principles.md"    shared/context/analyst-principles.md
cp identidade-visual-azzas.md shared/context/identidade-visual-azzas.md
cp TEMPLATE.md                shared/context/TEMPLATE.md
```

- [ ] **Step 3: Criar `shared/context/pii-rules.md`**

Extrair a seção "Proteção de Dados Pessoais" do `CLAUDE.md` atual para esse arquivo. Copiar o conteúdo da seção `## Proteção de Dados Pessoais (PII)` do `CLAUDE.md` (da linha que começa com `## Proteção` até antes de `## Regra de ouro`).

- [ ] **Step 4: Criar placeholders de dimensões**

Os arquivos de dimensão (`produto.md`, `filiais.md`, `colecao.md`) devem documentar as colunas das tabelas de dimensão compartilhadas. Criar com conteúdo mínimo agora — preencher com o schema real antes do primeiro agente novo:

```bash
echo "# Dimensão Produto\n\nEsta dimensão é compartilhada entre todos os agentes. Documente aqui as colunas de `PRODUTOS`, `PRODUTOS_PRECOS`, `PRODUTO_CORES`, `PRODUTOS_TAMANHOS`." > shared/context/dimensions/produto.md
echo "# Dimensão Filiais\n\nEsta dimensão é compartilhada entre todos os agentes. Documente aqui as colunas de `FILIAIS`, `LOJAS_REDE`, `LOJAS_PREVISAO_VENDAS`." > shared/context/dimensions/filiais.md
echo "# Dimensão Coleção\n\n(A definir — preencher com schema real quando disponível.)" > shared/context/dimensions/colecao.md
```

- [ ] **Step 5: Commit**

```bash
git add shared/
git commit -m "chore: create shared/context with principles, pii-rules, dimensions"
```

---

### Task 16: Mover frontend para portal/

**Files:**
- Move: `index.html`, `api/`, `public/`, `middleware.js`, `msal-init.js`, `vercel.json` → `portal/`

- [ ] **Step 1: Criar diretório portal/ e mover arquivos**

```bash
mkdir -p portal
git mv index.html       portal/index.html
git mv api/             portal/api/
git mv public/          portal/public/
git mv middleware.js    portal/middleware.js
git mv msal-init.js     portal/msal-init.js
git mv vercel.json      portal/vercel.json
```

- [ ] **Step 2: Mover analyses/ e library/**

```bash
git mv analyses/ portal/analyses/
git mv library/  portal/library/
```

- [ ] **Step 3: Verificar que vercel.json não tem paths absolutos quebrados**

```bash
cat portal/vercel.json
```

Verificar se há rewrites/routes que referenciam caminhos que precisam ser ajustados após o move.

- [ ] **Step 4: Commit**

```bash
git add portal/
git commit -m "chore: move frontend to portal/"
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
  git mv "$f" portal/library/vendas-linx/
done
```

- [ ] **Step 3: Mover diretórios de analyses**

```bash
for d in portal/analyses/*/; do
  email=$(basename "$d")
  if [ "$email" != "vendas-linx" ] && [ "$email" != "public" ]; then
    git mv "portal/analyses/$email" "portal/analyses/vendas-linx/$email"
  fi
done
```

- [ ] **Step 4: Verificar estrutura final**

```bash
find portal/library portal/analyses -maxdepth 3
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
git commit -m "chore: migrate library/ and analyses/ to domain subdirectory"
```

---

### Task 18: Reconfigurar Vercel para portal/

- [ ] **Step 1: No painel Vercel, atualizar Root Directory**

Acessar: Vercel → projeto `bq-analista` → Settings → General → Root Directory → definir como `portal`.

Isso causa um redeploy automático. Verificar que o deploy conclui sem erro.

- [ ] **Step 2: Verificar que as analyses existentes são acessíveis**

Acessar uma URL de análise publicada anteriormente (ex: `https://bq-analista.vercel.app/analyses/vendas-linx/<email>/<arquivo>.html`) e confirmar que carrega.

- [ ] **Step 3: Não há código a commitar neste passo — apenas configuração no painel Vercel.**

---

## Fase 5: Tooling e cleanup

### Task 19: Criar scripts/new-agent.sh

**Files:**
- Create: `scripts/new-agent.sh`

- [ ] **Step 1: Criar o script**

```bash
#!/usr/bin/env bash
# Usage: scripts/new-agent.sh <domain>
# Creates a new agent from the current vendas-linx agent as reference.

set -euo pipefail

DOMAIN="${1:?Usage: new-agent.sh <domain>}"
AGENT_DIR="agents/$DOMAIN"
REF_DIR="agents/vendas-linx"

if [ -d "$AGENT_DIR" ]; then
  echo "ERROR: $AGENT_DIR already exists" >&2
  exit 1
fi

echo "Creating agent: $DOMAIN"
cp -r "$REF_DIR" "$AGENT_DIR"

# Update pyproject.toml name
sed -i '' "s/name = \"agent-vendas-linx\"/name = \"agent-$DOMAIN\"/" "$AGENT_DIR/pyproject.toml"

# Update settings.toml domain
sed -i '' "s/domain = \"vendas-linx\"/domain = \"$DOMAIN\"/" "$AGENT_DIR/config/settings.toml"

# Clear allowed_datasets — must be set explicitly
sed -i '' 's/allowed_datasets = \[.*\]/allowed_datasets = []  # TODO: set for your domain/' "$AGENT_DIR/config/settings.toml"

# Clear allowed_execs — must be set explicitly
echo '{"allowed_emails": []}' > "$AGENT_DIR/config/allowed_execs.json"

# Clear context files — must be written for the new domain
echo "# Schema — $DOMAIN\n\nDocumente aqui as tabelas do domínio $DOMAIN." > "$AGENT_DIR/src/agent/context/schema.md"
echo "# Business Rules — $DOMAIN\n\nDocumente aqui as regras de negócio do domínio $DOMAIN." > "$AGENT_DIR/src/agent/context/business-rules.md"

echo ""
echo "Agent created at $AGENT_DIR"
echo ""
echo "Next steps:"
echo "  1. Edit $AGENT_DIR/config/settings.toml  — set allowed_datasets"
echo "  2. Edit $AGENT_DIR/config/allowed_execs.json — add authorized emails"
echo "  3. Edit $AGENT_DIR/src/agent/context/schema.md — document tables"
echo "  4. Edit $AGENT_DIR/src/agent/context/business-rules.md — document rules"
echo "  5. uv sync (from repo root)"
echo "  6. Test locally: see CLAUDE.md 'Como criar um novo agente'"
```

- [ ] **Step 2: Tornar o script executável**

```bash
chmod +x scripts/new-agent.sh
```

- [ ] **Step 3: Testar o script**

```bash
scripts/new-agent.sh atacado
ls agents/atacado/
cat agents/atacado/config/settings.toml | grep domain
# Esperado: domain = "atacado"
cat agents/atacado/config/allowed_execs.json
# Esperado: {"allowed_emails": []}
```

- [ ] **Step 4: Deletar agente de teste**

```bash
rm -rf agents/atacado
```

- [ ] **Step 5: Commit**

```bash
git add scripts/new-agent.sh
git commit -m "chore: add new-agent.sh scaffold script"
```

---

### Task 20: Atualizar CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Adicionar seção "Como criar um novo agente" ao CLAUDE.md**

Abrir `CLAUDE.md` e adicionar ao final (antes de qualquer outra seção existente que deva ficar por último):

```markdown
---

## Como criar um novo agente

> **Pré-requisito:** a migração inicial (`mcp-server/` → `packages/mcp-core/` + `agents/vendas-linx/`) deve estar concluída. Verifique que `uv sync` roda sem erro na raiz do repo.

**Passo 0 — Gere o agente com o script**

```bash
scripts/new-agent.sh <seu-dominio>
```

Não use `cp -r` — o script garante cópia do estado atual do repo, limpa configs sensíveis e cria os placeholders corretos.

**Passo 1 — Edite os arquivos obrigatórios**

| Arquivo | O que mudar |
|---|---|
| `config/settings.toml` | `allowed_datasets` — datasets BQ permitidos |
| `config/allowed_execs.json` | Emails autorizados neste agente |
| `src/agent/context/schema.md` | Tabelas, colunas, PKs, joins canônicos do domínio |
| `src/agent/context/business-rules.md` | Regras de negócio específicas |
| `src/agent/server.py` | Ferramentas extras do domínio (pode ficar vazio) |

Dimensões compartilhadas: referencie `shared/context/dimensions/` — não duplique conteúdo.
PII: classifique cada coluna antes de escrever o schema. Colunas PII não entram.

**Passo 2 — Teste localmente**

```bash
gcloud auth application-default login   # obrigatório para acessar BigQuery

cd agents/<seu-dominio>
uv sync
MCP_DEV_EXEC_EMAIL=seu@somagrupo.com.br \
MCP_JWT_SECRET=dev-secret \
MCP_REPO_ROOT=../../portal \
MCP_DOMAIN=<seu-dominio> \
MCP_SETTINGS=config/settings.toml \
uv run python -m agent.server
```

Verifique:
1. `get_context` retorna schema do domínio + princípios compartilhados
2. Query válida em `allowed_datasets` executa normalmente
3. Query em dataset fora de `allowed_datasets` retorna erro **sem** `billed_bytes` nos logs

**Passo 3 — Escreva testes**

- Bug no core (auth, BQ, SQL validator) → `packages/mcp-core/tests/`
- Comportamento específico do agente → `agents/<dominio>/tests/`

Use `agents/vendas-linx/tests/` como referência de estrutura.

**Passo 4 — Configure o Railway service**

1. Crie um novo service no Railway apontando para este repo
2. Build: Dockerfile path = `agents/<dominio>/Dockerfile`, build context = `.` (raiz)
3. Adicione as variáveis de ambiente:

| Variável | Instrução |
|---|---|
| `MCP_JWT_SECRET` | `openssl rand -hex 32` — nunca reutilize |
| `MCP_PUBLIC_HOST` | URL gerada pelo Railway após o primeiro deploy |
| `MCP_AZURE_TENANT_ID` | Mesmo do agente existente |
| `MCP_AZURE_CLIENT_ID` | Mesmo do agente existente |
| `MCP_AZURE_CLIENT_SECRET` | Mesmo do agente existente |
| `MCP_DOMAIN` | `<seu-dominio>` (só necessário se não usar settings.toml) |
| `MCP_GIT_PUSH` | `1` |
| `MCP_SETTINGS` | `/app/config/settings.toml` (default — não precisa setar) |
| `MCP_ALLOWLIST` | `/app/config/allowed_execs.json` (default — não precisa setar) |
| `GITHUB_TOKEN` | Token com permissão de push ao repo (para publicar analyses) |
| `GITHUB_REPO` | `arturlemos/bq-analista` (ou o nome correto do repo) |

4. Após o primeiro deploy, Railway gera a URL. Atualize `MCP_PUBLIC_HOST` e faça redeploy.

**Passo 5 — Emita token para o usuário**

```bash
cd agents/<seu-dominio>
uv run python scripts/issue_long_lived_token.py --email usuario@somagrupo.com.br
```

**Passo 6 — Registre no Claude.ai**

URL: `https://<MCP_PUBLIC_HOST>/mcp`
Header: `Authorization: Bearer <token>`
Confirme com `get_context` que o contexto do domínio está chegando.

**O que NÃO fazer**

- Não use `cp -r` — use `scripts/new-agent.sh`
- Não reimplemente auth, audit ou SQL validation no agente — mude no `mcp-core`
- Não duplique dimensões compartilhadas — referencie `shared/context/dimensions/`
- Não reutilize `MCP_JWT_SECRET` entre agentes
- Não suba sem validar enforcement de `allowed_datasets` (Passo 2, item 3)
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add new agent guide to CLAUDE.md"
```

---

### Task 21: Deletar mcp-server/ e cleanup de raiz

> Só execute esta task após validar o agente `vendas-linx` em produção rodando a partir de `agents/vendas-linx/`.

**Files:**
- Delete: `mcp-server/`
- Delete: `analyst principles.md` (movido para `shared/context/`)
- Delete: `schema.md` (movido para `agents/vendas-linx/src/agent/context/`)
- Delete: `business-rules.md` (idem)
- Delete: `SKILL.md` (idem)
- Delete: `identidade-visual-azzas.md` (movido para `shared/context/`)
- Delete: `TEMPLATE.md` (idem)

- [ ] **Step 1: Deletar mcp-server/**

```bash
git rm -r mcp-server/
```

- [ ] **Step 2: Deletar arquivos movidos da raiz**

```bash
git rm "analyst principles.md" schema.md business-rules.md SKILL.md
git rm identidade-visual-azzas.md TEMPLATE.md
```

- [ ] **Step 3: Verificar que nenhum CI ou script referencia mcp-server/**

```bash
grep -r "mcp-server" . --include="*.yml" --include="*.sh" --include="*.toml" --include="*.json"
```

Esperado: nenhuma referência ativa (só pode aparecer em histórico git, não em arquivos).

- [ ] **Step 4: Commit final**

```bash
git add -A
git commit -m "chore: remove mcp-server/ and root-level context files after migration"
```

---

## Verificação final

- [ ] `uv sync` na raiz do repo roda sem erro
- [ ] `cd packages/mcp-core && uv run pytest -q` — todos os testes passam
- [ ] `cd agents/vendas-linx && uv run pytest -q` — todos os testes passam
- [ ] Docker build: `docker build -f agents/vendas-linx/Dockerfile -t test .` — conclui sem erro
- [ ] Agente responde em produção Railway
- [ ] Portal Vercel carrega em produção
- [ ] `scripts/new-agent.sh teste && rm -rf agents/teste` — executa sem erro
