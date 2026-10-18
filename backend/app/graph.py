"""
app/graph.py — FalkorDB connection and graph utilities for GraphMind.

The module does NOT crash at import time if FalkorDB is unavailable; each
function reports errors through return values / exceptions so callers (e.g.
the health endpoint) can surface a clear status without killing the process.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Lazy import so missing package produces a friendly error ──────────────────
try:
    from falkordb import FalkorDB  # type: ignore
    _FALKORDB_AVAILABLE = True
except ImportError:
    _FALKORDB_AVAILABLE = False
    logger.warning(
        "falkordb package is not installed. "
        "Run `pip install falkordb` to enable graph features."
    )


def _get_graph(
    host: str,
    port: int,
    graph_name: str,
    password: Optional[str] = None,
    ssl: bool = False,
):
    """Return a FalkorDB Graph object, or raise on connection failure."""
    if not _FALKORDB_AVAILABLE:
        raise RuntimeError("falkordb package is not installed.")

    try:
        from app.config import settings
        if password is None:
            password = settings.FALKORDB_PASSWORD
        if not ssl:
            ssl = settings.FALKORDB_SSL
    except Exception:
        pass

    db = FalkorDB(host=host, port=port, password=password, ssl=ssl)
    return db.select_graph(graph_name)


def check_connectivity(host: str, port: int, graph_name: str) -> dict[str, Any]:
    """
    Ping FalkorDB by running a trivial query.

    Returns
    -------
    {"ok": True}  on success
    {"ok": False, "error": "<message>"}  on failure
    """
    try:
        graph = _get_graph(host, port, graph_name)
        # A minimal read-only query that works on any FalkorDB instance.
        graph.query("RETURN 1")
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.error("FalkorDB connectivity check failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def safe_graph_write(
    host: str,
    port: int,
    graph_name: str,
    cypher: str,
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Execute a parameterised Cypher write query.

    Parameters
    ----------
    host, port, graph_name : connection details (from settings)
    cypher : Cypher query string with ``$param`` placeholders
    params : mapping of parameter names → values

    Returns
    -------
    {"ok": True, "result": <QueryResult>}  on success
    {"ok": False, "error": "<message>"}    on failure
    """
    try:
        graph = _get_graph(host, port, graph_name)
        result = graph.query(cypher, params or {})
        return {"ok": True, "result": result}
    except Exception as exc:  # noqa: BLE001
        logger.error("FalkorDB write failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def ensure_indexes(host: str, port: int, graph_name: str) -> dict[str, Any]:
    """
    Ensure schema indexes exist on Fact, Entity, and Source nodes in FalkorDB.
    Gracefully handles already-existing index errors so it can run idempotently.
    """
    index_statements = [
        "CREATE INDEX FOR (f:Fact) ON (f.id)",
        "CREATE INDEX FOR (f:Fact) ON (f.subject)",
        "CREATE INDEX FOR (f:Fact) ON (f.status)",
        "CREATE INDEX FOR (e:Entity) ON (e.id)",
        "CREATE INDEX FOR (e:Entity) ON (e.name)",
        "CREATE INDEX FOR (s:Source) ON (s.id)",
    ]
    created: list[str] = []
    already_indexed: list[str] = []
    errors: list[dict[str, str]] = []

    try:
        graph = _get_graph(host, port, graph_name)
        for stmt in index_statements:
            try:
                graph.query(stmt)
                created.append(stmt)
            except Exception as exc:  # noqa: BLE001
                err_str = str(exc).lower()
                if "already indexed" in err_str or "already exists" in err_str:
                    already_indexed.append(stmt)
                else:
                    logger.warning("Index statement '%s' failed: %s", stmt, exc)
                    errors.append({"statement": stmt, "error": str(exc)})
        return {
            "ok": len(errors) == 0,
            "created": created,
            "already_indexed": already_indexed,
            "errors": errors,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to connect to FalkorDB for indexing: %s", exc)
        return {"ok": False, "error": str(exc)}

