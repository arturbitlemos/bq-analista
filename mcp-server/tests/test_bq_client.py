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
