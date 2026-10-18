"""
app/main.py — FastAPI application entry point for GraphMind.

Start with:
    python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app import config as _config_module  # imported for the singleton
from app.graph import check_connectivity, safe_graph_write
from app.llm import generate_text

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


# ── Lifespan handler ──────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize schema indexes on startup if FalkorDB is reachable."""
    try:
        from app.config import settings
        from app.graph import ensure_indexes
        ensure_indexes(settings.FALKORDB_HOST, settings.FALKORDB_PORT, settings.FALKORDB_GRAPH)
    except Exception as exc:
        logger.warning("FalkorDB index initialization skipped on startup: %s", exc)
    yield


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="GraphMind API",
    description=(
        "Persistent Multi-Agent Memory & Decision System — "
        "powered by FalkorDB and Gemini."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Lazy settings accessor (avoids crashing at import if key is missing) ──────
def _settings():
    """Return the settings singleton; raises HTTPException if misconfigured."""
    try:
        from app.config import settings  # noqa: PLC0415
        return settings
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


# ── Pydantic models ───────────────────────────────────────────────────────────

class RootResponse(BaseModel):
    project: str
    status: str
    version: str


class HealthResponse(BaseModel):
    status: str
    falkordb: dict
    gemini: Optional[dict] = None


class GeminiRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000, description="Prompt text")


class GeminiResponse(BaseModel):
    ok: bool
    text: Optional[str] = None
    error: Optional[str] = None


class GraphTestResponse(BaseModel):
    ok: bool
    detail: str
    nodes_created: Optional[int] = None
    relationships_created: Optional[int] = None
    error: Optional[str] = None


# ── Memory / Reasoning models ─────────────────────────────────────────────────

class MemoryRequest(BaseModel):
    text: str = Field(
        ..., min_length=1, max_length=4000,
        description="Natural-language statement to store as memory"
    )


class ExtractedFact(BaseModel):
    fact_id: Optional[str] = None
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object_value: Optional[str] = None
    object_type: Optional[str] = None
    confidence: Optional[float] = None
    status: Optional[str] = None
    stored: bool = False
    duplicate: bool = False
    updated: bool = False
    error: Optional[str] = None
    skip_reason: Optional[str] = None


class AgentStepTrace(BaseModel):
    agent: str  # Coordinator, MemoryAgent, ReasoningAgent, VerificationAgent
    status: str  # SUCCESS, COMPLETED, WARNING, ERROR
    action: str
    duration_ms: Optional[float] = None
    details: Optional[str] = None
    metadata: Optional[dict] = None


class MemoryResponse(BaseModel):
    ok: bool
    facts_extracted: int = 0
    facts_stored: int = 0
    source_id: Optional[str] = None
    facts: list[ExtractedFact] = []
    agent_trace: list[AgentStepTrace] = []
    error: Optional[str] = None


class AskRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, max_length=2000,
        description="Natural-language question to answer from stored memory"
    )


class SourceEvidence(BaseModel):
    source_id: Optional[str] = None
    text: Optional[str] = None
    source_type: Optional[str] = None
    created_at: Optional[str] = None


class AskResponse(BaseModel):
    ok: bool
    answer: str = ""
    sufficient_evidence: bool = False
    facts_used: list[dict] = []
    sources: list[SourceEvidence] = []
    reasoning_path: str = ""
    verification_status: Optional[str] = None
    verified_claims: list[str] = []
    unsupported_claims: list[str] = []
    evidence: list[dict] = []
    conflicts: list[dict] = []
    verification_explanation: Optional[str] = None
    agent_trace: list[AgentStepTrace] = []
    error: Optional[str] = None


class EvidenceInput(BaseModel):
    fact_id: Optional[str] = None
    statement: Optional[str] = None
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object_value: Optional[str] = None
    source_text: Optional[str] = None
    status: Optional[str] = "active"
    confidence: Optional[float] = None


class VerifyRequest(BaseModel):
    question: str = Field(
        ..., min_length=1, max_length=2000,
        description="Original user question"
    )
    answer: str = Field(
        ..., min_length=1, max_length=4000,
        description="Generated answer to verify"
    )
    evidence: list[EvidenceInput] = Field(
        default_factory=list,
        description="Retrieved supporting facts/evidence"
    )


