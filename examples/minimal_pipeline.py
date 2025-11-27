import os

from dotenv import load_dotenv

from finbound import FinBound
from finbound.types import EvidenceContext


def main() -> None:
    # Load environment variables from .env if present
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Please set it in your environment or .env file."
        )

    fb = FinBound()

    user_request = (
        "What was the year-over-year change in interest expense last quarter, "
        "and explain in simple terms what it means for the company?"
    )

    print("▶ Running FinBound minimal pipeline...")
    print(f"User request: {user_request}\n")

    context = EvidenceContext(
        text_blocks=[
            "Company guidance states that interest expense increased by $3M year-over-year.",
            "Management attributes the change to higher variable-rate debt tied to LIBOR.",
        ],
        metadata={"source": "Sample investor update"},
    )

    result = fb.run(user_request, evidence_context=context)

    print("Answer:")
    print(result.answer)
    print("\nVerified:", result.verified)
    print("Citations:", result.citations)
    print("\nReasoning trace:")
    print(result.reasoning)

    if not result.verified:
        print("\nVerification issues:")
        for issue in result.verification_result.issues:
            print(f"- {issue}")


if __name__ == "__main__":
    main()
