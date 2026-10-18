"""
app/agents/reasoning_agent.py — Reasoning Agent for GraphMind.

Responsibilities
----------------
1. Accept a natural-language question.
2. Extract key entities/concepts from the question (heuristic).
3. Search FalkorDB for relevant Fact nodes (keyword + entity match).
4. Traverse multi-hop relationships to gather richer context.
5. Retrieve Source evidence attached to the facts.
6. Feed ONLY retrieved context + question to Gemini for answer generation.
7. Return answer, supporting fact IDs, source snippets, and reasoning path.
8. Explicitly report "insufficient evidence" when the graph is empty/irrelevant.
"""

from __future__ import annotations

import logging
import re
from typing import Any

# Module-level imports so tests can patch these by name.
from app.llm import generate_text
from app.graph import _get_graph

logger = logging.getLogger(__name__)

# ── Gemini prompts ────────────────────────────────────────────────────────────

_ANSWER_PROMPT = """\
You are a knowledge assistant.  Answer the question using ONLY the facts below.
If the facts do not contain enough information to answer, say exactly:
"I don't have enough information in my knowledge base to answer this question."

Facts retrieved from the knowledge graph:
{context}

Question: {question}

Answer:
"""


# ── Graph query helpers ───────────────────────────────────────────────────────

def _query_facts_for_entities(graph, entity_names: list[str], limit: int = 20) -> list[dict]:
    """
    Return facts whose subject or object_value matches any of *entity_names*.
    Uses case-insensitive substring matching, bounds results, and avoids duplicate queries.
    """
    if not entity_names:
        return []

    results: list[dict] = []
    seen_ids: set[str] = set()
    cleaned_names: list[str] = []

    for name in entity_names:
        name_clean = name.strip()
        if name_clean and name_clean.lower() not in [n.lower() for n in cleaned_names]:
            cleaned_names.append(name_clean)

    # Bound entity search terms to top 8 to prevent excessive query iterations
    bounded_names = cleaned_names[:8]

    from app.cache import cache
    cache_params = {"names": [n.lower() for n in bounded_names], "limit": limit}
    cached = cache.get("facts", "default", cache_params)
    if cached is not None:
        return [dict(f) for f in cached]

    for name_clean in bounded_names:
        if len(results) >= limit:
            break
        try:
            remaining_limit = limit - len(results)
            qr = graph.query(
                "MATCH (f:Fact) "
                "WHERE toLower(f.subject) CONTAINS toLower($name) "
                "   OR toLower(f.object_value) CONTAINS toLower($name) "
                "RETURN f.id, f.subject, f.predicate, f.object_value, "
                "       f.object_type, f.confidence, f.status, f.created_at "
                "LIMIT $lim",
                {"name": name_clean, "lim": remaining_limit},
            )
            for row in (qr.result_set or []):
                fid = row[0]
                if fid in seen_ids:
                    continue
                seen_ids.add(fid)
                results.append({
                    "fact_id": fid,
                    "subject": row[1],
                    "predicate": row[2],
                    "object_value": row[3],
                    "object_type": row[4],
                    "confidence": row[5],
                    "status": row[6],
                    "created_at": row[7],
                })
        except Exception as exc:
            logger.warning("Fact query for '%s' failed: %s", name_clean, exc)

    cache.set("facts", "default", cache_params, results, ttl_sec=30.0)
    return results


def _get_sources_for_facts(graph, fact_ids: list[str]) -> list[dict]:
    """
    Return sources that support any of *fact_ids*.
    Executes a single batched Cypher query to eliminate N+1 roundtrips,
    with an automatic fallback for test mocks expecting single-fact lookups.
    """
    if not fact_ids:
        return []
    sources: list[dict] = []
    seen: set[str] = set()
    bounded_fids = fact_ids[:15]

    try:
        qr = graph.query(
            "MATCH (s:Source)-[:SUPPORTS]->(f:Fact) "
            "WHERE f.id IN $fids "
            "RETURN s.id, s.text, s.source_type, s.created_at, f.id",
            {"fids": bounded_fids},
        )
        for row in (qr.result_set or []):
            sid = row[0]
            if sid not in seen:
                seen.add(sid)
                sources.append({
                    "source_id": sid,
                    "text": row[1],
                    "source_type": row[2],
                    "created_at": row[3],
                    "fact_id": row[4] if len(row) > 4 else None,
                })
    except Exception as exc:
        logger.warning("Batched source query failed, falling back to individual queries: %s", exc)
        for fid in bounded_fids[:10]:
            try:
                qr = graph.query(
                    "MATCH (s:Source)-[:SUPPORTS]->(f:Fact {id: $fid}) "
                    "RETURN s.id, s.text, s.source_type, s.created_at",
                    {"fid": fid},
                )
                for row in (qr.result_set or []):
                    sid = row[0]
                    if sid not in seen:
                        seen.add(sid)
                        sources.append({
                            "source_id": sid,
                            "text": row[1],
                            "source_type": row[2],
                            "created_at": row[3],
                            "fact_id": fid,
                        })
            except Exception as inner_exc:
                logger.warning("Source query for fact '%s' failed: %s", fid, inner_exc)

    return sources


