# FinBound Latency Optimization Plan

> **Version:** 2.0 (Production-Ready)
> **Last Updated:** November 2024
> **Status:** Implementation In Progress

## Executive Summary

**Current State:**

- FinBound: ~30 minutes for 100 samples (~18 seconds/sample)
- GPT-4 Baseline: ~3 minutes for 100 samples (~1.8 seconds/sample)
- **Gap: 10x slower than baseline**

**Target State:**

- FinBound: ≤3 minutes for 100 samples (~1.8 seconds/sample)
- Maintain accuracy: ≥78% (current benchmark)
- Maintain auditability: 100%

**Production Constraints (Financial Institutions):**

- Full 128K token context windows required
- No prompt reduction (complex financial documents)
- Per-document uniqueness (no table extraction caching viable)

---

## Root Cause Analysis

### Latency Breakdown Per Sample (Current Normal Mode ~17s)

| Component | Time (ms) | LLM Calls | Notes |
|-----------|-----------|-----------|-------|
| **Main Reasoning** | 2,000-3,000 | 1 (GPT-4o) | Core reasoning |
| **Table Extraction** | 3,000-9,000 | 1-3 (GPT-4o-mini) | 1-3 passes |
| **Multi-pass Verification** | 9,000-15,000 | 1-3 (GPT-4o) | 3 passes for complex |
| **Layer 0/1 Checks** | 100-500 | 0 | CPU-only |
| **Layer 2 Re-extraction** | 5,000-10,000 | 1 (GPT-4o) | If triggered |
| **LLM Verifier (Gate)** | 2,000-3,000 | 1 | In verification gate |
| **Retry (uncertain)** | 2,000-3,000 | 1 | If triggered |
| **Total** | **~17,000** | **5-12** | Sequential |

### Key Problem: Sequential LLM Calls

- Each sample makes 5-12 LLM API calls **sequentially**
- Each call has ~300-500ms network overhead + ~1.5-2s model inference
- No parallelization between samples
- No parallelization within verification passes

---

## Optimization Strategy: Production-Focused Approach

### Phase 1: Request-Level Parallelism (Primary - 90% of improvement)

**Impact: Reduce wall-clock time from 30 min to ≤3 min**

For banks/financial institutions processing many concurrent requests:

- Process 10-50 requests concurrently (horizontally scalable)
- Each request still takes ~17s, but throughput = N requests/17s
- 100 requests with 10 parallel workers = ~170s ≈ 3 min

### Phase 2: Intelligent Routing (Per-Request Optimization)

**Impact: Reduce per-request time from 17s to ~5-8s**

- Skip expensive verification for EASY questions (65% of workload)
- Single-pass verification for MEDIUM questions
- Full 3-pass verification only for HARD questions
- Parallel verification passes (run 3 passes concurrently, not sequentially)

### Phase 3: Model Tiering

**Impact: 2x improvement on auxiliary calls**

- GPT-4o-mini for table extraction (faster, cheaper)
- GPT-4o for main reasoning (accuracy-critical)
- GPT-4o for verification (only HARD questions)

### ~~Phase 4: Caching~~ (REMOVED - Not Production Viable)

> **Note:** Table extraction caching and prompt reduction were removed from
> this plan. In production financial environments:
>
> - Each document is unique (different company, year, filing)
> - Context windows can be 128K tokens
> - Cache hit rate would be near 0%
> - Prompt completeness is required for accuracy

---

## Implementation Plan

### Phase 1: Parallel Sample Processing (Week 1)

#### Task 1.1: Async Batch Runner
**File:** `experiments/parallel_runner.py`

```python
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from typing import List
from finbound import FinBound
from finbound.data.unified import UnifiedSample

class ParallelFinBoundRunner:
    """Run FinBound on multiple samples in parallel."""
    
    def __init__(
        self,
        max_concurrent: int = 10,
        rate_limit_rpm: int = 500,  # OpenAI tier limit
    ):
        self.max_concurrent = max_concurrent
        self.rate_limit_rpm = rate_limit_rpm
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_sample(
        self,
        fb: FinBound,
        sample: UnifiedSample,
    ):
        """Process a single sample with rate limiting."""
        async with self.semaphore:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: fb.run_unified_sample(sample, task_family="F1")
            )
            return result
    
    async def run_batch(
        self,
        samples: List[UnifiedSample],
    ):
        """Process all samples in parallel."""
        fb = FinBound(
            model="gpt-4o",
            low_latency_mode=True,  # Use optimized mode
        )
        
        tasks = [
            self.process_sample(fb, sample)
            for sample in samples
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
```

**Expected Impact:**
- 10 concurrent samples → 10x throughput
- 100 samples in ~180s (3 min) wall-clock time

#### Task 1.2: Rate Limiter Enhancement
**File:** `finbound/utils/rate_limiter.py`