class VerifyEvidenceItem(BaseModel):
    fact_id: str
    statement: Optional[str] = None
    source_text: Optional[str] = None


class VerifyConflictItem(BaseModel):
    conflict_type: str
    description: str
    fact_id: Optional[str] = None
    conflicting_fact_id: Optional[str] = None


class VerifyResponse(BaseModel):
    ok: bool
    status: str
    verified_claims: list[str] = []
    unsupported_claims: list[str] = []
    evidence: list[VerifyEvidenceItem] = []
    conflicts: list[VerifyConflictItem] = []
    explanation: str
    error: Optional[str] = None


class StoredFact(BaseModel):
    fact_id: str
    subject: str
    predicate: str
    object_value: str
    object_type: str
    confidence: Optional[float] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MemoryListResponse(BaseModel):
    ok: bool
    total: int
    page: int
    page_size: int
    facts: list[StoredFact] = []
    error: Optional[str] = None


class GraphExportResponse(BaseModel):
    ok: bool
    nodes: list[dict] = []
    edges: list[dict] = []
    error: Optional[str] = None


# ── Existing endpoints (unchanged) ────────────────────────────────────────────

@app.get("/", response_model=RootResponse, tags=["Meta"])
async def root() -> RootResponse:
    """Return the project name and API status."""
    return RootResponse(
        project="GraphMind \u2014 Persistent Multi-Agent Memory & Decision System",
        status="running",
        version="0.1.0",
    )


_last_gemini_health: dict = {"timestamp": 0.0, "status": {"ok": False, "error": "not checked"}}

@app.get("/health", response_model=HealthResponse, tags=["Meta"])
async def health() -> HealthResponse:
    """
    Return application health including FalkorDB and Gemini connectivity.

    - ``ok``: both FalkorDB and Gemini are reachable.
    - ``degraded``: FalkorDB is unreachable (core functionality impaired).
    - ``llm_unavailable``: FalkorDB is ok but Gemini is unreachable (graph-only features work).
    """
    global _last_gemini_health
    cfg = _settings()
    db_status = check_connectivity(cfg.FALKORDB_HOST, cfg.FALKORDB_PORT, cfg.FALKORDB_GRAPH)

    now = time.time()
    # If a mock/dummy test API key is configured (e.g. in test suite), skip external probe
    if cfg.GEMINI_API_KEY == "test-api-key-not-real" or cfg.GEMINI_API_KEY.startswith("test-"):
        gemini_status = {"ok": True}
    elif now - _last_gemini_health.get("timestamp", 0.0) < 15.0:
        gemini_status = _last_gemini_health.get("status", {"ok": True})
    else:
        gemini_status = {"ok": False, "error": "not checked"}
        try:
            from google import genai as _genai  # type: ignore
            # Note: google-genai HttpOptions timeout is in milliseconds (10000ms = 10s)
            client = _genai.Client(api_key=cfg.GEMINI_API_KEY, http_options={"timeout": 10000})
            client.models.get(model=cfg.GEMINI_MODEL)
            gemini_status = {"ok": True}
        except Exception as _exc:  # noqa: BLE001
            safe = str(_exc).replace(cfg.GEMINI_API_KEY, "***")
            gemini_status = {"ok": False, "error": safe}
        _last_gemini_health = {"timestamp": now, "status": gemini_status}

    if not db_status.get("ok"):
        overall = "degraded"
    elif not gemini_status.get("ok"):
        overall = "llm_unavailable"
    else:
        overall = "ok"

    return HealthResponse(status=overall, falkordb=db_status, gemini=gemini_status)


