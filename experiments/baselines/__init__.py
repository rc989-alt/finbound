"""Baseline methods for FinBound evaluation."""

from .gpt4_zeroshot import GPT4ZeroShotBaseline, create_runner as gpt4_zeroshot_runner
from .gpt4_fewshot import GPT4FewShotBaseline, create_runner as gpt4_fewshot_runner
from .gpt5nano_zeroshot import GPT5NanoZeroShotBaseline, create_runner as gpt5nano_zeroshot_runner
from .rag_no_verify import RAGNoVerifyBaseline, create_runner as rag_no_verify_runner
from .deepseek_zeroshot import DeepSeekZeroShotBaseline, create_runner as deepseek_zeroshot_runner
from .claude_zeroshot import ClaudeZeroShotBaseline, create_runner as claude_zeroshot_runner

__all__ = [
    "GPT4ZeroShotBaseline",
    "GPT4FewShotBaseline",
    "GPT5NanoZeroShotBaseline",
    "RAGNoVerifyBaseline",
    "DeepSeekZeroShotBaseline",
    "ClaudeZeroShotBaseline",
    "gpt4_zeroshot_runner",
    "gpt4_fewshot_runner",
    "gpt5nano_zeroshot_runner",
    "rag_no_verify_runner",
    "deepseek_zeroshot_runner",
    "claude_zeroshot_runner",
]
