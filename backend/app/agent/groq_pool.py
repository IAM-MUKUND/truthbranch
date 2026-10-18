"""
Thread-Safe Groq API Key Pool with Round-Robin Scheduling & Automatic Failover.

Features:
- Dynamically discovers all unique Groq keys from Settings (.env) and environment variables
  (e.g., GROQ_API_KEY, GROQ_API_KEY1..4).
- Balances API usage evenly across all available free-tier accounts using Round-Robin scheduling.
- Automatically catches RateLimitError (HTTP 429) or transient authentication/quota errors and
  immediately fails over to the next key in the pool without interrupting the request.
- Falls back gracefully to deterministic scripted mode if all keys are exhausted, ensuring
  zero error banners, quota notices, or rate-limit warnings ever surface on the user interface.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, List, Optional

from groq import APIError, Groq, RateLimitError

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


class GroqPool:
    """Manages a pool of Groq API clients with round-robin dispatch and transparent failover."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: List[str] = []
        self._clients: List[Groq] = []
        self._index: int = 0
        self._initialized: bool = False

    def reload(self) -> None:
        """Force re-initialization of keys and clients from environment and settings."""
        with self._lock:
            try:
                get_settings.cache_clear()
            except Exception:
                pass
            self._initialized = False
            self._init_pool_locked()

    def _init_pool_locked(self) -> None:
        settings = get_settings()

        candidates: List[Optional[str]] = [
            settings.groq_api_key,
            settings.groq_api_key1,
            settings.groq_api_key2,
            settings.groq_api_key3,
            settings.groq_api_key4,
        ]

        # Scan any additional GROQ_API_KEY* variables in os.environ
        for k, v in os.environ.items():
            if k.startswith("GROQ_API_KEY") and v:
                candidates.append(v)

        unique_keys: List[str] = []
        seen = set()

        for raw in candidates:
            if not raw:
                continue
            # Strip potential inline comments and whitespace
            cleaned = raw.split("#")[0].strip()
            if cleaned and cleaned.startswith("gsk_") and cleaned not in seen:
                seen.add(cleaned)
                unique_keys.append(cleaned)

        self._keys = unique_keys
        self._clients = [Groq(api_key=k) for k in self._keys]
        self._index = 0
        self._initialized = True

        logger.info(
            f"GroqPool initialized with {len(self._clients)} unique API key(s) for round-robin rotation."
        )

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._init_pool_locked()

    @property
    def key_count(self) -> int:
        self._ensure_initialized()
        return len(self._clients)

    @property
    def has_keys(self) -> bool:
        return self.key_count > 0

    def chat_completion(self, **kwargs: Any) -> Any:
        """
        Execute chat.completions.create with round-robin key selection and automatic failover.

        On encountering RateLimitError (HTTP 429) or transient API failures, it automatically
        rotates to the next key in the pool and retries up to the total number of keys.
        """
        self._ensure_initialized()

        if not self._clients:
            raise RuntimeError("No Groq API keys configured in pool.")

        total_keys = len(self._clients)

        # Atomically advance the round-robin starting index
        with self._lock:
            start_index = self._index
            self._index = (self._index + 1) % total_keys

        last_error: Optional[Exception] = None

        # Attempt call starting from start_index and progressing through all keys in pool
        for attempt in range(total_keys):
            current_idx = (start_index + attempt) % total_keys
            client = self._clients[current_idx]
            key_tag = f"...{self._keys[current_idx][-6:]}" if len(self._keys[current_idx]) >= 6 else "key"

            try:
                response = client.chat.completions.create(**kwargs)
                return response

            except RateLimitError as e:
                logger.warning(
                    f"[GroqPool] Rate limit reached on key [{key_tag}] (attempt {attempt + 1}/{total_keys}). "
                    f"Failing over to next key in pool..."
                )
                last_error = e
                continue

            except APIError as e:
                status = getattr(e, "status_code", None)
                if status in (429, 401, 403, 502, 503, 504):
                    logger.warning(
                        f"[GroqPool] API error {status} on key [{key_tag}] (attempt {attempt + 1}/{total_keys}): {e}. "
                        f"Failing over to next key in pool..."
                    )
                    last_error = e
                    continue
                logger.error(f"[GroqPool] Non-retryable API error on key [{key_tag}]: {e}")
                raise

            except Exception as e:
                logger.warning(
                    f"[GroqPool] Unexpected exception on key [{key_tag}] (attempt {attempt + 1}/{total_keys}): {e}. "
                    f"Failing over to next key..."
                )
                last_error = e
                continue

        logger.error(f"[GroqPool] All {total_keys} Groq API keys exhausted or rate-limited.")
        if last_error:
            raise last_error
        raise RuntimeError("All Groq API keys in pool failed.")


# Global singleton instance
groq_pool = GroqPool()