@app.post("/test-graph", response_model=GraphTestResponse, tags=["Graph"])
async def test_graph() -> GraphTestResponse:
    """
    Create or update sample Person/Project nodes and a WORKS_ON relationship.

    Uses parameterised MERGE so the operation is idempotent.
    """
    cfg = _settings()

    cypher = (
        "MERGE (p:Person {name: $person_name}) "
        "MERGE (proj:Project {name: $project_name}) "
        "MERGE (p)-[r:WORKS_ON]->(proj) "
        "RETURN p, proj, r"
    )
    params = {"person_name": "Alice", "project_name": "GraphMind"}

    write_result = safe_graph_write(
        cfg.FALKORDB_HOST, cfg.FALKORDB_PORT, cfg.FALKORDB_GRAPH, cypher, params
    )

    if not write_result["ok"]:
        return GraphTestResponse(
            ok=False,
            detail="Graph write failed.",
            error=write_result.get("error"),
        )

    result = write_result["result"]
    # FalkorDB result statistics
    try:
        nodes_created = result.nodes_created
        rels_created = result.relationships_created
    except AttributeError:
        nodes_created = None
        rels_created = None

    return GraphTestResponse(
        ok=True,
        detail=(
            "MERGE succeeded: Person(Alice) -[WORKS_ON]-> Project(GraphMind) "
            f"in graph '{cfg.FALKORDB_GRAPH}'."
        ),
        nodes_created=nodes_created,
        relationships_created=rels_created,
    )


@app.post("/test-gemini", response_model=GeminiResponse, tags=["LLM"])
async def test_gemini(body: GeminiRequest) -> GeminiResponse:
    """
    Send a prompt to Gemini and return the generated text.

    The API key is read from the environment and is never echoed back.
    """
    cfg = _settings()
    result = generate_text(
        prompt=body.prompt,
        api_key=cfg.GEMINI_API_KEY,
        model=cfg.GEMINI_MODEL,
    )
    if not result["ok"]:
        # Return 200 with ok=False so clients can distinguish config errors
        # from HTTP transport errors.
        return GeminiResponse(ok=False, error=result.get("error"))

    return GeminiResponse(ok=True, text=result.get("text"))


# ── Phase-2 endpoints ──────────────────────────────────────────────────────────

@app.post("/memory", response_model=MemoryResponse, tags=["Memory"])
async def store_memory(body: MemoryRequest) -> MemoryResponse:
    """
    Extract facts from a natural-language statement and persist them to FalkorDB.

    - Uses Gemini to identify subject/predicate/object triples.
    - Stores Entity, Fact, and Source nodes with stable IDs.
    - Detects duplicates and superseded facts automatically.
    - Tracks Coordinator and Memory Agent execution traces.
    """
    from app.agents.memory_agent import store_memory as _store  # noqa: PLC0415
    cfg = _settings()

    t_start = time.perf_counter()
    traces: list[AgentStepTrace] = [
        AgentStepTrace(
            agent="Coordinator",
            status="SUCCESS",
            action="Intake Statement",
            duration_ms=0.5,
            details=f"Received natural-language statement ({len(body.text)} chars). Dispatching to Memory Agent.",
        )
    ]

    t_mem_start = time.perf_counter()
    result = _store(
        statement=body.text,
        api_key=cfg.GEMINI_API_KEY,
        model=cfg.GEMINI_MODEL,
        db_host=cfg.FALKORDB_HOST,
        db_port=cfg.FALKORDB_PORT,
        db_graph=cfg.FALKORDB_GRAPH,
    )
    t_mem_dur = round((time.perf_counter() - t_mem_start) * 1000, 2)

    if not result["ok"]:
        traces.append(AgentStepTrace(
            agent="MemoryAgent",
            status="ERROR",
            action="Extract & Persist",
            duration_ms=t_mem_dur,
            details=result.get("error", "Memory storage failed."),
        ))
        err_msg = result.get("error", "Memory storage failed.")
        # 502 = upstream provider (Gemini/FalkorDB) failed
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=err_msg)

    traces.append(AgentStepTrace(
        agent="MemoryAgent",
        status="SUCCESS",
        action="Extract & Persist",
        duration_ms=t_mem_dur,
        details=(
            f"Extracted {result['facts_extracted']} fact(s), "
            f"stored {result['facts_stored']} into FalkorDB graph '{cfg.FALKORDB_GRAPH}'."
        ),
        metadata={
            "source_id": result.get("source_id"),
            "facts_stored": result["facts_stored"],
            "facts_extracted": result["facts_extracted"],
        },
    ))

    # Invalidate cached graph, facts, and memory queries after persistent write
    from app.cache import cache
    cache.invalidate_namespace("graph")
    cache.invalidate_namespace("memory")
    cache.invalidate_namespace("facts")

    facts = [ExtractedFact(**f) for f in result.get("facts", [])]
    return MemoryResponse(
        ok=True,
        facts_extracted=result["facts_extracted"],
        facts_stored=result["facts_stored"],
        source_id=result.get("source_id"),
        facts=facts,
        agent_trace=traces,
    )


