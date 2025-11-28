"""
FinBound Parallel Processing Module.

This module provides concurrent execution capabilities for processing
multiple financial documents/requests simultaneously, enabling throughput
optimization for production workloads.

Key Components:
    - ParallelRunner: Main orchestrator for concurrent request processing
    - AsyncRateLimiter: Token-bucket rate limiter for API throttling prevention
    - BatchProcessor: Utility for batch processing with progress tracking

Production Usage:
    For financial institutions processing many concurrent requests:
    - Process 10-50 requests concurrently
    - Automatic rate limiting to prevent API throttling
    - Full 128K token context support per request
    - Maintains accuracy and auditability guarantees

Example:
    >>> from finbound.parallel import ParallelRunner
    >>> runner = ParallelRunner(max_concurrent=10)
    >>> results = await runner.run_batch(samples, task_family="F1")
"""

from .runner import ParallelRunner
from .rate_limiter import AsyncRateLimiter
from .batch_processor import BatchProcessor

__all__ = [
    "ParallelRunner",
    "AsyncRateLimiter",
    "BatchProcessor",
]
