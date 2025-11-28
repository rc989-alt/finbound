#!/usr/bin/env python3
"""
Test new FinBound architecture (QuantLib + low latency mode) on failed samples.
Compares accuracy and latency between normal and low_latency modes.
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from finbound.reasoning.engine import ReasoningEngine
from finbound.types import StructuredRequest, EvidenceContract, EvidenceContext


def load_failed_samples() -> List[Dict[str, Any]]:
    """Load the failed samples from rerun_results.json."""
    results_path = Path(__file__).parent.parent / "experiments/F1_result/failed_questions/20251127_001517/rerun_results.json"
    with open(results_path) as f:
        return json.load(f)


def load_sample_evidence(sample_id: str, dataset: str) -> Dict[str, Any]:
    """Load full sample data with evidence."""
    if dataset == "finqa":
        # Load from FinQA dev.json
        raw_path = Path(__file__).parent.parent / "data/raw/FinQA/dataset/dev.json"
        with open(raw_path) as f:
            samples = json.load(f)
        for s in samples:
            if s.get("id") == sample_id:
                return s
    elif dataset == "tatqa":
        # Load from TAT-QA
        raw_path = Path(__file__).parent.parent / "data/raw/TAT-QA/dataset_raw/tatqa_dataset_dev.json"
        with open(raw_path) as f:
            samples = json.load(f)
        for s in samples:
            if s.get("table", {}).get("uid") == sample_id:
                return s
            # Also check questions
            for q in s.get("questions", []):
                if q.get("uid") == sample_id:
                    return {**s, "question": q}
    return {}


def format_evidence(sample: Dict[str, Any], dataset: str) -> EvidenceContext:
    """Format sample data into EvidenceContext."""
    text_blocks = []
    tables = []

    if dataset == "finqa":
        # Pre-text
        if "pre_text" in sample:
            text_blocks.extend(sample["pre_text"])
        # Table
        if "table" in sample:
            tables.append(sample["table"])
        # Post-text
        if "post_text" in sample:
            text_blocks.extend(sample["post_text"][:5])
    elif dataset == "tatqa":
        # Paragraphs
        for p in sample.get("paragraphs", []):
            text_blocks.append(p.get("text", ""))
        # Table
        if "table" in sample and sample["table"].get("table"):
            tables.append(sample["table"]["table"])

    return EvidenceContext(
        text_blocks=text_blocks,
        tables=tables,
        metadata={"dataset": dataset}
    )


def run_test(
    sample: Dict[str, Any],
    engine: ReasoningEngine,
    dataset: str,
) -> Dict[str, Any]:
    """Run a single sample through the engine."""
    question = sample.get("question", "")
    if isinstance(question, dict):
        question = question.get("question", "")

    evidence = format_evidence(sample, dataset)

    request = StructuredRequest(
        raw_text=f"Task: F1 - Financial Ground-Truth Reasoning\n"
                 f"Use tables and text to compute numeric answers with citations.\n\n"
                 f"Evidence Text:\n" + "\n".join(evidence.text_blocks[:3]) + "\n\n"
                 f"Question: {question}",
        requested_operations=["calculation"],
    )

    contract = EvidenceContract(
        description="Financial tables and text evidence",
    )

    start_time = time.time()
    try:
        result = engine.run(request, contract, evidence)
        latency_ms = (time.time() - start_time) * 1000
        return {
            "answer": result.answer,
            "latency_ms": latency_ms,
            "error": None
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "answer": None,
            "latency_ms": latency_ms,
            "error": str(e)
        }


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison."""
    if not answer:
        return ""
    answer = str(answer).strip().lower()
    answer = answer.replace(",", "").replace("$", "").replace("%", "").replace(" ", "")
    return answer


def compare_answers(predicted: str, gold: str, tolerance: float = 0.05) -> bool:
    """Compare predicted and gold answers with tolerance."""
    pred_norm = normalize_answer(predicted)
    gold_norm = normalize_answer(gold)

    if pred_norm == gold_norm:
        return True

    try:
        # Extract numbers
        import re
        pred_match = re.search(r'-?[\d.]+', pred_norm)
        gold_match = re.search(r'-?[\d.]+', gold_norm)

        if pred_match and gold_match:
            pred_val = float(pred_match.group())
            gold_val = float(gold_match.group())

            if gold_val == 0:
                return abs(pred_val) < 0.01

            relative_error = abs(pred_val - gold_val) / abs(gold_val)
            return relative_error <= tolerance
    except:
        pass

    return False