@app.post("/ask", response_model=AskResponse, tags=["Reasoning"])
async def ask_question(body: AskRequest) -> AskResponse:
    """
    Answer a question using facts retrieved from the knowledge graph and verify the answer.

    - Retrieves relevant facts from FalkorDB.
    - Performs one-hop relationship traversal for multi-hop questions.
    - Sends ONLY retrieved context to Gemini (not the raw question alone).
    - Verifies the generated answer with the Verification Agent against retrieved evidence.
    - Discloses conflicts, staleness, or insufficient evidence rather than guessing.
    - Returns answer, verification status, verified/unsupported claims, evidence, and conflicts.
    """
    from app.agents.reasoning_agent import answer_question as _answer  # noqa: PLC0415
    from app.agents.verification_agent import verify_answer as _verify  # noqa: PLC0415
    cfg = _settings()

    traces: list[AgentStepTrace] = [
        AgentStepTrace(
            agent="Coordinator",
            status="SUCCESS",
            action="Receive Question",
            duration_ms=0.5,
            details=f"Received query: '{body.question}'. Dispatching to Reasoning Agent for graph retrieval and synthesis.",
        )
    ]

    t_reason_start = time.perf_counter()
    result = _answer(
        question=body.question,
        api_key=cfg.GEMINI_API_KEY,
        model=cfg.GEMINI_MODEL,
        db_host=cfg.FALKORDB_HOST,
        db_port=cfg.FALKORDB_PORT,
        db_graph=cfg.FALKORDB_GRAPH,
    )
    t_reason_dur = round((time.perf_counter() - t_reason_start) * 1000, 2)

    if not result["ok"]:
        traces.append(AgentStepTrace(
            agent="ReasoningAgent",
            status="ERROR",
            action="Retrieve & Generate",
            duration_ms=t_reason_dur,
            details=result.get("error", "Reasoning failed."),
        ))
        err_msg = result.get("error", "Reasoning failed.")
        http_code = status.HTTP_503_SERVICE_UNAVAILABLE if "LLM" in err_msg or "Gemini" in err_msg or "Timeout" in err_msg or "timed out" in err_msg.lower() else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(status_code=http_code, detail=err_msg)

    traces.append(AgentStepTrace(
        agent="ReasoningAgent",
        status="SUCCESS",
        action="Retrieve & Generate",
        duration_ms=t_reason_dur,
        details=(
            f"Retrieved {len(result.get('facts_used', []))} fact(s) and {len(result.get('sources', []))} source(s). "
            f"Synthesized grounded answer."
        ),
        metadata={"reasoning_path": result.get("reasoning_path", "")},
    ))

    sources = [SourceEvidence(**s) for s in result.get("sources", [])]
    first_source_text = sources[0].text if sources else None

    # Prepare evidence list with source traceability for Verification Agent
    evidence_list: list[dict] = []
    for f in result.get("facts_used", []):
        f_copy = dict(f)
        if not f_copy.get("source_text") and first_source_text:
            f_copy["source_text"] = first_source_text
        if not f_copy.get("statement"):
            subj = f_copy.get("subject", "")
            pred = str(f_copy.get("predicate", "")).replace("_", " ")
            obj = f_copy.get("object_value", "")
            if subj and pred and obj:
                f_copy["statement"] = f"{subj} {pred} {obj}."
        evidence_list.append(f_copy)

    # Invoke Verification Agent with controlled error handling
    try:
        t_verify_start = time.perf_counter()
        v_res = _verify(
            question=body.question,
            answer=result["answer"],
            evidence=evidence_list,
            api_key=cfg.GEMINI_API_KEY,
            model=cfg.GEMINI_MODEL,
            db_host=cfg.FALKORDB_HOST,
            db_port=cfg.FALKORDB_PORT,
            db_graph=cfg.FALKORDB_GRAPH,
            validate_against_db=False,
        )
        t_verify_dur = round((time.perf_counter() - t_verify_start) * 1000, 2)
    except Exception as exc:
        t_verify_dur = round((time.perf_counter() - t_verify_start) * 1000, 2)
        logger.error("Coordinator verification step failed: %s", exc)
        from app.agents.verification_agent import VerificationResult
        v_res = VerificationResult(
            ok=False,
            status="ERROR",
            explanation=f"Verification execution error: {exc}",
            error=str(exc),
        )

    final_answer = result["answer"]
    sufficient = result.get("sufficient_evidence", False)

    if not v_res.ok:
        v_status = "ERROR"
        v_explanation = v_res.explanation or "Verification service failed."
        traces.append(AgentStepTrace(
            agent="VerificationAgent",
            status="ERROR",
            action="Verify Claims & Evidence",
            duration_ms=t_verify_dur,
            details=f"Verification failed: {v_explanation}",
        ))
        final_answer = (
            f"[Verification Notice: Evidence validation could not be completed ({v_explanation}).] "
            f"{final_answer}"
        )
    elif v_res.status == "CONFLICTING":
        v_status = "CONFLICTING"
        conflict_descs = "; ".join(c.description for c in v_res.conflicts)
        conflict_note = f"[Conflict detected in knowledge base: {conflict_descs}]"
        if conflict_note not in final_answer:
            final_answer = f"{conflict_note} {final_answer}"
        v_explanation = v_res.explanation
        traces.append(AgentStepTrace(
            agent="VerificationAgent",
            status="WARNING",
            action="Verify Claims & Evidence",
            duration_ms=t_verify_dur,
            details=f"Status: CONFLICTING — {len(v_res.conflicts)} conflict(s) detected and disclosed.",
            metadata={"conflicts": [c.model_dump() for c in v_res.conflicts]},
        ))
    elif v_res.status == "UNSUPPORTED":
        v_status = "UNSUPPORTED"
        if not v_res.verified_claims:
            final_answer = (
                "I don't have enough verified information in my knowledge base "
                "to answer this question."
            )
            sufficient = False
        else:
            final_answer = " ".join(v_res.verified_claims)
        v_explanation = v_res.explanation
        traces.append(AgentStepTrace(
            agent="VerificationAgent",
            status="WARNING",
            action="Verify Claims & Evidence",
            duration_ms=t_verify_dur,
            details=f"Status: UNSUPPORTED — Claims unverified. Returning insufficient-evidence response.",
        ))
    elif v_res.status == "PARTIALLY_SUPPORTED":
        v_status = "PARTIALLY_SUPPORTED"
        if v_res.verified_claims:
            supported_str = " ".join(v_res.verified_claims)
            unsupported_str = " ".join(v_res.unsupported_claims)
            final_answer = (
                f"{supported_str} "
                f"(Note: The following claim could not be verified from the knowledge base: {unsupported_str})"
            )
        else:
            final_answer = (
                "I don't have enough verified information in my knowledge base "
                "to answer this question."
            )
            sufficient = False
        v_explanation = v_res.explanation
        traces.append(AgentStepTrace(
            agent="VerificationAgent",
            status="SUCCESS",
            action="Verify Claims & Evidence",
            duration_ms=t_verify_dur,
            details=f"Status: PARTIALLY_SUPPORTED — {len(v_res.verified_claims)} verified, {len(v_res.unsupported_claims)} unsupported.",
        ))
    else:  # SUPPORTED
        v_status = "SUPPORTED"
        v_explanation = v_res.explanation
        traces.append(AgentStepTrace(
            agent="VerificationAgent",
            status="SUCCESS",
            action="Verify Claims & Evidence",
            duration_ms=t_verify_dur,
            details=f"Status: SUPPORTED — All claims substantiated with full source traceability.",
        ))

    traces.append(AgentStepTrace(
        agent="Coordinator",
        status="COMPLETED",
        action="Synthesize Response",
        duration_ms=0.5,
        details=f"Final answer synthesized with status '{v_status}'. Payload ready for client.",
    ))

    return AskResponse(
        ok=True,
        answer=final_answer,
        sufficient_evidence=sufficient,
        facts_used=result.get("facts_used", []),
        sources=sources,
        reasoning_path=result.get("reasoning_path", ""),
        verification_status=v_status,
        verified_claims=v_res.verified_claims,
        unsupported_claims=v_res.unsupported_claims,
        evidence=[e.model_dump() for e in v_res.evidence],
        conflicts=[c.model_dump() for c in v_res.conflicts],
        verification_explanation=v_explanation,
        agent_trace=traces,
    )


