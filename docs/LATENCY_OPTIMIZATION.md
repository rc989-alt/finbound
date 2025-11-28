# Latency Optimization Solutions for FinBound

## Current Latency Profile

| Component | Time | % of Total | Model Used |
|-----------|------|------------|------------|
| Table Extraction | ~3-4s | 15-20% | gpt-4o-mini (3 passes) |
| Main Reasoning | ~3-4s | 15-20% | gpt-4o |
| **Verification Gate** | **~12-15s** | **55-70%** | gpt-4o (3 passes) |
| **Total** | **~19-22s** | 100% | |

The **Verification Gate** is the main bottleneck, taking 55-70% of total latency due to:
- 3 sequential LLM calls for multi-pass verification
- Using the expensive `gpt-4o` model
- Each pass takes ~4-5s

---

## Optimization Options

### Option 1: Parallelize Verification Passes
**Estimated Savings: ~8-10s (from ~12-15s to ~4-5s)**

#### Implementation

```python
# File: finbound/reasoning/engine.py
# Location: _run_multi_pass_verification() method around line 2400

import concurrent.futures
from typing import Any, Dict, List

def _run_verification_pass(
    self,
    verification_model: str,
    verification_prompt: str,
    user_prompt: str,
    pass_idx: int,
) -> Dict[str, Any]:
    """Run a single verification pass. Thread-safe."""
    temp = 0.0 if pass_idx == 0 else 0.1

    # Create a new client for thread safety (connection pooling)
    completion = self._limiter.call(
        self._client.chat.completions.create,
        model=verification_model,
        messages=[
            {"role": "system", "content": verification_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temp,
    )
    result = completion.choices[0].message.content or "{}"

    try:
        result_text = result.strip().strip("`")
        if result_text.lower().startswith("json"):
            result_text = result_text[4:].strip()
        verification = json.loads(result_text)
        self._logger.info(
            "Pass %d result: correct=%s, answer=%s",
            pass_idx + 1,
            verification.get("is_correct"),
            verification.get("your_result") or verification.get("corrected_answer"),
        )
        return verification
    except (json.JSONDecodeError, KeyError) as e:
        self._logger.warning("Pass %d parse error: %s", pass_idx + 1, e)
        return {"is_correct": True}  # Default on parse error


def _run_multi_pass_verification_parallel(
    self,
    question_or_request,
    proposed_answer: str,
    reasoning: str,
    evidence_context,
    expected_sign: Optional[str] = None,
    question_classification = None,
) -> Tuple[bool, str | None]:
    """Run multi-pass verification IN PARALLEL for latency reduction.

    Instead of sequential: Pass1 (4s) -> Pass2 (4s) -> Pass3 (4s) = 12s
    Now parallel: Pass1 + Pass2 + Pass3 = 4s total
    """
    # ... (same setup code as before until line 2397) ...

    # Enable parallel mode via environment variable
    parallel_verification = os.getenv(
        "FINBOUND_PARALLEL_VERIFICATION", "0"
    ).lower() in ("1", "true", "yes")

    if parallel_verification and num_passes > 1:
        # PARALLEL EXECUTION
        self._logger.info(
            "Running %d verification passes in PARALLEL with %s",
            num_passes, verification_model
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_passes) as executor:
            futures = [
                executor.submit(
                    self._run_verification_pass,
                    verification_model,
                    verification_prompt,
                    user_prompt,
                    pass_idx,
                )
                for pass_idx in range(num_passes)
            ]

            pass_results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result(timeout=30)  # 30s timeout per pass
                    pass_results.append(result)
                except Exception as e:
                    self._logger.warning("Verification pass failed: %s", e)
                    pass_results.append({"is_correct": True})
    else:
        # SEQUENTIAL EXECUTION (original code)
        pass_results = []
        for pass_idx in range(num_passes):
            result = self._run_verification_pass(
                verification_model, verification_prompt, user_prompt, pass_idx
            )
            pass_results.append(result)

    # ... (same voting logic as before) ...
```

#### Configuration

```bash
# Enable parallel verification
export FINBOUND_PARALLEL_VERIFICATION=1
```

#### Considerations
- **Thread Safety**: OpenAI client is thread-safe with connection pooling
- **Rate Limits**: May hit API rate limits faster; adjust `rate_limiter.py` if needed
- **Error Handling**: Individual pass failures don't block others

---

### Option 2: Use gpt-4o-mini for Verification
**Estimated Savings: ~6-8s (from ~12-15s to ~4-6s)**

#### Implementation

```python
# File: finbound/reasoning/engine.py
# Location: Around line 2274-2275

# BEFORE (current):
verification_model = "gpt-4o" if is_complex else "gpt-4o-mini"

