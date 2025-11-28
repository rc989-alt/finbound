"""
QuantLib-powered financial calculation engine for GPT-4o integration.

This module provides precise financial calculations using QuantLib,
designed to be called by GPT-4o for accurate bond pricing, yield curves,
present value calculations, and other financial computations.
"""

from datetime import date
from typing import Optional, Union, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

import QuantLib as ql


class DayCountConvention(Enum):
    """Day count conventions for interest calculations."""
    ACTUAL_360 = "Actual/360"
    ACTUAL_365 = "Actual/365"
    ACTUAL_ACTUAL = "Actual/Actual"
    THIRTY_360 = "30/360"


class Frequency(Enum):
    """Payment frequency for bonds and swaps."""
    ANNUAL = 1
    SEMI_ANNUAL = 2
    QUARTERLY = 4
    MONTHLY = 12


@dataclass
class BondPricingResult:
    """Result of bond pricing calculation."""
    clean_price: float
    dirty_price: float
    accrued_interest: float
    yield_to_maturity: float
    duration: float
    modified_duration: float
    convexity: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "clean_price": round(self.clean_price, 4),
            "dirty_price": round(self.dirty_price, 4),
            "accrued_interest": round(self.accrued_interest, 4),
            "yield_to_maturity": round(self.yield_to_maturity, 6),
            "duration": round(self.duration, 4),
            "modified_duration": round(self.modified_duration, 4),
            "convexity": round(self.convexity, 4),
        }


@dataclass
class PresentValueResult:
    """Result of present value calculation."""
    present_value: float
    discount_factor: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "present_value": round(self.present_value, 4),
            "discount_factor": round(self.discount_factor, 6),
        }


