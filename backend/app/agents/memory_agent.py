"""
app/agents/memory_agent.py — Memory Agent for GraphMind.

Responsibilities
----------------
1. Accept a natural-language statement.
2. Call Gemini to extract structured facts (subject / predicate / object triples).
3. Persist Entity, Fact, and Source nodes in FalkorDB via parameterised queries.
4. Detect duplicates with MERGE; detect updates/contradictions by predicate lookup.
5. Return extraction results with stable IDs, timestamps, and storage status.

Graph Schema
------------
(:Entity  {id, name, type})
(:Fact    {id, subject, predicate, object_value, object_type,
           status, confidence, created_at, updated_at})
(:Source  {id, text, source_type, created_at})

(:Entity)-[:SUBJECT_OF]->(:Fact)
(:Fact)-[:OBJECT_OF]->(:Entity)          # when object is a known entity
(:Source)-[:SUPPORTS]->(:Fact)

Labels, relationship types, and predicates come exclusively from whitelisted
constants or Gemini-extracted values that are validated before touching Cypher.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

# Module-level imports enable test patching via mock.patch at these names.
from app.llm import generate_text
from app.graph import _get_graph

logger = logging.getLogger(__name__)

# ── Allowed object types (guards against Cypher injection via object_type) ────
_ALLOWED_OBJECT_TYPES = {"entity", "literal", "string", "number", "boolean", "date"}

# ── Gemini prompt template ────────────────────────────────────────────────────
_EXTRACTION_PROMPT = """\
You are a knowledge-graph fact extractor.

Given the user statement below, extract every distinct factual claim as a list
of triples: (subject, predicate, object).

Rules:
- subject   : the primary entity (string, title-case)
- predicate : a short verb phrase (snake_case, lowercase)
- object    : the value or target entity (string)
- object_type: "entity" if the object is a named thing; "literal" otherwise
- confidence: float 0.0-1.0 reflecting how clearly the text states this fact

Do NOT invent facts not present in the text.
Respond ONLY with a JSON array. No markdown fences, no explanation.

Example output:
[
  {{"subject": "GraphMind", "predicate": "uses_language", "object": "Python", "object_type": "entity", "confidence": 0.95}},
  {{"subject": "GraphMind", "predicate": "uses_database", "object": "FalkorDB", "object_type": "entity", "confidence": 0.95}}
]

