from __future__ import annotations

import os
import tomllib
from pathlib import Path
from pydantic import BaseModel


class ServerSettings(BaseModel):
    host: str
    port: int
    domain: str  # routes analyses/<domain>/ and library/<domain>/ paths


class BigQuerySettings(BaseModel):
    project_id: str  # data project — used for dataset/table validation
    billing_project_id: str | None = None  # project where jobs run; falls back to project_id if unset
    max_bytes_billed: int
    query_timeout_s: int
    max_rows: int
    allowed_datasets: list[str]  # enforced via BQ dry-run in bq_client._check_allowed_datasets


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
    if path.exists():
        data = tomllib.loads(path.read_text())
        settings = Settings.model_validate(data)
        _apply_env_overrides(settings)
        return settings
    return _settings_from_env()


def _apply_env_overrides(settings: Settings) -> None:
    """Override select settings fields from env vars (env takes precedence over toml)."""
    if v := os.environ.get("MCP_BQ_PROJECT_ID"):
        settings.bigquery.project_id = v
    if v := os.environ.get("MCP_BQ_BILLING_PROJECT_ID"):
        settings.bigquery.billing_project_id = v


def _settings_from_env() -> Settings:
    """Build Settings entirely from environment variables (Railway / container deployments)."""
    port = int(os.environ.get("PORT", os.environ.get("MCP_PORT", "3000")))
    return Settings(
        server=ServerSettings(host="0.0.0.0", port=port, domain=os.environ["MCP_DOMAIN"]),
        bigquery=BigQuerySettings(
            project_id=os.environ["MCP_BQ_PROJECT_ID"],
            billing_project_id=os.environ.get("MCP_BQ_BILLING_PROJECT_ID"),
            max_bytes_billed=int(os.environ.get("MCP_BQ_MAX_BYTES_BILLED", str(5_000_000_000))),
            query_timeout_s=int(os.environ.get("MCP_BQ_QUERY_TIMEOUT_S", "60")),
            max_rows=int(os.environ.get("MCP_BQ_MAX_ROWS", "100000")),
            allowed_datasets=os.environ.get(
                "MCP_BQ_ALLOWED_DATASETS", "soma_online_refined"
            ).split(","),
        ),
        github=GithubSettings(
            repo_path=os.environ.get("MCP_GITHUB_REPO_PATH", "/app/repo"),
            branch=os.environ.get("MCP_GITHUB_BRANCH", "main"),
            author_name=os.environ.get("MCP_GITHUB_AUTHOR_NAME", "mcp-exec-bot"),
            author_email=os.environ.get("MCP_GITHUB_AUTHOR_EMAIL", "mcp@azzas.com.br"),
        ),
        auth=AuthSettings(
            jwt_issuer=os.environ.get("MCP_AUTH_JWT_ISSUER", "mcp-exec-azzas"),
            access_token_ttl_s=int(os.environ.get("MCP_AUTH_ACCESS_TTL_S", "1800")),
            refresh_token_ttl_s=int(os.environ.get("MCP_AUTH_REFRESH_TTL_S", "2592000")),
        ),
        audit=AuditSettings(
            db_path=os.environ.get("MCP_AUDIT_DB_PATH", "/var/mcp/audit.db"),
            retention_days=int(os.environ.get("MCP_AUDIT_RETENTION_DAYS", "90")),
        ),
    )
