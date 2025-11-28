#!/usr/bin/env python3
"""
Latency Benchmark Script for FinBound.

Runs comprehensive latency benchmarks comparing different execution modes
and parallelization strategies.

Usage:
    python experiments/benchmark_latency.py --samples 100 --modes all
    python experiments/benchmark_latency.py --samples 50 --parallel 10
    python experiments/benchmark_latency.py --quick  # Quick test with 10 samples

Output:
    - Console summary with timing statistics
    - JSON file with detailed results
    - CSV file for analysis
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from finbound.parallel import ParallelRunner
from finbound.parallel.runner import ExecutionMode

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark run."""

    num_samples: int = 100
    modes: list[str] | None = None
    parallel_configs: list[int] | None = None
    task_family: str = "F1"
    output_dir: Path = Path("./benchmark_results")
    quick_mode: bool = False
    dry_run: bool = False


def check_api_key() -> tuple[bool, str]:
    """Check if OpenAI or Azure OpenAI is configured.

    Returns:
        Tuple of (is_configured, provider_name)
    """
    # Check Azure first
    azure_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    if azure_key and azure_endpoint:
        return True, "Azure OpenAI"

    # Check standard OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key and openai_key.startswith("sk-"):
        return True, "OpenAI"

    return False, ""


@dataclass
class BenchmarkResult:
    """Result from a single benchmark configuration."""

    config_name: str
    mode: str
    parallel_workers: int
    num_samples: int
    total_time_sec: float
    avg_latency_ms: float
    throughput_rps: float
    success_count: int
    failure_count: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float


def create_mock_samples(num_samples: int) -> list[Any]:
    """
    Create mock samples for benchmarking.

    In production, replace this with actual sample loading from
    your dataset (FinQA, TAT-QA, SEC filings, etc.)

    Args:
        num_samples: Number of samples to create

    Returns:
        List of mock UnifiedSample objects
    """
    # Import here to avoid circular imports during testing
    try:
        from finbound.data.unified import UnifiedSample
    except ImportError:
        # Create a simple mock if imports fail
        @dataclass
        class MockSample:
            id: str
            question: str
            context: str
            tables: list
            answer: str | None = None

        return [
            MockSample(
                id=f"sample_{i}",
                question="What is the percentage change in revenue from 2018 to 2019?",
                context="Revenue in 2018 was $100 million. Revenue in 2019 was $120 million.",
                tables=[],
                answer="20%",
            )
            for i in range(num_samples)
        ]

    # Create actual samples with realistic financial questions
    samples = []
    questions = [
        "What is the percentage change in net sales from 2018 to 2019?",
        "What is the total revenue for fiscal year 2019?",
        "What is the ratio of operating income to total revenue?",
        "What is the 2019 average free cash flow?",
        "How much did the interest expense decrease from 2018 to 2019?",
    ]

    for i in range(num_samples):
        question = questions[i % len(questions)]
        sample = UnifiedSample(
            id=f"benchmark_sample_{i}",
            question=question,
            raw_text=f"Financial data for sample {i}: Revenue 2018: $100M, 2019: $120M",
            tables=[],
            metadata={"source": "benchmark"},
        )
        samples.append(sample)

    return samples


def calculate_percentiles(latencies: list[float]) -> tuple[float, float, float]:
    """
    Calculate p50, p95, p99 latencies.

    Args:
        latencies: List of latency values in ms

    Returns:
        Tuple of (p50, p95, p99)
    """
    if not latencies:
        return (0.0, 0.0, 0.0)

    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    p50_idx = int(n * 0.50)
    p95_idx = int(n * 0.95)
    p99_idx = int(n * 0.99)

    return (
        sorted_latencies[min(p50_idx, n - 1)],
        sorted_latencies[min(p95_idx, n - 1)],
        sorted_latencies[min(p99_idx, n - 1)],
    )


