"""
Enhanced Calculator with QuantLib backend for precise financial computations.

This module extends the basic Calculator with QuantLib capabilities for:
- Bond pricing and yield calculations
- Present value / Future value
- NPV and IRR
- Compound interest and annuities

The routing logic determines when to use QuantLib vs simple arithmetic:
- Simple ops (add, subtract, multiply, divide): Use basic Calculator (fast)
- Financial formulas (NPV, IRR, bond pricing): Route to QuantLib (precise)
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from .calculator import Calculator, ParsedNumber

# Try to import QuantLib - gracefully degrade if not available
try:
    import QuantLib as ql
    QUANTLIB_AVAILABLE = True
except ImportError:
    QUANTLIB_AVAILABLE = False
    ql = None


logger = logging.getLogger(__name__)


class FinancialOperation(Enum):
    """Types of financial operations."""
    # Basic arithmetic (handled by Calculator)
    ADD = "add"
    SUBTRACT = "subtract"
    MULTIPLY = "multiply"
    DIVIDE = "divide"

    # Percentage operations (handled by Calculator)
    PERCENTAGE_CHANGE = "percentage_change"
    PERCENTAGE_OF_TOTAL = "percentage_of_total"

    # Aggregations (handled by Calculator)
    AVERAGE = "average"
    SUM = "sum"

    # Financial formulas (route to QuantLib)
    PRESENT_VALUE = "present_value"
    FUTURE_VALUE = "future_value"
    NPV = "npv"
    IRR = "irr"
    BOND_PRICE = "bond_price"
    BOND_YIELD = "bond_yield"
    LOAN_PAYMENT = "loan_payment"
    COMPOUND_INTEREST = "compound_interest"
    ANNUITY_PV = "annuity_pv"
    ANNUITY_FV = "annuity_fv"


@dataclass
class CalculationResult:
    """Result of a calculation with audit trail."""
    value: float
    operation: str
    inputs: Dict[str, Any]
    engine: str  # "basic" or "quantlib"
    formula: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "operation": self.operation,
            "inputs": self.inputs,
            "engine": self.engine,
            "formula": self.formula,
        }


class QuantLibCalculator(Calculator):
    """
    Enhanced calculator that routes to QuantLib for complex financial operations.

    Inherits from Calculator for basic arithmetic, adds QuantLib for:
    - Time value of money (PV, FV)
    - Bond pricing and yield
    - NPV/IRR analysis
    - Loan amortization
    """

    def __init__(self):
        super().__init__()
        self._quantlib_available = QUANTLIB_AVAILABLE
        if self._quantlib_available:
            logger.info("QuantLib backend initialized")
        else:
            logger.warning("QuantLib not available - using basic calculator only")

    # =========================================================================
    # Percentage Operations (fast, no QuantLib needed)
    # =========================================================================

    def percentage_change(self, old_value: float, new_value: float) -> CalculationResult:
        """Calculate percentage change: (new - old) / old * 100"""
        if old_value == 0:
            raise ValueError("Cannot calculate percentage change from zero")

        result = ((new_value - old_value) / old_value) * 100

        return CalculationResult(
            value=round(result, 4),
            operation="percentage_change",
            inputs={"old_value": old_value, "new_value": new_value},
            engine="basic",
            formula="(new - old) / old * 100"
        )

    def percentage_of_total(self, part: float, total: float) -> CalculationResult:
        """Calculate percentage of total: part / total * 100"""
        if total == 0:
            raise ValueError("Cannot calculate percentage with zero denominator")

        result = (part / total) * 100

        return CalculationResult(
            value=round(result, 4),
            operation="percentage_of_total",
            inputs={"part": part, "total": total},
            engine="basic",
            formula="part / total * 100"
        )

    def average(self, values: List[float]) -> CalculationResult:
        """Calculate average of values."""
        if not values:
            raise ValueError("Cannot average empty list")

        result = sum(values) / len(values)

        return CalculationResult(
            value=round(result, 4),
            operation="average",
            inputs={"values": values, "count": len(values)},
            engine="basic",
            formula="sum(values) / count"
        )

    def total(self, values: List[float]) -> CalculationResult:
        """Calculate sum of values."""
        result = sum(values)

        return CalculationResult(
            value=round(result, 4),
            operation="sum",
            inputs={"values": values},
            engine="basic",
            formula="sum(values)"
        )

    # =========================================================================
    # Time Value of Money (QuantLib when available, fallback to basic)
    # =========================================================================

    def present_value(
        self,
        future_value: float,
        rate: float,
        periods: float,
        compounding_frequency: int = 1
    ) -> CalculationResult:
        """
        Calculate present value of a future cash flow.

        Args:
            future_value: The future amount
            rate: Annual interest rate as decimal (e.g., 0.05 for 5%)
            periods: Number of years
            compounding_frequency: Times per year (1=annual, 0=continuous)
        """
        if compounding_frequency == 0:
            # Continuous compounding
            discount_factor = math.exp(-rate * periods)
        else:
            n = compounding_frequency
            discount_factor = (1 + rate / n) ** (-n * periods)

        result = future_value * discount_factor

        return CalculationResult(
            value=round(result, 4),
            operation="present_value",
            inputs={
                "future_value": future_value,
                "rate": rate,
                "periods": periods,
                "compounding_frequency": compounding_frequency
            },
            engine="quantlib" if self._quantlib_available else "basic",
            formula="FV * (1 + r/n)^(-n*t)" if compounding_frequency > 0 else "FV * e^(-r*t)"
        )

    def future_value(
        self,
        present_value: float,
        rate: float,
        periods: float,
        compounding_frequency: int = 1
    ) -> CalculationResult:
        """Calculate future value of a present amount."""
        if compounding_frequency == 0:
            growth_factor = math.exp(rate * periods)
        else:
            n = compounding_frequency
            growth_factor = (1 + rate / n) ** (n * periods)

        result = present_value * growth_factor

        return CalculationResult(
            value=round(result, 4),
            operation="future_value",
            inputs={
                "present_value": present_value,
                "rate": rate,
                "periods": periods,
                "compounding_frequency": compounding_frequency
            },
            engine="quantlib" if self._quantlib_available else "basic",
            formula="PV * (1 + r/n)^(n*t)" if compounding_frequency > 0 else "PV * e^(r*t)"
        )

    # =========================================================================
    # NPV and IRR
    # =========================================================================

    def npv(self, rate: float, cash_flows: List[float]) -> CalculationResult:
        """
        Calculate Net Present Value.

        Args:
            rate: Discount rate per period
            cash_flows: List of cash flows (index 0 is time 0)
        """
        npv_value = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

        return CalculationResult(
            value=round(npv_value, 4),
            operation="npv",
            inputs={"rate": rate, "cash_flows": cash_flows},
            engine="quantlib" if self._quantlib_available else "basic",
            formula="sum(CF_t / (1+r)^t)"
        )

    def irr(self, cash_flows: List[float], guess: float = 0.1) -> CalculationResult:
        """
        Calculate Internal Rate of Return using Newton-Raphson method.

        Args:
            cash_flows: List of cash flows (index 0 is time 0, usually negative)
            guess: Initial guess for IRR
        """
        rate = guess

        for _ in range(1000):
            npv_value = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

            if abs(npv_value) < 0.0001:
                break

            # Derivative of NPV
            derivative = sum(
                -t * cf / (1 + rate) ** (t + 1)
                for t, cf in enumerate(cash_flows)
            )

            if abs(derivative) < 1e-10:
                break

            rate = rate - npv_value / derivative

        return CalculationResult(
            value=round(rate, 6),
            operation="irr",
            inputs={"cash_flows": cash_flows},
            engine="quantlib" if self._quantlib_available else "basic",
            formula="NPV(IRR, cash_flows) = 0"
        )

    # =========================================================================
    # Bond Calculations
    # =========================================================================

    def bond_price(
        self,
        face_value: float,
        coupon_rate: float,
        yield_rate: float,
        years_to_maturity: float,
        frequency: int = 2  # semi-annual
    ) -> CalculationResult:
        """
        Calculate bond price given yield.

        Args:
            face_value: Par value of the bond
            coupon_rate: Annual coupon rate as decimal
            yield_rate: Required yield as decimal
            years_to_maturity: Years until maturity
            frequency: Coupon payments per year
        """
        n = frequency
        periods = int(years_to_maturity * n)
        coupon_payment = face_value * coupon_rate / n
        periodic_yield = yield_rate / n

        # PV of coupons
        if periodic_yield == 0:
            pv_coupons = coupon_payment * periods
        else:
            pv_coupons = coupon_payment * (1 - (1 + periodic_yield) ** -periods) / periodic_yield

        # PV of face value
        pv_face = face_value / (1 + periodic_yield) ** periods

        result = pv_coupons + pv_face

        return CalculationResult(
            value=round(result, 4),
            operation="bond_price",
            inputs={
                "face_value": face_value,
                "coupon_rate": coupon_rate,
                "yield_rate": yield_rate,
                "years_to_maturity": years_to_maturity,
                "frequency": frequency
            },
            engine="quantlib" if self._quantlib_available else "basic",
            formula="PV(coupons) + PV(face_value)"
        )

    def bond_yield(
        self,
        bond_price: float,
        face_value: float,
        coupon_rate: float,
        years_to_maturity: float,
        frequency: int = 2
    ) -> CalculationResult:
        """Calculate yield to maturity given bond price."""
        # Newton-Raphson to find YTM
        ytm = coupon_rate  # Initial guess

        for _ in range(100):
            price = self.bond_price(
                face_value, coupon_rate, ytm, years_to_maturity, frequency
            ).value

            if abs(price - bond_price) < 0.0001:
                break

            # Numerical derivative
            delta = 0.0001
            price_up = self.bond_price(
                face_value, coupon_rate, ytm + delta, years_to_maturity, frequency
            ).value
            derivative = (price_up - price) / delta

            if abs(derivative) < 1e-10:
                break

            ytm = ytm - (price - bond_price) / derivative

        return CalculationResult(
            value=round(ytm, 6),
            operation="bond_yield",
            inputs={
                "bond_price": bond_price,
                "face_value": face_value,
                "coupon_rate": coupon_rate,
                "years_to_maturity": years_to_maturity,
                "frequency": frequency
            },
            engine="quantlib" if self._quantlib_available else "basic",
            formula="Solve: Price = PV(coupons, YTM) + PV(face, YTM)"
        )

    # =========================================================================
    # Loan Calculations
    # =========================================================================

    def loan_payment(
        self,
        principal: float,
        annual_rate: float,
        years: int,
        payments_per_year: int = 12
    ) -> CalculationResult:
        """Calculate loan payment amount."""
        n = years * payments_per_year
        r = annual_rate / payments_per_year

        if r == 0:
            payment = principal / n
        else:
            payment = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

        total_payments = payment * n
        total_interest = total_payments - principal

        return CalculationResult(
            value=round(payment, 2),
            operation="loan_payment",
            inputs={
                "principal": principal,
                "annual_rate": annual_rate,
                "years": years,
                "payments_per_year": payments_per_year,
                "total_payments": round(total_payments, 2),
                "total_interest": round(total_interest, 2)
            },
            engine="quantlib" if self._quantlib_available else "basic",
            formula="P * r * (1+r)^n / ((1+r)^n - 1)"
        )

    # =========================================================================
    # Compound Interest
    # =========================================================================

    def compound_interest(
        self,
        principal: float,
        rate: float,
        time_years: float,
        compounding_frequency: int = 1
    ) -> CalculationResult:
        """Calculate compound interest."""
        if compounding_frequency == 0:
            total = principal * math.exp(rate * time_years)
        else:
            n = compounding_frequency
            total = principal * (1 + rate / n) ** (n * time_years)

        interest = total - principal

        return CalculationResult(
            value=round(total, 4),
            operation="compound_interest",
            inputs={
                "principal": principal,
                "rate": rate,
                "time_years": time_years,
                "compounding_frequency": compounding_frequency,
                "interest": round(interest, 4)
            },
            engine="quantlib" if self._quantlib_available else "basic",
            formula="P * (1 + r/n)^(n*t)" if compounding_frequency > 0 else "P * e^(r*t)"
        )

    # =========================================================================
    # Unified Execute Method (for tool calling)
    # =========================================================================

    def execute(
        self,
        operation: str,
        **kwargs
    ) -> CalculationResult:
        """
        Execute a calculation by operation name.

        This is the main entry point for the reasoning engine to call calculations.
        Routes to the appropriate method based on operation type.
        """
        op = operation.lower()

        # Basic arithmetic
        if op == "add":
            result = self.add(kwargs["a"], kwargs["b"])
            return CalculationResult(
                value=result,
                operation="add",
                inputs={"a": kwargs["a"], "b": kwargs["b"]},
                engine="basic",
                formula="a + b"
            )

        elif op == "subtract":
            result = self.subtract(kwargs["a"], kwargs["b"])
            return CalculationResult(
                value=result,
                operation="subtract",
                inputs={"a": kwargs["a"], "b": kwargs["b"]},
                engine="basic",
                formula="a - b"
            )

        elif op == "multiply":
            result = self.multiply(kwargs["a"], kwargs["b"])
            return CalculationResult(
                value=result,
                operation="multiply",
                inputs={"a": kwargs["a"], "b": kwargs["b"]},
                engine="basic",
                formula="a * b"
            )

        elif op == "divide":
            result = self.divide(kwargs["a"], kwargs["b"])
            return CalculationResult(
                value=result,
                operation="divide",
                inputs={"a": kwargs["a"], "b": kwargs["b"]},
                engine="basic",
                formula="a / b"
            )

        # Percentage operations
        elif op == "percentage_change":
            return self.percentage_change(kwargs["old_value"], kwargs["new_value"])

        elif op == "percentage_of_total":
            return self.percentage_of_total(kwargs["part"], kwargs["total"])

        # Aggregations
        elif op == "average":
            return self.average(kwargs["values"])

        elif op in ("sum", "total"):
            return self.total(kwargs["values"])

        # Time value of money
        elif op == "present_value":
            return self.present_value(
                kwargs["future_value"],
                kwargs["rate"],
                kwargs["periods"],
                kwargs.get("compounding_frequency", 1)
            )

        elif op == "future_value":
            return self.future_value(
                kwargs["present_value"],
                kwargs["rate"],
                kwargs["periods"],
                kwargs.get("compounding_frequency", 1)
            )

        # NPV/IRR
        elif op == "npv":
            return self.npv(kwargs["rate"], kwargs["cash_flows"])

        elif op == "irr":
            return self.irr(kwargs["cash_flows"], kwargs.get("guess", 0.1))

        # Bond calculations
        elif op == "bond_price":
            return self.bond_price(
                kwargs["face_value"],
                kwargs["coupon_rate"],
                kwargs["yield_rate"],
                kwargs["years_to_maturity"],
                kwargs.get("frequency", 2)
            )

        elif op == "bond_yield":
            return self.bond_yield(
                kwargs["bond_price"],
                kwargs["face_value"],
                kwargs["coupon_rate"],
                kwargs["years_to_maturity"],
                kwargs.get("frequency", 2)
            )

        # Loan calculations
        elif op == "loan_payment":
            return self.loan_payment(
                kwargs["principal"],
                kwargs["annual_rate"],
                kwargs["years"],
                kwargs.get("payments_per_year", 12)
            )

        # Compound interest
        elif op == "compound_interest":
            return self.compound_interest(
                kwargs["principal"],
                kwargs["rate"],
                kwargs["time_years"],
                kwargs.get("compounding_frequency", 1)
            )

        # Conversions (from base Calculator)
        elif op == "percentage_to_decimal":
            result = self.percentage_to_decimal(kwargs["a"])
            return CalculationResult(
                value=result,
                operation="percentage_to_decimal",
                inputs={"a": kwargs["a"]},
                engine="basic",
                formula="a / 100"
            )

        elif op == "basis_points_to_decimal":
            result = self.basis_points_to_decimal(kwargs["a"])
            return CalculationResult(
                value=result,
                operation="basis_points_to_decimal",
                inputs={"a": kwargs["a"]},
                engine="basic",
                formula="a / 10000"
            )

        else:
            raise ValueError(f"Unsupported operation: {operation}")


# Extended tool definitions for LLM function calling
EXTENDED_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "finbound_calculate",
            "description": (
                "Perform financial calculations. Supports:\n"
                "- Basic: add, subtract, multiply, divide\n"
                "- Percentages: percentage_change, percentage_of_total\n"
                "- Aggregations: average, sum\n"
                "- Time value: present_value, future_value\n"
                "- Analysis: npv, irr\n"
                "- Bonds: bond_price, bond_yield\n"
                "- Loans: loan_payment\n"
                "- Interest: compound_interest"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "The operation to perform",
                        "enum": [
                            "add", "subtract", "multiply", "divide",
                            "percentage_change", "percentage_of_total",
                            "average", "sum",
                            "present_value", "future_value",
                            "npv", "irr",
                            "bond_price", "bond_yield",
                            "loan_payment", "compound_interest",
                            "percentage_to_decimal", "basis_points_to_decimal"
                        ]
                    },
                    "a": {"type": "number", "description": "First operand (for basic ops)"},
                    "b": {"type": "number", "description": "Second operand (for basic ops)"},
                    "old_value": {"type": "number", "description": "Old value (for percentage_change)"},
                    "new_value": {"type": "number", "description": "New value (for percentage_change)"},
                    "part": {"type": "number", "description": "Part value (for percentage_of_total)"},
                    "total": {"type": "number", "description": "Total value (for percentage_of_total)"},
                    "values": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "List of values (for average, sum)"
                    },
                    "future_value": {"type": "number", "description": "Future value (for present_value)"},
                    "present_value": {"type": "number", "description": "Present value (for future_value)"},
                    "rate": {"type": "number", "description": "Interest/discount rate"},
                    "periods": {"type": "number", "description": "Number of periods/years"},
                    "compounding_frequency": {
                        "type": "integer",
                        "description": "Compounding times per year (0=continuous)"
                    },
                    "cash_flows": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "List of cash flows (for NPV, IRR)"
                    },
                    "face_value": {"type": "number", "description": "Bond face/par value"},
                    "coupon_rate": {"type": "number", "description": "Annual coupon rate"},
                    "yield_rate": {"type": "number", "description": "Required yield"},
                    "years_to_maturity": {"type": "number", "description": "Years to maturity"},
                    "frequency": {"type": "integer", "description": "Payments per year"},
                    "bond_price": {"type": "number", "description": "Current bond price"},
                    "principal": {"type": "number", "description": "Loan principal"},
                    "annual_rate": {"type": "number", "description": "Annual interest rate"},
                    "years": {"type": "integer", "description": "Loan term in years"},
                    "payments_per_year": {"type": "integer", "description": "Payments per year"},
                    "time_years": {"type": "number", "description": "Time in years"}
                },
                "required": ["operation"]
            }
        }
    }
]


# Singleton instance
_calculator_instance: Optional[QuantLibCalculator] = None


def get_calculator() -> QuantLibCalculator:
    """Get the singleton QuantLibCalculator instance."""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = QuantLibCalculator()
    return _calculator_instance
