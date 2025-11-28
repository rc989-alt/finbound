"""
Unit tests for FinBound Parallel Runner.

Tests the parallel processing infrastructure including:
- AsyncRateLimiter token bucket algorithm
- ParallelRunner concurrent execution
- BatchProcessor chunking and progress tracking
- ExecutionMode configurations
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from finbound.parallel.rate_limiter import (
    AsyncRateLimiter,
    create_rate_limiter_for_tier,
    OPENAI_TIER_CONFIGS,
)
from finbound.parallel.runner import (
    BatchResult,
    ExecutionMode,
    ParallelRunner,
    ParallelRunnerConfig,
    RequestResult,
)


class TestAsyncRateLimiter:
    """Tests for AsyncRateLimiter."""

    @pytest.mark.asyncio
    async def test_basic_acquire(self) -> None:
        """Test basic token acquisition."""
        limiter = AsyncRateLimiter(
            requests_per_minute=600,  # 10 per second
            burst_size=10,
        )

        # Should acquire immediately with available tokens
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should be nearly instant
        assert limiter.stats.total_requests == 1

    @pytest.mark.asyncio
    async def test_rate_limiting(self) -> None:
        """Test that rate limiting actually delays requests."""
        limiter = AsyncRateLimiter(
            requests_per_minute=60,  # 1 per second
            burst_size=1,
        )

        # First request should be instant
        await limiter.acquire()

        # Second request should wait ~1 second
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        # Should have waited approximately 1 second
        assert elapsed >= 0.9
        assert elapsed < 1.5

    @pytest.mark.asyncio
    async def test_burst_handling(self) -> None:
        """Test burst token bucket allows burst traffic."""
        limiter = AsyncRateLimiter(
            requests_per_minute=60,  # 1 per second
            burst_size=5,  # Allow 5 request burst
        )

        # Should allow 5 requests quickly due to burst
        start = time.time()
        for _ in range(5):
            await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed < 0.5  # All 5 should complete quickly
        assert limiter.stats.total_requests == 5

    @pytest.mark.asyncio
    async def test_stats_tracking(self) -> None:
        """Test statistics are tracked correctly."""
        limiter = AsyncRateLimiter(
            requests_per_minute=600,
            burst_size=10,
        )

        for _ in range(5):
            await limiter.acquire()

        assert limiter.stats.total_requests == 5
        assert limiter.stats.last_request_time > 0

        limiter.reset_stats()
        assert limiter.stats.total_requests == 0

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager usage."""
        limiter = AsyncRateLimiter(
            requests_per_minute=600,
            burst_size=10,
        )

        async with limiter:
            pass  # Token acquired on entry

        assert limiter.stats.total_requests == 1

    def test_tier_configs(self) -> None:
        """Test OpenAI tier configurations are valid."""
        for tier, config in OPENAI_TIER_CONFIGS.items():
            assert config.requests_per_minute > 0
            assert config.tokens_per_minute is None or config.tokens_per_minute > 0

    def test_create_rate_limiter_for_tier(self) -> None:
        """Test tier-based rate limiter creation."""
        limiter = create_rate_limiter_for_tier("tier5")
        assert limiter._config.requests_per_minute == 10000

        with pytest.raises(ValueError):
            create_rate_limiter_for_tier("invalid_tier")


