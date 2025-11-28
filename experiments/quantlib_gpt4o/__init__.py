"""
QuantLib + GPT-4o financial calculation engine.

This package provides:
- QuantLibEngine: Precise financial calculations using QuantLib
- QuantLibGPT: GPT-4o assistant with QuantLib tool calling
- QUANTLIB_TOOLS: Tool definitions for OpenAI function calling
"""

from .quantlib_engine import (
    QuantLibEngine,
    QUANTLIB_TOOLS,
    execute_tool,
    BondPricingResult,
    PresentValueResult,
    DayCountConvention,
    Frequency,
)

from .gpt4o_quantlib import (
    QuantLibGPT,
    run_single_query,
)

__all__ = [
    "QuantLibEngine",
    "QuantLibGPT",
    "QUANTLIB_TOOLS",
    "execute_tool",
    "run_single_query",
    "BondPricingResult",
    "PresentValueResult",
    "DayCountConvention",
    "Frequency",
]
