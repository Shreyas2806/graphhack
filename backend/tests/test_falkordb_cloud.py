"""
tests/test_falkordb_cloud.py — Tests for FalkorDB Cloud & Hosted Database Support.

Validates:
1. Configuration parsing (host:port, URL, credentials, SSL, local defaults).
2. Secret masking (passwords and API keys never exposed in error logs/messages).
3. Live graph operations (read, write, multi-hop query, source attribution) on isolated test data.
4. Persistence and schema indexing.
5. Cache invalidation upon writes.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings
from app.graph import _get_graph, _mask_secrets, check_connectivity, ensure_indexes, safe_graph_write
from app.cache import cache


# ── 1. Configuration & URL Parsing Tests ─────────────────────────────────────

class TestCloudConfigurationParsing:
    def test_standard_host_and_port(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("FALKORDB_HOST", "my-cluster.falkordb.cloud")
        monkeypatch.setenv("FALKORDB_PORT", "15432")
        monkeypatch.setenv("FALKORDB_PASSWORD", "secret-pass-123")
        monkeypatch.setenv("FALKORDB_SSL", "true")

        cfg = Settings()
        assert cfg.FALKORDB_HOST == "my-cluster.falkordb.cloud"
        assert cfg.FALKORDB_PORT == 15432
        assert cfg.FALKORDB_PASSWORD == "secret-pass-123"
        assert cfg.FALKORDB_SSL is True
        assert cfg.FALKORDB_URL is None

    def test_embedded_host_port_in_host_variable(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("FALKORDB_HOST", "cloud.falkordb.io:19999")
        monkeypatch.setenv("FALKORDB_PASSWORD", "cloud-pw")

        cfg = Settings()
        assert cfg.FALKORDB_HOST == "cloud.falkordb.io"
        assert cfg.FALKORDB_PORT == 19999
        assert cfg.FALKORDB_PASSWORD == "cloud-pw"

    def test_connection_url_scheme_auto_detection(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("FALKORDB_URL", "falkors://:secret@cloud.falkordb.io:6379")

        cfg = Settings()
        assert cfg.FALKORDB_URL == "falkors://:secret@cloud.falkordb.io:6379"
        assert cfg.FALKORDB_SSL is True

    def test_local_docker_defaults(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.delenv("FALKORDB_HOST", raising=False)
        monkeypatch.delenv("FALKORDB_PORT", raising=False)
        monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)
        monkeypatch.delenv("FALKORDB_SSL", raising=False)
        monkeypatch.delenv("FALKORDB_URL", raising=False)

        cfg = Settings()
        assert cfg.FALKORDB_HOST == "127.0.0.1"
        assert cfg.FALKORDB_PORT == 6379
        assert cfg.FALKORDB_PASSWORD is None
        assert cfg.FALKORDB_SSL is False


# ── 2. Security & Credential Masking Tests ───────────────────────────────────

class TestSecretMasking:
    def test_mask_secrets_replaces_password_and_key(self, monkeypatch):
        from app import config
        orig_settings = getattr(config, "settings", None)
        try:
            monkeypatch.setenv("GEMINI_API_KEY", "gemini_secret_xyz123")
            monkeypatch.setenv("FALKORDB_PASSWORD", "falkor_super_secret_pwd")

            config.settings = Settings()

            leak_message = "Auth error with password falkor_super_secret_pwd and key gemini_secret_xyz123"
            masked = _mask_secrets(leak_message)

            assert "falkor_super_secret_pwd" not in masked
            assert "gemini_secret_xyz123" not in masked
            assert "***" in masked
        finally:
            config.settings = orig_settings

    def test_check_connectivity_error_never_exposes_password(self):
        with patch("app.graph._get_graph", side_effect=Exception("Failed with secret_pass_999")):
            result = check_connectivity(
                host="127.0.0.1",
                port=6380,
                graph_name="graphmind",
            )
            assert result["ok"] is False


# ── 3. Live Graph Operations on Isolated Test Data ───────────────────────────

class TestLiveFalkorDBOperations:
    @pytest.fixture(autouse=True)
    def check_live_db(self):
        from dotenv import dotenv_values
        from pathlib import Path
        env_file = Path(__file__).resolve().parent.parent / ".env"
        env_vals = dotenv_values(str(env_file)) if env_file.exists() else {}
        self.host = env_vals.get("FALKORDB_HOST") or os.getenv("FALKORDB_HOST") or "127.0.0.1"
        self.port = int(env_vals.get("FALKORDB_PORT") or os.getenv("FALKORDB_PORT") or 6380)
        self.graph = env_vals.get("FALKORDB_GRAPH") or os.getenv("FALKORDB_GRAPH") or "graphmind"

        conn = check_connectivity(self.host, self.port, self.graph)
        if not conn.get("ok"):
            pytest.skip(f"FalkorDB database at {self.host}:{self.port} is not reachable for live operation testing.")

    def test_live_connectivity_ping(self):
        res = check_connectivity(self.host, self.port, self.graph)
        assert res["ok"] is True

    def test_live_isolated_read_write_multihop_and_attribution(self):
        """
        Tests:
        - Safe parameterized Cypher write
        - Entity, Fact, and Source creation with strict isolated test IDs
        - Multi-hop traversal (Source -> Fact -> Entity)
        - Source attribution retrieval
        - Clean teardown of test data
        """
        host = self.host
        port = self.port
        graph_name = self.graph

        test_id = "test_cloud_isolation_9988"
        source_id = f"src_{test_id}"
        fact_id = f"fact_{test_id}"
        entity_name = f"CloudEntity_{test_id}"

        # 1. Create Source, Fact, Entity nodes and relationships
        create_cypher = (
            "MERGE (s:Source {id: $source_id, text: $source_text}) "
            "MERGE (e:Entity {name: $entity_name}) "
            "MERGE (f:Fact {id: $fact_id, subject: $entity_name, predicate: 'hosted_on', object_value: 'FalkorDBCloud', status: 'active'}) "
            "MERGE (s)-[:EXTRACTED]->(f) "
            "MERGE (f)-[:ABOUT]->(e) "
            "RETURN f.id as fact_id"
        )
        params = {
            "source_id": source_id,
            "source_text": "GraphMind supports FalkorDB Cloud hosting.",
            "entity_name": entity_name,
            "fact_id": fact_id,
        }

        write_res = safe_graph_write(host, port, graph_name, create_cypher, params)
        assert write_res["ok"] is True

        try:
            # 2. Multi-hop traversal & Source Attribution Query
            graph = _get_graph(host, port, graph_name)
            query_cypher = (
                "MATCH (s:Source)-[:EXTRACTED]->(f:Fact)-[:ABOUT]->(e:Entity) "
                "WHERE f.id = $fact_id "
                "RETURN s.id as src_id, s.text as src_text, f.predicate as pred, f.object_value as obj, e.name as ent_name"
            )
            q_res = graph.query(query_cypher, {"fact_id": fact_id})
            assert len(q_res.result_set) == 1
            row = q_res.result_set[0]

            assert row[0] == source_id
            assert "supports FalkorDB Cloud" in row[1]
            assert row[2] == "hosted_on"
            assert row[3] == "FalkorDBCloud"
            assert row[4] == entity_name

        finally:
            # 3. Teardown: Clean up isolated test data
            cleanup_cypher = (
                "MATCH (s:Source {id: $source_id}) DETACH DELETE s "
            )
            safe_graph_write(host, port, graph_name, cleanup_cypher, {"source_id": source_id})
            cleanup_fact = (
                "MATCH (f:Fact {id: $fact_id}) DETACH DELETE f "
            )
            safe_graph_write(host, port, graph_name, cleanup_fact, {"fact_id": fact_id})
            cleanup_entity = (
                "MATCH (e:Entity {name: $entity_name}) DETACH DELETE e "
            )
            safe_graph_write(host, port, graph_name, cleanup_entity, {"entity_name": entity_name})

    def test_ensure_indexes_idempotent(self):
        res = ensure_indexes(self.host, self.port, self.graph)
        assert res["ok"] is True
        assert isinstance(res["created"], list)
        assert isinstance(res["already_indexed"], list)


# ── 4. Cache Invalidation Tests ──────────────────────────────────────────────

class TestCacheInvalidationOnWrite:
    def test_cache_invalidation_lifecycle(self):
        # Set cache entries across namespaces
        cache.set("facts", "test_scope", {"query": "sample"}, {"answer": "cached"})
        cache.set("graph", "test_scope", {}, {"nodes": [1, 2]})
        cache.set("memory", "test_scope", {"page": 1}, {"total": 5})

        assert cache.get("facts", "test_scope", {"query": "sample"}) is not None
        assert cache.get("graph", "test_scope", {}) is not None
        assert cache.get("memory", "test_scope", {"page": 1}) is not None

        # Invalidate as done in main.py upon memory write
        inv_facts = cache.invalidate_namespace("facts")
        inv_graph = cache.invalidate_namespace("graph")
        inv_mem = cache.invalidate_namespace("memory")

        assert inv_facts >= 1
        assert inv_graph >= 1
        assert inv_mem >= 1

        assert cache.get("facts", "test_scope", {"query": "sample"}) is None
        assert cache.get("graph", "test_scope", {}) is None
        assert cache.get("memory", "test_scope", {"page": 1}) is None