class TestParallelRunnerConfig:
    """Tests for ParallelRunnerConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ParallelRunnerConfig()
        assert config.max_concurrent == 10
        assert config.execution_mode == ExecutionMode.LOW_LATENCY
        assert config.api_tier == "tier5"
        assert config.timeout_per_request == 120.0

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = ParallelRunnerConfig(
            max_concurrent=20,
            execution_mode=ExecutionMode.ULTRA_LOW_LATENCY,
            api_tier="tier3",
            timeout_per_request=60.0,
        )
        assert config.max_concurrent == 20
        assert config.execution_mode == ExecutionMode.ULTRA_LOW_LATENCY
        assert config.api_tier == "tier3"
        assert config.timeout_per_request == 60.0


class TestExecutionMode:
    """Tests for ExecutionMode enum."""

    def test_mode_values(self) -> None:
        """Test execution mode values."""
        assert ExecutionMode.NORMAL.value == "normal"
        assert ExecutionMode.LOW_LATENCY.value == "low_latency"
        assert ExecutionMode.ULTRA_LOW_LATENCY.value == "ultra_low_latency"

    def test_mode_from_string(self) -> None:
        """Test creating mode from string."""
        assert ExecutionMode("normal") == ExecutionMode.NORMAL
        assert ExecutionMode("low_latency") == ExecutionMode.LOW_LATENCY
        assert ExecutionMode("ultra_low_latency") == ExecutionMode.ULTRA_LOW_LATENCY


class TestRequestResult:
    """Tests for RequestResult dataclass."""

    def test_successful_result(self) -> None:
        """Test successful request result."""
        result = RequestResult(
            sample_id="test_1",
            result=MagicMock(answer="42%"),
            error=None,
            latency_ms=1500.0,
            success=True,
        )
        assert result.success
        assert result.error is None
        assert result.latency_ms == 1500.0

    def test_failed_result(self) -> None:
        """Test failed request result."""
        result = RequestResult(
            sample_id="test_2",
            result=None,
            error="Timeout after 120s",
            latency_ms=120000.0,
            success=False,
        )
        assert not result.success
        assert result.error == "Timeout after 120s"


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_batch_statistics(self) -> None:
        """Test batch result statistics."""
        results = [
            RequestResult("s1", MagicMock(), None, 1000, True),
            RequestResult("s2", MagicMock(), None, 2000, True),
            RequestResult("s3", None, "Error", 500, False),
        ]

        batch = BatchResult(
            results=results,
            total_time_ms=5000.0,
            success_count=2,
            failure_count=1,
            avg_latency_ms=1500.0,
            throughput_rps=0.6,
        )

        assert batch.success_count == 2
        assert batch.failure_count == 1
        assert len(batch.results) == 3


class TestParallelRunner:
    """Tests for ParallelRunner class."""

    def test_init_default(self) -> None:
        """Test default initialization."""
        runner = ParallelRunner()
        assert runner.config.max_concurrent == 10
        assert runner.config.execution_mode == ExecutionMode.LOW_LATENCY

    def test_init_with_string_mode(self) -> None:
        """Test initialization with string mode."""
        runner = ParallelRunner(execution_mode="ultra_low_latency")
        assert runner.config.execution_mode == ExecutionMode.ULTRA_LOW_LATENCY

    def test_init_with_enum_mode(self) -> None:
        """Test initialization with enum mode."""
        runner = ParallelRunner(execution_mode=ExecutionMode.NORMAL)
        assert runner.config.execution_mode == ExecutionMode.NORMAL

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager cleanup."""
        async with ParallelRunner(max_concurrent=5) as runner:
            assert runner.config.max_concurrent == 5
        # Executor should be shut down after context exit

    @pytest.mark.asyncio
    async def test_run_batch_empty(self) -> None:
        """Test running empty batch."""
        async with ParallelRunner(max_concurrent=5) as runner:
            result = await runner.run_batch([], task_family="F1")
            assert result.success_count == 0
            assert result.failure_count == 0
            assert len(result.results) == 0


class TestParallelRunnerIntegration:
    """Integration tests for ParallelRunner (require mocking)."""

    @pytest.mark.asyncio
    async def test_run_single_mocked(self) -> None:
        """Test running single sample with mocked FinBound."""
        @dataclass
        class MockSample:
            id: str = "test_sample"
            question: str = "What is 2+2?"

        @dataclass
        class MockResult:
            answer: str = "4"
            verified: bool = True

        with patch.object(
            ParallelRunner,
            "_run_finbound_sync",
            return_value=MockResult(),
        ):
            async with ParallelRunner(max_concurrent=1) as runner:
                result = await runner.run_single(MockSample())

                assert result.success
                assert result.result is not None
                assert result.result.answer == "4"

    @pytest.mark.asyncio
    async def test_run_batch_mocked(self) -> None:
        """Test running batch with mocked FinBound."""
        @dataclass
        class MockSample:
            id: str
            question: str = "What is 2+2?"

        @dataclass
        class MockResult:
            answer: str = "4"
            verified: bool = True

        samples = [MockSample(id=f"sample_{i}") for i in range(5)]

        with patch.object(
            ParallelRunner,
            "_run_finbound_sync",
            return_value=MockResult(),
        ):
            async with ParallelRunner(max_concurrent=3) as runner:
                result = await runner.run_batch(samples, task_family="F1")

                assert result.success_count == 5
                assert result.failure_count == 0
                assert len(result.results) == 5

    @pytest.mark.asyncio
    async def test_timeout_handling(self) -> None:
        """Test timeout handling for slow requests."""
        @dataclass
        class MockSample:
            id: str = "slow_sample"

        def slow_finbound_sync(*args: Any, **kwargs: Any) -> Any:
            # Simulate a slow synchronous function
            import time
            time.sleep(10)  # Longer than timeout
            return MagicMock()

        with patch.object(
            ParallelRunner,
            "_run_finbound_sync",
            side_effect=slow_finbound_sync,
        ):
            async with ParallelRunner(
                max_concurrent=1,
                timeout_per_request=0.1,  # Very short timeout
            ) as runner:
                result = await runner.run_single(MockSample())

                assert not result.success
                assert "Timeout" in (result.error or "")


class TestExecutionModeEnvironment:
    """Tests for environment-based execution mode configuration."""

    def test_ultra_low_latency_env(self) -> None:
        """Test ultra-low latency mode from environment."""
        import os

        original = os.environ.get("FINBOUND_ULTRA_LOW_LATENCY")
        try:
            os.environ["FINBOUND_ULTRA_LOW_LATENCY"] = "1"

            # Create runner with ultra mode enabled via env
            runner = ParallelRunner(
                max_concurrent=5,
                execution_mode=ExecutionMode.LOW_LATENCY,
            )

            # The runner should still use the explicit mode
            assert runner.config.execution_mode == ExecutionMode.LOW_LATENCY

        finally:
            if original is not None:
                os.environ["FINBOUND_ULTRA_LOW_LATENCY"] = original
            else:
                os.environ.pop("FINBOUND_ULTRA_LOW_LATENCY", None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