# AFTER (option to use mini for all):
def _get_verification_model(self, is_complex: bool) -> str:
    """Get the model to use for verification passes.

    Environment variables:
    - FINBOUND_VERIFICATION_MODEL: Override model (e.g., "gpt-4o-mini")
    - FINBOUND_FAST_VERIFICATION: Use gpt-4o-mini even for complex questions
    """
    # Allow explicit model override
    override_model = os.getenv("FINBOUND_VERIFICATION_MODEL")
    if override_model:
        return override_model

    # Fast verification mode: always use mini
    fast_verification = os.getenv(
        "FINBOUND_FAST_VERIFICATION", "0"
    ).lower() in ("1", "true", "yes")

    if fast_verification:
        self._logger.info("Using gpt-4o-mini for fast verification")
        return "gpt-4o-mini"

    # Default: use gpt-4o for complex, gpt-4o-mini for simple
    return "gpt-4o" if is_complex else "gpt-4o-mini"

# Update line ~2275:
verification_model = self._get_verification_model(is_complex)
```

#### Configuration

```bash
# Option A: Use mini for everything (fastest)
export FINBOUND_FAST_VERIFICATION=1

# Option B: Explicitly set model
export FINBOUND_VERIFICATION_MODEL=gpt-4o-mini
```

#### Accuracy Trade-off Analysis

| Model | Latency/Pass | Verification Accuracy | Use Case |
|-------|--------------|----------------------|----------|
| gpt-4o | ~4-5s | ~95% | Production, high-stakes |
| gpt-4o-mini | ~1-2s | ~85-90% | Development, cost-sensitive |

**Recommendation**: Test on your benchmark to measure accuracy impact. Expected ~5% accuracy drop.

---

### Option 3: Reduce to 2 Verification Passes
**Estimated Savings: ~4-5s (from ~12-15s to ~8-10s)**

#### Implementation

```python
# File: finbound/reasoning/engine.py
# Location: Around line 2277-2278

# BEFORE:
num_passes = 3 if is_complex else 1

# AFTER:
def _get_num_verification_passes(self, is_complex: bool) -> int:
    """Get number of verification passes to run.

    Environment variables:
    - FINBOUND_VERIFICATION_PASSES: Override number of passes (1-5)
    - FINBOUND_TWO_PASS_MODE: Use 2 passes instead of 3 for complex
    """
    # Allow explicit override
    override_passes = os.getenv("FINBOUND_VERIFICATION_PASSES")
    if override_passes:
        try:
            return max(1, min(5, int(override_passes)))
        except ValueError:
            pass

    # Two-pass mode for complex questions
    two_pass_mode = os.getenv(
        "FINBOUND_TWO_PASS_MODE", "0"
    ).lower() in ("1", "true", "yes")

    if is_complex:
        return 2 if two_pass_mode else 3
    return 1

# Update line ~2278:
num_passes = self._get_num_verification_passes(is_complex)

# Also update voting logic for 2-pass mode (around line 2449):
if num_passes == 2:
    # Two-pass mode: both must agree for correction
    # If they disagree, accept original answer
    if pass_results[0].get("is_correct") != pass_results[1].get("is_correct"):
        self._logger.info("Two-pass disagreement, accepting original answer")
        return True, None

    # Both agree it's wrong -> apply correction
    if not pass_results[0].get("is_correct"):
        # Use answer from pass with higher confidence reasoning
        corrected = pass_results[0].get("corrected_answer") or pass_results[1].get("corrected_answer")
        if corrected:
            return False, str(corrected)

    return True, None
```

#### Configuration

```bash
# Use 2 passes instead of 3
export FINBOUND_TWO_PASS_MODE=1

# Or explicitly set pass count
export FINBOUND_VERIFICATION_PASSES=2
```

#### Accuracy Trade-off

| Passes | Latency | Consensus Reliability | Error Correction Rate |
|--------|---------|----------------------|----------------------|
| 3 | ~12-15s | High (2/3 majority) | ~95% |
| 2 | ~8-10s | Medium (must agree) | ~85-90% |
| 1 | ~4-5s | Low | ~75-80% |

**Recommendation**: 2 passes with "both must agree" logic maintains good reliability.

---

### Option 4: Skip Verification for High-Confidence Answers
**Estimated Savings: Variable (~12s for 30-50% of questions)**

This is already partially implemented via `FINBOUND_FAST_PATH_VERIFICATION`. Here's an enhanced version:

#### Implementation

```python
# File: finbound/reasoning/engine.py
# Add new method around line 2215

