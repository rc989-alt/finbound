from __future__ import annotations

from typing import Iterable, List

from ..types import PolicyVerdict, StructuredRequest
from .validators import BaseValidator, DomainValidator, RegulatoryValidator, ScenarioValidator


class PolicyEngine:
    """
    Rule-based policy engine backed by pluggable validators.
    """

    def __init__(self, validators: Iterable[BaseValidator] | None = None) -> None:
        self._validators: List[BaseValidator] = list(
            validators
            if validators is not None
            else [
                RegulatoryValidator(),
                ScenarioValidator(),
                DomainValidator(),
            ]
        )

    def check_compliance(self, request: StructuredRequest) -> PolicyVerdict:
        reasons: List[str] = []
        for validator in self._validators:
            reasons.extend(validator.validate(request))
        approved = not reasons
        return PolicyVerdict(approved=approved, reasons=reasons)