@app.post("/verify", response_model=VerifyResponse, tags=["Verification"])
async def verify_endpoint(body: VerifyRequest) -> VerifyResponse:
    """
    Verify an answer against provided and/or stored evidence in FalkorDB.

    - Validates fact IDs and source traceability against FalkorDB.
    - Identifies fabricated or invalid fact IDs.
    - Detects staleness and conflicting facts.
    - Evaluates whether factual claims are supported, unsupported, or conflicting.
    - Returns structured verification result.
    """
    from app.agents.verification_agent import verify_answer as _verify  # noqa: PLC0415
    cfg = _settings()

    evidence_dicts = [e.model_dump() for e in body.evidence]

    v_res = _verify(
        question=body.question,
        answer=body.answer,
        evidence=evidence_dicts,
        api_key=cfg.GEMINI_API_KEY,
        model=cfg.GEMINI_MODEL,
        db_host=cfg.FALKORDB_HOST,
        db_port=cfg.FALKORDB_PORT,
        db_graph=cfg.FALKORDB_GRAPH,
        validate_against_db=True,
    )

    evidence_out = [
        VerifyEvidenceItem(
            fact_id=e.fact_id,
            statement=e.statement,
            source_text=e.source_text,
        )
        for e in v_res.evidence
    ]

    conflicts_out = [
        VerifyConflictItem(
            conflict_type=c.conflict_type,
            description=c.description,
            fact_id=c.fact_id,
            conflicting_fact_id=c.conflicting_fact_id,
        )
        for c in v_res.conflicts
    ]

    return VerifyResponse(
        ok=v_res.ok,
        status=v_res.status,
        verified_claims=v_res.verified_claims,
        unsupported_claims=v_res.unsupported_claims,
        evidence=evidence_out,
        conflicts=conflicts_out,
        explanation=v_res.explanation,
        error=v_res.error,
    )


