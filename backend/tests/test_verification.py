"""
tests/test_verification.py — Phase-3 Verification Agent and evidence validation tests.

Covers:
1. Fully supported answer (deterministic and LLM-assisted).
2. Answer containing unsupported claims (partial support & full unsupport).
3. Fabricated fact IDs (in answer citations and in evidence vs FalkorDB).
4. Contradictory facts (within evidence and against FalkorDB).
5. Stale / superseded facts (with and without explicit qualification).
6. Empty evidence handling (both factual claims and insufficient-info answers).
7. Verification dependency failure (LLM failure, DB failure — never marked verified).
8. POST /verify API endpoint.
9. POST /ask pipeline integration with verification (supported, conflicts disclosed, unsupported revised, failure handling).
10. Live integration test with running FalkorDB service (if reachable).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.agents.verification_agent import (
    verify_answer,
    STATUS_SUPPORTED,
    STATUS_PARTIALLY_SUPPORTED,
    STATUS_UNSUPPORTED,
    STATUS_CONFLICTING,
    STATUS_ERROR,
)


@pytest.fixture
def client():
    return TestClient(app)


# ── 1. Unit Tests for Verification Agent ──────────────────────────────────────

class TestVerificationAgentUnit:

    def test_fully_supported_answer_deterministic(self):
        """When evidence active facts match subject and object, answer is verified SUPPORTED."""
        evidence = [
            {
                "fact_id": "f_12345678",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "FalkorDB",
                "source_text": "GraphMind uses FalkorDB for graph storage.",
                "status": "active",
            }
        ]
        result = verify_answer(
            question="Which database does GraphMind use?",
            answer="GraphMind uses FalkorDB.",
            evidence=evidence,
            validate_against_db=False,
        )

        assert result.ok is True
        assert result.status == STATUS_SUPPORTED
        assert len(result.verified_claims) >= 1
        assert len(result.unsupported_claims) == 0
        assert len(result.evidence) == 1
        assert result.evidence[0].fact_id == "f_12345678"
        assert result.evidence[0].source_text == "GraphMind uses FalkorDB for graph storage."

    def test_fully_supported_answer_llm_assisted(self):
        """When Gemini assists with claim verification, returns SUPPORTED status."""
        evidence = [
            {
                "fact_id": "f_12345678",
                "subject": "GraphMind",
                "predicate": "uses_framework",
                "object_value": "FastAPI",
                "source_text": "GraphMind backend is built on FastAPI.",
                "status": "active",
            }
        ]
        mock_llm_response = {
            "ok": True,
            "text": json.dumps({
                "claims": [
                    {
                        "claim": "GraphMind is powered by FastAPI.",
                        "status": "SUPPORTED",
                        "supported_by_fact_ids": ["f_12345678"],
                        "explanation": "Directly matches evidence.",
                    }
                ],
                "conflicts": [],
            }),
        }

        with patch("app.agents.verification_agent.generate_text", return_value=mock_llm_response):
            result = verify_answer(
                question="What framework does GraphMind use?",
                answer="GraphMind is powered by FastAPI.",
                evidence=evidence,
                api_key="mock_key",
                model="mock_model",
                validate_against_db=False,
            )

        assert result.ok is True
        assert result.status == STATUS_SUPPORTED
        assert "GraphMind is powered by FastAPI." in result.verified_claims
        assert len(result.unsupported_claims) == 0

    def test_answer_containing_unsupported_claim(self):
        """Answer with one verified and one unestablished claim is PARTIALLY_SUPPORTED."""
        evidence = [
            {
                "fact_id": "f_db",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "FalkorDB",
                "source_text": "GraphMind uses FalkorDB.",
                "status": "active",
            }
        ]
        result = verify_answer(
            question="Tell me about GraphMind's database and release year.",
            answer="GraphMind uses FalkorDB. GraphMind was created in 1995.",
            evidence=evidence,
            validate_against_db=False,
        )

        assert result.ok is True
        assert result.status == STATUS_PARTIALLY_SUPPORTED
        assert any("FalkorDB" in c for c in result.verified_claims)
        assert any("1995" in c for c in result.unsupported_claims)

    def test_answer_citing_fabricated_fact_id_in_text(self):
        """Citing a fact ID that was never retrieved flags an integrity violation and marks claim unsupported."""
        evidence = [
            {
                "fact_id": "real_fact_123",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "FalkorDB",
                "source_text": "GraphMind uses FalkorDB.",
                "status": "active",
            }
        ]
        # Answer explicitly cites [fabricated_fact_999]
        result = verify_answer(
            question="Which database?",
            answer="GraphMind uses Redis [fabricated_fact_999].",
            evidence=evidence,
            validate_against_db=False,
        )

        assert result.status == STATUS_UNSUPPORTED
        assert "fabricated or non-existent fact ID" in result.explanation
        assert "fabricated_fact_999" in result.explanation

    def test_fabricated_fact_id_in_evidence_falkordb_validation(self):
        """When validate_against_db is True, non-existent fact IDs in FalkorDB are caught."""
        evidence = [
            {
                "fact_id": "fake_id_not_in_graph",
                "statement": "GraphMind uses MongoDB.",
                "source_text": "I heard GraphMind uses MongoDB.",
                "status": "active",
            }
        ]
        mock_graph = MagicMock()
        empty_qr = MagicMock()
        empty_qr.result_set = []
        mock_graph.query.return_value = empty_qr

        with patch("app.agents.verification_agent._get_graph", return_value=mock_graph):
            result = verify_answer(
                question="Which database?",
                answer="GraphMind uses MongoDB.",
                evidence=evidence,
                db_host="127.0.0.1",
                db_port=6379,
                db_graph="test_graph",
                validate_against_db=True,
            )

        assert result.status == STATUS_UNSUPPORTED
        assert "fake_id_not_in_graph" in result.explanation

    def test_contradictory_facts_in_evidence(self):
        """Conflicting facts for the same entity and predicate result in CONFLICTING status."""
        evidence = [
            {
                "fact_id": "f_1",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "FalkorDB",
                "source_text": "GraphMind uses FalkorDB.",
                "status": "active",
            },
            {
                "fact_id": "f_2",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "MongoDB",
                "source_text": "GraphMind uses MongoDB.",
                "status": "active",
            },
        ]
        result = verify_answer(
            question="Which database does GraphMind use?",
            answer="GraphMind uses FalkorDB.",
            evidence=evidence,
            validate_against_db=False,
        )

        assert result.status == STATUS_CONFLICTING
        assert len(result.conflicts) >= 1
        assert "Conflicting facts" in result.conflicts[0].description

    def test_contradictory_fact_against_falkordb(self):
        """Evidence fact that contradicts active stored fact in FalkorDB triggers CONFLICTING."""
        evidence = [
            {
                "fact_id": "f_retrieved",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "MySQL",
                "source_text": "Old note: GraphMind uses MySQL.",
                "status": "active",
            }
        ]
        mock_graph = MagicMock()

        def query_side(cypher, params=None):
            qr = MagicMock()
            if "MATCH (f:Fact {id: $fid})" in cypher:
                qr.result_set = [["f_retrieved", "GraphMind", "uses_database", "MySQL", "active", "Old note"]]
                return qr
            if "status: 'active'" in cypher:
                # Active DB fact is FalkorDB
                qr.result_set = [["f_active_db", "FalkorDB"]]
                return qr
            qr.result_set = []
            return qr

        mock_graph.query.side_effect = query_side

        with patch("app.agents.verification_agent._get_graph", return_value=mock_graph):
            result = verify_answer(
                question="Which database?",
                answer="GraphMind uses MySQL.",
                evidence=evidence,
                db_host="localhost",
                db_port=6379,
                db_graph="g",
                validate_against_db=True,
            )

        assert result.status == STATUS_CONFLICTING
        assert len(result.conflicts) >= 1
        assert any("conflicts with active FalkorDB fact" in c.description for c in result.conflicts)

    def test_stale_superseded_fact_without_qualification(self):
        """Superseded fact asserted as current without qualification is flagged as a conflict/staleness."""
        evidence = [
            {
                "fact_id": "f_superseded",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "Redis",
                "source_text": "Initial prototype used Redis.",
                "status": "superseded",
            }
        ]
        result = verify_answer(
            question="Which database does GraphMind use?",
            answer="GraphMind uses Redis.",
            evidence=evidence,
            validate_against_db=False,
        )

        assert result.status == STATUS_CONFLICTING
        assert len(result.conflicts) >= 1
        assert "superseded/stale" in result.conflicts[0].description
        assert "without qualification" in result.conflicts[0].description

    def test_stale_superseded_fact_with_qualification(self):
        """Superseded fact asserted with explicit qualification ('previously') does not fail staleness."""
        evidence = [
            {
                "fact_id": "f_superseded",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "Redis",
                "source_text": "Initial prototype used Redis.",
                "status": "superseded",
            }
        ]
        result = verify_answer(
            question="What did GraphMind previously use?",
            answer="GraphMind previously used Redis.",
            evidence=evidence,
            validate_against_db=False,
        )

        # Because answer is qualified with 'previously', staleness conflict is not raised
        assert len(result.conflicts) == 0

    def test_empty_evidence_factual_claim(self):
        """When evidence is empty and answer claims facts, status is UNSUPPORTED."""
        result = verify_answer(
            question="Where is GraphMind hosted?",
            answer="GraphMind is hosted on AWS.",
            evidence=[],
            validate_against_db=False,
        )

        assert result.ok is True
        assert result.status == STATUS_UNSUPPORTED
        assert len(result.verified_claims) == 0
        assert "GraphMind is hosted on AWS." in result.unsupported_claims
        assert "No evidence" in result.explanation

    def test_empty_evidence_insufficient_info_answer(self):
        """When evidence is empty and answer says insufficient info, answer is verified SUPPORTED."""
        result = verify_answer(
            question="Where is GraphMind hosted?",
            answer="I don't have enough information in my knowledge base to answer this question.",
            evidence=[],
            validate_against_db=False,
        )

        assert result.ok is True
        assert result.status == STATUS_SUPPORTED
        assert len(result.verified_claims) == 1
        assert len(result.unsupported_claims) == 0

    def test_verification_dependency_failure_llm(self):
        """If Gemini fails during verification, return ok=False, status=ERROR. Never mark verified."""
        evidence = [
            {
                "fact_id": "f_1",
                "subject": "GraphMind",
                "predicate": "uses_database",
                "object_value": "FalkorDB",
                "source_text": "GraphMind uses FalkorDB.",
                "status": "active",
            }
        ]
        with patch(
            "app.agents.verification_agent.generate_text",
            return_value={"ok": False, "error": "LLM Service Unavailable (503)"},
        ):
            result = verify_answer(
                question="How does GraphMind store memories?",
                answer="GraphMind relies upon specialized neural associative memory graphs.",
                evidence=evidence,
                api_key="key",
                model="model",
                validate_against_db=False,
            )

        assert result.ok is False
        assert result.status == STATUS_ERROR
        assert "LLM Service Unavailable" in result.explanation

    def test_verification_dependency_failure_falkordb(self):
        """If FalkorDB connection fails during validate_against_db, return ok=False, status=ERROR."""
        evidence = [{"fact_id": "f1", "statement": "Some fact"}]
        with patch(
            "app.agents.verification_agent._get_graph",
            side_effect=Exception("Connection to FalkorDB refused"),
        ):
            result = verify_answer(
                question="Which database?",
                answer="Some answer",
                evidence=evidence,
                db_host="localhost",
                db_port=6379,
                db_graph="g",
                validate_against_db=True,
            )

        assert result.ok is False
        assert result.status == STATUS_ERROR
        assert "Connection to FalkorDB refused" in result.explanation


# ── 2. Tests for POST /verify Endpoint ────────────────────────────────────────

class TestVerifyEndpoint:

    def test_post_verify_fully_supported(self, client):
        payload = {
            "question": "Which database does GraphMind use?",
            "answer": "GraphMind uses FalkorDB.",
            "evidence": [
                {
                    "fact_id": "f_12345678",
                    "statement": "GraphMind uses FalkorDB.",
                    "subject": "GraphMind",
                    "predicate": "uses_database",
                    "object_value": "FalkorDB",
                    "source_text": "I am building GraphMind using Python and FalkorDB.",
                }
            ],
        }

        mock_graph = MagicMock()
        qr = MagicMock()
        qr.result_set = [["f_12345678", "GraphMind", "uses_database", "FalkorDB", "active", "I am building GraphMind using Python and FalkorDB."]]
        mock_graph.query.return_value = qr

        with patch("app.agents.verification_agent._get_graph", return_value=mock_graph):
            resp = client.post("/verify", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["status"] == "SUPPORTED"
        assert len(data["verified_claims"]) >= 1
        assert len(data["unsupported_claims"]) == 0
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["fact_id"] == "f_12345678"

    def test_post_verify_unsupported(self, client):
        payload = {
            "question": "What is the capital of Mars?",
            "answer": "Olympus City is the capital of Mars.",
            "evidence": [],
        }
        resp = client.post("/verify", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["status"] == "UNSUPPORTED"
        assert len(data["unsupported_claims"]) >= 1

    def test_post_verify_fabricated_fact_id(self, client):
        payload = {
            "question": "Which database?",
            "answer": "GraphMind uses FalkorDB.",
            "evidence": [
                {
                    "fact_id": "fabricated_nonexistent_id",
                    "statement": "GraphMind uses FalkorDB.",
                }
            ],
        }
        mock_graph = MagicMock()
        empty_qr = MagicMock()
        empty_qr.result_set = []
        mock_graph.query.return_value = empty_qr

        with patch("app.agents.verification_agent._get_graph", return_value=mock_graph):
            resp = client.post("/verify", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "UNSUPPORTED"
        assert "fabricated or non-existent fact ID" in data["explanation"]

    def test_post_verify_db_failure(self, client):
        payload = {
            "question": "Which database?",
            "answer": "GraphMind uses FalkorDB.",
            "evidence": [{"fact_id": "f1"}],
        }
        with patch(
            "app.agents.verification_agent._get_graph",
            side_effect=Exception("DB Connection timeout"),
        ):
            resp = client.post("/verify", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert data["status"] == "ERROR"
        assert "DB Connection timeout" in data["explanation"]


# ── 3. Tests for POST /ask Pipeline Integration ───────────────────────────────

class TestAskPipelineVerification:

    def test_ask_pipeline_fully_supported(self, client):
        mock_reasoning_result = {
            "ok": True,
            "answer": "GraphMind uses FalkorDB.",
            "sufficient_evidence": True,
            "facts_used": [
                {
                    "fact_id": "f_1",
                    "subject": "GraphMind",
                    "predicate": "uses_database",
                    "object_value": "FalkorDB",
                    "status": "active",
                }
            ],
            "sources": [
                {
                    "source_id": "s_1",
                    "text": "GraphMind is powered by FalkorDB.",
                    "source_type": "user_statement",
                    "created_at": "2024-01-01",
                }
            ],
            "reasoning_path": "Retrieved 1 fact.",
        }

        with patch("app.agents.reasoning_agent.answer_question", return_value=mock_reasoning_result):
            resp = client.post("/ask", json={"question": "Which database does GraphMind use?"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["verification_status"] == "SUPPORTED"
        assert "FalkorDB" in data["answer"]
        assert len(data["verified_claims"]) >= 1
        assert len(data["unsupported_claims"]) == 0
        assert len(data["evidence"]) >= 1
        assert data["evidence"][0]["source_text"] == "GraphMind is powered by FalkorDB."

    def test_ask_pipeline_discloses_conflict(self, client):
        """When conflicting facts exist, /ask discloses the conflict and reports CONFLICTING status."""
        mock_reasoning_result = {
            "ok": True,
            "answer": "GraphMind uses FalkorDB.",
            "sufficient_evidence": True,
            "facts_used": [
                {
                    "fact_id": "f_1",
                    "subject": "GraphMind",
                    "predicate": "uses_database",
                    "object_value": "FalkorDB",
                    "status": "active",
                },
                {
                    "fact_id": "f_2",
                    "subject": "GraphMind",
                    "predicate": "uses_database",
                    "object_value": "Neo4j",
                    "status": "active",
                },
            ],
            "sources": [
                {"source_id": "s_1", "text": "FalkorDB note."},
                {"source_id": "s_2", "text": "Neo4j note."},
            ],
            "reasoning_path": "Found 2 conflicting facts.",
        }

        with patch("app.agents.reasoning_agent.answer_question", return_value=mock_reasoning_result):
            resp = client.post("/ask", json={"question": "Which database does GraphMind use?"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["verification_status"] == "CONFLICTING"
        assert len(data["conflicts"]) >= 1
        assert "Conflict detected in knowledge base" in data["answer"]

    def test_ask_pipeline_unsupported_claim_revised(self, client):
        """When the answer is unsupported by evidence, /ask returns clear insufficient-evidence message."""
        mock_reasoning_result = {
            "ok": True,
            "answer": "GraphMind was invented in 1980 by an ancient civilization.",
            "sufficient_evidence": True,
            "facts_used": [],  # no supporting facts
            "sources": [],
            "reasoning_path": "Hallucinated without facts.",
        }

        with patch("app.agents.reasoning_agent.answer_question", return_value=mock_reasoning_result):
            resp = client.post("/ask", json={"question": "When was GraphMind invented?"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["verification_status"] == "UNSUPPORTED"
        assert "don't have enough verified information" in data["answer"].lower()
        assert data["sufficient_evidence"] is False

    def test_ask_pipeline_verification_failure_never_marks_verified(self, client):
        """If verification service fails, answer is returned with verification_status='ERROR' and never verified."""
        mock_reasoning_result = {
            "ok": True,
            "answer": "GraphMind relies upon specialized neural associative memory graphs.",
            "sufficient_evidence": True,
            "facts_used": [
                {"fact_id": "f1", "subject": "GraphMind", "predicate": "uses_database", "object_value": "FalkorDB"}
            ],
            "sources": [],
            "reasoning_path": "Retrieved 1 fact.",
        }

        with (
            patch("app.agents.reasoning_agent.answer_question", return_value=mock_reasoning_result),
            patch("app.agents.verification_agent.generate_text", return_value={"ok": False, "error": "Gemini timeout"}),
        ):
            resp = client.post("/ask", json={"question": "Which database?"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["verification_status"] == "ERROR"
        assert "Gemini timeout" in data["verification_explanation"]


# ── 4. Live Integration Test with Running FalkorDB ─────────────────────────────

class TestLiveIntegration:

    def test_live_falkordb_verification_integration(self, client):
        """
        Integration test verifying a fact directly against the live running FalkorDB container.
        Skipped automatically if FalkorDB is not reachable.
        """
        from app.graph import check_connectivity, safe_graph_write
        from app.config import settings

        conn = check_connectivity(settings.FALKORDB_HOST, settings.FALKORDB_PORT, settings.FALKORDB_GRAPH)
        if not conn.get("ok"):
            pytest.skip("Live FalkorDB container is not reachable.")

        test_fact_id = "test_live_verify_001"
        test_source_id = "test_live_src_001"
        test_statement = "GraphMind integration test uses FalkorDB."

        # Write test nodes to live graph
        cypher = (
            "MERGE (s:Source {id: $sid}) "
            "ON CREATE SET s.text = $stext, s.source_type = 'test' "
            "MERGE (f:Fact {id: $fid}) "
            "ON CREATE SET f.subject = 'GraphMindIntegration', f.predicate = 'uses_db', "
            "              f.object_value = 'FalkorDB', f.status = 'active', f.confidence = 1.0 "
            "MERGE (s)-[:SUPPORTS]->(f) "
            "RETURN f.id"
        )
        write_res = safe_graph_write(
            settings.FALKORDB_HOST,
            settings.FALKORDB_PORT,
            settings.FALKORDB_GRAPH,
            cypher,
            {"sid": test_source_id, "fid": test_fact_id, "stext": test_statement},
        )
        assert write_res["ok"] is True

        try:
            # Call POST /verify with this real stored fact
            verify_payload = {
                "question": "What does GraphMindIntegration use?",
                "answer": "GraphMindIntegration uses FalkorDB.",
                "evidence": [
                    {
                        "fact_id": test_fact_id,
                        "subject": "GraphMindIntegration",
                        "predicate": "uses_db",
                        "object_value": "FalkorDB",
                    }
                ],
            }
            resp = client.post("/verify", json=verify_payload)
            assert resp.status_code == 200
            data = resp.json()

            assert data["ok"] is True
            assert data["status"] == "SUPPORTED"
            assert len(data["verified_claims"]) >= 1
            # Check source traceability retrieved from live FalkorDB
            assert len(data["evidence"]) == 1
            assert data["evidence"][0]["source_text"] == test_statement

        finally:
            # Clean up test nodes
            cleanup_cypher = (
                "MATCH (f:Fact {id: $fid}) OPTIONAL MATCH (s:Source {id: $sid}) DETACH DELETE f, s"
            )
            safe_graph_write(
                settings.FALKORDB_HOST,
                settings.FALKORDB_PORT,
                settings.FALKORDB_GRAPH,
                cleanup_cypher,
                {"fid": test_fact_id, "sid": test_source_id},
            )
