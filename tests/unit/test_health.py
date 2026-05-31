# /home/dmitriy/PycharmProjects/PDFnik-Backend/tests/unit/test_health.py
# repo: PDFnik-Backend

"""
Tests for the GET /health endpoint.

FastAPI TestClient is used to call the endpoint without a real server.
RabbitMQ broker and filesystem are mocked so tests run without Docker.
"""

import sys
import types
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Stub pdfnik_contracts before any import that pulls rabbit_connector
# ---------------------------------------------------------------------------


def _stub_pdfnik_contracts() -> None:
    if "pdfnik_contracts" in sys.modules:
        return
    for name in ["pdfnik_contracts", "pdfnik_contracts.pdf_content"]:
        sys.modules[name] = types.ModuleType(name)
    pc = sys.modules["pdfnik_contracts.pdf_content"]
    pc.PdfOrder = MagicMock()
    pc.BotDocument = MagicMock()
    pc.PdfBlock = object


_stub_pdfnik_contracts()

from main_app.api.routes.health import health_router  # noqa: E402

# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(health_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_router(connected: bool = True) -> MagicMock:
    broker = MagicMock()
    broker._connection = MagicMock() if connected else None
    router = MagicMock()
    router.broker = broker
    return router


# ---------------------------------------------------------------------------
# All checks pass
# ---------------------------------------------------------------------------


class TestHealthAllOk:
    def test_returns_200(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(True)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            (tmp_path / "runs.db").touch()
            response = client.get("/health")

        assert response.status_code == 200

    def test_status_ok(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(True)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            (tmp_path / "runs.db").touch()
            response = client.get("/health")

        assert response.json()["status"] == "ok"

    def test_all_checks_ok(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(True)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            (tmp_path / "runs.db").touch()
            response = client.get("/health")

        checks = response.json()["checks"]
        assert checks["rabbitmq"] == "ok"
        assert checks["files_storage"] == "ok"


# ---------------------------------------------------------------------------
# RabbitMQ not connected
# ---------------------------------------------------------------------------


class TestHealthRabbitMQDown:
    def test_returns_503(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(False)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            response = client.get("/health")

        assert response.status_code == 503

    def test_status_degraded(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(False)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            response = client.get("/health")

        assert response.json()["status"] == "degraded"

    def test_rabbitmq_check_shows_not_connected(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(False)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            response = client.get("/health")

        assert response.json()["checks"]["rabbitmq"] == "not connected"

    def test_rabbitmq_exception_returns_503(self, client, tmp_path):
        broken_router = MagicMock()
        broken_router.broker = MagicMock()
        type(broken_router.broker)._connection = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("connection lost"))
        )

        with (
            patch("main_app.api.routes.health.rabbit_router", broken_router),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            response = client.get("/health")

        assert response.status_code == 503
        assert "error" in response.json()["checks"]["rabbitmq"]


# ---------------------------------------------------------------------------
# files_storage missing
# ---------------------------------------------------------------------------


class TestHealthStorageMissing:
    def test_returns_503_when_storage_missing(self, client, tmp_path):
        missing = tmp_path / "does_not_exist"

        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(True)),
            patch("main_app.api.routes.health.FILES_ROOT", missing),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            response = client.get("/health")

        assert response.status_code == 503
        assert response.json()["checks"]["files_storage"] == "missing"


# ---------------------------------------------------------------------------
# runs_db not initialized (non-fatal)
# ---------------------------------------------------------------------------


class TestHealthRunsDbMissing:
    def test_returns_200_when_db_missing(self, client, tmp_path):
        """Missing runs.db is non-fatal — DB is created on first transcription."""
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(True)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["checks"]["runs_db"] == "not initialized"

    def test_returns_200_when_db_present(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(True)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            (tmp_path / "runs.db").touch()
            response = client.get("/health")

        assert response.json()["checks"]["runs_db"] == "ok"


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------


class TestHealthResponseStructure:
    def test_response_has_status_and_checks(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(True)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            response = client.get("/health")

        body = response.json()
        assert "status" in body
        assert "checks" in body
        assert isinstance(body["checks"], dict)

    def test_checks_contains_expected_keys(self, client, tmp_path):
        with (
            patch("main_app.api.routes.health.rabbit_router", _mock_router(True)),
            patch("main_app.api.routes.health.FILES_ROOT", tmp_path),
            patch("main_app.api.routes.health.RUNS_DB_PATH", tmp_path / "runs.db"),
        ):
            response = client.get("/health")

        checks = response.json()["checks"]
        assert "rabbitmq" in checks
        assert "files_storage" in checks
        assert "runs_db" in checks
