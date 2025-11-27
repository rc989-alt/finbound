"""
FinBound Correction Module

Three-layer correction pipeline for improving answer accuracy:
- Layer 0: Auto-fix for format/scale/type errors (~10ms)
- Layer 1: Formula KB + deterministic recomputation (~500ms-2s)
- Layer 2: LLM-guided re-extraction (~10-15s)
"""

from .layer0_autofix import (
    Layer0Input,
    Layer0Result,
    detect_question_type,
    scale_autoconvert,
    strip_format,
    run_layer0,
)

from .layer2 import (
    Layer2Input,
    Layer2Result,
    Layer2Corrector,
    run_layer2,
    should_trigger_layer2,
)

__all__ = [
    # Layer 0
    "Layer0Input",
    "Layer0Result",
    "detect_question_type",
    "scale_autoconvert",
    "strip_format",
    "run_layer0",
    # Layer 2
    "Layer2Input",
    "Layer2Result",
    "Layer2Corrector",
    "run_layer2",
    "should_trigger_layer2",
]