def _should_skip_verification(
    self,
    question_classification: Optional[ClassificationResult],
    layer0_result: Optional[Dict[str, Any]],
    proposed_answer: str,
    reasoning: str,
) -> Tuple[bool, str]:
    """Determine if we can skip expensive multi-pass verification.

    Returns (should_skip, reason).

    Skip verification when:
    1. Question is classified as EASY
    2. Layer 0 passed with high confidence
    3. Answer matches a simple lookup pattern
    4. No calculation keywords detected
    """
    # Check environment variable
    skip_enabled = os.getenv(
        "FINBOUND_SKIP_VERIFICATION_FOR_EASY", "0"
    ).lower() in ("1", "true", "yes")

    if not skip_enabled:
        return False, "skip_disabled"

    # Condition 1: EASY questions
    if question_classification and question_classification.difficulty == Difficulty.EASY:
        return True, "easy_question"

    # Condition 2: Layer 0 high confidence
    if layer0_result:
        if (
            layer0_result.get("passed", False) and
            layer0_result.get("fast_path_eligible", False) and
            layer0_result.get("confidence") == "high"
        ):
            return True, "layer0_high_confidence"

    # Condition 3: Simple lookup (direct value extraction)
    # Answers like "42%" or "$1,234" with short reasoning are likely lookups
    is_simple_lookup = (
        len(proposed_answer) < 20 and
        len(reasoning) < 300 and
        "calculated" not in reasoning.lower() and
        "computed" not in reasoning.lower()
    )
    if is_simple_lookup and not self._detect_calculation_type(reasoning):
        return True, "simple_lookup"

    return False, "requires_verification"


# Modify _run_multi_pass_verification to use this:
def _run_multi_pass_verification(
    self,
    question_or_request,
    proposed_answer: str,
    reasoning: str,
    evidence_context,
    expected_sign: Optional[str] = None,
    question_classification = None,
    layer0_result: Optional[Dict[str, Any]] = None,  # NEW PARAMETER
) -> Tuple[bool, str | None]:
    """Run multi-pass verification with smart skipping."""

    # Check if we can skip verification entirely
    should_skip, skip_reason = self._should_skip_verification(
        question_classification, layer0_result, proposed_answer, reasoning
    )

    if should_skip:
        self._logger.info(
            "Skipping multi-pass verification (reason: %s)", skip_reason
        )
        return True, None

    # ... rest of verification code ...
```

#### Configuration

```bash
# Enable skipping verification for high-confidence answers
export FINBOUND_SKIP_VERIFICATION_FOR_EASY=1

# Combined with existing fast-path
export FINBOUND_FAST_PATH_VERIFICATION=1
```

#### Coverage Analysis

Based on benchmark data:
- ~30-40% of questions are EASY → skip verification entirely
- ~20-30% pass Layer 0 with high confidence → skip verification
- ~40-50% require full verification

**Expected savings**: Skip verification for 30-50% of samples → average ~5-7s savings.

---

## Combined Optimization Strategy

For maximum latency reduction, combine multiple options:

### Aggressive Mode (Fastest, ~5-6s total)
```bash
export FINBOUND_PARALLEL_VERIFICATION=1      # Parallel passes
export FINBOUND_FAST_VERIFICATION=1          # Use gpt-4o-mini
export FINBOUND_TWO_PASS_MODE=1              # Only 2 passes
export FINBOUND_SKIP_VERIFICATION_FOR_EASY=1 # Skip when confident
```
**Expected latency: ~5-6s** (vs current ~19-22s)
**Expected accuracy: ~75-78%** (vs current 81%)

### Balanced Mode (Good trade-off, ~10-12s total)
```bash
export FINBOUND_PARALLEL_VERIFICATION=1      # Parallel passes
export FINBOUND_TWO_PASS_MODE=1              # Only 2 passes
export FINBOUND_SKIP_VERIFICATION_FOR_EASY=1 # Skip when confident
# Keep gpt-4o for verification
```
**Expected latency: ~10-12s**
**Expected accuracy: ~79-80%**

### Conservative Mode (Minimal accuracy loss, ~12-14s total)
```bash
export FINBOUND_PARALLEL_VERIFICATION=1      # Parallel passes only
```
**Expected latency: ~12-14s**
**Expected accuracy: ~80-81%**

---

## Implementation Checklist

- [ ] Add `_run_verification_pass()` helper method
- [ ] Add `concurrent.futures` import
- [ ] Add `_get_verification_model()` method
- [ ] Add `_get_num_verification_passes()` method
- [ ] Add `_should_skip_verification()` method
- [ ] Update `_run_multi_pass_verification()` to use new methods
- [ ] Add environment variable handling
- [ ] Update voting logic for 2-pass mode
- [ ] Add logging for optimization decisions
- [ ] Test each option independently
- [ ] Benchmark accuracy impact

---

## Monitoring & Metrics

Add these metrics to track optimization impact:

```python
# File: finbound/reasoning/engine.py

# Add to reasoning result metadata:
reasoning_result.raw_model_output["latency_metrics"] = {
    "verification_passes_run": num_passes,
    "verification_model": verification_model,
    "verification_skipped": should_skip,
    "skip_reason": skip_reason,
    "parallel_mode": parallel_verification,
    "total_verification_time_ms": verification_elapsed_ms,
}
```

This allows post-analysis of latency distribution across samples.
