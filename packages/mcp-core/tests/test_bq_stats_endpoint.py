import sqlite3
import tempfile
import time
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_core.api_routes import register_api_routes
from mcp_core.auth_middleware import AuthContext


def _make_client(audit_db_path: str) -> TestClient:
    app = FastAPI()
    auth_ctx = MagicMock(spec=AuthContext)
    register_api_routes(
        app,
        auth_ctx=auth_ctx,
        bq_factory=MagicMock(),
        blob_factory=MagicMock(),
        audit_db_path=audit_db_path,
    )
    return TestClient(app)


def _seed_db(path: str) -> None:
    now = time.time()
    with sqlite3.connect(path) as c:
        c.execute("""
            CREATE TABLE audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                exec_email TEXT NOT NULL,
                tool TEXT NOT NULL,
                sql TEXT,
                bytes_scanned INTEGER DEFAULT 0,
                row_count INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                result TEXT NOT NULL,
                error TEXT
            )
        """)
        c.executemany(
            "INSERT INTO audit (ts, exec_email, tool, sql, bytes_scanned, row_count, duration_ms, result, error)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (now - 3600,      "a@soma.com", "consultar_bq", "SELECT 1", 1024, 1, 200, "success", None),
                (now - 1800,      "a@soma.com", "consultar_bq", "SELECT 2", 2048, 5, 300, "success", None),
                (now - 900,       "b@soma.com", "consultar_bq", "SELECT 3", 512,  2, 150, "error",   "syntax error"),
                # Outside 30-day window — must not appear in totals
                (now - 31*86400,  "a@soma.com", "consultar_bq", "SELECT 4", 9999, 0, 100, "success", None),
            ],
        )


def test_bq_stats_returns_aggregates():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _seed_db(db_path)
        with patch("mcp_core.api_routes.extract_exec_email", return_value="user@soma.com"):
            client = _make_client(db_path)
            resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert "by_user" in data
        assert "totals" in data
        assert "recent_errors" in data
        assert data["totals"]["total_calls"] == 3
        assert data["totals"]["total_errors"] == 1
        assert data["totals"]["distinct_users"] == 2
    finally:
        os.unlink(db_path)


def test_bq_stats_by_user_sorted_desc():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _seed_db(db_path)
        with patch("mcp_core.api_routes.extract_exec_email", return_value="user@soma.com"):
            client = _make_client(db_path)
            resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
        users = resp.json()["by_user"]
        assert users[0]["exec_email"] == "a@soma.com"
        assert users[0]["total_calls"] == 2
        assert users[1]["exec_email"] == "b@soma.com"
        assert users[1]["errors"] == 1
    finally:
        os.unlink(db_path)


def test_bq_stats_recent_errors_populated():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        _seed_db(db_path)
        with patch("mcp_core.api_routes.extract_exec_email", return_value="user@soma.com"):
            client = _make_client(db_path)
            resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
        errors = resp.json()["recent_errors"]
        assert len(errors) == 1
        assert errors[0]["exec_email"] == "b@soma.com"
        assert "syntax error" in errors[0]["error"]
    finally:
        os.unlink(db_path)


def test_bq_stats_empty_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        # Empty DB file — no table, no data
        with patch("mcp_core.api_routes.extract_exec_email", return_value="user@soma.com"):
            client = _make_client(db_path)
            resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["by_user"] == []
        assert data["recent_errors"] == []
    finally:
        os.unlink(db_path)


def test_bq_stats_missing_audit_db_path():
    """When audit_db_path=None, endpoint returns 200 with empty data."""
    app = FastAPI()
    auth_ctx = MagicMock(spec=AuthContext)
    with patch("mcp_core.api_routes.extract_exec_email", return_value="user@soma.com"):
        register_api_routes(
            app,
            auth_ctx=auth_ctx,
            bq_factory=MagicMock(),
            blob_factory=MagicMock(),
            audit_db_path=None,
        )
        client = TestClient(app)
        resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["by_user"] == []
    assert data["totals"] == {}
    assert data["recent_errors"] == []


def test_bq_stats_returns_401_on_invalid_token():
    """Endpoint must return 401 when extract_exec_email raises AuthError."""
    from mcp_core.auth_middleware import AuthError
    app = FastAPI()
    auth_ctx = MagicMock(spec=AuthContext)
    with patch(
        "mcp_core.api_routes.extract_exec_email",
        side_effect=AuthError("invalid token"),
    ):
        register_api_routes(
            app,
            auth_ctx=auth_ctx,
            bq_factory=MagicMock(),
            blob_factory=MagicMock(),
            audit_db_path=None,
        )
        client = TestClient(app)
        resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer bad"})
    assert resp.status_code == 401