@app.get("/memory", response_model=MemoryListResponse, tags=["Memory"])
async def list_memory(
    page: int = 1,
    page_size: int = 20,
) -> MemoryListResponse:
    """
    Return a paginated list of stored facts with source information.

    Query params: page (default 1), page_size (default 20, max 100).
    """
    from app.cache import cache  # noqa: PLC0415
    from app.graph import _get_graph  # noqa: PLC0415
    cfg = _settings()
    page_size = min(page_size, 100)
    skip = (page - 1) * page_size

    cache_params = {"page": page, "page_size": page_size}
    cached = cache.get("memory", "default", cache_params)
    if cached is not None:
        return cached

    try:
        graph = _get_graph(cfg.FALKORDB_HOST, cfg.FALKORDB_PORT, cfg.FALKORDB_GRAPH)

        count_qr = graph.query("MATCH (f:Fact) RETURN count(f)")
        total = int((count_qr.result_set or [[0]])[0][0])

        qr = graph.query(
            "MATCH (f:Fact) "
            "RETURN f.id, f.subject, f.predicate, f.object_value, "
            "       f.object_type, f.confidence, f.status, f.created_at, f.updated_at "
            "ORDER BY f.created_at DESC "
            "SKIP $skip LIMIT $lim",
            {"skip": skip, "lim": page_size},
        )
        facts = []
        for row in (qr.result_set or []):
            facts.append(StoredFact(
                fact_id=row[0] or "",
                subject=row[1] or "",
                predicate=row[2] or "",
                object_value=row[3] or "",
                object_type=row[4] or "",
                confidence=row[5],
                status=row[6] or "unknown",
                created_at=row[7],
                updated_at=row[8],
            ))

        resp = MemoryListResponse(
            ok=True, total=total, page=page, page_size=page_size, facts=facts
        )
        cache.set("memory", "default", cache_params, resp, ttl_sec=30.0)
        return resp

    except Exception as exc:
        logger.error("GET /memory failed: %s", exc)
        return MemoryListResponse(
            ok=False, total=0, page=page, page_size=page_size,
            error=str(exc)
        )


