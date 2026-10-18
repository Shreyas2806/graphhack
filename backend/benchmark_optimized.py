"""
Benchmark script to record empirical post-optimization metrics for GraphMind.
Measures:
1. Graph queries (direct FalkorDB Cypher with batched queries & indexes)
2. Cached vs uncached retrieval
3. Gemini LLM API latency with timeouts & retries
4. Verification Agent latency (deterministic token-matching vs LLM)
5. End-to-End POST /ask & POST /memory with cache invalidation
"""

import os
import sys
import time
import statistics
import json

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import settings
from app.graph import _get_graph, ensure_indexes
from app.llm import generate_text
from app.agents.reasoning_agent import _query_facts_for_entities, _get_sources_for_facts, _multihop_expand
from app.agents.verification_agent import verify_answer
from app.cache import cache
from fastapi.testclient import TestClient
from app.main import app


def run_post_benchmarks():
    client = TestClient(app)
    results = {}

    print("--- 1. Testing FalkorDB Optimized Retrieval ---")
    graph = _get_graph(settings.FALKORDB_HOST, settings.FALKORDB_PORT, settings.FALKORDB_GRAPH)
    
    # 1.1 Direct Ping
    graph_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        res = graph.query("MATCH (f:Fact) RETURN count(f)")
        t1 = time.perf_counter()
        graph_times.append((t1 - t0) * 1000)
    results["falkordb_ping_ms"] = {
        "mean": statistics.mean(graph_times),
        "median": statistics.median(graph_times),
        "min": min(graph_times),
        "max": max(graph_times),
    }
    print(f"FalkorDB Ping: {results['falkordb_ping_ms']}")

    # 1.2 Entity query with indexes (uncached first run)
    cache.clear()
    t0 = time.perf_counter()
    facts = _query_facts_for_entities(graph, ["GraphMind", "Python", "Alice"], limit=20)
    t1 = time.perf_counter()
    uncached_entity_ms = (t1 - t0) * 1000

    # 1.3 Entity query (cached subsequent runs)
    cached_entity_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        cached_facts = _query_facts_for_entities(graph, ["GraphMind", "Python", "Alice"], limit=20)
        t1 = time.perf_counter()
        cached_entity_times.append((t1 - t0) * 1000)

    results["graph_entity_query_ms"] = {
        "uncached_ms": uncached_entity_ms,
        "cached_mean_ms": statistics.mean(cached_entity_times),
        "cached_min_ms": min(cached_entity_times),
        "cached_max_ms": max(cached_entity_times),
        "speedup_factor": round(uncached_entity_ms / (statistics.mean(cached_entity_times) + 1e-6), 1),
    }
    print(f"Graph Entity Query (uncached vs cached): {results['graph_entity_query_ms']}")

    # 1.4 Batched Sources Retrieval
    fact_ids = [f["fact_id"] for f in facts[:5]]
    source_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        sources = _get_sources_for_facts(graph, fact_ids)
        t1 = time.perf_counter()
        source_times.append((t1 - t0) * 1000)
    results["graph_sources_retrieval_batched_ms"] = {
        "mean": statistics.mean(source_times),
        "median": statistics.median(source_times),
        "min": min(source_times),
        "max": max(source_times),
    }
    print(f"Graph Sources Retrieval (batched): {results['graph_sources_retrieval_batched_ms']}")

    # 1.5 Batched Multihop Traversal
    multihop_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        extra = _multihop_expand(graph, fact_ids)
        t1 = time.perf_counter()
        multihop_times.append((t1 - t0) * 1000)
    results["graph_multihop_batched_ms"] = {
        "mean": statistics.mean(multihop_times),
        "median": statistics.median(multihop_times),
        "min": min(multihop_times),
        "max": max(multihop_times),
    }
    print(f"Graph Multihop Expand (batched): {results['graph_multihop_batched_ms']}")

    # 1.6 GET /graph with pagination and caching
    cache.invalidate_namespace("graph")
    t0 = time.perf_counter()
    r1 = client.get("/graph?limit=50&skip=0")
    t1 = time.perf_counter()
    uncached_export_ms = (t1 - t0) * 1000

    cached_export_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        r2 = client.get("/graph?limit=50&skip=0")
        t1 = time.perf_counter()
        cached_export_times.append((t1 - t0) * 1000)

    results["api_get_graph_cached_ms"] = {
        "uncached_ms": uncached_export_ms,
        "cached_mean_ms": statistics.mean(cached_export_times),
        "cached_min_ms": min(cached_export_times),
        "speedup_factor": round(uncached_export_ms / (statistics.mean(cached_export_times) + 1e-6), 1),
    }
    print(f"GET /graph (uncached vs cached): {results['api_get_graph_cached_ms']}")

    print("\n--- 2. Testing Verification Agent Deterministic Performance ---")
    test_evidence = [
        {"fact_id": "fact_live_falkordb", "statement": "GraphMind uses database FalkorDB.", "source_text": "GraphMind uses FalkorDB for persistent graph memory."}
    ]
    v_det_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        v_res = verify_answer(
            question="What database does GraphMind use?",
            answer="GraphMind uses database FalkorDB.",
            evidence=test_evidence,
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            validate_against_db=False,
        )
        t1 = time.perf_counter()
        v_det_times.append((t1 - t0) * 1000)

    results["verification_deterministic_ms"] = {
        "mean": statistics.mean(v_det_times),
        "median": statistics.median(v_det_times),
        "min": min(v_det_times),
        "max": max(v_det_times),
        "status": v_res.status,
    }
    print(f"Verification deterministic fast-path: {results['verification_deterministic_ms']}")

    print("\n--- 3. Testing POST /memory Persistence & Invalidation ---")
    t0 = time.perf_counter()
    mem_resp = client.post("/memory", json={"text": "GraphMind includes Coordinator, Memory, Reasoning, and Verification agents."})
    t1 = time.perf_counter()
    mem_ms = (t1 - t0) * 1000
    results["post_memory_ms"] = {
        "status_code": mem_resp.status_code,
        "latency_ms": mem_ms,
        "facts_stored": mem_resp.json().get("facts_stored", 0) if mem_resp.status_code == 200 else 0,
    }
    print(f"POST /memory: {results['post_memory_ms']}")

    # Save results to json
    out_path = os.path.join(backend_dir, "optimized_metrics.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved optimized metrics to {out_path}")


if __name__ == "__main__":
    run_post_benchmarks()
