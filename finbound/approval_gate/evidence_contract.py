from __future__ import annotations

from ..types import EvidenceContract, StructuredRequest


class EvidenceContractGenerator:
    """
    Minimal evidence contract generator.

    For now we simply require at least one citation in the explanation.
    """

    def generate(self, request: StructuredRequest) -> EvidenceContract:
        clauses = [
            "At least one grounded financial citation (table cell or paragraph) must support the answer."
        ]

        if request.metrics:
            metrics_str = ", ".join(request.metrics)
            clauses.append(f"Citations must explicitly reference the metrics: {metrics_str}.")

        if request.period:
            clauses.append(f"Evidence must fall within the period {request.period}.")

        if request.time_horizon:
            clauses.append(f"Reasoning must respect the {request.time_horizon} horizon stated in the request.")

        required_citations = max(1, len(request.metrics))

        description = " ".join(clauses)
        return EvidenceContract(description=description, required_citations=required_citations)