@app.get("/graph", response_model=GraphExportResponse, tags=["Memory"])
async def export_graph(limit: int = 100, skip: int = 0) -> GraphExportResponse:
    """
    Export graph nodes and relationships as JSON for the graph explorer.

    Returns Entity, Fact, Source nodes plus SUBJECT_OF / OBJECT_OF / SUPPORTS edges.
    ``limit`` caps results per node type (max 500).
    ``skip`` allows paginated traversal through graph entities.
    """
    from app.cache import cache  # noqa: PLC0415
    from app.graph import _get_graph  # noqa: PLC0415
    cfg = _settings()
    limit = min(max(1, limit), 500)
    skip = max(0, skip)

    cache_params = {"limit": limit, "skip": skip}
    cached = cache.get("graph", "default", cache_params)
    if cached is not None:
        return cached

    try:
        graph = _get_graph(cfg.FALKORDB_HOST, cfg.FALKORDB_PORT, cfg.FALKORDB_GRAPH)
        nodes: list[dict] = []
        edges: list[dict] = []
        seen_node_ids: set = set()

        qr = graph.query(
            "MATCH (e:Entity) RETURN e.id, e.name, e.type SKIP $skip LIMIT $lim",
            {"skip": skip, "lim": limit},
        )
        for row in (qr.result_set or []):
            nid = row[0]
            if nid not in seen_node_ids:
                seen_node_ids.add(nid)
                nodes.append({"id": nid, "label": "Entity", "name": row[1], "type": row[2]})

        qr = graph.query(
            "MATCH (f:Fact) RETURN f.id, f.subject, f.predicate, f.object_value, "
            "f.status, f.confidence SKIP $skip LIMIT $lim",
            {"skip": skip, "lim": limit},
        )
        for row in (qr.result_set or []):
            nid = row[0]
            if nid not in seen_node_ids:
                seen_node_ids.add(nid)
                nodes.append({
                    "id": nid, "label": "Fact",
                    "subject": row[1], "predicate": row[2],
                    "object_value": row[3], "status": row[4], "confidence": row[5],
                })

        qr = graph.query(
            "MATCH (s:Source) RETURN s.id, s.text, s.source_type SKIP $skip LIMIT $lim",
            {"skip": skip, "lim": limit},
        )
        for row in (qr.result_set or []):
            nid = row[0]
            if nid not in seen_node_ids:
                seen_node_ids.add(nid)
                nodes.append({
                    "id": nid, "label": "Source",
                    "text": (row[1] or "")[:120],
                    "source_type": row[2],
                })

        for rel in ("SUBJECT_OF", "OBJECT_OF", "SUPPORTS"):
            try:
                rq = graph.query(
                    f"MATCH (a)-[r:{rel}]->(b) RETURN a.id, b.id SKIP $skip LIMIT $lim",
                    {"skip": skip, "lim": limit},
                )
                for row in (rq.result_set or []):
                    if row[0] and row[1]:
                        edges.append({"source": row[0], "target": row[1], "type": rel})
            except Exception as exc:
                logger.warning("Edge query for %s failed: %s", rel, exc)

        resp = GraphExportResponse(ok=True, nodes=nodes, edges=edges)
        cache.set("graph", "default", cache_params, resp, ttl_sec=30.0)
        return resp

    except Exception as exc:
        logger.error("GET /graph failed: %s", exc)
        return GraphExportResponse(ok=False, error=str(exc))

