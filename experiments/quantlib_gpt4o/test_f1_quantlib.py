#!/usr/bin/env python3
"""
Test GPT-4o + QuantLib on the F1 dataset.

This script runs the QuantLib-powered GPT-4o approach on FinQA samples
and compares results with the gold answers.
"""

import json
import sys
import time
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from quantlib_engine import QuantLibEngine, QUANTLIB_TOOLS, execute_tool


# Extended tools for general financial calculations (add, subtract, multiply, divide)
BASIC_CALC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "subtract",
            "description": "Subtract b from a (a - b)",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number (to subtract)"}
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "multiply",
            "description": "Multiply two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "divide",
            "description": "Divide a by b (a / b)",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "Numerator"},
                    "b": {"type": "number", "description": "Denominator"}
                },
                "required": ["a", "b"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "percentage_change",
            "description": "Calculate percentage change from old to new value: ((new - old) / old) * 100",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_value": {"type": "number", "description": "Old/base value"},
                    "new_value": {"type": "number", "description": "New value"}
                },
                "required": ["old_value", "new_value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ratio",
            "description": "Calculate ratio as percentage: (part / whole) * 100",
            "parameters": {
                "type": "object",
                "properties": {
                    "part": {"type": "number", "description": "Part value"},
                    "whole": {"type": "number", "description": "Whole/total value"}
                },
                "required": ["part", "whole"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "average",
            "description": "Calculate average of a list of numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "values": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "List of numbers to average"
                    }
                },
                "required": ["values"]
            }
        }
    }
]

# Combine all tools
ALL_TOOLS = BASIC_CALC_TOOLS + QUANTLIB_TOOLS


def execute_basic_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute basic calculation tools."""
    if tool_name == "add":
        return round(arguments["a"] + arguments["b"], 6)
    elif tool_name == "subtract":
        return round(arguments["a"] - arguments["b"], 6)
    elif tool_name == "multiply":
        return round(arguments["a"] * arguments["b"], 6)
    elif tool_name == "divide":
        if arguments["b"] == 0:
            return "Error: Division by zero"
        return round(arguments["a"] / arguments["b"], 6)
    elif tool_name == "percentage_change":
        old = arguments["old_value"]
        new = arguments["new_value"]
        if old == 0:
            return "Error: Cannot calculate percentage change from zero"
        return round(((new - old) / old) * 100, 4)
    elif tool_name == "ratio":
        part = arguments["part"]
        whole = arguments["whole"]
        if whole == 0:
            return "Error: Cannot calculate ratio with zero denominator"
        return round((part / whole) * 100, 4)
    elif tool_name == "average":
        values = arguments["values"]
        if not values:
            return "Error: Cannot average empty list"
        return round(sum(values) / len(values), 4)
    else:
        return None


def execute_any_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Execute any tool (basic or QuantLib)."""
    # Try basic tools first
    result = execute_basic_tool(tool_name, arguments)
    if result is not None:
        return result

    # Fall back to QuantLib tools
    return execute_tool(tool_name, arguments)


SYSTEM_PROMPT = """You are a financial analyst assistant that answers questions about financial data from tables and text.

You have access to calculation tools. USE THEM for all numerical computations - do not calculate in your head.

When given a question and evidence (tables/text):
1. Identify the relevant numbers from the evidence
2. Determine what calculation is needed
3. Use the appropriate tool(s) to compute the answer
4. Return ONLY the final numerical answer

Important:
- Extract exact values from the tables/text provided
- Use the calculation tools for ALL math operations
- For percentage changes: use percentage_change(old_value, new_value)
- For ratios/proportions: use ratio(part, whole) or divide(a, b)
- For averages: use average([list of values])
- Return the answer as a number (with % sign if it's a percentage)
- Be precise - use the exact values from the evidence
"""


def format_evidence(sample: Dict[str, Any]) -> str:
    """Format the evidence (table + text) for the prompt."""
    parts = []

    # Pre-text
    if "pre_text" in sample and sample["pre_text"]:
        parts.append("Context:")
        for line in sample["pre_text"]:
            parts.append(f"  {line}")
        parts.append("")

    # Table
    if "table" in sample and sample["table"]:
        parts.append("Table:")
        for row in sample["table"]:
            parts.append(f"  {' | '.join(str(cell) for cell in row)}")
        parts.append("")

    # Post-text
    if "post_text" in sample and sample["post_text"]:
        parts.append("Additional context:")
        for line in sample["post_text"][:5]:  # Limit post-text
            parts.append(f"  {line}")

    return "\n".join(parts)


def run_quantlib_gpt4o(
    question: str,
    evidence: str,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Run a single question through GPT-4o with QuantLib tools.

    Returns:
        Dict with answer, tool_calls, and latency
    """
    client = OpenAI()

    user_prompt = f"""Evidence:
{evidence}

Question: {question}

Use the calculation tools to compute the answer. Return ONLY the final numerical answer."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    tool_calls_made = []
    start_time = time.time()

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=ALL_TOOLS,
        tool_choice="auto",
        temperature=0
    )

    assistant_message = response.choices[0].message

    # Handle tool calls
    max_iterations = 10
    iteration = 0

    while assistant_message.tool_calls and iteration < max_iterations:
        iteration += 1

        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })

        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            tool_calls_made.append({
                "function": function_name,
                "arguments": arguments
            })

            try:
                result = execute_any_tool(function_name, arguments)
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps(result) if not isinstance(result, str) else result
                })
                tool_calls_made[-1]["result"] = result
            except Exception as e:
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": f"Error: {str(e)}"
                })
                tool_calls_made[-1]["error"] = str(e)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
            temperature=0
        )

        assistant_message = response.choices[0].message

    latency_ms = (time.time() - start_time) * 1000

    return {
        "answer": assistant_message.content,
        "tool_calls": tool_calls_made,
        "latency_ms": latency_ms
    }


