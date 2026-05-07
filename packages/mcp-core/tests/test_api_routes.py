from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcp_core.api_routes import register_api_routes
from mcp_core.auth_middleware import AuthContext


def _make_app() -> TestClient:
    app = FastAPI()
    register_api_routes(
        app,
        auth_ctx=MagicMock(spec=AuthContext),
        bq_factory=MagicMock(),
        blob_factory=MagicMock(),
    )
    return TestClient(app)


def test_bq_stats_endpoint_removed():
    """/api/admin/bq-stats must not exist after removing the SQLite fan-out."""
    client = _make_app()
    resp = client.get("/api/admin/bq-stats", headers={"Authorization": "Bearer fake"})
    assert resp.status_code == 404


def test_healthz_still_present():
    """/healthz must still respond after api_routes cleanup."""
    from unittest.mock import AsyncMock
    app = FastAPI()
    register_api_routes(
        app,
        auth_ctx=MagicMock(spec=AuthContext),
        bq_factory=MagicMock(),
        blob_factory=MagicMock(),
    )
    client = TestClient(app)
    with patch("mcp_core.api_routes.db") as mock_db:
        mock_db.transaction.return_value.__aenter__ = AsyncMock(return_value=MagicMock(fetchval=AsyncMock(return_value=1)))
        mock_db.transaction.return_value.__aexit__ = AsyncMock(return_value=False)
        resp = client.get("/healthz")
    assert resp.status_code == 200
