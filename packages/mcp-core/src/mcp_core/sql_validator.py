from __future__ import annotations

import re


class SqlValidationError(ValueError):
    pass


_BANNED_STARTS = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP",
    "ALTER", "TRUNCATE", "GRANT", "REVOKE", "CALL", "BEGIN",
    "DECLARE", "SET", "EXECUTE", "EXPORT",
)
_ALLOWED_STARTS = ("SELECT", "WITH")


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql.strip()


def validate_readonly_sql(sql: str) -> None:
    """Allow only SELECT / WITH single-statement queries. Raise on anything else."""
    cleaned = _strip_comments(sql).rstrip(";").strip()
    if not cleaned:
        raise SqlValidationError("empty SQL")
    if ";" in cleaned:
        raise SqlValidationError("multi-statement SQL not allowed")
    head = cleaned.split(None, 1)[0].upper()
    if head in _BANNED_STARTS:
        raise SqlValidationError(f"statement type not allowed: {head}")
    if head not in _ALLOWED_STARTS:
        raise SqlValidationError(f"only SELECT/WITH allowed, got: {head}")
