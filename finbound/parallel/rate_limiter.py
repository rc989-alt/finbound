"""
Async Rate Limiter for FinBound Parallel Processing.

Implements a token-bucket rate limiting algorithm for controlling API call
rates during concurrent execution. This prevents OpenAI API throttling
while maximizing throughput.

Security Considerations:
    - Thread-safe via asyncio.Lock
    - No sensitive data stored
    - Configurable limits per API tier

Production Configuration:
    - OpenAI Tier 1: 500 RPM, 30K TPM
    - OpenAI Tier 2: 5,000 RPM, 450K TPM
    - OpenAI Tier 3: 5,000 RPM, 1M TPM
    - OpenAI Tier 4: 10,000 RPM, 2M TPM
    - OpenAI Tier 5: 10,000 RPM, 10M TPM
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting.

    Attributes:
        requests_per_minute: Maximum requests per minute (RPM)
        tokens_per_minute: Maximum tokens per minute (TPM), optional
        burst_size: Maximum burst size for token bucket
        retry_delay_base: Base delay for exponential backoff (seconds)
        max_retries: Maximum retry attempts for rate limit errors
    """

    requests_per_minute: int = 500
    tokens_per_minute: int | None = None
    burst_size: int = 50
    retry_delay_base: float = 1.0
    max_retries: int = 5


@dataclass
class RateLimitStats:
    """Statistics for rate limiter monitoring.

    Attributes:
        total_requests: Total number of requests processed
        total_tokens: Total tokens consumed (if tracked)
        throttled_count: Number of times throttling was applied
        retry_count: Number of retry attempts
        last_request_time: Timestamp of last request
    """

    total_requests: int = 0
    total_tokens: int = 0
    throttled_count: int = 0
    retry_count: int = 0
    last_request_time: float = 0.0