async def run_benchmark_config(
    samples: list[Any],
    mode: ExecutionMode,
    parallel_workers: int,
    task_family: str,
) -> BenchmarkResult:
    """
    Run a single benchmark configuration.

    Args:
        samples: Samples to process
        mode: Execution mode
        parallel_workers: Number of parallel workers
        task_family: Task family for formatting

    Returns:
        BenchmarkResult with timing statistics
    """
    config_name = f"{mode.value}_parallel{parallel_workers}"
    logger.info(
        "Running benchmark: %s with %d samples",
        config_name,
        len(samples),
    )

    start_time = time.time()

    try:
        async with ParallelRunner(
            max_concurrent=parallel_workers,
            execution_mode=mode,
            api_tier="tier5",
        ) as runner:
            batch_result = await runner.run_batch(samples, task_family=task_family)

        total_time = time.time() - start_time

        # Calculate percentiles
        latencies = [r.latency_ms for r in batch_result.results if r.success]
        p50, p95, p99 = calculate_percentiles(latencies)

        return BenchmarkResult(
            config_name=config_name,
            mode=mode.value,
            parallel_workers=parallel_workers,
            num_samples=len(samples),
            total_time_sec=total_time,
            avg_latency_ms=batch_result.avg_latency_ms,
            throughput_rps=batch_result.throughput_rps,
            success_count=batch_result.success_count,
            failure_count=batch_result.failure_count,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
        )

    except Exception as e:
        logger.error("Benchmark failed: %s", e)
        total_time = time.time() - start_time
        return BenchmarkResult(
            config_name=config_name,
            mode=mode.value,
            parallel_workers=parallel_workers,
            num_samples=len(samples),
            total_time_sec=total_time,
            avg_latency_ms=0,
            throughput_rps=0,
            success_count=0,
            failure_count=len(samples),
            p50_latency_ms=0,
            p95_latency_ms=0,
            p99_latency_ms=0,
        )


async def run_all_benchmarks(config: BenchmarkConfig) -> list[BenchmarkResult]:
    """
    Run all benchmark configurations.

    Args:
        config: Benchmark configuration

    Returns:
        List of BenchmarkResult objects
    """
    # Create samples
    samples = create_mock_samples(config.num_samples)
    logger.info("Created %d samples for benchmarking", len(samples))

    # Determine modes to test
    modes = []
    if config.modes is None or "all" in config.modes:
        modes = [
            ExecutionMode.NORMAL,
            ExecutionMode.LOW_LATENCY,
            ExecutionMode.ULTRA_LOW_LATENCY,
        ]
    else:
        for mode_str in config.modes:
            modes.append(ExecutionMode(mode_str))

    # Determine parallel configurations
    parallel_configs = config.parallel_configs or [1, 5, 10, 20]

    results: list[BenchmarkResult] = []

    for mode in modes:
        for workers in parallel_configs:
            result = await run_benchmark_config(
                samples=samples,
                mode=mode,
                parallel_workers=workers,
                task_family=config.task_family,
            )
            results.append(result)

            # Print intermediate result
            print(
                f"\n{result.config_name}: "
                f"{result.total_time_sec:.1f}s total, "
                f"{result.avg_latency_ms:.0f}ms avg, "
                f"{result.throughput_rps:.2f} RPS, "
                f"{result.success_count}/{result.num_samples} success"
            )

    return results


