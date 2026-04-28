from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from google.cloud import bigquery
from google.oauth2 import service_account

from mcp_core.settings import BigQuerySettings


class DatasetNotAllowedError(ValueError):
    pass


def _bq_credentials_from_env() -> service_account.Credentials | None:
    """Parse MCP_BQ_SA_KEY (JSON content or path) into Credentials. Returns None if unset."""
    raw = os.environ.get("MCP_BQ_SA_KEY")
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("{"):
        info = json.loads(raw)
    else:
        # Treat as file path
        with open(raw) as f:
            info = json.load(f)
    return service_account.Credentials.from_service_account_info(info)


def _label_sanitize(email: str) -> str:
    # GCP labels: lowercase letters, numbers, dashes, underscores; max 63 chars.
    return re.sub(r"[^a-z0-9_-]", "_", email.lower())[:63]


class _BqLike(Protocol):
    def query(self, sql: str, job_config: Any) -> Any: ...


@dataclass
class QueryResult:
    rows: list[dict[str, object]]
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
            creds = _bq_credentials_from_env()
            self.bq = bigquery.Client(
                project=self.settings.billing_project_id or self.settings.project_id,
                credentials=creds,  # None falls back to ADC
            )

    def _check_allowed_datasets(self, sql: str) -> None:
        """Run BQ dry-run to extract referenced datasets; raise if any is not allowed.

        allowed_datasets entries can be:
          - "dataset_name"           → allowed only under settings.project_id
          - "other-project.dataset"  → allowed under the specified project
        """
        cfg = bigquery.QueryJobConfig(
            dry_run=True,
            use_query_cache=False,
            maximum_bytes_billed=self.settings.max_bytes_billed,
        )
        job = self.bq.query(sql, job_config=cfg)
        # job.result() is not needed for dry-run; referenced_tables is populated immediately
        for table_ref in job.referenced_tables:
            qualified = f"{table_ref.project}.{table_ref.dataset_id}"
            allowed = any(
                (entry == table_ref.dataset_id and table_ref.project == self.settings.project_id)
                if "." not in entry
                else entry == qualified
                for entry in self.settings.allowed_datasets
            )
            if not allowed:
                raise DatasetNotAllowedError(
                    f"'{qualified}' not in allowed scope "
                    f"(project={self.settings.project_id}, datasets={self.settings.allowed_datasets})"
                )

    def run_query(self, sql: str, exec_email: str) -> QueryResult:
        self._check_allowed_datasets(sql)  # raises DatasetNotAllowedError if unauthorized
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
        rows: list[dict[str, object]] = []
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
