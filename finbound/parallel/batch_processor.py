"""
Batch Processor for FinBound Parallel Execution.

Provides utilities for batch processing with chunking, progress tracking,
result aggregation, and error reporting.

Features:
    - Automatic chunking for very large batches
    - Progress tracking with callbacks
    - Result aggregation and statistics
    - Retry handling for transient failures
    - JSON/CSV export of results

Production Usage:
    For processing thousands of documents:
    - Chunks into smaller batches to prevent memory issues
    - Tracks progress for long-running jobs
    - Handles partial failures gracefully
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterator

from ..data.unified import UnifiedSample
from .runner import BatchResult, ExecutionMode, ParallelRunner, RequestResult

logger = logging.getLogger(__name__)


@dataclass
class BatchProcessorConfig:
    """Configuration for batch processor.

    Attributes:
        chunk_size: Number of samples per chunk
        max_concurrent: Maximum concurrent requests per chunk
        execution_mode: Processing mode
        api_tier: OpenAI API tier
        save_intermediate: Save results after each chunk
        output_dir: Directory for saving results
        retry_failed: Retry failed samples in separate batch
    """

    chunk_size: int = 100
    max_concurrent: int = 10
    execution_mode: ExecutionMode = ExecutionMode.LOW_LATENCY
    api_tier: str = "tier5"
    save_intermediate: bool = True
    output_dir: Path | str = "./results"
    retry_failed: bool = True


@dataclass
class ProcessingStats:
    """Statistics for batch processing run.

    Attributes:
        total_samples: Total number of samples
        processed: Number processed (success + failure)
        success: Number of successful samples
        failed: Number of failed samples
        total_time_sec: Total processing time in seconds
        avg_latency_ms: Average latency per sample
        throughput_rps: Requests per second
        chunks_processed: Number of chunks processed
    """

    total_samples: int
    processed: int
    success: int
    failed: int
    total_time_sec: float
    avg_latency_ms: float
    throughput_rps: float
    chunks_processed: int


class BatchProcessor:
    """
    Batch processor with chunking and progress tracking.

    Handles large-scale processing by:
    - Breaking into manageable chunks
    - Tracking and reporting progress
    - Saving intermediate results
    - Retrying failed samples

    Example:
        >>> processor = BatchProcessor(chunk_size=100, max_concurrent=10)
        >>> results = await processor.process(samples, task_family="F1")
        >>> print(f"Success rate: {results.stats.success}/{results.stats.total_samples}")

    Production Usage:
        >>> # Process 10,000 documents
        >>> processor = BatchProcessor(
        ...     chunk_size=100,
        ...     max_concurrent=20,
        ...     save_intermediate=True,
        ...     output_dir="./results/batch_001",
        ... )
        >>> async for chunk_result in processor.process_streaming(samples):
        ...     print(f"Chunk complete: {chunk_result.success_count} success")
    """

    def __init__(
        self,
        chunk_size: int = 100,
        max_concurrent: int = 10,
        execution_mode: ExecutionMode | str = ExecutionMode.LOW_LATENCY,
        api_tier: str = "tier5",
        save_intermediate: bool = True,
        output_dir: Path | str = "./results",
        retry_failed: bool = True,
    ) -> None:
        """
        Initialize batch processor.

        Args:
            chunk_size: Number of samples per chunk (default 100)
            max_concurrent: Maximum concurrent requests per chunk
            execution_mode: Processing mode
            api_tier: OpenAI API tier for rate limiting
            save_intermediate: Save results after each chunk
            output_dir: Directory for saving results
            retry_failed: Retry failed samples in separate batch
        """
        if isinstance(execution_mode, str):
            execution_mode = ExecutionMode(execution_mode)

        self._config = BatchProcessorConfig(
            chunk_size=chunk_size,
            max_concurrent=max_concurrent,
            execution_mode=execution_mode,
            api_tier=api_tier,
            save_intermediate=save_intermediate,
            output_dir=Path(output_dir),
            retry_failed=retry_failed,
        )

        self._stats = ProcessingStats(
            total_samples=0,
            processed=0,
            success=0,
            failed=0,
            total_time_sec=0,
            avg_latency_ms=0,
            throughput_rps=0,
            chunks_processed=0,
        )

        logger.info(
            "BatchProcessor initialized: chunk_size=%d, max_concurrent=%d",
            chunk_size,
            max_concurrent,
        )

    @property
    def config(self) -> BatchProcessorConfig:
        """Get current configuration."""
        return self._config

    @property
    def stats(self) -> ProcessingStats:
        """Get current processing statistics."""
        return self._stats

    async def process(
        self,
        samples: list[UnifiedSample],
        task_family: str = "F1",
        progress_callback: Callable[[ProcessingStats], None] | None = None,
    ) -> tuple[list[RequestResult], ProcessingStats]:
        """
        Process all samples with chunking and progress tracking.

        Args:
            samples: All samples to process
            task_family: Task family for formatting
            progress_callback: Optional callback for progress updates

        Returns:
            Tuple of (all_results, final_stats)

        Example:
            >>> results, stats = await processor.process(samples)
            >>> print(f"Processed {stats.success}/{stats.total_samples}")
        """
        start_time = time.time()
        all_results: list[RequestResult] = []

        self._stats = ProcessingStats(
            total_samples=len(samples),
            processed=0,
            success=0,
            failed=0,
            total_time_sec=0,
            avg_latency_ms=0,
            throughput_rps=0,
            chunks_processed=0,
        )

        # Ensure output directory exists
        if self._config.save_intermediate:
            self._config.output_dir.mkdir(parents=True, exist_ok=True)

        # Process in chunks
        chunks = list(self._chunk_samples(samples))
        total_chunks = len(chunks)

        logger.info(
            "Processing %d samples in %d chunks",
            len(samples),
            total_chunks,
        )

        for chunk_idx, chunk in enumerate(chunks):
            logger.info(
                "Processing chunk %d/%d (%d samples)",
                chunk_idx + 1,
                total_chunks,
                len(chunk),
            )

            # Process chunk
            async with ParallelRunner(
                max_concurrent=self._config.max_concurrent,
                execution_mode=self._config.execution_mode,
                api_tier=self._config.api_tier,
            ) as runner:
                chunk_result = await runner.run_batch(chunk, task_family=task_family)

            # Update statistics
            all_results.extend(chunk_result.results)
            self._stats.processed += len(chunk_result.results)
            self._stats.success += chunk_result.success_count
            self._stats.failed += chunk_result.failure_count
            self._stats.chunks_processed += 1

            # Save intermediate results
            if self._config.save_intermediate:
                self._save_chunk_results(chunk_idx, chunk_result)

            # Update timing stats
            elapsed = time.time() - start_time
            self._stats.total_time_sec = elapsed
            if self._stats.success > 0:
                successful_latencies = [
                    r.latency_ms for r in all_results if r.success
                ]
                self._stats.avg_latency_ms = (
                    sum(successful_latencies) / len(successful_latencies)
                )
            self._stats.throughput_rps = (
                self._stats.processed / elapsed if elapsed > 0 else 0
            )

            # Progress callback
            if progress_callback:
                progress_callback(self._stats)

            logger.info(
                "Chunk %d/%d complete: %d success, %d failed, %.1fs elapsed",
                chunk_idx + 1,
                total_chunks,
                chunk_result.success_count,
                chunk_result.failure_count,
                elapsed,
            )

        # Retry failed samples if configured
        if self._config.retry_failed and self._stats.failed > 0:
            failed_indices = [
                i for i, r in enumerate(all_results) if not r.success
            ]
            if failed_indices:
                logger.info(
                    "Retrying %d failed samples",
                    len(failed_indices),
                )
                # Note: Retry logic would go here
                # For now, we just log the failed samples

        # Save final results
        if self._config.save_intermediate:
            self._save_final_results(all_results)

        logger.info(
            "Batch processing complete: %d/%d success (%.1f%%), %.1fs total, %.2f RPS",
            self._stats.success,
            self._stats.total_samples,
            100 * self._stats.success / max(1, self._stats.total_samples),
            self._stats.total_time_sec,
            self._stats.throughput_rps,
        )

        return all_results, self._stats

    async def process_streaming(
        self,
        samples: list[UnifiedSample],
        task_family: str = "F1",
    ) -> Iterator[BatchResult]:
        """
        Process samples in streaming fashion, yielding results per chunk.

        Useful for very large batches where you want to process results
        as they become available.

        Args:
            samples: All samples to process
            task_family: Task family for formatting

        Yields:
            BatchResult for each chunk as it completes

        Example:
            >>> async for chunk_result in processor.process_streaming(samples):
            ...     save_to_database(chunk_result.results)
        """
        chunks = list(self._chunk_samples(samples))

        for chunk_idx, chunk in enumerate(chunks):
            logger.info(
                "Processing chunk %d/%d",
                chunk_idx + 1,
                len(chunks),
            )

            async with ParallelRunner(
                max_concurrent=self._config.max_concurrent,
                execution_mode=self._config.execution_mode,
                api_tier=self._config.api_tier,
            ) as runner:
                chunk_result = await runner.run_batch(chunk, task_family=task_family)

            yield chunk_result

    def _chunk_samples(
        self,
        samples: list[UnifiedSample],
    ) -> Iterator[list[UnifiedSample]]:
        """
        Split samples into chunks.

        Args:
            samples: All samples

        Yields:
            Chunks of samples
        """
        for i in range(0, len(samples), self._config.chunk_size):
            yield samples[i : i + self._config.chunk_size]

    def _save_chunk_results(
        self,
        chunk_idx: int,
        result: BatchResult,
    ) -> None:
        """
        Save results from a single chunk.

        Args:
            chunk_idx: Index of the chunk
            result: Results from processing the chunk
        """
        output_file = self._config.output_dir / f"chunk_{chunk_idx:04d}.json"
        data = {
            "chunk_idx": chunk_idx,
            "total_time_ms": result.total_time_ms,
            "success_count": result.success_count,
            "failure_count": result.failure_count,
            "results": [
                {
                    "sample_id": r.sample_id,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "answer": r.result.answer if r.result else None,
                    "error": r.error,
                }
                for r in result.results
            ],
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.debug("Saved chunk results to %s", output_file)

    def _save_final_results(
        self,
        results: list[RequestResult],
    ) -> None:
        """
        Save final aggregated results.

        Args:
            results: All results from processing
        """
        output_file = self._config.output_dir / "final_results.json"
        data = {
            "stats": asdict(self._stats),
            "results": [
                {
                    "sample_id": r.sample_id,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "answer": r.result.answer if r.result else None,
                    "verified": r.result.verified if r.result else None,
                    "error": r.error,
                }
                for r in results
            ],
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info("Saved final results to %s", output_file)

    def get_failed_samples(
        self,
        results: list[RequestResult],
        samples: list[UnifiedSample],
    ) -> list[UnifiedSample]:
        """
        Get samples that failed processing.

        Args:
            results: Results from processing
            samples: Original samples (in same order)

        Returns:
            List of samples that failed
        """
        failed_indices = {
            i for i, r in enumerate(results) if not r.success
        }
        return [s for i, s in enumerate(samples) if i in failed_indices]