def normalize_answer(answer: str) -> str:
    """Normalize answer for comparison."""
    if not answer:
        return ""

    # Remove common formatting
    answer = answer.strip()
    answer = answer.replace(",", "")
    answer = answer.replace("$", "")
    answer = answer.replace(" ", "")

    # Extract number from text
    match = re.search(r'-?\d+\.?\d*', answer)
    if match:
        return match.group()

    return answer


def compare_answers(predicted: str, gold: str, tolerance: float = 0.05) -> bool:
    """Compare predicted and gold answers with tolerance."""
    pred_norm = normalize_answer(predicted)
    gold_norm = normalize_answer(gold)

    # Exact match
    if pred_norm == gold_norm:
        return True

    # Numeric comparison with tolerance
    try:
        pred_val = float(pred_norm)
        gold_val = float(gold_norm)

        if gold_val == 0:
            return abs(pred_val) < 0.01

        relative_error = abs(pred_val - gold_val) / abs(gold_val)
        return relative_error <= tolerance
    except ValueError:
        return False


def load_f1_samples(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load F1 samples from the curated dataset."""
    samples_path = Path(__file__).parent.parent.parent / "data/curated_samples/F1/finqa_samples.json"

    if not samples_path.exists():
        # Fall back to loading from raw FinQA
        raw_path = Path(__file__).parent.parent.parent / "data/raw/FinQA/dataset/dev.json"
        with open(raw_path) as f:
            all_samples = json.load(f)

        # Take first N samples
        samples = all_samples[:limit] if limit else all_samples
        return samples

    with open(samples_path) as f:
        samples = json.load(f)

    # Load full sample data from raw FinQA
    raw_path = Path(__file__).parent.parent.parent / "data/raw/FinQA/dataset/dev.json"
    with open(raw_path) as f:
        raw_samples = json.load(f)

    raw_by_id = {s["id"]: s for s in raw_samples}

    # Merge curated samples with full data
    full_samples = []
    for s in samples:
        sample_id = s["id"]
        if sample_id in raw_by_id:
            full_sample = raw_by_id[sample_id].copy()
            full_sample["gold_answer"] = s["answer"]
            full_samples.append(full_sample)

    if limit:
        full_samples = full_samples[:limit]

    return full_samples


def run_evaluation(
    samples: List[Dict[str, Any]],
    model: str = "gpt-4o",
    output_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Run evaluation on samples.

    Returns:
        Dict with results and metrics
    """
    results = []
    correct = 0
    total = 0

    for i, sample in enumerate(samples):
        sample_id = sample.get("id", f"sample_{i}")
        question = sample.get("qa", {}).get("question", sample.get("question", ""))
        gold_answer = sample.get("gold_answer", sample.get("qa", {}).get("answer", ""))

        print(f"\n[{i+1}/{len(samples)}] {sample_id}")
        print(f"  Q: {question[:80]}...")

        evidence = format_evidence(sample)

        try:
            result = run_quantlib_gpt4o(question, evidence, model)
            predicted = result["answer"] or ""

            is_correct = compare_answers(predicted, gold_answer)

            if is_correct:
                correct += 1
            total += 1

            print(f"  Predicted: {predicted}")
            print(f"  Gold: {gold_answer}")
            print(f"  Correct: {is_correct}")
            print(f"  Tool calls: {len(result['tool_calls'])}")

            results.append({
                "sample_id": sample_id,
                "question": question,
                "predicted_answer": predicted,
                "gold_answer": gold_answer,
                "is_correct": is_correct,
                "tool_calls": result["tool_calls"],
                "latency_ms": result["latency_ms"]
            })

        except Exception as e:
            print(f"  Error: {str(e)}")
            total += 1
            results.append({
                "sample_id": sample_id,
                "question": question,
                "predicted_answer": "",
                "gold_answer": gold_answer,
                "is_correct": False,
                "error": str(e)
            })

    accuracy = correct / total if total > 0 else 0

    metrics = {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "model": model,
        "timestamp": datetime.now().isoformat()
    }

    print(f"\n{'='*60}")
    print(f"RESULTS: {correct}/{total} correct ({accuracy*100:.1f}%)")
    print(f"{'='*60}")

    # Save results if output_dir specified
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(output_dir / "results.json", "w") as f:
            json.dump(results, f, indent=2)

        with open(output_dir / "metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

        print(f"Results saved to: {output_dir}")

    return {"results": results, "metrics": metrics}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test GPT-4o + QuantLib on F1 dataset")
    parser.add_argument("--limit", type=int, default=10, help="Number of samples to test")
    parser.add_argument("--model", type=str, default="gpt-4o", help="Model to use")
    parser.add_argument("--output", type=str, default=None, help="Output directory")

    args = parser.parse_args()

    print("=== GPT-4o + QuantLib F1 Evaluation ===\n")

    # Load samples
    print(f"Loading F1 samples (limit={args.limit})...")
    samples = load_f1_samples(limit=args.limit)
    print(f"Loaded {len(samples)} samples\n")

    # Set output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / f"results_{timestamp}"

    # Run evaluation
    run_evaluation(samples, model=args.model, output_dir=output_dir)
