"""
tests/test_health.py — Basic tests for GET / and GET /health.

External services (FalkorDB, Gemini) are mocked so tests run without
a live database or API key.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Provide dummy env vars before importing app modules ───────────────────────
@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("FALKORDB_HOST", "127.0.0.1")
    monkeypatch.setenv("FALKORDB_PORT", "6379")
    monkeypatch.setenv("FALKORDB_GRAPH", "graphmind")


@pytest.fixture()
def client(_mock_env):
    # Import inside fixture so env vars are already set.
    # We also need to patch dotenv loading so it doesn't override our monkeypatches.
    with patch("dotenv.load_dotenv", return_value=True):
        # Re-import config with test env vars active.
        import importlib
        import app.config as cfg_mod
        importlib.reload(cfg_mod)

        from app.main import app
        with TestClient(app) as c:
            yield c


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRoot:
    def test_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_contains_project_name(self, client):
        data = resp = client.get("/")
        data = resp.json()
        assert "GraphMind" in data["project"]
        assert data["status"] == "running"
        assert "version" in data


class TestHealth:
    def test_health_ok_when_falkordb_reachable(self, client):
        with patch("app.main.check_connectivity", return_value={"ok": True}):
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["falkordb"]["ok"] is True

    def test_health_degraded_when_falkordb_down(self, client):
        with patch(
            "app.main.check_connectivity",
            return_value={"ok": False, "error": "Connection refused"},
        ):
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["falkordb"]["ok"] is False

    def test_health_does_not_expose_api_key(self, client):
        with patch("app.main.check_connectivity", return_value={"ok": True}):
            resp = client.get("/health")
        assert "test-api-key-not-real" not in resp.text


class TestTestGemini:
    def test_gemini_success(self, client):
        with patch(
            "app.main.generate_text",
            return_value={"ok": True, "text": "Hello from Gemini!"},
        ):
            resp = client.post("/test-gemini", json={"prompt": "Say hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "Hello from Gemini!" in data["text"]

    def test_gemini_api_error_returns_ok_false(self, client):
        with patch(
            "app.main.generate_text",
            return_value={"ok": False, "error": "API key invalid"},
        ):
            resp = client.post("/test-gemini", json={"prompt": "Say hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["error"] is not None

    def test_empty_prompt_rejected(self, client):
        resp = client.post("/test-gemini", json={"prompt": ""})
        assert resp.status_code == 422  # Pydantic validation error


class TestTestGraph:
    def test_graph_write_success(self, client):
        mock_result = MagicMock()
        mock_result.nodes_created = 2
        mock_result.relationships_created = 1

        with patch(
            "app.main.safe_graph_write",
            return_value={"ok": True, "result": mock_result},
        ):
            resp = client.post("/test-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["nodes_created"] == 2

    def test_graph_write_failure(self, client):
        with patch(
            "app.main.safe_graph_write",
            return_value={"ok": False, "error": "Connection refused"},
        ):
            resp = client.post("/test-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["error"] == "Connection refused"