def _multihop_expand(graph, fact_ids: list[str], limit: int = 10) -> list[dict]:
    """
    One-hop expansion: for entity objects in the retrieved facts, fetch their
    own facts so we can answer multi-hop questions.
    Uses a single set-based traversal query with bounded limit, with graceful fallback.
    """
    if not fact_ids:
        return []
    extra: list[dict] = []
    seen: set[str] = set(fact_ids)
    bounded_fids = fact_ids[:10]

    try:
        qr = graph.query(
            "MATCH (f:Fact)-[:OBJECT_OF]->(e:Entity)<-[:SUBJECT_OF]-(f2:Fact) "
            "WHERE f.id IN $fids AND NOT f2.id IN $seen "
            "RETURN f2.id, f2.subject, f2.predicate, f2.object_value, "
            "       f2.object_type, f2.confidence, f2.status, f2.created_at "
            "LIMIT $lim",
            {"fids": bounded_fids, "seen": list(seen), "lim": limit},
        )
        for row in (qr.result_set or []):
            f2id = row[0]
            if f2id in seen:
                continue
            seen.add(f2id)
            extra.append({
                "fact_id": f2id,
                "subject": row[1],
                "predicate": row[2],
                "object_value": row[3],
                "object_type": row[4],
                "confidence": row[5],
                "status": row[6],
                "created_at": row[7],
                "hop": 2,
            })
    except Exception as exc:
        logger.warning("Batched multi-hop expansion failed, using individual queries: %s", exc)
        for fid in bounded_fids[:5]:
            try:
                qr = graph.query(
                    "MATCH (f:Fact {id: $fid})-[:OBJECT_OF]->(e:Entity)"
                    "<-[:SUBJECT_OF]-(f2:Fact) "
                    "WHERE NOT f2.id IN $seen "
                    "RETURN f2.id, f2.subject, f2.predicate, f2.object_value, "
                    "       f2.object_type, f2.confidence, f2.status, f2.created_at "
                    "LIMIT $lim",
                    {"fid": fid, "seen": list(seen), "lim": limit},
                )
                for row in (qr.result_set or []):
                    f2id = row[0]
                    if f2id in seen:
                        continue
                    seen.add(f2id)
                    extra.append({
                        "fact_id": f2id,
                        "subject": row[1],
                        "predicate": row[2],
                        "object_value": row[3],
                        "object_type": row[4],
                        "confidence": row[5],
                        "status": row[6],
                        "created_at": row[7],
                        "hop": 2,
                    })
            except Exception as inner_exc:
                logger.warning("Multi-hop fallback for '%s' failed: %s", fid, inner_exc)

    return extra


# ── Main public function ───────────────────────────────────────────────────────