def save_results(
    results: list[BenchmarkResult],
    output_dir: Path,
) -> None:
    """
    Save benchmark results to files.

    Args:
        results: List of benchmark results
        output_dir: Directory to save results
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save as JSON
    json_path = output_dir / f"benchmark_{timestamp}.json"
    with open(json_path, "w") as f:
        json.dump(
            [asdict(r) for r in results],
            f,
            indent=2,
        )
    logger.info("Saved JSON results to %s", json_path)

    # Save as CSV
    csv_path = output_dir / f"benchmark_{timestamp}.csv"
    with open(csv_path, "w") as f:
        # Header
        headers = [
            "config_name",
            "mode",
            "parallel_workers",
            "num_samples",
            "total_time_sec",
            "avg_latency_ms",
            "throughput_rps",
            "success_count",
            "failure_count",
            "p50_latency_ms",
            "p95_latency_ms",
            "p99_latency_ms",
        ]
        f.write(",".join(headers) + "\n")

        # Data
        for r in results:
            row = [
                r.config_name,
                r.mode,
                str(r.parallel_workers),
                str(r.num_samples),
                f"{r.total_time_sec:.2f}",
                f"{r.avg_latency_ms:.2f}",
                f"{r.throughput_rps:.4f}",
                str(r.success_count),
                str(r.failure_count),
                f"{r.p50_latency_ms:.2f}",
                f"{r.p95_latency_ms:.2f}",
                f"{r.p99_latency_ms:.2f}",
            ]
            f.write(",".join(row) + "\n")

    logger.info("Saved CSV results to %s", csv_path)


def print_summary(results: list[BenchmarkResult]) -> None:
    """
    Print summary of benchmark results.

    Args:
        results: List of benchmark results
    """
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)

    # Group by mode
    by_mode: dict[str, list[BenchmarkResult]] = {}
    for r in results:
        by_mode.setdefault(r.mode, []).append(r)

    for mode, mode_results in by_mode.items():
        print(f"\n{mode.upper()} MODE:")
        print("-" * 60)
        print(
            f"{'Workers':<10} {'Total(s)':<12} {'Avg(ms)':<12} "
            f"{'RPS':<12} {'Success':<10}"
        )
        print("-" * 60)

        for r in sorted(mode_results, key=lambda x: x.parallel_workers):
            print(
                f"{r.parallel_workers:<10} {r.total_time_sec:<12.1f} "
                f"{r.avg_latency_ms:<12.0f} {r.throughput_rps:<12.2f} "
                f"{r.success_count}/{r.num_samples}"
            )

    # Find best configuration
    best = min(results, key=lambda r: r.total_time_sec if r.success_count > 0 else float("inf"))
    print("\n" + "=" * 80)
    print(f"BEST CONFIGURATION: {best.config_name}")
    print(f"  Total Time: {best.total_time_sec:.1f}s")
    print(f"  Avg Latency: {best.avg_latency_ms:.0f}ms")
    print(f"  Throughput: {best.throughput_rps:.2f} RPS")
    print(f"  Success Rate: {100 * best.success_count / best.num_samples:.1f}%")
    print("=" * 80)

    # Check if target met (3 minutes for 100 samples)
    target_time = 180  # 3 minutes in seconds
    if best.total_time_sec <= target_time:
        print(f"\n✅ TARGET MET: {best.total_time_sec:.1f}s <= {target_time}s (3 minutes)")
    else:
        print(f"\n❌ TARGET NOT MET: {best.total_time_sec:.1f}s > {target_time}s (3 minutes)")
        print(f"   Gap: {best.total_time_sec - target_time:.1f}s over target")


def main() -> None:
    """Main entry point for benchmark script."""
    parser = argparse.ArgumentParser(
        description="FinBound Latency Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full benchmark with 100 samples
  python benchmark_latency.py --samples 100 --modes all

  # Quick test with 10 samples
  python benchmark_latency.py --quick

  # Test specific mode with specific parallelism
  python benchmark_latency.py --samples 50 --modes low_latency --parallel 10 20

  # Dry run to test infrastructure (no API calls)
  python benchmark_latency.py --quick --dry-run
        """,
    )

    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="Number of samples to benchmark (default: 100)",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["all"],
        help="Execution modes to test: normal, low_latency, ultra_low_latency, all",
    )
    parser.add_argument(
        "--parallel",
        nargs="+",
        type=int,
        default=[1, 5, 10, 20],
        help="Parallel worker counts to test (default: 1 5 10 20)",
    )
    parser.add_argument(
        "--task",
        default="F1",
        help="Task family for formatting (default: F1)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./benchmark_results"),
        help="Output directory for results",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test mode: 10 samples, low_latency only, parallel 5",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test infrastructure without making API calls",
    )

    args = parser.parse_args()

    # Check for API key
    is_configured, provider = check_api_key()
    if not args.dry_run and not is_configured:
        print("\n⚠️  WARNING: No API configuration found!")
        print("   To run actual benchmarks, please configure either:")
        print("\n   OPTION 1 - OpenAI:")
        print("     - Set OPENAI_API_KEY environment variable")
        print("\n   OPTION 2 - Azure OpenAI:")
        print("     - Set AZURE_OPENAI_API_KEY")
        print("     - Set AZURE_OPENAI_ENDPOINT")
        print("     - Set AZURE_OPENAI_DEPLOYMENT_GPT4O (your gpt-4o deployment name)")
        print("     - Set AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI (your gpt-4o-mini deployment name)")
        print("\n   Or copy .env.example to .env and fill in your values.")
        print("\n   Run with --dry-run to test infrastructure without API calls.\n")
        sys.exit(1)
    elif is_configured:
        print(f"\n✓ Using {provider} for API calls")

    # Quick mode overrides
    if args.quick:
        args.samples = 10
        args.modes = ["low_latency"]
        args.parallel = [5]

    config = BenchmarkConfig(
        num_samples=args.samples,
        modes=args.modes,
        parallel_configs=args.parallel,
        task_family=args.task,
        output_dir=args.output,
        quick_mode=args.quick,
    )

    print("\nStarting FinBound Latency Benchmark")
    print(f"  Samples: {config.num_samples}")
    print(f"  Modes: {config.modes}")
    print(f"  Parallel configs: {config.parallel_configs}")
    print(f"  Output: {config.output_dir}")
    print()

    # Run benchmarks
    results = asyncio.run(run_all_benchmarks(config))

    # Save and display results
    save_results(results, config.output_dir)
    print_summary(results)


if __name__ == "__main__":
    main()
