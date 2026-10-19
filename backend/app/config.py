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
        self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

        # Optional with defaults
        # ── FalkorDB Connection Settings ───────────────────────────────────────
        raw_url = os.getenv("FALKORDB_URL", "").strip()
        raw_host = os.getenv("FALKORDB_HOST", "127.0.0.1").strip()

        # If raw_host contains a connection scheme, treat it as a URL
        if raw_host.startswith(("falkor://", "falkors://", "redis://", "rediss://")):
            raw_url = raw_host

        self.FALKORDB_URL: Optional[str] = raw_url if raw_url else None

        # Parse host:port if embedded in FALKORDB_HOST (common in cloud endpoint strings)
        if not self.FALKORDB_URL and ":" in raw_host and not raw_host.startswith(("http://", "https://")):
            parts = raw_host.split(":", 1)
            self.FALKORDB_HOST = parts[0].strip()
            try:
                self.FALKORDB_PORT = int(parts[1].strip())
            except ValueError:
                self.FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
        else:
            self.FALKORDB_HOST = raw_host
            self.FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))

        self.FALKORDB_GRAPH = os.getenv("FALKORDB_GRAPH", "graphmind").strip()

        user = os.getenv("FALKORDB_USERNAME", "").strip()
        self.FALKORDB_USERNAME: Optional[str] = user if user else None

        pwd = os.getenv("FALKORDB_PASSWORD", "").strip()
        self.FALKORDB_PASSWORD: Optional[str] = pwd if pwd else None

        ssl_env = os.getenv("FALKORDB_SSL", "").strip().lower()
        if ssl_env in ("true", "1", "yes"):
            self.FALKORDB_SSL = True
        elif ssl_env in ("false", "0", "no"):
            self.FALKORDB_SSL = False
        else:
            # Auto-enable SSL if using secure scheme (falkors:// or rediss://)
            self.FALKORDB_SSL = bool(
                (self.FALKORDB_URL and self.FALKORDB_URL.startswith(("falkors://", "rediss://")))
                or raw_host.startswith(("falkors://", "rediss://"))
            )

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