class QuantLibEngine:
    """
    Financial calculation engine powered by QuantLib.

    Provides precise calculations for:
    - Bond pricing and analytics
    - Present value / Future value
    - Yield curve construction
    - Interest rate calculations
    - Option pricing (basic)
    """

    def __init__(self, evaluation_date: Optional[date] = None):
        """
        Initialize the QuantLib engine.

        Args:
            evaluation_date: The date for calculations. Defaults to today.
        """
        if evaluation_date is None:
            evaluation_date = date.today()

        self._eval_date = ql.Date(
            evaluation_date.day,
            evaluation_date.month,
            evaluation_date.year
        )
        ql.Settings.instance().evaluationDate = self._eval_date
        self._calendar = ql.TARGET()

    def _to_ql_date(self, d: date) -> ql.Date:
        """Convert Python date to QuantLib Date."""
        return ql.Date(d.day, d.month, d.year)

    def _get_day_count(self, convention: DayCountConvention) -> ql.DayCounter:
        """Get QuantLib day counter from convention."""
        mapping = {
            DayCountConvention.ACTUAL_360: ql.Actual360(),
            DayCountConvention.ACTUAL_365: ql.Actual365Fixed(),
            DayCountConvention.ACTUAL_ACTUAL: ql.ActualActual(ql.ActualActual.ISDA),
            DayCountConvention.THIRTY_360: ql.Thirty360(ql.Thirty360.BondBasis),
        }
        return mapping.get(convention, ql.ActualActual(ql.ActualActual.ISDA))

    def _get_frequency(self, freq: Frequency) -> int:
        """Get QuantLib frequency from enum."""
        mapping = {
            Frequency.ANNUAL: ql.Annual,
            Frequency.SEMI_ANNUAL: ql.Semiannual,
            Frequency.QUARTERLY: ql.Quarterly,
            Frequency.MONTHLY: ql.Monthly,
        }
        return mapping.get(freq, ql.Semiannual)

    # =========================================================================
    # Present Value / Future Value Calculations
    # =========================================================================

    def present_value(
        self,
        future_value: float,
        rate: float,
        periods: float,
        compounding_frequency: int = 1
    ) -> PresentValueResult:
        """
        Calculate present value of a future cash flow.

        Args:
            future_value: The future amount
            rate: Annual interest rate (e.g., 0.05 for 5%)
            periods: Number of years
            compounding_frequency: Times per year (1=annual, 2=semi, 4=quarterly, 12=monthly)

        Returns:
            PresentValueResult with PV and discount factor
        """
        if compounding_frequency == 0:
            # Continuous compounding
            import math
            discount_factor = math.exp(-rate * periods)
        else:
            # Discrete compounding
            n = compounding_frequency
            discount_factor = (1 + rate / n) ** (-n * periods)

        pv = future_value * discount_factor

        return PresentValueResult(
            present_value=pv,
            discount_factor=discount_factor
        )

    def future_value(
        self,
        present_value: float,
        rate: float,
        periods: float,
        compounding_frequency: int = 1
    ) -> float:
        """
        Calculate future value of a present amount.

        Args:
            present_value: The current amount
            rate: Annual interest rate (e.g., 0.05 for 5%)
            periods: Number of years
            compounding_frequency: Times per year (1=annual, 2=semi, 4=quarterly, 12=monthly)

        Returns:
            Future value
        """
        if compounding_frequency == 0:
            # Continuous compounding
            import math
            growth_factor = math.exp(rate * periods)
        else:
            n = compounding_frequency
            growth_factor = (1 + rate / n) ** (n * periods)

        return round(present_value * growth_factor, 4)

    # =========================================================================
    # Bond Pricing
    # =========================================================================

    def price_fixed_rate_bond(
        self,
        face_value: float,
        coupon_rate: float,
        maturity_date: date,
        issue_date: Optional[date] = None,
        yield_rate: Optional[float] = None,
        frequency: Frequency = Frequency.SEMI_ANNUAL,
        day_count: DayCountConvention = DayCountConvention.THIRTY_360
    ) -> BondPricingResult:
        """
        Price a fixed-rate bond.

        Args:
            face_value: Par value of the bond
            coupon_rate: Annual coupon rate (e.g., 0.05 for 5%)
            maturity_date: Bond maturity date
            issue_date: Bond issue date (defaults to evaluation date)
            yield_rate: Yield to use for pricing (defaults to coupon rate)
            frequency: Coupon payment frequency
            day_count: Day count convention

        Returns:
            BondPricingResult with price and analytics
        """
        if issue_date is None:
            issue_date = date(
                self._eval_date.year(),
                self._eval_date.month(),
                self._eval_date.dayOfMonth()
            )

        if yield_rate is None:
            yield_rate = coupon_rate

        # Convert dates
        ql_issue = self._to_ql_date(issue_date)
        ql_maturity = self._to_ql_date(maturity_date)

        # Build schedule
        schedule = ql.Schedule(
            ql_issue,
            ql_maturity,
            ql.Period(self._get_frequency(frequency)),
            self._calendar,
            ql.Unadjusted,
            ql.Unadjusted,
            ql.DateGeneration.Backward,
            False
        )

        # Create bond
        dc = self._get_day_count(day_count)
        bond = ql.FixedRateBond(
            0,  # settlement days
            face_value,
            schedule,
            [coupon_rate],
            dc
        )

        # Create yield curve for pricing
        flat_curve = ql.FlatForward(
            self._eval_date,
            yield_rate,
            dc
        )
        curve_handle = ql.YieldTermStructureHandle(flat_curve)

        # Price the bond
        bond_engine = ql.DiscountingBondEngine(curve_handle)
        bond.setPricingEngine(bond_engine)

        clean_price = bond.cleanPrice()
        dirty_price = bond.dirtyPrice()
        accrued = bond.accruedAmount()

        # Calculate YTM from clean price
        ytm = bond.bondYield(clean_price, dc, ql.Compounded, self._get_frequency(frequency))

        # Duration and convexity
        duration = ql.BondFunctions.duration(
            bond, ytm, dc, ql.Compounded, self._get_frequency(frequency)
        )
        mod_duration = ql.BondFunctions.duration(
            bond, ytm, dc, ql.Compounded, self._get_frequency(frequency), ql.Duration.Modified
        )
        convexity = ql.BondFunctions.convexity(
            bond, ytm, dc, ql.Compounded, self._get_frequency(frequency)
        )

        return BondPricingResult(
            clean_price=clean_price,
            dirty_price=dirty_price,
            accrued_interest=accrued,
            yield_to_maturity=ytm,
            duration=duration,
            modified_duration=mod_duration,
            convexity=convexity
        )

    def bond_price_from_yield(
        self,
        face_value: float,
        coupon_rate: float,
        yield_rate: float,
        years_to_maturity: float,
        frequency: Frequency = Frequency.SEMI_ANNUAL
    ) -> float:
        """
        Calculate bond price given yield (simplified formula).

        Args:
            face_value: Par value of the bond
            coupon_rate: Annual coupon rate (e.g., 0.05 for 5%)
            yield_rate: Required yield (e.g., 0.06 for 6%)
            years_to_maturity: Years until maturity
            frequency: Payment frequency

        Returns:
            Bond price
        """
        n = frequency.value  # payments per year
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

        return round(pv_coupons + pv_face, 4)

    def yield_from_price(
        self,
        bond_price: float,
        face_value: float,
        coupon_rate: float,
        years_to_maturity: float,
        frequency: Frequency = Frequency.SEMI_ANNUAL
    ) -> float:
        """
        Calculate yield to maturity given bond price (Newton-Raphson method).

        Args:
            bond_price: Current bond price
            face_value: Par value
            coupon_rate: Annual coupon rate
            years_to_maturity: Years until maturity
            frequency: Payment frequency

        Returns:
            Yield to maturity (annual)
        """
        # Initial guess
        ytm = coupon_rate

        for _ in range(100):  # Max iterations
            price = self.bond_price_from_yield(
                face_value, coupon_rate, ytm, years_to_maturity, frequency
            )

            if abs(price - bond_price) < 0.0001:
                break

            # Calculate derivative (numerical)
            delta = 0.0001
            price_up = self.bond_price_from_yield(
                face_value, coupon_rate, ytm + delta, years_to_maturity, frequency
            )
            derivative = (price_up - price) / delta

            if abs(derivative) < 1e-10:
                break

            ytm = ytm - (price - bond_price) / derivative

        return round(ytm, 6)

    # =========================================================================
    # Interest Rate Calculations
    # =========================================================================

    def simple_interest(
        self,
        principal: float,
        rate: float,
        time_years: float
    ) -> Dict[str, float]:
        """
        Calculate simple interest.

        Args:
            principal: Initial amount
            rate: Annual interest rate
            time_years: Time in years

        Returns:
            Dict with interest and total amount
        """
        interest = principal * rate * time_years
        return {
            "principal": round(principal, 4),
            "interest": round(interest, 4),
            "total": round(principal + interest, 4),
            "rate": rate,
            "time_years": time_years
        }

    def compound_interest(
        self,
        principal: float,
        rate: float,
        time_years: float,
        compounding_frequency: int = 1
    ) -> Dict[str, float]:
        """
        Calculate compound interest.

        Args:
            principal: Initial amount
            rate: Annual interest rate
            time_years: Time in years
            compounding_frequency: Times per year (0 for continuous)

        Returns:
            Dict with interest and total amount
        """
        if compounding_frequency == 0:
            # Continuous
            import math
            total = principal * math.exp(rate * time_years)
        else:
            n = compounding_frequency
            total = principal * (1 + rate / n) ** (n * time_years)

        interest = total - principal

        return {
            "principal": round(principal, 4),
            "interest": round(interest, 4),
            "total": round(total, 4),
            "rate": rate,
            "time_years": time_years,
            "compounding_frequency": compounding_frequency
        }

    def effective_annual_rate(
        self,
        nominal_rate: float,
        compounding_frequency: int
    ) -> float:
        """
        Convert nominal rate to effective annual rate.

        Args:
            nominal_rate: Stated annual rate
            compounding_frequency: Times per year (0 for continuous)

        Returns:
            Effective annual rate
        """
        if compounding_frequency == 0:
            import math
            return round(math.exp(nominal_rate) - 1, 6)
        else:
            n = compounding_frequency
            return round((1 + nominal_rate / n) ** n - 1, 6)

    # =========================================================================
    # Annuity Calculations
    # =========================================================================

    def annuity_present_value(
        self,
        payment: float,
        rate: float,
        periods: int,
        is_annuity_due: bool = False
    ) -> float:
        """
        Calculate present value of an annuity.

        Args:
            payment: Periodic payment amount
            rate: Periodic interest rate
            periods: Number of periods
            is_annuity_due: True if payments at beginning of period

        Returns:
            Present value
        """
        if rate == 0:
            pv = payment * periods
        else:
            pv = payment * (1 - (1 + rate) ** -periods) / rate

        if is_annuity_due:
            pv *= (1 + rate)

        return round(pv, 4)

    def annuity_future_value(
        self,
        payment: float,
        rate: float,
        periods: int,
        is_annuity_due: bool = False
    ) -> float:
        """
        Calculate future value of an annuity.

        Args:
            payment: Periodic payment amount
            rate: Periodic interest rate
            periods: Number of periods
            is_annuity_due: True if payments at beginning of period

        Returns:
            Future value
        """
        if rate == 0:
            fv = payment * periods
        else:
            fv = payment * ((1 + rate) ** periods - 1) / rate

        if is_annuity_due:
            fv *= (1 + rate)

        return round(fv, 4)

    def loan_payment(
        self,
        principal: float,
        annual_rate: float,
        years: int,
        payments_per_year: int = 12
    ) -> Dict[str, float]:
        """
        Calculate loan payment amount.

        Args:
            principal: Loan amount
            annual_rate: Annual interest rate
            years: Loan term in years
            payments_per_year: Number of payments per year

        Returns:
            Dict with payment info
        """
        n = years * payments_per_year
        r = annual_rate / payments_per_year

        if r == 0:
            payment = principal / n
        else:
            payment = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

        total_payments = payment * n
        total_interest = total_payments - principal

        return {
            "monthly_payment": round(payment, 2),
            "total_payments": round(total_payments, 2),
            "total_interest": round(total_interest, 2),
            "principal": principal,
            "annual_rate": annual_rate,
            "years": years
        }

    # =========================================================================
    # NPV and IRR
    # =========================================================================

    def npv(
        self,
        rate: float,
        cash_flows: List[float]
    ) -> float:
        """
        Calculate Net Present Value.

        Args:
            rate: Discount rate per period
            cash_flows: List of cash flows (index 0 is time 0)

        Returns:
            Net present value
        """
        npv_value = sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))
        return round(npv_value, 4)

    def irr(
        self,
        cash_flows: List[float],
        guess: float = 0.1
    ) -> float:
        """
        Calculate Internal Rate of Return.

        Args:
            cash_flows: List of cash flows (index 0 is time 0, usually negative)
            guess: Initial guess for IRR

        Returns:
            Internal rate of return
        """
        rate = guess

        for _ in range(1000):
            npv_value = self.npv(rate, cash_flows)

            if abs(npv_value) < 0.0001:
                break

            # Derivative
            delta = 0.0001
            npv_up = self.npv(rate + delta, cash_flows)
            derivative = (npv_up - npv_value) / delta

            if abs(derivative) < 1e-10:
                break

            rate = rate - npv_value / derivative

        return round(rate, 6)


