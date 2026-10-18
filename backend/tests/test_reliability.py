"""
tests/test_reliability.py — Unit tests for Phase 5 reliability enhancements:
- Idempotent retries and duplicate write prevention
- Historical fact versioning & SUPERSEDES edge creation
- Verification failure handling and notice disclosure in Coordinator
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.agents.memory_agent import store_memory
from app.agents.verification_agent import VerificationResult


@pytest.fixture(autouse=True)
def _clean_cache():
    from app.cache import cache
    cache.clear()


def test_idempotent_duplicate_write_prevention():
    """Identical fact stored twice is detected as duplicate and not recreated."""
    mock_graph = MagicMock()
    existing_qr = MagicMock()
    existing_qr.result_set = [["fact_1", "FalkorDB", "active"]]
    empty_qr = MagicMock()
    empty_qr.result_set = []

    def query_side(cypher, params=None):
        if "MATCH (f:Fact {subject" in cypher:
            return existing_qr
        return empty_qr

    mock_graph.query.side_effect = query_side

    triples = json.dumps([
        {"subject": "GraphMind", "predicate": "uses_database", "object": "FalkorDB", "object_type": "entity", "confidence": 0.95}
    ])

    with (
        patch("app.agents.memory_agent.generate_text", return_value={"ok": True, "text": triples}),
        patch("app.agents.memory_agent._get_graph", return_value=mock_graph),
    ):
        res = store_memory("GraphMind uses FalkorDB", "key", "model", "host", 6379, "graph")

    assert res["ok"] is True
    assert res["facts_stored"] == 1
    assert res["facts"][0]["duplicate"] is True
    assert res["facts"][0]["updated"] is False


def test_supersedes_historical_version_on_update():
    """When a fact's value changes, the old fact is superseded and linked via SUPERSEDES."""
    mock_graph = MagicMock()
    existing_qr = MagicMock()
    existing_qr.result_set = [["fact_old", "Redis", "active"]]
    empty_qr = MagicMock()
    empty_qr.result_set = []

    queries_run = []

    def query_side(cypher, params=None):
        queries_run.append((cypher, params))
        if "MATCH (f:Fact {subject" in cypher:
            return existing_qr
        return empty_qr

    mock_graph.query.side_effect = query_side

    triples = json.dumps([
        {"subject": "GraphMind", "predicate": "uses_database", "object": "FalkorDB", "object_type": "entity", "confidence": 0.95}
    ])

    with (
        patch("app.agents.memory_agent.generate_text", return_value={"ok": True, "text": triples}),
        patch("app.agents.memory_agent._get_graph", return_value=mock_graph),
    ):
        res = store_memory("GraphMind uses FalkorDB", "key", "model", "host", 6379, "graph")

    assert res["ok"] is True
    assert res["facts"][0]["updated"] is True
    # Verify superseded status query was called
    supersede_calls = [q for q, p in queries_run if "SET f.status = 'superseded'" in q]
    assert len(supersede_calls) >= 1
    # Verify SUPERSEDES edge was created
    supersedes_edge_calls = [q for q, p in queries_run if "SUPERSEDES" in q]
    assert len(supersedes_edge_calls) >= 1


def test_coordinator_handles_verification_failure_without_false_verification():
    """If Verification Agent fails, Coordinator marks status as ERROR and prepends a notice."""
    client = TestClient(app)

    mock_reasoning = {
        "ok": True,
        "answer": "GraphMind runs on FalkorDB.",
        "sufficient_evidence": True,
        "facts_used": [{"fact_id": "f1", "subject": "GraphMind", "predicate": "uses_database", "object_value": "FalkorDB"}],
        "sources": [{"source_id": "s1", "text": "GraphMind runs on FalkorDB."}],
        "reasoning_path": "Found 1 fact.",
    }

    mock_failed_verification = VerificationResult(
        ok=False,
        status="ERROR",
        explanation="LLM service quota exhausted",
        error="429 ResourceExhausted",
    )

    with (
        patch("app.agents.reasoning_agent.answer_question", return_value=mock_reasoning),
        patch("app.agents.verification_agent.verify_answer", return_value=mock_failed_verification),
    ):
        resp = client.post("/ask", json={"question": "What database?"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["verification_status"] == "ERROR"
    assert "Verification Notice" in data["answer"]
    assert any(step["status"] == "ERROR" and step["agent"] == "VerificationAgent" for step in data["agent_trace"])
