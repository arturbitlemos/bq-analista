from __future__ import annotations

import tomllib
from pathlib import Path
from pydantic import BaseModel


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
