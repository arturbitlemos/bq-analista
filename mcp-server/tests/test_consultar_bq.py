from unittest.mock import MagicMock, patch

from mcp_exec.server import consultar_bq_impl
from mcp_exec.bq_client import QueryResult


@patch("mcp_exec.server._build_bq_client")
def test_rejects_non_select(build_mock) -> None:
    build_mock.return_value = MagicMock()
    result = consultar_bq_impl(sql="DELETE FROM x", exec_email="e@x.com", progress=None)
    assert result["error"].startswith("sql_validation:")


@patch("mcp_exec.server._build_bq_client")
def test_happy_path_returns_rows(build_mock) -> None:
    fake = MagicMock()
    fake.run_query.return_value = QueryResult(
        rows=[{"col": 1}], row_count=1, bytes_billed=10, bytes_processed=20
    )
    build_mock.return_value = fake

    out = consultar_bq_impl(sql="SELECT 1 AS col", exec_email="e@x.com", progress=None)
    assert out["row_count"] == 1
    assert out["rows"] == [{"col": 1}]
    assert out["bytes_billed"] == 10


@patch("mcp_exec.server._build_bq_client")
def test_progress_callback_invoked(build_mock) -> None:
    fake = MagicMock()
    fake.run_query.return_value = QueryResult(rows=[], row_count=0, bytes_billed=0, bytes_processed=0)
    build_mock.return_value = fake

    calls: list[str] = []
    consultar_bq_impl(sql="SELECT 1", exec_email="e@x.com", progress=calls.append)
    assert any("querying BigQuery" in c for c in calls)
