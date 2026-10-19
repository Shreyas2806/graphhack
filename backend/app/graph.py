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


def _mask_secrets(message: str) -> str:
    """Mask passwords and API keys from error messages before logging or returning."""
    masked = str(message)
    try:
        from app.config import settings
        if getattr(settings, "FALKORDB_PASSWORD", None):
            masked = masked.replace(settings.FALKORDB_PASSWORD, "***")
        if getattr(settings, "GEMINI_API_KEY", None):
            masked = masked.replace(settings.GEMINI_API_KEY, "***")
    except Exception:
        pass
    return masked


def _get_graph(
    host: Optional[str] = None,
    port: Optional[int] = None,
    graph_name: Optional[str] = None,
    password: Optional[str] = None,
    ssl: Optional[bool] = None,
    username: Optional[str] = None,
    url: Optional[str] = None,
):
    """
    Return a FalkorDB Graph object connecting to either local Docker or hosted FalkorDB Cloud.
    Handles explicit connection strings, host:port parsing, timeouts, passwords, and TLS.
    """
    if not _FALKORDB_AVAILABLE:
        raise RuntimeError("falkordb package is not installed.")

    try:
        from app.config import settings
        matches_configured = (
            host is None
            or (host == getattr(settings, "FALKORDB_HOST", None) and (port is None or port == getattr(settings, "FALKORDB_PORT", None)))
        )
        if host is None:
            host = settings.FALKORDB_HOST
        if port is None:
            port = settings.FALKORDB_PORT
        if graph_name is None:
            graph_name = settings.FALKORDB_GRAPH
        if password is None and matches_configured:
            password = settings.FALKORDB_PASSWORD
        if ssl is None and matches_configured:
            ssl = settings.FALKORDB_SSL
        if username is None and matches_configured:
            username = settings.FALKORDB_USERNAME
        if url is None and matches_configured:
            url = settings.FALKORDB_URL
    except Exception:
        pass

    target_graph = graph_name or "graphmind"
    socket_kwargs = {
        "socket_connect_timeout": 5.0,
        "socket_timeout": 15.0,
    }

    # 1. Connection via URL if provided
    if url or (host and host.startswith(("falkor://", "falkors://", "redis://", "rediss://"))):
        target_url = url or host
        db = FalkorDB.from_url(target_url, **socket_kwargs)
        return db.select_graph(target_graph)

    # 2. Connection via host + port + credentials
    effective_host = host or "127.0.0.1"
    effective_port = port or 6379

    if ":" in effective_host and not effective_host.startswith(("http://", "https://")):
        parts = effective_host.split(":", 1)
        effective_host = parts[0].strip()
        try:
            effective_port = int(parts[1].strip())
        except ValueError:
            pass

    client_kwargs: dict[str, Any] = {
        "host": effective_host,
        "port": effective_port,
        **socket_kwargs,
    }
    if password:
        client_kwargs["password"] = password
    if username:
        client_kwargs["username"] = username
    if ssl:
        client_kwargs["ssl"] = True

    db = FalkorDB(**client_kwargs)
    return db.select_graph(target_graph)


def check_connectivity(
    host: Optional[str] = None,
    port: Optional[int] = None,
    graph_name: Optional[str] = None,
    password: Optional[str] = None,
    ssl: Optional[bool] = None,
    username: Optional[str] = None,
    url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ping FalkorDB by running a trivial query.

    Returns
    -------
    {"ok": True}  on success
    {"ok": False, "error": "<masked-message>"}  on failure
    """
    try:
        graph = _get_graph(
            host=host,
            port=port,
            graph_name=graph_name,
            password=password,
            ssl=ssl,
            username=username,
            url=url,
        )
        # A minimal read-only query that works on any FalkorDB instance.
        graph.query("RETURN 1")
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        safe_err = _mask_secrets(str(exc))
        logger.error("FalkorDB connectivity check failed: %s", safe_err)
        return {"ok": False, "error": safe_err}


def safe_graph_write(
    host: Optional[str] = None,
    port: Optional[int] = None,
    graph_name: Optional[str] = None,
    cypher: str = "",
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Execute a parameterised Cypher write query.

    Parameters
    ----------
    host, port, graph_name : connection details (from settings or defaults)
    cypher : Cypher query string with ``$param`` placeholders
    params : mapping of parameter names → values

    Returns
    -------
    {"ok": True, "result": <QueryResult>}  on success
    {"ok": False, "error": "<message>"}    on failure
    """
    try:
        graph = _get_graph(host=host, port=port, graph_name=graph_name)
        result = graph.query(cypher, params or {})
        return {"ok": True, "result": result}
    except Exception as exc:  # noqa: BLE001
        safe_err = _mask_secrets(str(exc))
        logger.error("FalkorDB write failed: %s", safe_err)
        return {"ok": False, "error": safe_err}


def ensure_indexes(
    host: Optional[str] = None,
    port: Optional[int] = None,
    graph_name: Optional[str] = None,
) -> dict[str, Any]:
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
        graph = _get_graph(host=host, port=port, graph_name=graph_name)
        for stmt in index_statements:
            try:
                graph.query(stmt)
                created.append(stmt)
            except Exception as exc:  # noqa: BLE001
                err_str = str(exc).lower()
                if "already indexed" in err_str or "already exists" in err_str:
                    already_indexed.append(stmt)
                else:
                    safe_err = _mask_secrets(str(exc))
                    logger.warning("Index statement '%s' failed: %s", stmt, safe_err)
                    errors.append({"statement": stmt, "error": safe_err})
        return {
            "ok": len(errors) == 0,
            "created": created,
            "already_indexed": already_indexed,
            "errors": errors,
        }
    except Exception as exc:  # noqa: BLE001
        safe_err = _mask_secrets(str(exc))
        logger.error("Failed to connect to FalkorDB for indexing: %s", safe_err)
        return {"ok": False, "error": safe_err}