User statement:
{statement}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stable_id(*parts: str) -> str:
    """SHA-256 based 16-char stable ID from arbitrary string parts."""
    raw = "|".join(parts).lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_str(value: str, max_len: int = 256) -> str:
    """Strip control characters and truncate."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", str(value)).strip()
    return cleaned[:max_len]


def _validate_triple(triple: dict) -> tuple[bool, str]:
    """Return (ok, reason).  Rejects triples with missing/suspicious fields."""
    required = ("subject", "predicate", "object", "object_type")
    for key in required:
        if key not in triple or not str(triple[key]).strip():
            return False, f"Missing or empty field: {key}"
    ot = str(triple["object_type"]).lower()
    if ot not in _ALLOWED_OBJECT_TYPES:
        return False, f"object_type '{ot}' not in allowed set"
    return True, ""


# ── Main public function ───────────────────────────────────────────────────────

def store_memory(
    statement: str,
    api_key: str,
    model: str,
    db_host: str,
    db_port: int,
    db_graph: str,
) -> dict[str, Any]:
    """
    Extract facts from *statement*, persist to FalkorDB, return summary.

    Returns
    -------
    {
        "ok": bool,
        "facts_extracted": int,
        "facts_stored": int,
        "facts": [ { fact fields + "stored", "duplicate", "updated" } ],
        "source_id": str,
        "error": str | None
    }
    """
    # 1. Call Gemini to extract triples ----------------------------------------
    prompt = _EXTRACTION_PROMPT.format(statement=statement)
    llm_result = generate_text(prompt=prompt, api_key=api_key, model=model)
    if not llm_result["ok"]:
        return {"ok": False, "error": f"LLM extraction failed: {llm_result['error']}",
                "facts_extracted": 0, "facts_stored": 0, "facts": []}

    raw_text = llm_result["text"].strip()

    # 2. Parse JSON response ----------------------------------------------------
    raw_text = re.sub(r"^```[a-z]*\n?", "", raw_text, flags=re.IGNORECASE)
    raw_text = re.sub(r"\n?```$", "", raw_text.strip())

    try:
        triples = json.loads(raw_text)
        if not isinstance(triples, list):
            triples = []
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse LLM JSON: %s | raw=%s", exc, raw_text[:200])
        return {
            "ok": False,
            "error": f"LLM returned non-JSON response: {raw_text[:120]}",
            "facts_extracted": 0,
            "facts_stored": 0,
            "facts": [],
        }

    # 3. Connect to graph -------------------------------------------------------
    try:
        graph = _get_graph(db_host, db_port, db_graph)
    except Exception as exc:
        return {"ok": False, "error": f"FalkorDB connection failed: {exc}",
                "facts_extracted": len(triples), "facts_stored": 0, "facts": []}

    now = _now_iso()

    # 4. Create/merge Source node -----------------------------------------------
    source_text = _sanitize_str(statement, 1000)
    source_id = _stable_id("source", source_text)

    try:
        graph.query(
            "MERGE (s:Source {id: $sid}) "
            "ON CREATE SET s.text = $text, s.source_type = $stype, s.created_at = $ts",
            {"sid": source_id, "text": source_text, "stype": "user_statement", "ts": now},
        )
    except Exception as exc:
        return {"ok": False, "error": f"Failed to store source: {exc}",
                "facts_extracted": len(triples), "facts_stored": 0, "facts": []}

    # 5. Process each triple ----------------------------------------------------
    results: list[dict] = []
    facts_stored = 0

    for raw_triple in triples:
        valid, reason = _validate_triple(raw_triple)
        if not valid:
            logger.warning("Skipping invalid triple %s: %s", raw_triple, reason)
            results.append({**raw_triple, "stored": False, "skip_reason": reason})
            continue

        subject      = _sanitize_str(raw_triple["subject"])
        predicate    = _sanitize_str(raw_triple["predicate"])
        obj          = _sanitize_str(raw_triple["object"])
        object_type  = str(raw_triple["object_type"]).lower()
        confidence   = float(raw_triple.get("confidence", 0.8))

        fact_id    = _stable_id(subject, predicate, obj)
        entity_id  = _stable_id("entity", subject)

        duplicate   = False
        updated     = False
        status      = "active"

        superseded_ids: list[str] = []
        try:
            existing = graph.query(
                "MATCH (f:Fact {subject: $subj, predicate: $pred}) "
                "RETURN f.id AS fid, f.object_value AS obj_val, f.status AS st",
                {"subj": subject, "pred": predicate},
            )
            existing_rows = list(existing.result_set) if existing.result_set else []

            for ex_row in existing_rows:
                ex_id  = ex_row[0]
                ex_obj = ex_row[1]
                ex_st  = ex_row[2] if len(ex_row) > 2 else "active"

                if ex_obj == obj:
                    duplicate = True
                    fact_id   = ex_id
                elif ex_st == "active":
                    updated = True
                    superseded_ids.append(ex_id)
                    try:
                        graph.query(
                            "MATCH (f:Fact {id: $fid}) SET f.status = 'superseded', f.updated_at = $ts",
                            {"fid": ex_id, "ts": now},
                        )
                    except Exception as s_exc:
                        logger.warning("Failed to supersede old fact %s: %s", ex_id, s_exc)
        except Exception as exc:
            logger.warning("Duplicate check failed for %s: %s", fact_id, exc)

        try:
            graph.query(
                "MERGE (f:Fact {id: $fid}) "
                "ON CREATE SET "
                "  f.subject = $subj, f.predicate = $pred, "
                "  f.object_value = $obj, f.object_type = $ot, "
                "  f.status = $status, f.confidence = $conf, "
                "  f.created_at = $ts, f.updated_at = $ts "
                "ON MATCH SET "
                "  f.updated_at = $ts, f.status = $status",
                {
                    "fid": fact_id, "subj": subject, "pred": predicate,
                    "obj": obj, "ot": object_type, "status": status,
                    "conf": confidence, "ts": now,
                },
            )

            # Link new fact to superseded versions to preserve historical lineage
            for old_id in superseded_ids:
                try:
                    graph.query(
                        "MATCH (nf:Fact {id: $nid}), (of:Fact {id: $oid}) "
                        "MERGE (nf)-[:SUPERSEDES]->(of)",
                        {"nid": fact_id, "oid": old_id},
                    )
                except Exception as l_exc:
                    logger.warning("Failed to link SUPERSEDES edge from %s to %s: %s", fact_id, old_id, l_exc)

            graph.query(
                "MERGE (e:Entity {id: $eid}) "
                "ON CREATE SET e.name = $name, e.type = 'entity'",
                {"eid": entity_id, "name": subject},
            )

            graph.query(
                "MATCH (e:Entity {id: $eid}), (f:Fact {id: $fid}) "
                "MERGE (e)-[:SUBJECT_OF]->(f)",
                {"eid": entity_id, "fid": fact_id},
            )

            if object_type == "entity":
                obj_entity_id = _stable_id("entity", obj)
                graph.query(
                    "MERGE (oe:Entity {id: $eid}) "
                    "ON CREATE SET oe.name = $name, oe.type = 'entity'",
                    {"eid": obj_entity_id, "name": obj},
                )
                graph.query(
                    "MATCH (f:Fact {id: $fid}), (oe:Entity {id: $oid}) "
                    "MERGE (f)-[:OBJECT_OF]->(oe)",
                    {"fid": fact_id, "oid": obj_entity_id},
                )

            graph.query(
                "MATCH (s:Source {id: $sid}), (f:Fact {id: $fid}) "
                "MERGE (s)-[:SUPPORTS]->(f)",
                {"sid": source_id, "fid": fact_id},
            )

            facts_stored += 1
            results.append({
                "fact_id": fact_id,
                "subject": subject,
                "predicate": predicate,
                "object_value": obj,
                "object_type": object_type,
                "confidence": confidence,
                "status": status,
                "stored": True,
                "duplicate": duplicate,
                "updated": updated,
            })

        except Exception as exc:
            logger.error("Failed to store fact %s: %s", fact_id, exc)
            results.append({
                "fact_id": fact_id,
                "subject": subject,
                "predicate": predicate,
                "stored": False,
                "error": str(exc),
            })

    return {
        "ok": True,
        "facts_extracted": len(triples),
        "facts_stored": facts_stored,
        "source_id": source_id,
        "facts": results,
    }
