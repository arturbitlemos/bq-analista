from __future__ import annotations

import re

import sqlglot
import sqlglot.expressions as exp


class SqlValidationError(ValueError):
    pass


_BANNED_STARTS = (
    "INSERT", "UPDATE", "DELETE", "MERGE", "CREATE", "DROP",
    "ALTER", "TRUNCATE", "GRANT", "REVOKE", "CALL", "BEGIN",
    "DECLARE", "SET", "EXECUTE", "EXPORT", "LOAD",
)
_ALLOWED_STARTS = ("SELECT", "WITH")

# Node types that represent write or schema-change operations.
_WRITE_NODE_TYPES = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge,
    exp.Create, exp.Drop, exp.Alter, exp.TruncateTable, exp.Command,
)

# BigQuery TVFs / scalar functions that execute arbitrary code against
# external systems.  The inner "sql" argument is a plain string literal so
# sqlglot does not parse it — we must block the call by function name.
_DANGEROUS_FUNCTIONS: frozenset[str] = frozenset({"EXTERNAL_QUERY"})


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql.strip()


def _func_name(node: exp.Func) -> str:
    """Return the SQL function name (upper-case), or empty string.

    `exp.Anonymous` wraps unknown functions and stores the user-supplied
    name on `.name`.  Other `Func` subclasses expose the canonical SQL name
    via `.sql_name()`.  Checking both means EXTERNAL_QUERY is caught even if
    a future sqlglot version registers it as a named Func subclass.
    """
    if isinstance(node, exp.Anonymous):
        return (node.name or "").upper()
    try:
        return (node.sql_name() or "").upper()
    except Exception:
        return ""


def _validate_ast(sql: str) -> None:
    """Parse SQL with sqlglot and walk the full AST for write operations.

    Falls back silently when sqlglot cannot parse (e.g. BigQuery-specific
    syntax not yet fully supported) so that the token-level check remains the
    safety net for those cases.
    """
    try:
        stmts = sqlglot.parse(sql, read="bigquery", error_level=sqlglot.ErrorLevel.WARN)
    except Exception:
        return

    real = [s for s in stmts if s is not None]
    if not real:
        return
    if len(real) > 1:
        raise SqlValidationError("multi-statement SQL not allowed")

    root = real[0]

    # Root must be a read-only query form: Select, Union, Intersect, Except
    # (all inherit from exp.Query). Write nodes — Insert/Update/Delete/Merge/
    # Create/Drop/Alter — do not inherit from Query, so this rejects them.
    if not isinstance(root, exp.Query):
        raise SqlValidationError(
            f"statement type not allowed: {type(root).__name__.upper()}"
        )

    # Walk the entire AST looking for embedded write or dangerous-function nodes
    for node in root.walk():
        if isinstance(node, _WRITE_NODE_TYPES):
            raise SqlValidationError(
                f"write operation not allowed inside query: {type(node).__name__}"
            )
        if isinstance(node, exp.Func):
            name = _func_name(node)
            if name in _DANGEROUS_FUNCTIONS:
                raise SqlValidationError(f"function not allowed: {name}")


def validate_readonly_sql(sql: str) -> None:
    """Allow only SELECT / WITH single-statement queries. Raise on anything else.

    Two-layer check:
    1. Token-level (fast, dialect-agnostic) — rejects known dangerous keywords
       at the start of the statement and bare semicolons.
    2. AST-level via sqlglot (BigQuery dialect) — walks the full parse tree to
       catch write operations or dangerous TVF calls embedded anywhere inside a
       syntactically valid SELECT, e.g. inside a CTE body or EXTERNAL_QUERY call.
    """
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

    _validate_ast(cleaned)
