import pytest

from mcp_exec.sql_validator import SqlValidationError, validate_readonly_sql


def test_accepts_select() -> None:
    validate_readonly_sql("SELECT 1")
    validate_readonly_sql("SELECT * FROM `p.d.t` WHERE x = 1")


def test_accepts_with_cte() -> None:
    validate_readonly_sql("WITH a AS (SELECT 1) SELECT * FROM a")


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


def test_strips_comments_before_check() -> None:
    validate_readonly_sql("-- a comment\nSELECT 1")
    validate_readonly_sql("/* block */ SELECT 1")
