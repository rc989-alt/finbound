"""Simple rate limiter for API calls."""

from __future__ import annotations

import logging
import time
import threading
from typing import Callable, TypeVar, Any

T = TypeVar("T")

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple rate limiter with exponential backoff.

    Usage:
        limiter = RateLimiter(requests_per_minute=20)
        result = limiter.call(api_function, arg1, kwarg=value)
    """

    def __init__(
        self,
        requests_per_minute: int = 20,  # Conservative default
        retry_delay_seconds: float = 5.0,  # Longer initial delay
        max_retries: int = 5,  # More retries
    ) -> None:
        self._min_interval = 60.0 / requests_per_minute
        self._retry_delay = retry_delay_seconds
        self._max_retries = max_retries
        self._last_call = 0.0
        self._lock = threading.Lock()

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Call function with rate limiting and retry logic."""
        with self._lock:
            elapsed = time.time() - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)

        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                with self._lock:
                    self._last_call = time.time()
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                is_retryable = any(x in error_str for x in [
                    'rate limit', 'rate_limit', '429', 'timeout',
                    'connection', 'temporarily', 'overloaded', '503', '500'
                ])

                if attempt < self._max_retries and is_retryable:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(f"API call failed (attempt {attempt + 1}/{self._max_retries + 1}), retrying in {delay:.1f}s: {e}")
                    time.sleep(delay)
                elif not is_retryable:
                    raise

        raise last_error  # type: ignore


# Global instance
_limiter: RateLimiter | None = None


def get_rate_limiter(
    requests_per_minute: int = 30,
    retry_delay_seconds: float = 2.0,
    max_retries: int = 3,
) -> RateLimiter:
    """Get or create global rate limiter."""
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            retry_delay_seconds=retry_delay_seconds,
            max_retries=max_retries,
        )
    return _limiter