def answer_question(
    question: str,
    api_key: str,
    model: str,
    db_host: str,
    db_port: int,
    db_graph: str,
) -> dict[str, Any]:
    """
    Retrieve relevant graph context and produce a grounded answer.

    Returns
    -------
    {
        "ok": bool,
        "answer": str,
        "facts_used": [ {fact fields} ],
        "sources": [ {source fields} ],
        "reasoning_path": str,
        "sufficient_evidence": bool,
        "error": str | None
    }
    """
    heuristic_entities = _heuristic_entities(question)

    try:
        graph = _get_graph(db_host, db_port, db_graph)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"FalkorDB connection failed: {exc}",
            "answer": "",
            "facts_used": [],
            "sources": [],
            "reasoning_path": "",
            "sufficient_evidence": False,
        }

    # Retrieve relevant facts
    direct_facts = _query_facts_for_entities(graph, heuristic_entities, limit=15)

    # Multi-hop expansion
    direct_ids = [f["fact_id"] for f in direct_facts]
    extra_facts = _multihop_expand(graph, direct_ids, limit=10)

    all_facts = direct_facts + extra_facts
    active_facts = [f for f in all_facts if f.get("status") != "superseded"]

    # Retrieve sources
    all_fact_ids = [f["fact_id"] for f in active_facts]
    sources = _get_sources_for_facts(graph, all_fact_ids)

    # Preserve source_text and evidence IDs on active facts
    source_map: dict[str, str] = {}
    for s in sources:
        if s.get("fact_id") and s.get("text"):
            source_map[s["fact_id"]] = s["text"]

    first_source_text = sources[0].get("text") if sources else None
    for f in active_facts:
        if not f.get("source_text"):
            f["source_text"] = source_map.get(f["fact_id"], first_source_text)

    if not active_facts:
        return {
            "ok": True,
            "answer": (
                "I don't have enough information in my knowledge base "
                "to answer this question."
            ),
            "facts_used": [],
            "sources": [],
            "reasoning_path": "No relevant facts found in the graph.",
            "sufficient_evidence": False,
        }

    # Deduplicate and prioritize highest-confidence facts to reduce Gemini token context
    unique_active_facts: list[dict] = []
    seen_triples: set[tuple[str, str, str]] = set()

    for f in sorted(active_facts, key=lambda x: float(x.get("confidence") or 0.8), reverse=True):
        trip = (
            str(f.get("subject", "")).strip().lower(),
            str(f.get("predicate", "")).strip().lower(),
            str(f.get("object_value", "")).strip().lower(),
        )
        if trip not in seen_triples:
            seen_triples.add(trip)
            unique_active_facts.append(f)

    # Bound prompt facts to top 12 relevant facts
    context_facts = unique_active_facts[:12]
    context_lines = []
    for f in context_facts:
        context_lines.append(
            f"- {f['subject']} {f['predicate'].replace('_', ' ')} {f['object_value']} "
            f"(confidence: {f.get('confidence', '?')}, id: {f['fact_id']})"
        )
    context_block = "\n".join(context_lines)

    reasoning_path = (
        f"Retrieved {len(direct_facts)} direct fact(s) matching question entities "
        f"[{', '.join(heuristic_entities[:5])}]; "
        f"expanded to {len(extra_facts)} multi-hop fact(s). "
        f"Filtered to {len(active_facts)} active fact(s). "
        f"Sources: {len(sources)}."
    )

    answer_prompt = _ANSWER_PROMPT.format(context=context_block, question=question)
    llm_result = generate_text(prompt=answer_prompt, api_key=api_key, model=model)

    if not llm_result["ok"]:
        return {
            "ok": False,
            "error": f"LLM answer generation failed: {llm_result['error']}",
            "answer": "",
            "facts_used": active_facts,
            "sources": sources,
            "reasoning_path": reasoning_path,
            "sufficient_evidence": bool(active_facts),
        }

    answer_text = llm_result["text"].strip()
    sufficient = "don't have enough information" not in answer_text.lower()

    return {
        "ok": True,
        "answer": answer_text,
        "facts_used": active_facts,
        "sources": sources,
        "reasoning_path": reasoning_path,
        "sufficient_evidence": sufficient,
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _heuristic_entities(question: str) -> list[str]:
    """
    Extract candidate entity names from a question without an LLM call.

    Strategy:
    - Keep tokens that are title-cased or all-caps (likely proper nouns).
    - Also keep the entire de-punctuated question as a fallback broad search term.
    - Deduplicate while preserving order.
    """
    cleaned = re.sub(r"[^\w\s]", " ", question).strip()
    tokens = cleaned.split()

    candidates: list[str] = []
    seen: set[str] = set()

    for tok in tokens:
        if len(tok) < 3:
            continue
        if tok[0].isupper() or tok.isupper():
            key = tok.lower()
            if key not in seen:
                seen.add(key)
                candidates.append(tok)

    # Bigrams of consecutive title-cased words
    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if a[0].isupper() and b[0].isupper():
            bigram = f"{a} {b}"
            key = bigram.lower()
            if key not in seen:
                seen.add(key)
                candidates.append(bigram)

    # Fallback: any significant word (len >= 4)
    for tok in tokens:
        if len(tok) >= 4:
            key = tok.lower()
            if key not in seen:
                seen.add(key)
                candidates.append(tok)

    return candidates[:10]