# =============================================================================
# GPT-4o Tool Definitions
# =============================================================================

QUANTLIB_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_present_value",
            "description": "Calculate the present value of a future cash flow",
            "parameters": {
                "type": "object",
                "properties": {
                    "future_value": {
                        "type": "number",
                        "description": "The future amount to discount"
                    },
                    "rate": {
                        "type": "number",
                        "description": "Annual interest rate as decimal (e.g., 0.05 for 5%)"
                    },
                    "periods": {
                        "type": "number",
                        "description": "Number of years"
                    },
                    "compounding_frequency": {
                        "type": "integer",
                        "description": "Times per year (1=annual, 2=semi, 4=quarterly, 12=monthly, 0=continuous)",
                        "default": 1
                    }
                },
                "required": ["future_value", "rate", "periods"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_future_value",
            "description": "Calculate the future value of a present amount",
            "parameters": {
                "type": "object",
                "properties": {
                    "present_value": {
                        "type": "number",
                        "description": "The current amount"
                    },
                    "rate": {
                        "type": "number",
                        "description": "Annual interest rate as decimal"
                    },
                    "periods": {
                        "type": "number",
                        "description": "Number of years"
                    },
                    "compounding_frequency": {
                        "type": "integer",
                        "description": "Times per year",
                        "default": 1
                    }
                },
                "required": ["present_value", "rate", "periods"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "price_bond",
            "description": "Calculate bond price given yield",
            "parameters": {
                "type": "object",
                "properties": {
                    "face_value": {
                        "type": "number",
                        "description": "Par value of the bond"
                    },
                    "coupon_rate": {
                        "type": "number",
                        "description": "Annual coupon rate as decimal"
                    },
                    "yield_rate": {
                        "type": "number",
                        "description": "Required yield as decimal"
                    },
                    "years_to_maturity": {
                        "type": "number",
                        "description": "Years until maturity"
                    },
                    "frequency": {
                        "type": "integer",
                        "description": "Coupon payments per year (1, 2, 4, or 12)",
                        "default": 2
                    }
                },
                "required": ["face_value", "coupon_rate", "yield_rate", "years_to_maturity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_yield",
            "description": "Calculate yield to maturity given bond price",
            "parameters": {
                "type": "object",
                "properties": {
                    "bond_price": {
                        "type": "number",
                        "description": "Current bond price"
                    },
                    "face_value": {
                        "type": "number",
                        "description": "Par value"
                    },
                    "coupon_rate": {
                        "type": "number",
                        "description": "Annual coupon rate"
                    },
                    "years_to_maturity": {
                        "type": "number",
                        "description": "Years until maturity"
                    },
                    "frequency": {
                        "type": "integer",
                        "description": "Payments per year",
                        "default": 2
                    }
                },
                "required": ["bond_price", "face_value", "coupon_rate", "years_to_maturity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_loan_payment",
            "description": "Calculate loan payment amount",
            "parameters": {
                "type": "object",
                "properties": {
                    "principal": {
                        "type": "number",
                        "description": "Loan amount"
                    },
                    "annual_rate": {
                        "type": "number",
                        "description": "Annual interest rate"
                    },
                    "years": {
                        "type": "integer",
                        "description": "Loan term in years"
                    },
                    "payments_per_year": {
                        "type": "integer",
                        "description": "Number of payments per year",
                        "default": 12
                    }
                },
                "required": ["principal", "annual_rate", "years"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_npv",
            "description": "Calculate Net Present Value of cash flows",
            "parameters": {
                "type": "object",
                "properties": {
                    "rate": {
                        "type": "number",
                        "description": "Discount rate per period"
                    },
                    "cash_flows": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "List of cash flows (index 0 is time 0)"
                    }
                },
                "required": ["rate", "cash_flows"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_irr",
            "description": "Calculate Internal Rate of Return",
            "parameters": {
                "type": "object",
                "properties": {
                    "cash_flows": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "List of cash flows (first is usually negative investment)"
                    }
                },
                "required": ["cash_flows"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_compound_interest",
            "description": "Calculate compound interest on an investment",
            "parameters": {
                "type": "object",
                "properties": {
                    "principal": {
                        "type": "number",
                        "description": "Initial investment"
                    },
                    "rate": {
                        "type": "number",
                        "description": "Annual interest rate"
                    },
                    "time_years": {
                        "type": "number",
                        "description": "Investment period in years"
                    },
                    "compounding_frequency": {
                        "type": "integer",
                        "description": "Times per year (0 for continuous)",
                        "default": 1
                    }
                },
                "required": ["principal", "rate", "time_years"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Execute a QuantLib tool call.

    Args:
        tool_name: Name of the tool to execute
        arguments: Tool arguments

    Returns:
        Tool result
    """
    engine = QuantLibEngine()

    if tool_name == "calculate_present_value":
        result = engine.present_value(
            future_value=arguments["future_value"],
            rate=arguments["rate"],
            periods=arguments["periods"],
            compounding_frequency=arguments.get("compounding_frequency", 1)
        )
        return result.to_dict()

    elif tool_name == "calculate_future_value":
        return engine.future_value(
            present_value=arguments["present_value"],
            rate=arguments["rate"],
            periods=arguments["periods"],
            compounding_frequency=arguments.get("compounding_frequency", 1)
        )

    elif tool_name == "price_bond":
        freq_map = {1: Frequency.ANNUAL, 2: Frequency.SEMI_ANNUAL,
                    4: Frequency.QUARTERLY, 12: Frequency.MONTHLY}
        freq = freq_map.get(arguments.get("frequency", 2), Frequency.SEMI_ANNUAL)
        return engine.bond_price_from_yield(
            face_value=arguments["face_value"],
            coupon_rate=arguments["coupon_rate"],
            yield_rate=arguments["yield_rate"],
            years_to_maturity=arguments["years_to_maturity"],
            frequency=freq
        )

    elif tool_name == "calculate_yield":
        freq_map = {1: Frequency.ANNUAL, 2: Frequency.SEMI_ANNUAL,
                    4: Frequency.QUARTERLY, 12: Frequency.MONTHLY}
        freq = freq_map.get(arguments.get("frequency", 2), Frequency.SEMI_ANNUAL)
        return engine.yield_from_price(
            bond_price=arguments["bond_price"],
            face_value=arguments["face_value"],
            coupon_rate=arguments["coupon_rate"],
            years_to_maturity=arguments["years_to_maturity"],
            frequency=freq
        )

    elif tool_name == "calculate_loan_payment":
        return engine.loan_payment(
            principal=arguments["principal"],
            annual_rate=arguments["annual_rate"],
            years=arguments["years"],
            payments_per_year=arguments.get("payments_per_year", 12)
        )

    elif tool_name == "calculate_npv":
        return engine.npv(
            rate=arguments["rate"],
            cash_flows=arguments["cash_flows"]
        )

    elif tool_name == "calculate_irr":
        return engine.irr(cash_flows=arguments["cash_flows"])

    elif tool_name == "calculate_compound_interest":
        return engine.compound_interest(
            principal=arguments["principal"],
            rate=arguments["rate"],
            time_years=arguments["time_years"],
            compounding_frequency=arguments.get("compounding_frequency", 1)
        )

    else:
        raise ValueError(f"Unknown tool: {tool_name}")


if __name__ == "__main__":
    # Demo
    engine = QuantLibEngine()

    print("=== QuantLib Financial Engine Demo ===\n")

    # Present Value
    print("1. Present Value of $10,000 in 5 years at 5%:")
    pv = engine.present_value(10000, 0.05, 5)
    print(f"   PV = ${pv.present_value:,.2f}")
    print(f"   Discount Factor = {pv.discount_factor:.6f}\n")

    # Bond Pricing
    print("2. Bond Price: $1000 face, 5% coupon, 10yr, 6% yield:")
    price = engine.bond_price_from_yield(1000, 0.05, 0.06, 10)
    print(f"   Price = ${price:,.2f}\n")

    # Loan Payment
    print("3. Loan Payment: $250,000 mortgage, 6.5%, 30 years:")
    loan = engine.loan_payment(250000, 0.065, 30)
    print(f"   Monthly Payment = ${loan['monthly_payment']:,.2f}")
    print(f"   Total Interest = ${loan['total_interest']:,.2f}\n")

    # NPV
    print("4. NPV of project: -$100k initial, $30k/yr for 5 years at 10%:")
    npv = engine.npv(0.10, [-100000, 30000, 30000, 30000, 30000, 30000])
    print(f"   NPV = ${npv:,.2f}\n")

    # IRR
    print("5. IRR of same project:")
    irr = engine.irr([-100000, 30000, 30000, 30000, 30000, 30000])
    print(f"   IRR = {irr*100:.2f}%\n")
