from pathlib import Path

import pytest

from mcp_core.settings import Settings, load_settings


def test_loads_example_settings(tmp_path: Path) -> None:
    toml = tmp_path / "settings.toml"
    toml.write_text(
        '[server]\nhost="0.0.0.0"\nport=3000\ndomain="test-domain"\n'
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


def test_missing_file_falls_back_to_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_BQ_PROJECT_ID", "test-project")
    monkeypatch.setenv("MCP_DOMAIN", "test-domain")
    s = load_settings(tmp_path / "missing.toml")
    assert s.bigquery.project_id == "test-project"
    assert s.server.host == "0.0.0.0"
    assert s.server.domain == "test-domain"


def test_server_settings_requires_domain():
    from pydantic import ValidationError

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


def test_settings_domain_loads_from_toml(tmp_path: Path) -> None:
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
