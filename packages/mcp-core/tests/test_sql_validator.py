import pytest

from mcp_core.sql_validator import SqlValidationError, validate_readonly_sql


# ── Accepted (read-only) ──────────────────────────────────────────────────────

def test_accepts_select() -> None:
    validate_readonly_sql("SELECT 1")
    validate_readonly_sql("SELECT * FROM `p.d.t` WHERE x = 1")


def test_accepts_with_cte() -> None:
    validate_readonly_sql("WITH a AS (SELECT 1) SELECT * FROM a")


def test_accepts_information_schema() -> None:
    validate_readonly_sql("SELECT * FROM INFORMATION_SCHEMA.TABLES")


def test_accepts_subquery() -> None:
    validate_readonly_sql("SELECT * FROM (SELECT x FROM `p.d.t`) sub")


def test_accepts_ml_tvf() -> None:
    # ML.PREDICT is a read-only TVF — must not be blocked
    validate_readonly_sql(
        "SELECT * FROM ML.PREDICT(MODEL `proj.ds.model`, TABLE `proj.ds.data`)"
    )


def test_accepts_complex_analytics() -> None:
    validate_readonly_sql(
        """
        WITH base AS (
            SELECT rede_lojas, SUM(venda_liquida) AS total
            FROM `p.d.transacoes`
            WHERE data_venda >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
            GROUP BY 1
        )
        SELECT * FROM base ORDER BY total DESC LIMIT 10
        """
    )


# ── Rejected: bare DML / DDL (token-level) ───────────────────────────────────

def test_rejects_ddl() -> None:
    for s in [
        "CREATE TABLE x AS SELECT 1",
        "DROP TABLE x",
        "ALTER TABLE x ADD COLUMN y INT64",
        "TRUNCATE TABLE x",
    ]:
        with pytest.raises(SqlValidationError):
            validate_readonly_sql(s)


def test_rejects_dml() -> None:
    for s in [
        "INSERT INTO x VALUES (1)",
        "UPDATE x SET y = 1",
        "DELETE FROM x",
        "MERGE INTO x ...",
    ]:
        with pytest.raises(SqlValidationError):
            validate_readonly_sql(s)


def test_rejects_multi_statement() -> None:
    with pytest.raises(SqlValidationError):
        validate_readonly_sql("SELECT 1; SELECT 2")


def test_rejects_scripting() -> None:
    for s in ["DECLARE x INT64 DEFAULT 0; SELECT x", "BEGIN SELECT 1; END"]:
        with pytest.raises(SqlValidationError):
            validate_readonly_sql(s)


def test_rejects_load_data() -> None:
    with pytest.raises(SqlValidationError):
        validate_readonly_sql("LOAD DATA INTO `p.d.t` FROM FILES (format='CSV', uris=['gs://b/f'])")


def test_strips_comments_before_check() -> None:
    validate_readonly_sql("-- a comment\nSELECT 1")
    validate_readonly_sql("/* block */ SELECT 1")


# ── Rejected: AST-level bypasses (the CRITICAL-2 attack surface) ─────────────

def test_rejects_dml_inside_cte() -> None:
    """DML inside a CTE body must be caught even though the query starts with WITH."""
    with pytest.raises(SqlValidationError, match="write operation"):
        validate_readonly_sql(
            "WITH x AS (INSERT INTO `p.d.t` VALUES (1)) SELECT * FROM x"
        )


def test_rejects_delete_inside_cte() -> None:
    with pytest.raises(SqlValidationError, match="write operation"):
        validate_readonly_sql(
            "WITH x AS (DELETE FROM `p.d.t` WHERE TRUE) SELECT 1"
        )


def test_rejects_external_query() -> None:
    """EXTERNAL_QUERY executes arbitrary SQL on a Cloud SQL instance."""
    with pytest.raises(SqlValidationError, match="function not allowed: EXTERNAL_QUERY"):
        validate_readonly_sql(
            "SELECT * FROM EXTERNAL_QUERY('proj/loc/conn', 'DELETE FROM sensitive')"
        )


def test_rejects_external_query_in_cte() -> None:
    with pytest.raises(SqlValidationError, match="function not allowed: EXTERNAL_QUERY"):
        validate_readonly_sql(
            "WITH x AS (SELECT * FROM EXTERNAL_QUERY('c', 'SELECT 1')) SELECT * FROM x"
        )
