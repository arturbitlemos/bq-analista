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
