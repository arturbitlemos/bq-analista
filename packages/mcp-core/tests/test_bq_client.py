import pytest
from unittest.mock import MagicMock, call

from mcp_core.bq_client import BqClient, DatasetNotAllowedError
from mcp_core.settings import BigQuerySettings


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


def _settings_allowed(allowed: list[str]) -> BigQuerySettings:
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

    client = BqClient(settings=_settings_allowed(["silver_linx"]), bq=mock_bq)
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

    client = BqClient(settings=_settings_allowed(["silver_linx"]), bq=mock_bq)
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

    client = BqClient(settings=_settings_allowed(["silver_linx"]), bq=mock_bq)
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

    client = BqClient(settings=_settings_allowed(["silver_linx"]), bq=mock_bq)
    result = client.run_query("SELECT 1", exec_email="user@soma.com.br")
    assert result.row_count == 0
