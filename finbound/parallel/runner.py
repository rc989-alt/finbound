"""
Parallel Runner for FinBound.

Provides concurrent execution of multiple financial reasoning requests,
enabling high-throughput processing for production workloads.

Architecture:
    - Request-level parallelism (not token-level)
    - Each request maintains full context (up to 128K tokens)
    - Automatic rate limiting to prevent API throttling
    - Progress tracking and error handling

Security:
    - No sensitive data cached between requests
    - Each request is isolated
    - API keys handled securely via environment variables

Performance:
    - 10 parallel requests: ~10x throughput improvement
    - 20 parallel requests: ~20x throughput improvement
    - Scales linearly until API rate limits are reached
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from ..core import FinBound
from ..data.unified import UnifiedSample
from ..types import FinBoundResult
from .rate_limiter import create_rate_limiter_for_tier

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution mode for parallel processing."""

    NORMAL = "normal"
    LOW_LATENCY = "low_latency"
    ULTRA_LOW_LATENCY = "ultra_low_latency"


@dataclass
class ParallelRunnerConfig:
    """Configuration for parallel runner.

    Attributes:
        max_concurrent: Maximum concurrent requests
        execution_mode: Processing mode (normal, low_latency, ultra_low_latency)
        api_tier: OpenAI API tier for rate limiting
        timeout_per_request: Timeout in seconds per request
        model: Model to use for reasoning
        enable_progress: Enable progress reporting
    """

    max_concurrent: int = 10
    execution_mode: ExecutionMode = ExecutionMode.LOW_LATENCY
    api_tier: str = "tier5"
    timeout_per_request: float = 120.0
    model: str = "gpt-4o"
    enable_progress: bool = True


@dataclass
class RequestResult:
    """Result from processing a single request.

    Attributes:
        sample_id: Identifier for the sample
        result: FinBound result (if successful)
        error: Error message (if failed)
        latency_ms: Processing time in milliseconds
        success: Whether processing succeeded
    """

    sample_id: str
    result: FinBoundResult | None
    error: str | None
    latency_ms: float
    success: bool


@dataclass
class BatchResult:
    """Aggregated result from batch processing.

    Attributes:
        results: List of individual request results
        total_time_ms: Total wall-clock time
        success_count: Number of successful requests
        failure_count: Number of failed requests
        avg_latency_ms: Average latency per request
        throughput_rps: Requests per second throughput
    """

    results: list[RequestResult]
    total_time_ms: float
    success_count: int
    failure_count: int
    avg_latency_ms: float
    throughput_rps: float