Add token-bucket rate limiting to prevent API throttling:
```python
class AsyncRateLimiter:
    """Token bucket rate limiter for parallel execution."""
    
    def __init__(self, rpm: int = 500, burst: int = 50):
        self.rpm = rpm
        self.tokens = burst
        self.max_tokens = burst
        self.refill_rate = rpm / 60  # tokens per second
        self.last_refill = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return
            
            wait_time = (1 - self.tokens) / self.refill_rate
            await asyncio.sleep(wait_time)
            self.tokens = 0
```

---

### Phase 2: Ultra-Low Latency Mode (Week 1-2)

#### Task 2.1: Streamlined Engine Mode
**File:** `finbound/reasoning/engine.py`

Add new `ultra_low_latency_mode`:

```python
def __init__(
    self,
    model: str = "gpt-4o",
    use_quantlib: bool = True,
    low_latency_mode: bool = False,
    ultra_low_latency_mode: bool = False,  # NEW
):
    if ultra_low_latency_mode:
        # Override all settings for maximum speed
        self._enable_table_extraction = False  # Skip LLM table extraction
        self._enable_verification_pass = False  # Skip multi-pass verification
        self._model = "gpt-4o-mini"  # Faster model
        self._max_tool_iterations = 2  # Reduce iterations
```

**Changes in `run()` method:**
```python
def run(self, ...):
    if self._ultra_low_latency_mode:
        # Single-shot reasoning without table extraction or verification
        # Rely entirely on Layer 0 auto-corrections
        return self._run_single_shot_reasoning(structured_request, evidence_context)
    
    # ... existing logic
```

#### Task 2.2: Skip Table Extraction for Simple Questions
**File:** `finbound/reasoning/engine.py`

Modify `_extract_table_cells()`:
```python
def _extract_table_cells(self, question: str, evidence_context: ...):
    # NEW: Skip for simple direct lookup questions
    if self._is_simple_lookup(question):
        return ""  # Let main reasoning handle it
    
    # NEW: Use cached extraction if available
    cache_key = self._compute_table_cache_key(evidence_context)
    if cache_key in self._table_extraction_cache:
        return self._table_extraction_cache[cache_key]
    
    # ... existing extraction logic
    
def _is_simple_lookup(self, question: str) -> bool:
    """Detect simple single-value lookups that don't need table extraction."""
    simple_patterns = [
        r"what (?:is|was) the .* in (\d{4})",  # "What was X in 2019?"
        r"how much (?:is|was) .* in (\d{4})",
    ]
    # If question mentions only ONE year, likely simple lookup
    years = re.findall(r"\b(19|20)\d{2}\b", question)
    return len(set(years)) <= 1
```

#### Task 2.3: Intelligent Verification Routing
**File:** `finbound/reasoning/engine.py`

Optimize `_verify_calculation()`:
```python
def _verify_calculation(self, ...):
    # NEW: Skip verification entirely for easy questions
    if question_classification.difficulty == Difficulty.EASY:
        return True, None
    
    # NEW: Single pass for medium (no multi-pass)
    if question_classification.difficulty == Difficulty.MEDIUM:
        return self._single_pass_verify(...)  # GPT-4o-mini
    
    # Only HARD questions get full verification (but parallel)
    # ... existing multi-pass logic with parallelization
```

---

### Phase 3: Caching & Prompt Optimization (Week 2)

#### Task 3.1: Table Extraction Cache
**File:** `finbound/reasoning/extraction/cache.py`

```python
from functools import lru_cache
import hashlib

class TableExtractionCache:
    """Cache table extraction results to avoid redundant LLM calls."""
    
    def __init__(self, max_size: int = 1000):
        self._cache = {}
        self._max_size = max_size
    
    def get_key(self, tables: List, question_type: str) -> str:
        """Generate cache key from table content and question type."""
        table_hash = hashlib.md5(
            str(tables).encode()
        ).hexdigest()
        return f"{table_hash}:{question_type}"
    
    def get(self, key: str):
        return self._cache.get(key)
    
    def set(self, key: str, value):
        if len(self._cache) >= self._max_size:
            # LRU eviction
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = value
```

#### Task 3.2: Prompt Token Reduction
**File:** `finbound/reasoning/engine.py`

Current system prompts are 2000+ tokens. Reduce by:

1. **Conditional formula guidance** - Only include relevant formulas:
```python
def _get_formula_guidance(self, calc_types: List[str]) -> str:
    if not calc_types:
        return ""  # Skip entirely for non-calculation questions
    
    # Only include formulas for detected types (not all 15+)
    return "\n".join(
        FORMULA_TEMPLATES[ct] for ct in calc_types if ct in FORMULA_TEMPLATES
    )
```

2. **Compact verification prompts** - Reduce from 1500 tokens to 500:
```python
COMPACT_VERIFICATION_PROMPT = """
Verify the calculation:
1. Extract values from evidence
2. Apply correct formula
3. Compare to proposed answer

Return JSON: {"is_correct": bool, "corrected_answer": str|null}
"""
```