def main():
    print("=" * 70)
    print("Testing New FinBound Architecture on Failed Samples")
    print("=" * 70)

    # Load failed samples
    failed_samples = load_failed_samples()
    print(f"\nLoaded {len(failed_samples)} failed samples")

    # Initialize engines
    print("\nInitializing engines...")
    engine_normal = ReasoningEngine(
        model="gpt-4o",
        use_quantlib=True,
        low_latency_mode=False,
        enable_verification_pass=True,
        enable_table_extraction=True,
    )

    engine_fast = ReasoningEngine(
        model="gpt-4o",
        use_quantlib=True,
        low_latency_mode=True,
        enable_verification_pass=True,
        enable_table_extraction=True,
    )

    # Results storage
    results_normal = []
    results_fast = []

    # Test each sample
    for i, failed in enumerate(failed_samples[:10]):  # Test first 10
        sample_id = failed["sample_id"]
        dataset = failed["dataset"]
        gold_answer = failed["gold_answer"]
        old_predicted = failed["predicted_answer"]
        old_latency = failed["latency_ms"]
        question = failed["question"]

        print(f"\n[{i+1}/10] {sample_id}")
        print(f"  Q: {question[:60]}...")
        print(f"  Gold: {gold_answer}")
        print(f"  Old: {old_predicted} ({old_latency:.0f}ms)")

        # Load full sample evidence
        full_sample = load_sample_evidence(sample_id, dataset)
        if not full_sample:
            print(f"  SKIP: Could not load sample evidence")
            continue

        # Inject question if needed
        if dataset == "finqa":
            full_sample["question"] = question
        elif dataset == "tatqa" and "question" not in full_sample:
            full_sample["question"] = question

        # Run with normal mode
        print(f"  Testing normal mode...", end=" ", flush=True)
        result_normal = run_test(full_sample, engine_normal, dataset)
        is_correct_normal = compare_answers(result_normal["answer"] or "", gold_answer)
        print(f"{result_normal['answer']} ({result_normal['latency_ms']:.0f}ms) {'✓' if is_correct_normal else '✗'}")

        results_normal.append({
            "sample_id": sample_id,
            "gold": gold_answer,
            "old_predicted": old_predicted,
            "old_latency_ms": old_latency,
            "new_predicted": result_normal["answer"],
            "new_latency_ms": result_normal["latency_ms"],
            "is_correct": is_correct_normal,
        })

        # Run with low latency mode
        print(f"  Testing low latency mode...", end=" ", flush=True)
        result_fast = run_test(full_sample, engine_fast, dataset)
        is_correct_fast = compare_answers(result_fast["answer"] or "", gold_answer)
        print(f"{result_fast['answer']} ({result_fast['latency_ms']:.0f}ms) {'✓' if is_correct_fast else '✗'}")

        results_fast.append({
            "sample_id": sample_id,
            "gold": gold_answer,
            "predicted": result_fast["answer"],
            "latency_ms": result_fast["latency_ms"],
            "is_correct": is_correct_fast,
        })

    # Summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    # Normal mode
    correct_normal = sum(1 for r in results_normal if r["is_correct"])
    avg_latency_normal = sum(r["new_latency_ms"] for r in results_normal) / len(results_normal) if results_normal else 0
    avg_old_latency = sum(r["old_latency_ms"] for r in results_normal) / len(results_normal) if results_normal else 0

    # Low latency mode
    correct_fast = sum(1 for r in results_fast if r["is_correct"])
    avg_latency_fast = sum(r["latency_ms"] for r in results_fast) / len(results_fast) if results_fast else 0

    print(f"\nOLD Architecture (baseline):")
    print(f"  Accuracy: 5/22 (22.7%)")  # From original data
    print(f"  Avg Latency: {avg_old_latency:.0f}ms")

    print(f"\nNEW Architecture (normal mode, QuantLib):")
    print(f"  Accuracy: {correct_normal}/{len(results_normal)} ({100*correct_normal/len(results_normal):.1f}%)")
    print(f"  Avg Latency: {avg_latency_normal:.0f}ms")
    print(f"  Latency Change: {100*(avg_latency_normal-avg_old_latency)/avg_old_latency:+.1f}%")

    print(f"\nNEW Architecture (low latency mode, QuantLib):")
    print(f"  Accuracy: {correct_fast}/{len(results_fast)} ({100*correct_fast/len(results_fast):.1f}%)")
    print(f"  Avg Latency: {avg_latency_fast:.0f}ms")
    print(f"  Latency Change: {100*(avg_latency_fast-avg_old_latency)/avg_old_latency:+.1f}%")

    # Save results
    output_dir = Path(__file__).parent.parent / "experiments/architecture_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with open(output_dir / f"normal_mode_{timestamp}.json", "w") as f:
        json.dump(results_normal, f, indent=2)

    with open(output_dir / f"low_latency_{timestamp}.json", "w") as f:
        json.dump(results_fast, f, indent=2)

    summary = {
        "timestamp": timestamp,
        "samples_tested": len(results_normal),
        "old_architecture": {
            "accuracy": "22.7%",
            "avg_latency_ms": round(avg_old_latency, 0)
        },
        "new_normal": {
            "accuracy": f"{100*correct_normal/len(results_normal):.1f}%",
            "correct": correct_normal,
            "total": len(results_normal),
            "avg_latency_ms": round(avg_latency_normal, 0)
        },
        "new_low_latency": {
            "accuracy": f"{100*correct_fast/len(results_fast):.1f}%",
            "correct": correct_fast,
            "total": len(results_fast),
            "avg_latency_ms": round(avg_latency_fast, 0)
        }
    }

    with open(output_dir / f"summary_{timestamp}.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()