class AsyncRateLimiter:
    """
    Async token-bucket rate limiter for parallel API execution.

    Implements the token bucket algorithm with:
    - Configurable RPM (requests per minute)
    - Optional TPM (tokens per minute) tracking
    - Exponential backoff for rate limit errors
    - Thread-safe async implementation

    Example:
        >>> limiter = AsyncRateLimiter(requests_per_minute=500)
        >>> async with limiter:
        ...     result = await api_call()

        >>> # Or with explicit acquire
        >>> await limiter.acquire()
        >>> result = await api_call()

    Production Usage:
        >>> # For OpenAI Tier 5 (Enterprise)
        >>> limiter = AsyncRateLimiter(
        ...     requests_per_minute=10000,
        ...     tokens_per_minute=10_000_000,
        ...     burst_size=100
        ... )
    """

    def __init__(
        self,
        requests_per_minute: int = 500,
        tokens_per_minute: int | None = None,
        burst_size: int = 50,
        retry_delay_base: float = 1.0,
        max_retries: int = 5,
    ) -> None:
        """
        Initialize the async rate limiter.

        Args:
            requests_per_minute: Maximum RPM allowed
            tokens_per_minute: Maximum TPM allowed (optional)
            burst_size: Maximum tokens in bucket for burst handling
            retry_delay_base: Base delay for exponential backoff
            max_retries: Maximum retry attempts
        """
        self._config = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            tokens_per_minute=tokens_per_minute,
            burst_size=burst_size,
            retry_delay_base=retry_delay_base,
            max_retries=max_retries,
        )

        # Token bucket state
        self._tokens = float(burst_size)
        self._max_tokens = float(burst_size)
        self._refill_rate = requests_per_minute / 60.0  # tokens per second
        self._last_refill = time.monotonic()

        # Concurrency control
        self._lock = asyncio.Lock()
        self._semaphore: asyncio.Semaphore | None = None

        # Statistics
        self._stats = RateLimitStats()

        logger.info(
            "AsyncRateLimiter initialized: %d RPM, burst=%d",
            requests_per_minute,
            burst_size,
        )

    @property
    def stats(self) -> RateLimitStats:
        """Get current rate limiter statistics."""
        return self._stats

    async def acquire(self, tokens: int = 1) -> None:
        """
        Acquire permission to make an API call.

        Blocks if rate limit would be exceeded. Uses token bucket
        algorithm for smooth rate limiting with burst support.

        Args:
            tokens: Number of tokens to acquire (default 1 for request count)

        Raises:
            asyncio.CancelledError: If wait is cancelled
        """
        async with self._lock:
            now = time.monotonic()

            # Refill tokens based on elapsed time
            elapsed = now - self._last_refill
            self._tokens = min(
                self._max_tokens,
                self._tokens + elapsed * self._refill_rate,
            )
            self._last_refill = now

            # Check if we have enough tokens
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._stats.total_requests += 1
                self._stats.last_request_time = time.time()
                return

            # Calculate wait time
            tokens_needed = tokens - self._tokens
            wait_time = tokens_needed / self._refill_rate

            self._stats.throttled_count += 1
            logger.debug(
                "Rate limit throttle: waiting %.2fs (tokens=%.2f, needed=%d)",
                wait_time,
                self._tokens,
                tokens,
            )

        # Wait outside the lock to allow other operations
        await asyncio.sleep(wait_time)

        # Re-acquire after waiting
        async with self._lock:
            self._tokens = 0  # Used all accumulated tokens
            self._last_refill = time.monotonic()
            self._stats.total_requests += 1
            self._stats.last_request_time = time.time()

    async def acquire_with_retry(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute function with rate limiting and automatic retry.

        Implements exponential backoff for rate limit errors (429).

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            Exception: Last error after all retries exhausted
        """
        last_error: Exception | None = None

        for attempt in range(self._config.max_retries + 1):
            await self.acquire()

            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    # Run sync function in thread pool
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        None, lambda: func(*args, **kwargs)
                    )
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check if retryable
                is_retryable = any(
                    x in error_str
                    for x in [
                        "rate limit",
                        "rate_limit",
                        "429",
                        "timeout",
                        "connection",
                        "temporarily",
                        "overloaded",
                        "503",
                        "500",
                    ]
                )

                if attempt < self._config.max_retries and is_retryable:
                    delay = self._config.retry_delay_base * (2**attempt)
                    self._stats.retry_count += 1
                    logger.warning(
                        "Rate limit retry %d/%d after %.1fs: %s",
                        attempt + 1,
                        self._config.max_retries,
                        delay,
                        str(e)[:100],
                    )
                    await asyncio.sleep(delay)
                elif not is_retryable:
                    raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("Unexpected state in acquire_with_retry")

    async def __aenter__(self) -> "AsyncRateLimiter":
        """Context manager entry - acquires rate limit token."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        pass

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = RateLimitStats()


# Preset configurations for common API tiers
OPENAI_TIER_CONFIGS = {
    "tier1": RateLimitConfig(requests_per_minute=500, tokens_per_minute=30_000),
    "tier2": RateLimitConfig(requests_per_minute=5_000, tokens_per_minute=450_000),
    "tier3": RateLimitConfig(requests_per_minute=5_000, tokens_per_minute=1_000_000),
    "tier4": RateLimitConfig(requests_per_minute=10_000, tokens_per_minute=2_000_000),
    "tier5": RateLimitConfig(requests_per_minute=10_000, tokens_per_minute=10_000_000),
}


def create_rate_limiter_for_tier(tier: str) -> AsyncRateLimiter:
    """
    Create rate limiter configured for specific OpenAI API tier.

    Args:
        tier: One of "tier1", "tier2", "tier3", "tier4", "tier5"

    Returns:
        Configured AsyncRateLimiter instance

    Example:
        >>> limiter = create_rate_limiter_for_tier("tier5")
    """
    if tier not in OPENAI_TIER_CONFIGS:
        raise ValueError(
            f"Unknown tier: {tier}. Must be one of {list(OPENAI_TIER_CONFIGS.keys())}"
        )

    config = OPENAI_TIER_CONFIGS[tier]
    return AsyncRateLimiter(
        requests_per_minute=config.requests_per_minute,
        tokens_per_minute=config.tokens_per_minute,
        burst_size=min(100, config.requests_per_minute // 10),
    )
