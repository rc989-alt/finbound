#!/usr/bin/env python3
"""
Real Data Benchmark for FinBound Latency Optimization.

Tests the parallel processing infrastructure with actual FinQA dataset samples.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from finbound.parallel import ParallelRunner
from finbound.data.unified import UnifiedSample

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class FinQASample:
    """A sample from the FinQA dataset."""
    id: str
    question: str
    pre_text: list[str]
    post_text: list[str]
    table: list[list[str]]
    gold_answer: str
    program: str


def load_finqa_samples(data_path: str, limit: int = 10) -> list[UnifiedSample]:
    """Load samples from FinQA dataset and convert to UnifiedSample format."""
    with open(data_path) as f:
        data = json.load(f)
    
    samples = []
    for i, item in enumerate(data[:limit]):
        qa = item.get("qa", {})
        
        # Combine pre and post text
        pre_text = item.get("pre_text", [])
        post_text = item.get("post_text", [])
        combined_text = "\n".join(pre_text + post_text)
        
        # Get table
        table = item.get("table", [])
        
        # Create UnifiedSample
        sample = UnifiedSample(
            id=item.get("id", f"finqa_{i}"),
            question=qa.get("question", ""),
            raw_text=combined_text,
            tables=[table] if table else [],
            answer=qa.get("answer", ""),
            metadata={
                "source": "finqa",
                "program": qa.get("program", ""),
                "filename": item.get("filename", ""),
            }
        )
        samples.append(sample)
    
    return samples


async def run_benchmark(
    samples: list[UnifiedSample],
    max_concurrent: int = 5,
    mode: str = "low_latency",
) -> dict[str, Any]:
    """Run benchmark on real samples."""
    
    logger.info(f"Starting benchmark with {len(samples)} real FinQA samples")
    logger.info(f"Mode: {mode}, Concurrent workers: {max_concurrent}")
    
    start_time = time.time()
    
    async with ParallelRunner(
        max_concurrent=max_concurrent,
        execution_mode=mode,
        timeout_per_request=180,  # 3 minutes per request
    ) as runner:
        result = await runner.run_batch(samples, task_family="F1")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Calculate accuracy
    correct = 0
    results_detail = []
    
    for i, res in enumerate(result.results):
        sample = samples[i] if i < len(samples) else None
        gold = sample.answer if sample else ""
        predicted = ""
        
        if res.success and res.result:
            # Extract answer from result
            if hasattr(res.result, 'answer'):
                predicted = str(res.result.answer)
            elif isinstance(res.result, dict):
                predicted = str(res.result.get('answer', ''))
        
        # Simple accuracy check (exact match after normalization)
        is_correct = normalize_answer(predicted) == normalize_answer(gold)
        if is_correct:
            correct += 1
        
        results_detail.append({
            "id": res.sample_id,
            "question": sample.question[:100] if sample else "",
            "gold": gold,
            "predicted": predicted,
            "correct": is_correct,
            "latency_ms": res.latency_ms,
            "success": res.success,
            "error": res.error,
        })
    
    accuracy = correct / len(samples) if samples else 0
    
    return {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "mode": mode,
            "max_concurrent": max_concurrent,
            "num_samples": len(samples),
            "dataset": "FinQA (train)",
        },
        "results": {
            "total_time_sec": total_time,
            "avg_latency_ms": result.avg_latency_ms,
            "success_count": result.success_count,
            "failure_count": result.failure_count,
            "accuracy": accuracy,
            "correct": correct,
            "total": len(samples),
        },
        "details": results_detail,
    }


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison."""
    if not answer:
        return ""
    # Remove percentage signs, commas, whitespace
    answer = str(answer).strip().lower()
    answer = answer.replace("%", "").replace(",", "").replace("$", "")
    answer = answer.strip()
    return answer


def main():
    """Run the real data benchmark."""
    import argparse
    
    parser = argparse.ArgumentParser(description="FinBound Real Data Benchmark")
    parser.add_argument("--samples", type=int, default=10, help="Number of samples")
    parser.add_argument("--parallel", type=int, default=5, help="Parallel workers")
    parser.add_argument("--mode", default="low_latency", help="Execution mode")
    parser.add_argument("--data", default="data/finqa/train.json", help="Data path")
    args = parser.parse_args()
    
    # Check API configuration
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if azure_key:
        print(f"\n✓ Using Azure OpenAI")
    elif openai_key:
        print(f"\n✓ Using OpenAI")
    else:
        print("\n⚠️  No API key configured!")
        sys.exit(1)
    
    # Check data file
    if not Path(args.data).exists():
        print(f"\n⚠️  Data file not found: {args.data}")
        print("Run: curl -L 'https://raw.githubusercontent.com/czyssrs/FinQA/main/dataset/train.json' -o data/finqa/train.json")
        sys.exit(1)
    
    # Load samples
    print(f"\nLoading {args.samples} samples from FinQA dataset...")
    samples = load_finqa_samples(args.data, args.samples)
    print(f"Loaded {len(samples)} samples")
    
    # Show sample questions
    print("\nSample questions:")
    for i, s in enumerate(samples[:3]):
        print(f"  {i+1}. {s.question[:80]}...")
    
    # Run benchmark
    print(f"\n{'='*60}")
    print("RUNNING REAL DATA BENCHMARK")
    print(f"{'='*60}")
    
    result = asyncio.run(run_benchmark(
        samples,
        max_concurrent=args.parallel,
        mode=args.mode,
    ))
    
    # Save results
    output_dir = Path("benchmark_results")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"real_data_benchmark_{timestamp}.json"
    
    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)
    
    # Print summary
    print(f"\n{'='*60}")
    print("REAL DATA BENCHMARK RESULTS")
    print(f"{'='*60}")
    print(f"\nDataset: FinQA (official train set)")
    print(f"Samples: {result['config']['num_samples']}")
    print(f"Mode: {result['config']['mode']}")
    print(f"Parallel Workers: {result['config']['max_concurrent']}")
    print(f"\n--- Performance ---")
    print(f"Total Time: {result['results']['total_time_sec']:.1f}s")
    print(f"Avg Latency: {result['results']['avg_latency_ms']:.0f}ms per request")
    print(f"Success Rate: {result['results']['success_count']}/{result['config']['num_samples']} ({100*result['results']['success_count']/result['config']['num_samples']:.0f}%)")
    print(f"\n--- Accuracy ---")
    print(f"Correct: {result['results']['correct']}/{result['results']['total']}")
    print(f"Accuracy: {100*result['results']['accuracy']:.1f}%")
    print(f"\nResults saved to: {output_file}")
    
    # Show individual results
    print(f"\n--- Individual Results ---")
    for d in result['details'][:5]:
        status = "✓" if d['correct'] else "✗"
        print(f"{status} {d['id']}: gold={d['gold']}, predicted={d['predicted']}, latency={d['latency_ms']:.0f}ms")
    
    if len(result['details']) > 5:
        print(f"  ... and {len(result['details'])-5} more")


if __name__ == "__main__":
    main()
