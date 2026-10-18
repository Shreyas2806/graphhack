"""
app/config.py — Environment configuration for GraphMind backend.

Loads settings from a .env file (or real environment) and exposes them
as a single `Settings` instance.  Missing *required* variables raise a
clear `RuntimeError` at startup so the developer knows exactly what to fix.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env from the backend/ directory ────────────────────────────────────
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


class Settings:
    """Application settings read from environment variables."""

    # ── Gemini ────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str
    GEMINI_MODEL: str

    # ── FalkorDB ──────────────────────────────────────────────────────────────
    FALKORDB_HOST: str
    FALKORDB_PORT: int
    FALKORDB_GRAPH: str

    def __init__(self) -> None:
        # Required
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set.\n"
                "Add it to backend/.env or export it as an environment variable.\n"
                "Example:  GEMINI_API_KEY=AIza..."
            )
        self.GEMINI_API_KEY = api_key

        # Optional with defaults
        self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        self.FALKORDB_HOST = os.getenv("FALKORDB_HOST", "127.0.0.1").strip()
        self.FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
        self.FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "graphmind").strip()

        # Caching configuration (Phase 4)
        enable_cache_env = os.getenv("ENABLE_CACHE", "true").strip().lower()
        self.ENABLE_CACHE = enable_cache_env in ("true", "1", "yes")
        self.CACHE_TTL_SECONDS = float(os.getenv("CACHE_TTL_SECONDS", "60.0"))


# ── Singleton ─────────────────────────────────────────────────────────────────
# Initialised once at import time; raises RuntimeError immediately if required
# env vars are absent so failures are obvious rather than buried in a request.
try:
    settings = Settings()
except RuntimeError as _exc:
    # Re-raise with the original message; the app will refuse to start.
    raise