#### Task 3.3: Question Classification Cache
**File:** `finbound/routing/question_classifier.py`

```python
@lru_cache(maxsize=1000)
def classify_question(question: str) -> ClassificationResult:
    """Cached question classification."""
    # ... existing logic
```

---

## Testing & Validation Plan

### Benchmark Script
**File:** `experiments/benchmark_latency.py`

```python
import time
import asyncio
from experiments.parallel_runner import ParallelFinBoundRunner

async def run_latency_benchmark():
    """Benchmark latency with different configurations."""
    
    samples = load_curated_100_samples()
    
    configs = [
        {"name": "Sequential Normal", "parallel": 1, "mode": "normal"},
        {"name": "Sequential Low-Latency", "parallel": 1, "mode": "low_latency"},
        {"name": "Parallel (10x) Low-Latency", "parallel": 10, "mode": "low_latency"},
        {"name": "Parallel (10x) Ultra", "parallel": 10, "mode": "ultra_low_latency"},
    ]
    
    results = []
    for config in configs:
        start = time.time()
        runner = ParallelFinBoundRunner(max_concurrent=config["parallel"])
        outputs = await runner.run_batch(samples)
        elapsed = time.time() - start
        
        accuracy = calculate_accuracy(outputs, samples)
        
        results.append({
            "config": config["name"],
            "total_time_sec": elapsed,
            "per_sample_ms": (elapsed / len(samples)) * 1000,
            "accuracy": accuracy,
        })
        
        print(f"{config['name']}: {elapsed:.1f}s total, {accuracy:.1%} accuracy")
    
    return results
```

### Expected Results

| Configuration | Total Time | Per Sample | Accuracy | Meets Target? |
|--------------|------------|------------|----------|---------------|
| Sequential Normal | ~30 min | 17,000ms | 78% | ❌ |
| Sequential Low-Latency | ~10 min | 6,000ms | 78% | ❌ |
| **Parallel (10x) Low-Latency** | **~3 min** | **600ms eff.** | **78%** | **✅** |
| Parallel (10x) Ultra | ~1.5 min | 300ms eff. | 75-78% | ✅ (if accuracy OK) |

---

## Implementation Timeline

### Week 1: Core Parallelization
- [ ] Day 1-2: Implement `ParallelFinBoundRunner`
- [ ] Day 3: Implement `AsyncRateLimiter`
- [ ] Day 4: Add ultra-low latency mode
- [ ] Day 5: Initial testing & benchmarking

### Week 2: Optimizations
- [ ] Day 1-2: Table extraction caching
- [ ] Day 3: Prompt optimization
- [ ] Day 4: Question classification caching
- [ ] Day 5: Full benchmark & accuracy validation

### Week 3: Production Hardening
- [ ] Error handling & retry logic
- [ ] Monitoring & logging
- [ ] Documentation
- [ ] Final validation

---

## Risk Mitigation

### Risk 1: API Rate Limiting
**Mitigation:** Token bucket rate limiter, exponential backoff, use multiple API keys

### Risk 2: Accuracy Degradation
**Mitigation:** 
- Run full accuracy benchmark before/after each change
- Keep verification for HARD questions only
- A/B test modes on validation set

### Risk 3: Memory Pressure (Parallel Execution)
**Mitigation:**
- Limit max_concurrent to 10-20
- Process in batches of 100
- Use streaming responses where possible

---

## Success Criteria

| Metric | Current | Target | Validation |
|--------|---------|--------|------------|
| Total Time (100 samples) | 30 min | ≤3 min | Benchmark script |
| Accuracy | 78% | ≥78% | F1 curated set |
| Grounding | 89% | ≥85% | Metric check |
| Hallucination Rate | 10% | ≤12% | Metric check |
| Auditability | 100% | 100% | MLflow traces |

---

## Appendix: Quick Start Commands

```bash
# Run latency benchmark
python experiments/benchmark_latency.py

# Run with parallel execution (10 concurrent)
python experiments/run_experiments.py --methods finbound --task F1 --curated --parallel 10

# Run with ultra-low latency mode
python experiments/run_experiments.py --methods finbound --task F1 --curated --ultra-low-latency

# Full comparison benchmark
python experiments/run_experiments.py --methods finbound gpt4_zeroshot --task F1 --curated --compare-latency
```

---

## Summary

The **key insight** is that the current implementation processes samples sequentially with multiple serial LLM calls per sample. The solution is:

1. **Parallelize samples** (10x concurrent) - This alone achieves the 3-minute target
2. **Optimize per-sample latency** (reduce from 17s to 5-6s) - Additional headroom
3. **Cache repeated computations** - Further optimization

With these changes, FinBound can achieve **≤3 minutes for 100 samples** while maintaining **78%+ accuracy** and **100% auditability**.