class ParallelRunner:
    """
    Concurrent request processor for FinBound.

    Processes multiple financial reasoning requests in parallel,
    significantly improving throughput for production workloads.

    Example:
        >>> runner = ParallelRunner(max_concurrent=10)
        >>> results = await runner.run_batch(samples, task_family="F1")
        >>> print(f"Processed {len(results.results)} in {results.total_time_ms}ms")

    Production Usage:
        >>> # For high-throughput financial document processing
        >>> runner = ParallelRunner(
        ...     max_concurrent=20,
        ...     execution_mode=ExecutionMode.LOW_LATENCY,
        ...     api_tier="tier5",
        ... )
        >>> results = await runner.run_batch(samples)

    Thread Safety:
        This class is designed for async usage. Each call to run_batch
        is safe to run concurrently with proper rate limiting.
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        execution_mode: ExecutionMode | str = ExecutionMode.LOW_LATENCY,
        api_tier: str = "tier5",
        timeout_per_request: float = 120.0,
        model: str = "gpt-4o",
        enable_progress: bool = True,
    ) -> None:
        """
        Initialize the parallel runner.

        Args:
            max_concurrent: Maximum concurrent requests (recommend 10-20)
            execution_mode: Processing mode (affects latency vs accuracy)
            api_tier: OpenAI API tier for rate limiting configuration
            timeout_per_request: Timeout in seconds per request
            model: Model to use for reasoning
            enable_progress: Enable progress logging
        """
        # Convert string mode to enum if needed
        if isinstance(execution_mode, str):
            execution_mode = ExecutionMode(execution_mode)

        self._config = ParallelRunnerConfig(
            max_concurrent=max_concurrent,
            execution_mode=execution_mode,
            api_tier=api_tier,
            timeout_per_request=timeout_per_request,
            model=model,
            enable_progress=enable_progress,
        )

        # Create rate limiter based on API tier
        self._rate_limiter = create_rate_limiter_for_tier(api_tier)

        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Thread pool for running sync FinBound code
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent,
            thread_name_prefix="finbound_worker",
        )

        # Progress tracking
        self._processed_count = 0
        self._total_count = 0

        logger.info(
            "ParallelRunner initialized: max_concurrent=%d, mode=%s, tier=%s",
            max_concurrent,
            execution_mode.value,
            api_tier,
        )

    @property
    def config(self) -> ParallelRunnerConfig:
        """Get current configuration."""
        return self._config

    async def run_batch(
        self,
        samples: list[UnifiedSample],
        task_family: str = "F1",
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> BatchResult:
        """
        Process a batch of samples in parallel.

        Args:
            samples: List of unified samples to process
            task_family: Task family for formatting (F1, F2, etc.)
            progress_callback: Optional callback(current, total) for progress

        Returns:
            BatchResult with all results and statistics

        Example:
            >>> samples = load_samples()
            >>> result = await runner.run_batch(samples, task_family="F1")
            >>> for r in result.results:
            ...     if r.success:
            ...         print(f"{r.sample_id}: {r.result.answer}")
        """
        self._processed_count = 0
        self._total_count = len(samples)

        start_time = time.time()
        logger.info(
            "Starting batch processing: %d samples, %d concurrent",
            len(samples),
            self._config.max_concurrent,
        )

        # Create tasks for all samples
        tasks = [
            self._process_sample(
                sample=sample,
                sample_idx=idx,
                task_family=task_family,
                progress_callback=progress_callback,
            )
            for idx, sample in enumerate(samples)
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, handling any exceptions
        processed_results: list[RequestResult] = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    RequestResult(
                        sample_id=str(idx),
                        result=None,
                        error=str(result),
                        latency_ms=0,
                        success=False,
                    )
                )
            else:
                processed_results.append(result)

        total_time_ms = (time.time() - start_time) * 1000
        success_count = sum(1 for r in processed_results if r.success)
        failure_count = len(processed_results) - success_count

        # Calculate statistics
        successful_latencies = [
            r.latency_ms for r in processed_results if r.success
        ]
        avg_latency_ms = (
            sum(successful_latencies) / len(successful_latencies)
            if successful_latencies
            else 0
        )
        throughput_rps = len(processed_results) / (total_time_ms / 1000)

        logger.info(
            "Batch complete: %d/%d success, %.1fs total, %.0f ms/request avg, %.2f RPS",
            success_count,
            len(processed_results),
            total_time_ms / 1000,
            avg_latency_ms,
            throughput_rps,
        )

        return BatchResult(
            results=processed_results,
            total_time_ms=total_time_ms,
            success_count=success_count,
            failure_count=failure_count,
            avg_latency_ms=avg_latency_ms,
            throughput_rps=throughput_rps,
        )

    async def _process_sample(
        self,
        sample: UnifiedSample,
        sample_idx: int,
        task_family: str,
        progress_callback: Callable[[int, int], None] | None,
    ) -> RequestResult:
        """
        Process a single sample with rate limiting and error handling.

        Args:
            sample: Sample to process
            sample_idx: Index in batch for identification
            task_family: Task family for formatting
            progress_callback: Optional progress callback

        Returns:
            RequestResult with success/failure information
        """
        sample_id = getattr(sample, "id", None) or f"sample_{sample_idx}"

        async with self._semaphore:
            # Acquire rate limit token
            await self._rate_limiter.acquire()

            start_time = time.time()
            try:
                # Run FinBound in thread pool (it's synchronous)
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._executor,
                        self._run_finbound_sync,
                        sample,
                        task_family,
                    ),
                    timeout=self._config.timeout_per_request,
                )

                latency_ms = (time.time() - start_time) * 1000

                # Update progress
                self._processed_count += 1
                if self._config.enable_progress and self._processed_count % 10 == 0:
                    logger.info(
                        "Progress: %d/%d (%.1f%%)",
                        self._processed_count,
                        self._total_count,
                        100 * self._processed_count / self._total_count,
                    )

                if progress_callback:
                    progress_callback(self._processed_count, self._total_count)

                return RequestResult(
                    sample_id=sample_id,
                    result=result,
                    error=None,
                    latency_ms=latency_ms,
                    success=True,
                )

            except asyncio.TimeoutError:
                latency_ms = (time.time() - start_time) * 1000
                logger.warning(
                    "Sample %s timed out after %.1fs",
                    sample_id,
                    latency_ms / 1000,
                )
                self._processed_count += 1
                return RequestResult(
                    sample_id=sample_id,
                    result=None,
                    error=f"Timeout after {self._config.timeout_per_request}s",
                    latency_ms=latency_ms,
                    success=False,
                )

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                logger.error(
                    "Sample %s failed: %s",
                    sample_id,
                    str(e)[:200],
                )
                self._processed_count += 1
                return RequestResult(
                    sample_id=sample_id,
                    result=None,
                    error=str(e),
                    latency_ms=latency_ms,
                    success=False,
                )

    def _run_finbound_sync(
        self,
        sample: UnifiedSample,
        task_family: str,
    ) -> FinBoundResult:
        """
        Run FinBound synchronously (called from thread pool).

        Args:
            sample: Sample to process
            task_family: Task family for formatting

        Returns:
            FinBoundResult from processing
        """
        # Determine low_latency_mode based on execution mode
        low_latency_mode = self._config.execution_mode in (
            ExecutionMode.LOW_LATENCY,
            ExecutionMode.ULTRA_LOW_LATENCY,
        )

        # Set environment variable for ultra-low latency mode
        if self._config.execution_mode == ExecutionMode.ULTRA_LOW_LATENCY:
            os.environ["FINBOUND_ULTRA_LOW_LATENCY"] = "1"
            os.environ["FINBOUND_PARALLEL_VERIFICATION"] = "1"
        elif self._config.execution_mode == ExecutionMode.LOW_LATENCY:
            os.environ["FINBOUND_PARALLEL_VERIFICATION"] = "1"

        # Create FinBound instance for this request
        fb = FinBound(
            model=self._config.model,
            low_latency_mode=low_latency_mode,
        )

        return fb.run_unified_sample(sample, task_family=task_family)

    async def run_single(
        self,
        sample: UnifiedSample,
        task_family: str = "F1",
    ) -> RequestResult:
        """
        Process a single sample (convenience method).

        Args:
            sample: Sample to process
            task_family: Task family for formatting

        Returns:
            RequestResult with processing result
        """
        return await self._process_sample(
            sample=sample,
            sample_idx=0,
            task_family=task_family,
            progress_callback=None,
        )

    def shutdown(self) -> None:
        """Shutdown the thread pool executor."""
        self._executor.shutdown(wait=True)
        logger.info("ParallelRunner shutdown complete")

    async def __aenter__(self) -> "ParallelRunner":
        """Async context manager entry."""
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """Async context manager exit - cleanup resources."""
        self.shutdown()


def run_batch_sync(
    samples: list[UnifiedSample],
    max_concurrent: int = 10,
    execution_mode: str = "low_latency",
    task_family: str = "F1",
) -> BatchResult:
    """
    Synchronous wrapper for batch processing.

    Convenience function for non-async code.

    Args:
        samples: Samples to process
        max_concurrent: Maximum concurrent requests
        execution_mode: Processing mode
        task_family: Task family for formatting

    Returns:
        BatchResult with all results

    Example:
        >>> from finbound.parallel import run_batch_sync
        >>> results = run_batch_sync(samples, max_concurrent=10)
    """
    async def _run() -> BatchResult:
        async with ParallelRunner(
            max_concurrent=max_concurrent,
            execution_mode=execution_mode,
        ) as runner:
            return await runner.run_batch(samples, task_family=task_family)

    return asyncio.run(_run())
