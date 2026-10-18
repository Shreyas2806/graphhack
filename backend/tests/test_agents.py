"""
tests/test_agents.py — Phase-2 tests for memory and reasoning agents.

All external services (FalkorDB, Gemini) are mocked.
No live credentials or running database required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("FALKORDB_HOST", "127.0.0.1")
    monkeypatch.setenv("FALKORDB_PORT", "6379")
    monkeypatch.setenv("FALKORDB_GRAPH", "graphmind")
    from app.cache import cache
    cache.clear()


@pytest.fixture()
def client(_mock_env):
    with patch("dotenv.load_dotenv", return_value=True):
        import importlib
        import app.config as cfg_mod
        importlib.reload(cfg_mod)

        from app.main import app
        with TestClient(app) as c:
            yield c


# ── Helpers ────────────────────────────────────────────────────────────────────

def _empty_graph():
    """Mock FalkorDB Graph where all queries return empty result sets."""
    graph = MagicMock()
    qr = MagicMock()
    qr.result_set = []
    graph.query.return_value = qr
    return graph


SAMPLE_TRIPLES = json.dumps([
    {
        "subject": "GraphMind",
        "predicate": "uses_language",
        "object": "Python",
        "object_type": "entity",
        "confidence": 0.95,
    },
    {
        "subject": "GraphMind",
        "predicate": "uses_database",
        "object": "FalkorDB",
        "object_type": "entity",
        "confidence": 0.95,
    },
])


# ── memory_agent unit tests ───────────────────────────────────────────────────
# Both `generate_text` and `_get_graph` are imported at module level in
# memory_agent.py, so we patch them AT their imported name on that module.

class TestMemoryAgentExtraction:

    def test_extracts_and_stores_facts(self):
        """Happy-path: Gemini returns valid JSON triples and facts are stored."""
        from app.agents.memory_agent import store_memory

        mock_graph = _empty_graph()

        with (
            patch("app.agents.memory_agent.generate_text",
                  return_value={"ok": True, "text": SAMPLE_TRIPLES}),
            patch("app.agents.memory_agent._get_graph", return_value=mock_graph),
        ):
            result = store_memory(
                statement="GraphMind uses Python and FalkorDB.",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is True
        assert result["facts_extracted"] == 2
        assert result["facts_stored"] == 2
        assert result["source_id"] is not None
        subjects = {f["subject"] for f in result["facts"] if f.get("stored")}
        assert "GraphMind" in subjects

    def test_handles_gemini_failure(self):
        """LLM failure returns ok=False without crashing."""
        from app.agents.memory_agent import store_memory

        with patch("app.agents.memory_agent.generate_text",
                   return_value={"ok": False, "error": "API down"}):
            result = store_memory(
                statement="anything",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is False
        assert "API down" in result["error"]
        assert result["facts_extracted"] == 0

    def test_handles_non_json_llm_response(self):
        """Non-JSON LLM output returns ok=False with a clear error."""
        from app.agents.memory_agent import store_memory

        with patch("app.agents.memory_agent.generate_text",
                   return_value={"ok": True, "text": "Sorry, I cannot help."}):
            result = store_memory(
                statement="anything",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is False
        assert "JSON" in result["error"] or "non-JSON" in result["error"]

    def test_skips_invalid_triples(self):
        """Triples with empty required fields are skipped, not crashed on."""
        from app.agents.memory_agent import store_memory

        bad_triples = json.dumps([
            {"subject": "", "predicate": "does_something",
             "object": "X", "object_type": "entity", "confidence": 0.9},
        ])
        mock_graph = _empty_graph()

        with (
            patch("app.agents.memory_agent.generate_text",
                  return_value={"ok": True, "text": bad_triples}),
            patch("app.agents.memory_agent._get_graph", return_value=mock_graph),
        ):
            result = store_memory(
                statement="test",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is True
        assert result["facts_stored"] == 0
        assert result["facts"][0]["stored"] is False

    def test_detects_duplicate_fact(self):
        """Exact same triple stored twice is marked as a duplicate."""
        from app.agents.memory_agent import store_memory

        triple = json.dumps([{
            "subject": "GraphMind", "predicate": "uses_language",
            "object": "Python", "object_type": "entity", "confidence": 0.9,
        }])

        mock_graph = MagicMock()
        existing_qr = MagicMock()
        existing_qr.result_set = [["abc123", "Python", "active"]]
        empty_qr = MagicMock()
        empty_qr.result_set = []

        def query_side(cypher, params=None):
            if "MATCH (f:Fact {subject" in cypher:
                return existing_qr
            return empty_qr

        mock_graph.query.side_effect = query_side

        with (
            patch("app.agents.memory_agent.generate_text",
                  return_value={"ok": True, "text": triple}),
            patch("app.agents.memory_agent._get_graph", return_value=mock_graph),
        ):
            result = store_memory(
                statement="GraphMind uses Python",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is True
        assert result["facts"][0]["duplicate"] is True

    def test_handles_falkordb_connection_error(self):
        """If FalkorDB is down, returns ok=False with a helpful error."""
        from app.agents.memory_agent import store_memory

        with (
            patch("app.agents.memory_agent.generate_text",
                  return_value={"ok": True, "text": SAMPLE_TRIPLES}),
            patch("app.agents.memory_agent._get_graph",
                  side_effect=Exception("Connection refused")),
        ):
            result = store_memory(
                statement="anything",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is False
        assert "Connection refused" in result["error"]


# ── reasoning_agent unit tests ────────────────────────────────────────────────

class TestReasoningAgent:

    def _fact_row(self, subject, predicate, obj, fid="fact1"):
        return [fid, subject, predicate, obj, "entity", 0.9, "active", "2024-01-01"]

    def test_returns_grounded_answer(self):
        """When facts exist, Gemini receives context and returns an answer."""
        from app.agents.reasoning_agent import answer_question

        mock_graph = MagicMock()
        fact_qr = MagicMock()
        fact_qr.result_set = [
            self._fact_row("GraphMind", "uses_database", "FalkorDB", "f1"),
        ]
        source_qr = MagicMock()
        source_qr.result_set = [
            ["s1", "GraphMind uses FalkorDB", "user_statement", "2024-01-01"]
        ]
        empty_qr = MagicMock()
        empty_qr.result_set = []

        def query_side(cypher, params=None):
            if "CONTAINS" in cypher and "MATCH (f:Fact)" in cypher:
                return fact_qr
            if "MATCH (s:Source)" in cypher:
                return source_qr
            return empty_qr

        mock_graph.query.side_effect = query_side

        with (
            patch("app.agents.reasoning_agent._get_graph", return_value=mock_graph),
            patch("app.agents.reasoning_agent.generate_text",
                  return_value={"ok": True, "text": "GraphMind uses FalkorDB."}),
        ):
            result = answer_question(
                question="Which database does GraphMind use?",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is True
        assert "FalkorDB" in result["answer"]
        assert result["sufficient_evidence"] is True
        assert len(result["facts_used"]) >= 1

    def test_reports_insufficient_evidence_when_graph_empty(self):
        """Empty graph → insufficient evidence without calling Gemini."""
        from app.agents.reasoning_agent import answer_question

        mock_graph = _empty_graph()

        with patch("app.agents.reasoning_agent._get_graph", return_value=mock_graph):
            result = answer_question(
                question="Which cloud provider hosts GraphMind?",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is True
        assert result["sufficient_evidence"] is False
        assert len(result["answer"]) > 0

    def test_handles_falkordb_error(self):
        """FalkorDB connection failure returns ok=False."""
        from app.agents.reasoning_agent import answer_question

        with patch("app.agents.reasoning_agent._get_graph",
                   side_effect=Exception("Refused")):
            result = answer_question(
                question="anything?",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is False
        assert "Refused" in result["error"]

    def test_handles_gemini_error_after_retrieval(self):
        """LLM failure during answer generation returns ok=False."""
        from app.agents.reasoning_agent import answer_question

        mock_graph = MagicMock()
        fact_qr = MagicMock()
        fact_qr.result_set = [
            self._fact_row("GraphMind", "uses_database", "FalkorDB"),
        ]
        empty_qr = MagicMock()
        empty_qr.result_set = []

        def query_side(cypher, params=None):
            if "CONTAINS" in cypher:
                return fact_qr
            return empty_qr

        mock_graph.query.side_effect = query_side

        with (
            patch("app.agents.reasoning_agent._get_graph", return_value=mock_graph),
            patch("app.agents.reasoning_agent.generate_text",
                  return_value={"ok": False, "error": "LLM timeout"}),
        ):
            result = answer_question(
                question="What database does GraphMind use?",
                api_key="k", model="m",
                db_host="h", db_port=6379, db_graph="g",
            )

        assert result["ok"] is False
        assert "LLM timeout" in result["error"]


# ── API endpoint integration tests ────────────────────────────────────────────

class TestMemoryEndpoint:
    def test_post_memory_success(self, client):
        mock_result = {
            "ok": True,
            "facts_extracted": 2,
            "facts_stored": 2,
            "source_id": "src123",
            "facts": [
                {
                    "fact_id": "f1", "subject": "GraphMind",
                    "predicate": "uses_language",
                    "object_value": "Python", "object_type": "entity",
                    "confidence": 0.95, "status": "active",
                    "stored": True, "duplicate": False, "updated": False,
                }
            ],
        }
        with patch("app.agents.memory_agent.store_memory", return_value=mock_result):
            resp = client.post("/memory", json={"text": "GraphMind uses Python."})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["facts_stored"] == 2
        assert data["source_id"] == "src123"

    def test_post_memory_empty_text_rejected(self, client):
        resp = client.post("/memory", json={"text": ""})
        assert resp.status_code == 422

    def test_post_memory_llm_failure_returns_502(self, client):
        fail_result = {
            "ok": False, "error": "Gemini unavailable",
            "facts_extracted": 0, "facts_stored": 0, "facts": [],
        }
        with patch("app.agents.memory_agent.store_memory", return_value=fail_result):
            resp = client.post("/memory", json={"text": "Something."})
        assert resp.status_code == 502


class TestAskEndpoint:
    def test_post_ask_with_evidence(self, client):
        mock_result = {
            "ok": True,
            "answer": "GraphMind uses FalkorDB.",
            "sufficient_evidence": True,
            "facts_used": [
                {"fact_id": "f1", "subject": "GraphMind",
                 "predicate": "uses_database", "object_value": "FalkorDB"}
            ],
            "sources": [
                {"source_id": "s1", "text": "GraphMind uses FalkorDB.",
                 "source_type": "user_statement", "created_at": "2024-01-01"}
            ],
            "reasoning_path": "Retrieved 1 fact.",
        }
        with patch("app.agents.reasoning_agent.answer_question",
                   return_value=mock_result):
            resp = client.post("/ask", json={"question": "Which database?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["sufficient_evidence"] is True
        assert "FalkorDB" in data["answer"]

    def test_post_ask_insufficient_evidence(self, client):
        mock_result = {
            "ok": True,
            "answer": (
                "I don't have enough information in my knowledge base "
                "to answer this question."
            ),
            "sufficient_evidence": False,
            "facts_used": [],
            "sources": [],
            "reasoning_path": "No relevant facts found.",
        }
        with patch("app.agents.reasoning_agent.answer_question",
                   return_value=mock_result):
            resp = client.post("/ask", json={"question": "Which cloud provider?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sufficient_evidence"] is False

    def test_post_ask_empty_question_rejected(self, client):
        resp = client.post("/ask", json={"question": ""})
        assert resp.status_code == 422


class TestListMemoryEndpoint:
    def test_get_memory_success(self, client):
        mock_graph = MagicMock()
        count_qr = MagicMock()
        count_qr.result_set = [[3]]
        fact_qr = MagicMock()
        fact_qr.result_set = [
            ["f1", "GraphMind", "uses_language", "Python", "entity",
             0.95, "active", "2024-01-01", "2024-01-01"],
        ]

        def qside(cypher, params=None):
            if "count" in cypher.lower():
                return count_qr
            return fact_qr

        mock_graph.query.side_effect = qside

        # main.py imports _get_graph lazily from app.graph; patch at source.
        with patch("app.graph._get_graph", return_value=mock_graph):
            resp = client.get("/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["total"] == 3
        assert len(data["facts"]) >= 1

    def test_get_memory_db_error_returns_error_response(self, client):
        with patch("app.graph._get_graph", side_effect=Exception("DB down")):
            resp = client.get("/memory")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False


class TestGraphEndpoint:
    def test_get_graph_success(self, client):
        mock_graph = MagicMock()
        node_qr = MagicMock()
        node_qr.result_set = [["eid1", "GraphMind", "entity"]]
        empty_qr = MagicMock()
        empty_qr.result_set = []

        def qside(cypher, params=None):
            if "RETURN e.id" in cypher:
                return node_qr
            return empty_qr

        mock_graph.query.side_effect = qside

        with patch("app.graph._get_graph", return_value=mock_graph):
            resp = client.get("/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    def test_get_graph_db_error_returns_error_response(self, client):
        with patch("app.graph._get_graph", side_effect=Exception("DB down")):
            resp = client.get("/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False


# ── Regression: existing endpoints still pass ─────────────────────────────────

class TestHealthRegression:
    def test_health_still_works(self, client):
        with patch("app.main.check_connectivity", return_value={"ok": True}):
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root_still_works(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "GraphMind" in resp.json()["project"]
