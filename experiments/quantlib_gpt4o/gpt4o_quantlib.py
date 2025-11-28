"""
GPT-4o + QuantLib integration for precise financial calculations.

This module provides a GPT-4o powered assistant that uses QuantLib
for accurate financial computations.
"""

import json
import os
from typing import Optional, List, Dict, Any

from openai import OpenAI
from dotenv import load_dotenv

from quantlib_engine import QuantLibEngine, QUANTLIB_TOOLS, execute_tool

load_dotenv()


class QuantLibGPT:
    """
    GPT-4o assistant with QuantLib calculation capabilities.

    Uses GPT-4o for natural language understanding and QuantLib
    for precise financial calculations.
    """

    SYSTEM_PROMPT = """You are a financial analysis assistant with access to precise financial calculation tools powered by QuantLib.

When users ask financial questions, use the available tools to compute accurate answers. Always show your work and explain the calculations.

Available capabilities:
- Present Value / Future Value calculations
- Bond pricing and yield calculations
- Loan payment calculations
- NPV and IRR analysis
- Compound interest calculations

Important guidelines:
1. Always use the calculation tools for numerical answers - don't estimate
2. Explain the financial concepts in simple terms
3. Show the inputs and outputs clearly
4. If a question is ambiguous, ask for clarification on parameters like:
   - Interest rate (annual vs periodic)
   - Compounding frequency
   - Time period
5. Express rates as decimals in tool calls (5% = 0.05)
"""

    def __init__(self, model: str = "gpt-4o"):
        """Initialize the GPT-4o + QuantLib assistant."""
        self.client = OpenAI()
        self.model = model
        self.engine = QuantLibEngine()
        self.conversation: List[Dict[str, Any]] = []

    def _handle_tool_calls(self, tool_calls) -> List[Dict[str, Any]]:
        """Execute tool calls and return results."""
        results = []
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            try:
                result = execute_tool(function_name, arguments)
                results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps(result)
                })
            except Exception as e:
                results.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps({"error": str(e)})
                })

        return results

    def chat(self, user_message: str) -> str:
        """
        Send a message and get a response.

        Args:
            user_message: User's question or request

        Returns:
            Assistant's response
        """
        # Add user message to conversation
        self.conversation.append({
            "role": "user",
            "content": user_message
        })

        # Build messages
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ] + self.conversation

        # Call GPT-4o
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=QUANTLIB_TOOLS,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message

        # Handle tool calls if any
        while assistant_message.tool_calls:
            # Add assistant message with tool calls
            self.conversation.append({
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

            # Execute tools
            tool_results = self._handle_tool_calls(assistant_message.tool_calls)
            self.conversation.extend(tool_results)

            # Get next response
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ] + self.conversation

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=QUANTLIB_TOOLS,
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message

        # Add final response to conversation
        final_response = assistant_message.content or ""
        self.conversation.append({
            "role": "assistant",
            "content": final_response
        })

        return final_response

    def reset(self):
        """Clear conversation history."""
        self.conversation = []


def run_single_query(query: str, model: str = "gpt-4o") -> Dict[str, Any]:
    """
    Run a single financial query.

    Args:
        query: The financial question
        model: Model to use

    Returns:
        Dict with query, response, and tool calls made
    """
    client = OpenAI()
    engine = QuantLibEngine()

    messages = [
        {
            "role": "system",
            "content": QuantLibGPT.SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": query
        }
    ]

    tool_calls_made = []

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=QUANTLIB_TOOLS,
        tool_choice="auto"
    )

    assistant_message = response.choices[0].message

    while assistant_message.tool_calls:
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
            arguments = json.loads(tool_call.function.arguments)

            tool_calls_made.append({
                "function": function_name,
                "arguments": arguments
            })

            try:
                result = execute_tool(function_name, arguments)
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps(result)
                })
                tool_calls_made[-1]["result"] = result
            except Exception as e:
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "content": json.dumps({"error": str(e)})
                })
                tool_calls_made[-1]["error"] = str(e)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=QUANTLIB_TOOLS,
            tool_choice="auto"
        )

        assistant_message = response.choices[0].message

    return {
        "query": query,
        "response": assistant_message.content,
        "tool_calls": tool_calls_made
    }


if __name__ == "__main__":
    print("=== GPT-4o + QuantLib Financial Assistant ===\n")

    # Test queries
    test_queries = [
        "What is the present value of $50,000 that I will receive in 10 years if the discount rate is 7%?",
        "I have a bond with $1,000 face value, 4% annual coupon, 5 years to maturity. If yields are currently 5%, what should I pay for it?",
        "I want to take out a $400,000 mortgage at 7% for 30 years. What will my monthly payment be?",
        "I'm considering an investment that costs $50,000 upfront and returns $15,000 per year for 5 years. What is the IRR?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"--- Query {i} ---")
        print(f"Q: {query}\n")

        result = run_single_query(query)

        print("Tool Calls:")
        for tc in result["tool_calls"]:
            print(f"  - {tc['function']}: {tc['arguments']}")
            if "result" in tc:
                print(f"    Result: {tc['result']}")

        print(f"\nA: {result['response']}\n")
        print("=" * 60 + "\n")
