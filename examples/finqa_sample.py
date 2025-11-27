import os
import re
from textwrap import indent

from dotenv import load_dotenv

from finbound import FinBound
from finbound.data import FinQALoader
from finbound.types import EvidenceContext


def _extract_first_number(text: str) -> str | None:
    cleaned = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    return match.group(0)


def _build_evidence_context(sample) -> EvidenceContext:
    text_blocks = sample.context_snippets + sample.evidence_texts[:3]
    tables = sample.table[:4] if sample.table else []
    metadata = {"issuer": sample.issuer, "source_file": sample.filename}
    return EvidenceContext(text_blocks=text_blocks, tables=tables, metadata=metadata)


def main() -> None:
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Please set it in your environment or .env file."
        )

    sample = FinQALoader().load()
    evidence_context = _build_evidence_context(sample)

    fb = FinBound()

    user_request = (
        "Answer the financial question using the provided evidence. "
        "If numerical relationships (percentages, basis points, deltas) allow you to "
        "derive the answer with arithmetic, you must compute it and explain the steps.\n\n"
        f"Question: {sample.question}"
    )

    print("▶ Running FinBound on a FinQA sample...\n")
    print("FinQA sample ID:", sample.id)
    print("Issuer (from filename):", sample.issuer)
    print("FinQA gold answer:", sample.answer)
    print("\nUser request sent to FinBound:\n")
    print(indent(user_request, "  "))
    print("\nEvidence context provided to FinBound:\n")
    print(indent(evidence_context.as_prompt_section(), "  "))
    print("\n---\n")

    result = fb.run(user_request, evidence_context=evidence_context)

    print("Model answer:", result.answer)

    pred_num = _extract_first_number(result.answer)
    gold_num = _extract_first_number(sample.answer) or sample.answer.strip()

    if pred_num is not None:
        is_match = pred_num == gold_num
        print(f"\nNumeric check: model={pred_num}, gold={gold_num}, match={is_match}")
    else:
        print("\nNumeric check: no numeric value found in model answer.")

    print("Verified:", result.verified)
    print("Citations:", result.citations)
    print("\nReasoning trace:\n")
    print(indent(result.reasoning, "  "))

    if not result.verified:
        print("\nVerification issues:")
        for issue in result.verification_result.issues:
            print(f"- {issue}")


if __name__ == "__main__":
    main()
