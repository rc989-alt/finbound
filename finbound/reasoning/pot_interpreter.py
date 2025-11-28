"""
Program-of-Thoughts (PoT) Interpreter for Multi-Step Financial Calculations.

This module provides a safe DSL-based interpreter that executes step-by-step
computation programs using QuantLibCalculator. It's designed for complex
multi-step questions where LLM reasoning alone tends to fail.

Key features:
- Restricted op set (no arbitrary code execution)
- Full audit trail for each step
- Sign-aware operations
- Integration with existing QuantLibCalculator

Usage:
    from finbound.reasoning.pot_interpreter import PoTInterpreter, PoTProgram

    program = PoTProgram.from_dict({
        "steps": [
            {"id": "step1", "op": "average", "inputs": {"values": [4411, 4044]}},
            {"id": "step2", "op": "average", "inputs": {"values": [3680, 3200]}},
            {"id": "step3", "op": "subtract", "inputs": {"a": "$step1", "b": "$step2"}}
        ],
        "final_step": "step3"
    })

    interpreter = PoTInterpreter()
    result = interpreter.execute(program, values_from_evidence)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..tools.quantlib_calculator import QuantLibCalculator, CalculationResult, get_calculator


logger = logging.getLogger(__name__)


# Allowed operations (whitelist for safety)
ALLOWED_OPS = {
    # Basic arithmetic
    "add", "subtract", "multiply", "divide",
    # Percentage operations
    "percentage_change", "percentage_of_total",
    # Aggregations
    "average", "sum", "total",
    # Financial operations (via QuantLib)
    "present_value", "future_value", "npv", "irr",
    # Special operations
    "negate",  # Flip sign: a -> -a
    "abs",     # Absolute value
}


@dataclass
class PoTStep:
    """A single step in a Program-of-Thoughts computation."""
    id: str
    op: str
    inputs: Dict[str, Any]
    from_steps: List[str] = field(default_factory=list)  # References like "$step1"
    description: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PoTStep":
        """Parse a step from JSON/dict format."""
        step_id = data.get("id", data.get("step_id", ""))
        op = data.get("op", data.get("operation", ""))
        inputs = data.get("inputs", {})
        description = data.get("description")

        # Extract step references from inputs
        from_steps = []
        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith("$"):
                from_steps.append(value[1:])  # Remove $ prefix
            elif isinstance(value, list):
                for v in value:
                    if isinstance(v, str) and v.startswith("$"):
                        from_steps.append(v[1:])

        return cls(
            id=step_id,
            op=op.lower(),
            inputs=inputs,
            from_steps=from_steps,
            description=description,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "op": self.op,
            "inputs": self.inputs,
            "from_steps": self.from_steps,
            "description": self.description,
        }


@dataclass
class PoTProgram:
    """A complete Program-of-Thoughts computation program."""
    steps: List[PoTStep]
    final_step: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PoTProgram":
        """Parse a program from JSON/dict format."""
        steps_data = data.get("steps", data.get("computation_steps", []))
        steps = [PoTStep.from_dict(s) for s in steps_data]

        final_step = data.get("final_step", data.get("result_step", ""))
        if not final_step and steps:
            final_step = steps[-1].id  # Default to last step

        metadata = data.get("metadata", {})

        return cls(steps=steps, final_step=final_step, metadata=metadata)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "final_step": self.final_step,
            "metadata": self.metadata,
        }

    def validate(self) -> List[str]:
        """Validate the program structure. Returns list of errors (empty if valid)."""
        errors = []

        if not self.steps:
            errors.append("Program has no steps")
            return errors

        step_ids = {s.id for s in self.steps}

        # Check final step exists
        if self.final_step not in step_ids:
            errors.append(f"Final step '{self.final_step}' not found in steps")

        # Check all ops are allowed
        for step in self.steps:
            if step.op not in ALLOWED_OPS:
                errors.append(f"Step '{step.id}': unknown operation '{step.op}'")

            # Check step references exist
            for ref in step.from_steps:
                if ref not in step_ids:
                    errors.append(f"Step '{step.id}': references unknown step '{ref}'")

        # Check for cycles (simple check: referenced steps must come before)
        seen = set()
        for step in self.steps:
            for ref in step.from_steps:
                if ref not in seen:
                    # Reference to a later step - could be a cycle
                    # This is a simple check; full cycle detection would need DFS
                    pass  # Allow forward references for now
            seen.add(step.id)

        return errors


@dataclass
class PoTExecutionResult:
    """Result of executing a PoT program."""
    success: bool
    final_value: Optional[float]
    step_results: Dict[str, CalculationResult]
    audit_trail: List[Dict[str, Any]]
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "final_value": self.final_value,
            "step_results": {k: v.to_dict() for k, v in self.step_results.items()},
            "audit_trail": self.audit_trail,
            "error_message": self.error_message,
        }


class PoTInterpreter:
    """
    Interpreter for Program-of-Thoughts (PoT) computation programs.

    Executes a sequence of calculation steps using QuantLibCalculator,
    with full audit trail for verification.
    """

    def __init__(self, calculator: Optional[QuantLibCalculator] = None):
        self._calculator = calculator or get_calculator()
        self._logger = logging.getLogger(__name__)

    def execute(
        self,
        program: PoTProgram,
        values_from_evidence: Optional[Dict[str, float]] = None,
    ) -> PoTExecutionResult:
        """
        Execute a PoT program.

        Args:
            program: The program to execute
            values_from_evidence: Optional dict mapping labels to values
                                  (used to resolve $evidence.label references)

        Returns:
            PoTExecutionResult with final value and full audit trail
        """
        values_from_evidence = values_from_evidence or {}

        # Validate program
        errors = program.validate()
        if errors:
            return PoTExecutionResult(
                success=False,
                final_value=None,
                step_results={},
                audit_trail=[],
                error_message=f"Invalid program: {'; '.join(errors)}",
            )

        step_results: Dict[str, CalculationResult] = {}
        audit_trail: List[Dict[str, Any]] = []

        for step in program.steps:
            try:
                result = self._execute_step(step, step_results, values_from_evidence)
                step_results[step.id] = result

                audit_trail.append({
                    "step_id": step.id,
                    "operation": step.op,
                    "inputs_raw": step.inputs,
                    "inputs_resolved": self._resolve_inputs(step.inputs, step_results, values_from_evidence),
                    "result": result.value,
                    "engine": result.engine,
                    "formula": result.formula,
                })

                self._logger.debug(
                    "PoT step %s: %s = %s", step.id, step.op, result.value
                )

            except Exception as e:
                self._logger.error("PoT step %s failed: %s", step.id, e)
                return PoTExecutionResult(
                    success=False,
                    final_value=None,
                    step_results=step_results,
                    audit_trail=audit_trail,
                    error_message=f"Step '{step.id}' failed: {str(e)}",
                )

        # Get final result
        if program.final_step not in step_results:
            return PoTExecutionResult(
                success=False,
                final_value=None,
                step_results=step_results,
                audit_trail=audit_trail,
                error_message=f"Final step '{program.final_step}' not executed",
            )

        final_result = step_results[program.final_step]

        return PoTExecutionResult(
            success=True,
            final_value=final_result.value,
            step_results=step_results,
            audit_trail=audit_trail,
        )

    def _execute_step(
        self,
        step: PoTStep,
        step_results: Dict[str, CalculationResult],
        values_from_evidence: Dict[str, float],
    ) -> CalculationResult:
        """Execute a single step."""
        resolved_inputs = self._resolve_inputs(step.inputs, step_results, values_from_evidence)

        # Handle special operations not in QuantLibCalculator
        if step.op == "negate":
            value = resolved_inputs.get("a", resolved_inputs.get("value", 0))
            return CalculationResult(
                value=-value,
                operation="negate",
                inputs={"a": value},
                engine="basic",
                formula="-a",
            )

        if step.op == "abs":
            value = resolved_inputs.get("a", resolved_inputs.get("value", 0))
            return CalculationResult(
                value=abs(value),
                operation="abs",
                inputs={"a": value},
                engine="basic",
                formula="|a|",
            )

        # Use QuantLibCalculator for standard operations
        return self._calculator.execute(step.op, **resolved_inputs)

    def _resolve_inputs(
        self,
        inputs: Dict[str, Any],
        step_results: Dict[str, CalculationResult],
        values_from_evidence: Dict[str, float],
    ) -> Dict[str, Any]:
        """Resolve step references and evidence references in inputs."""
        resolved = {}

        for key, value in inputs.items():
            resolved[key] = self._resolve_value(value, step_results, values_from_evidence)

        return resolved

    def _resolve_value(
        self,
        value: Any,
        step_results: Dict[str, CalculationResult],
        values_from_evidence: Dict[str, float],
    ) -> Any:
        """Resolve a single value (which may be a reference)."""
        if isinstance(value, str):
            # Step reference: $step1
            if value.startswith("$") and not value.startswith("$evidence."):
                step_id = value[1:]
                if step_id in step_results:
                    return step_results[step_id].value
                raise ValueError(f"Unknown step reference: {value}")

            # Evidence reference: $evidence.revenue_2019
            if value.startswith("$evidence."):
                label = value[10:]  # Remove "$evidence."
                if label in values_from_evidence:
                    return values_from_evidence[label]
                # Try fuzzy matching
                for ev_label, ev_value in values_from_evidence.items():
                    if label.lower() in ev_label.lower():
                        return ev_value
                raise ValueError(f"Unknown evidence reference: {value}")

            # Try to parse as number
            try:
                return float(value.replace(",", "").replace("$", "").replace("%", ""))
            except ValueError:
                return value

        elif isinstance(value, list):
            return [self._resolve_value(v, step_results, values_from_evidence) for v in value]

        return value


def create_pot_program_for_sign_sensitive(
    operation: str,
    old_value: float,
    new_value: float,
    question_asks_decrease: bool = False,
) -> PoTProgram:
    """
    Create a PoT program for sign-sensitive calculations (changes, differences).

    This helper ensures correct sign handling for questions like:
    - "What was the change in X from 2018 to 2019?" (should be negative if X decreased)
    - "By how much did X decrease?" (expects positive value for decrease amount)

    Args:
        operation: "percentage_change" or "absolute_change"
        old_value: Earlier period value
        new_value: Later period value
        question_asks_decrease: If True, return abs value (question expects positive)
    """
    if operation == "percentage_change":
        steps = [
            PoTStep(
                id="change",
                op="percentage_change",
                inputs={"old_value": old_value, "new_value": new_value},
                description=f"Calculate percentage change: ({new_value} - {old_value}) / {old_value} * 100",
            )
        ]
    else:  # absolute_change
        steps = [
            PoTStep(
                id="change",
                op="subtract",
                inputs={"a": new_value, "b": old_value},
                description=f"Calculate absolute change: {new_value} - {old_value}",
            )
        ]

    if question_asks_decrease:
        # If question asks "how much did X decrease", we may need to flip sign
        steps.append(PoTStep(
            id="final",
            op="negate",
            inputs={"a": "$change"},
            description="Flip sign for 'decrease' phrasing",
        ))
        final_step = "final"
    else:
        final_step = "change"

    return PoTProgram(
        steps=steps,
        final_step=final_step,
        metadata={"type": "sign_sensitive", "operation": operation},
    )


def create_pot_program_for_temporal_average(
    values_by_year: Dict[int, float],
    target_year: int,
) -> PoTProgram:
    """
    Create a PoT program for temporal average calculations.

    In TAT-QA convention, "2019 average X" = (X_2019 + X_2018) / 2

    Args:
        values_by_year: Dict mapping years to values
        target_year: The target year (e.g., 2019 for "2019 average")
    """
    prior_year = target_year - 1

    if target_year not in values_by_year or prior_year not in values_by_year:
        raise ValueError(f"Need values for both {target_year} and {prior_year}")

    current_val = values_by_year[target_year]
    prior_val = values_by_year[prior_year]

    return PoTProgram(
        steps=[
            PoTStep(
                id="avg",
                op="average",
                inputs={"values": [current_val, prior_val]},
                description=f"Calculate {target_year} average: ({current_val} + {prior_val}) / 2",
            )
        ],
        final_step="avg",
        metadata={"type": "temporal_average", "target_year": target_year},
    )


def create_pot_program_for_change_in_averages(
    values_by_year: Dict[int, float],
    year1: int,
    year2: int,
) -> PoTProgram:
    """
    Create a PoT program for "change between YEAR1 average and YEAR2 average".

    Args:
        values_by_year: Dict mapping years to values
        year1: Earlier year
        year2: Later year
    """
    # Need 4 values: year1, year1-1, year2, year2-1
    required_years = [year1, year1-1, year2, year2-1]
    for y in required_years:
        if y not in values_by_year:
            raise ValueError(f"Need value for year {y}")

    return PoTProgram(
        steps=[
            PoTStep(
                id="avg1",
                op="average",
                inputs={"values": [values_by_year[year1], values_by_year[year1-1]]},
                description=f"Calculate {year1} average",
            ),
            PoTStep(
                id="avg2",
                op="average",
                inputs={"values": [values_by_year[year2], values_by_year[year2-1]]},
                description=f"Calculate {year2} average",
            ),
            PoTStep(
                id="change",
                op="subtract",
                inputs={"a": "$avg2", "b": "$avg1"},
                description=f"Calculate change: {year2} avg - {year1} avg",
            ),
        ],
        final_step="change",
        metadata={"type": "change_in_averages", "year1": year1, "year2": year2},
    )
