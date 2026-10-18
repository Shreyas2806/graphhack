"""
app/llm.py — Gemini LLM integration for GraphMind.

Uses the official `google-genai` SDK.  API keys are read exclusively from
the environment; they are never logged or returned in responses.
Includes bounded retries with exponential backoff for transient errors,
explicit request timeouts, and accurate error classification.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Lazy import ───────────────────────────────────────────────────────────────
try:
    from google import genai  # type: ignore
    from google.genai import errors as genai_errors  # type: ignore
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logger.warning(
        "google-genai package is not installed. "
        "Run `pip install google-genai` to enable LLM features."
    )


def _is_transient_error(error_msg: str, exc: Exception) -> bool:
    """Return True if the error is transient and eligible for retry."""
    err_upper = error_msg.upper()
    transient_indicators = [
        "429", "RESOURCE_EXHAUSTED", "TOO MANY REQUESTS",
        "503", "UNAVAILABLE", "HIGH DEMAND",
        "500", "INTERNAL", "SERVER ERROR",
        "504", "GATEWAY TIMEOUT", "TIMEOUT", "TIMED OUT", "TIME OUT",
        "DEADLINE_EXCEEDED", "CONNECTION RESET", "REMOTE DISCONNECTED",
        "HANDSHAKE", "SSL", "CONNECT",
    ]
    if any(ind in err_upper for ind in transient_indicators):
        return True
    return isinstance(exc, (TimeoutError, ConnectionError, OSError))


def generate_text(
    prompt: str,
    api_key: str,
    model: str,
    timeout: float = 60.0,
    max_retries: int = 3,
    initial_delay: float = 1.0,
) -> dict:
    """
    Send *prompt* to Gemini and return the generated text.
    Handles explicit timeouts and bounded exponential backoff retries for transient errors.

    Parameters
    ----------
    prompt        : user prompt string
    api_key       : Gemini API key (read from settings, never logged)
    model         : model identifier, e.g. ``gemini-2.5-flash``
    timeout       : request timeout in seconds (default 30.0)
    max_retries   : maximum number of retry attempts for transient errors (default 3)
    initial_delay : base delay for exponential backoff (default 1.0s)

    Returns
    -------
    {"ok": True,  "text": "<generated text>"}
    {"ok": False, "error": "<human-readable message>"}
    """
    if not _GENAI_AVAILABLE:
        return {
            "ok": False,
            "error": (
                "google-genai package is not installed. "
                "Run `pip install google-genai`."
            ),
        }

    if not api_key:
        return {
            "ok": False,
            "error": (
                "GEMINI_API_KEY is missing. "
                "Set it in backend/.env before calling this endpoint."
            ),
        }

    attempt = 0
    while attempt <= max_retries:
        try:
            # google-genai HttpOptions.timeout is in milliseconds; multiply by 1000.
            timeout_ms = int(max(timeout, 5.0) * 1000)
            client = genai.Client(
                api_key=api_key,
                http_options={"timeout": timeout_ms},
            )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            text: Optional[str] = None
            if hasattr(response, "text"):
                text = response.text
            if text is None:
                return {"ok": False, "error": "Gemini returned an empty response."}
            return {"ok": True, "text": text}

        except Exception as exc:  # noqa: BLE001
            safe_msg = str(exc).replace(api_key, "***")
            exc_name = type(exc).__name__
            is_transient = _is_transient_error(safe_msg, exc)

            if is_transient and attempt < max_retries:
                attempt += 1
                backoff = initial_delay * (2 ** (attempt - 1)) + random.uniform(0.1, 0.4)
                logger.warning(
                    "Gemini transient error on attempt %d/%d (%s). Retrying in %.2fs...",
                    attempt, max_retries, exc_name, backoff,
                )
                time.sleep(backoff)
                continue

            logger.error("Gemini API error (attempt %d/%d): %s", attempt + 1, max_retries + 1, safe_msg)

            # Accurate classification of error categories
            safe_upper = safe_msg.upper()
            if "API_KEY" in safe_upper or "INVALID_ARGUMENT" in safe_upper or "PERMISSION_DENIED" in safe_upper:
                return {
                    "ok": False,
                    "error": (
                        f"Gemini API key error ({exc_name}). "
                        "Check that GEMINI_API_KEY is correct."
                    ),
                }
            if "429" in safe_upper or "RESOURCE_EXHAUSTED" in safe_upper:
                return {
                    "ok": False,
                    "error": (
                        "Gemini rate limit exceeded (429 Resource Exhausted). "
                        "Please retry in a few moments."
                    ),
                }
            if "503" in safe_upper or "HIGH DEMAND" in safe_upper or "UNAVAILABLE" in safe_upper:
                return {
                    "ok": False,
                    "error": (
                        "Gemini service unavailable due to high demand (503). "
                        "Please retry shortly."
                    ),
                }
            if "404" in safe_upper or "NOT_FOUND" in safe_upper:
                return {
                    "ok": False,
                    "error": (
                        f"Model '{model}' not found (404 Not Found). "
                        "Check GEMINI_MODEL in your .env file."
                    ),
                }

            return {"ok": False, "error": f"Gemini API error ({exc_name}): {safe_msg}"}

    return {"ok": False, "error": "Gemini request exceeded maximum retry attempts."}
