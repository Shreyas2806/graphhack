"""
Benchmark script to record empirical baseline metrics for GraphMind.
Measures:
1. Graph queries (direct FalkorDB Cypher latency)
2. Gemini LLM API latency
3. Verification Agent latency (deterministic vs LLM)
4. End-to-end Question Answering (POST /ask)
5. End-to-end Memory Storage (POST /memory)
"""

import os
import sys
import time
import statistics
import json

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import settings
from app.graph import _get_graph
from app.llm import generate_text
from app.agents.memory_agent import store_memory
from app.agents.reasoning_agent import answer_question, _query_facts_for_entities, _get_sources_for_facts, _multihop_expand
from app.agents.verification_agent import verify_answer
from fastapi.testclient import TestClient
from app.main import app

def run_benchmarks():
    client = TestClient(app)
    results = {}

    print("--- 1. Testing FalkorDB Direct Retrieval Baseline ---")
    graph = _get_graph(settings.FALKORDB_HOST, settings.FALKORDB_PORT, settings.FALKORDB_GRAPH)
    
    # Measure simple ping / match
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

    # Measure entity query
    entity_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        facts = _query_facts_for_entities(graph, ["GraphMind", "Python", "Alice"], limit=20)
        t1 = time.perf_counter()
        entity_times.append((t1 - t0) * 1000)
    results["graph_entity_query_ms"] = {
        "mean": statistics.mean(entity_times),
        "median": statistics.median(entity_times),
        "min": min(entity_times),
        "max": max(entity_times),
        "count_retrieved": len(facts),
    }
    print(f"Graph Entity Query: {results['graph_entity_query_ms']}")

    # Measure source retrieval (existing N+1 pattern)
    fact_ids = [f["fact_id"] for f in facts[:5]]
    source_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        sources = _get_sources_for_facts(graph, fact_ids)
        t1 = time.perf_counter()
        source_times.append((t1 - t0) * 1000)
    results["graph_sources_retrieval_ms"] = {
        "mean": statistics.mean(source_times),
        "median": statistics.median(source_times),
        "min": min(source_times),
        "max": max(source_times),
    }
    print(f"Graph Sources Retrieval (N+1): {results['graph_sources_retrieval_ms']}")

    # Measure multihop expand
    multihop_times = []
    for _ in range(10):
        t0 = time.perf_counter()
        extra = _multihop_expand(graph, fact_ids)
        t1 = time.perf_counter()
        multihop_times.append((t1 - t0) * 1000)
    results["graph_multihop_ms"] = {
        "mean": statistics.mean(multihop_times),
        "median": statistics.median(multihop_times),
        "min": min(multihop_times),
        "max": max(multihop_times),
    }
    print(f"Graph Multihop Expand: {results['graph_multihop_ms']}")

    # Measure export graph GET /graph
    export_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        r = client.get("/graph?limit=100")
        t1 = time.perf_counter()
        export_times.append((t1 - t0) * 1000)
    results["api_get_graph_ms"] = {
        "mean": statistics.mean(export_times),
        "median": statistics.median(export_times),
        "min": min(export_times),
        "max": max(export_times),
    }
    print(f"GET /graph: {results['api_get_graph_ms']}")

    print("\n--- 2. Testing Gemini LLM Baseline Latency ---")
    gemini_times = []
    errors = 0
    for i in range(3):
        t0 = time.perf_counter()
        res = generate_text("Reply with exactly 'OK'", settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
        t1 = time.perf_counter()
        if res.get("ok"):
            gemini_times.append((t1 - t0) * 1000)
        else:
            errors += 1
            print(f"Gemini error: {res.get('error')}")
    results["gemini_call_ms"] = {
        "mean": statistics.mean(gemini_times) if gemini_times else None,
        "median": statistics.median(gemini_times) if gemini_times else None,
        "min": min(gemini_times) if gemini_times else None,
        "max": max(gemini_times) if gemini_times else None,
        "error_count": errors,
    }
    print(f"Gemini direct call: {results['gemini_call_ms']}")

    print("\n--- 3. Testing Verification Agent Baseline Latency ---")
    # Deterministic verification path (exact match)
    v_det_times = []
    test_evidence = [
        {"fact_id": "f1", "statement": "GraphMind uses FalkorDB.", "source_text": "GraphMind uses FalkorDB."}
    ]
    for _ in range(5):
        t0 = time.perf_counter()
        v_res = verify_answer(
            question="What database does GraphMind use?",
            answer="GraphMind uses FalkorDB.",
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
    }
    print(f"Verification deterministic: {results['verification_deterministic_ms']}")

    # LLM verification path (requires semantic evaluation)
    v_llm_times = []
    for _ in range(2):
        t0 = time.perf_counter()
        v_res = verify_answer(
            question="What database does GraphMind use and why?",
            answer="GraphMind leverages FalkorDB for low-latency graph traversals and Redis compatibility.",
            evidence=test_evidence,
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            validate_against_db=False,
        )
        t1 = time.perf_counter()
        v_llm_times.append((t1 - t0) * 1000)
    results["verification_llm_ms"] = {
        "mean": statistics.mean(v_llm_times) if v_llm_times else None,
        "median": statistics.median(v_llm_times) if v_llm_times else None,
        "min": min(v_llm_times) if v_llm_times else None,
        "max": max(v_llm_times) if v_llm_times else None,
    }
    print(f"Verification LLM: {results['verification_llm_ms']}")

    print("\n--- 4. Testing End-to-End POST /ask Baseline ---")
    ask_times = []
    ask_responses = []
    for q in ["What database does GraphMind use?", "Who works on GraphMind?"]:
        t0 = time.perf_counter()
        resp = client.post("/ask", json={"question": q})
        t1 = time.perf_counter()
        if resp.status_code == 200:
            ask_times.append((t1 - t0) * 1000)
            data = resp.json()
            ask_responses.append({
                "question": q,
                "latency_ms": round((t1 - t0) * 1000, 2),
                "verification_status": data.get("verification_status"),
                "facts_count": len(data.get("facts_used", [])),
                "agent_trace": data.get("agent_trace", []),
            })
        else:
            print(f"Ask error: {resp.status_code} {resp.text}")
    results["e2e_ask_ms"] = {
        "mean": statistics.mean(ask_times) if ask_times else None,
        "median": statistics.median(ask_times) if ask_times else None,
        "min": min(ask_times) if ask_times else None,
        "max": max(ask_times) if ask_times else None,
        "details": ask_responses,
    }
    print(f"End-to-End POST /ask: {results['e2e_ask_ms']}")

    # Save results to json
    out_path = os.path.join(backend_dir, "baseline_metrics.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved baseline metrics to {out_path}")

if __name__ == "__main__":
    run_benchmarks()
