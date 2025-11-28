FinBound: A Verification-Gated AI Governance Framework for Evidence-Grounded Financial Reasoning

RQ1: Does a verification-gated reasoning workflow significantly reduce hallucinations and improve grounding accuracy in financial tasks compared to standard RAG?
RQ2: What is the latency–accuracy trade-off of FinBound under real-world financial constraints?

---

## Current Implementation Status

**Latest Benchmark Results (F1 Task Family):**
- Accuracy: 81% (baseline: 78%)
- Grounding Accuracy: 97%
- Hallucination Rate: 7%
- Transparency Score: 99%
- Auditability: 100%

---

## 1. Motivation

Financial text reasoning tasks—such as earnings analysis, financial QA, and scenario-based explanations—require extremely high standards of factual accuracy and auditability:

- **Zero hallucination is mandatory.**
- Every reasoning step must be grounded in the correct evidence (tables, financial metrics, 10-K/10-Q excerpts).
- The entire workflow must be auditable and reproducible.
- Outputs must comply with regulatory requirements (e.g., SR 11-7, Basel guidelines, SEC Fair Disclosure).

However, existing large language models fall short:
- They frequently hallucinate numbers and financial facts.
- They cannot ensure that each reasoning step is sufficiently evidence-supported.
- They lack reproducibility (no run-ID, no execution trace).
- They lack assurance, making external audit practically impossible.

To address these limitations, this paper introduces:
**FinBound**: the first verification-gated AI governance framework specifically designed for trustworthy financial reasoning.

---

## 2. FinBound Architecture

```
FinBound = Approval Gate + Three-Layer Correction Pipeline + Verification Gate + Evidence-Grounded Reasoning Engine
```

### 2.0 Codebase Structure

```
finbound/
├── approval_gate/              # Pre-execution policy checks
│   ├── policy_engine.py        # Policy rule engine
│   ├── request_parser.py       # Structured request parsing
│   ├── evidence_contract.py    # Evidence contract generator
│   └── validators/             # Validation modules
│       ├── domain.py           # Domain constraints
│       ├── regulatory.py       # Regulatory compliance (SR 11-7)
│       └── scenario.py         # Scenario coherence checks
│
├── reasoning/                  # Evidence-Grounded Reasoning Engine
│   ├── engine.py               # Main reasoning engine (~1500 lines)
│   │   ├── Multi-pass table extraction
│   │   ├── Tool-calling for calculations
│   │   ├── Answer format rules
│   │   └── Layer 0 auto-correction integration
│   ├── chain_of_evidence/      # Chain-of-evidence tracking
│   │   ├── chain.py            # Evidence chain management
│   │   └── step.py             # Reasoning step types
│   ├── gates/                  # Layer 1 & 2 guardrails
│   │   ├── layer1_local.py     # Lightweight per-step checks
│   │   └── layer2_stage.py     # Stage-critical checkpoints
│   ├── extraction/
│   │   └── table_parser.py     # Structured table extraction
│   ├── citations/
│   │   ├── citation.py         # Citation objects
│   │   └── formatter.py        # Citation formatting
│   └── prompt_builder.py       # Dynamic prompt construction
│
├── routing/                    # Three-Layer Correction Pipeline
│   ├── layer0_checks.py        # Type/unit/sign/range detection + AUTO-CORRECTION
│   │   ├── PROPORTION_KEYWORDS detection
│   │   ├── ABSOLUTE_CHANGE_PATTERNS detection
│   │   ├── _strip_percentage_symbol() auto-fix
│   │   ├── _scale_to_proportion() auto-fix
│   │   ├── _flip_sign() auto-fix
│   │   └── _compute_confidence() for fast-path routing
│   └── layer1.py               # Formula detection + recomputation
│       ├── Formula type detection (percentage_change, absolute_change, etc.)
│       ├── Operand extraction from reasoning text
│       └── Recomputation verification
│
├── correction/                 # Correction utilities
│   └── layer0_autofix.py       # Auto-correction helpers
│
├── verification_gate/          # Post-execution verification
│   ├── gate.py                 # Main verification gate with FAST-PATH
│   │   ├── Layer 0/1 integration
│   │   ├── Fast-path for high-confidence answers
│   │   └── Hybrid verifier orchestration
│   ├── checkers/               # Verification checkers
│   │   ├── grounding.py        # Evidence grounding check
│   │   ├── scenario.py         # Scenario consistency
│   │   └── traceability.py     # Run traceability
│   ├── verifiers/              # Hybrid verifiers
│   │   ├── rule_based.py       # Rule-based checks
│   │   ├── retrieval.py        # Retrieval verification
│   │   └── llm_consistency.py  # LLM self-consistency
│   ├── numeric_checker.py      # Numeric validation
│   └── retry/                  # Retry logic
│       └── handler.py
│
├── retrieval/                  # Evidence retrieval
│   ├── hybrid.py               # Hybrid retrieval (dense + sparse)
│   └── query_builder.py        # Query construction
│
├── data/                       # Data loading & processing
│   ├── loaders/
│   │   ├── finqa.py            # FinQA dataset loader
│   │   ├── tatqa.py            # TAT-QA dataset loader
│   │   └── sec_filings.py      # SEC filings loader
│   ├── unified.py              # Unified sample format
│   ├── processors/             # Data processors
│   │   ├── table_parser.py
│   │   ├── text_extractor.py
│   │   └── section_splitter.py
│   └── index/
│       ├── corpus_builder.py
│       └── evidence_store.py
│
├── evaluation/                 # Evaluation framework
│   ├── metrics/
│   │   ├── grounding_accuracy.py
│   │   ├── hallucination_rate.py
│   │   ├── transparency_score.py
│   │   ├── auditability.py
│   │   └── run_id_fidelity.py
│   ├── benchmark/
│   │   └── finbound_bench.py
│   └── pipeline.py
│
├── tasks/                      # Task family implementations
│   ├── f1_ground_truth.py      # F1: Financial Ground-Truth Reasoning
│   ├── f2_retrieval.py         # F2: Long-Context Retrieval
│   ├── f3_explanation.py       # F3: Explanation Verification
│   ├── f4_scenario.py          # F4: Scenario Consistency
│   └── executor.py             # Task executor
│
├── tracking/                   # MLflow integration
│   └── mlflow_logger.py        # Run logging & reproducibility
│
├── tools/
│   └── calculator.py           # Deterministic calculator tool
│
├── utils/
│   ├── answer_normalizer.py    # Answer normalization
│   ├── numeric_matcher.py      # Number extraction
│   ├── rate_limiter.py         # API rate limiting
│   └── logging_config.py
│
├── types.py                    # Type definitions
└── core.py                     # Core pipeline orchestration
```

### 2.1 Three-Layer Correction Pipeline (Key Innovation)

The correction pipeline progressively validates and corrects answers:

```
Layer 0 (Cheap Checks)     Layer 1 (Formula KB)       Layer 2 (LLM Extraction)
        ↓                         ↓                          ↓
   Type/Unit/Sign          Formula Detection          Complex Table Reasoning
   Range Sanity            Operand Extraction         Multi-hop Verification
   AUTO-CORRECTION         Recomputation              LLM-guided Re-extraction
        ↓                         ↓                          ↓
   Fast-Path Exit?         Confidence Check           Final Answer
```

#### Layer 0: Type/Unit/Sign Detection + Auto-Correction
- **Detection**: Type mismatch, unit ambiguity, sign errors, range violations
- **Auto-Correction**:
  - Strip % symbol for absolute questions
  - Scale proportion (0.95 ↔ 95%)
  - Flip sign when direction is clear
- **Fast-Path**: High-confidence answers skip Layer 1/2 (reduces latency)

#### Layer 1: Formula Detection + Recomputation
- Detect formula type from question (percentage_change, absolute_change, etc.)
- Extract operands from reasoning text
- Recompute answer independently
- Flag discrepancies for Layer 2

#### Layer 2: LLM-Guided Extraction (Future)
- For complex tables requiring multi-hop reasoning
- Focused extraction prompts
- Multi-pass consensus voting

### 2.2 Approval Gate (Pre-execution Assurance)

```
User Request → Pre-checks (toxicity / unsupported ops)
→ Structured Task Parser
→ Policy Rules Engine
→ Evidence Contract Generator
→ Approval Verdict
→ (If Pass) → Evidence-Grounded Reasoning Engine
```

#### 2.2.1 Structured Request Parsing
E.g. the user asks: "Summarize how a 2% interest rate increase impacts our Q4 performance."

Policy engine transforms it to structured request:
```json
{
  "scenario": "interest_rate_increase",
  "magnitude": 0.02,
  "period": "Q4",
  "required_evidence": ["10-K interest expense", "debt footnotes"],
  "disallowed": ["predict future", "invent numbers"]
}
```

#### 2.2.2 Policy Compliance Checking
- ✔ Required fields completion
- ✔ Regulatory constraints (SR 11-7)
- ✔ Scenario coherence
- ✔ Domain constraints

#### 2.2.3 Evidence Contract Generation
```yaml
Evidence Contract:
- From: 10-K (Item 7)
- Section: Interest Expense
- Table: Consolidated Statements
- Required fields: Interest expense YoY change, Weighted avg borrowing rate
- Forbidden: invented numeric estimates
```

### 2.3 Evidence-Grounded Reasoning Engine

**Key Components:**
- Multi-pass table extraction (3 passes with voting)
- Tool-calling for deterministic calculations
- Chain-of-evidence tracking
- Layer 1 guardrails (per-step constraints)
- Layer 2 stage gates (checkpoints)

**Answer Format Rules:**
- Percentage formatting for percentage questions
- Ratio scaling (0.18 → 18.0 for ratio questions)
- Sign preservation for change questions
- Proportion handling (keep 0-1 scale)

### 2.4 Verification Gate

**Hybrid Verifier Components:**
- Rule-based verifier (citation format, accounting identity)
- Retrieval verifier (evidence existence)
- LLM verifier (reasoning consistency)
- Numeric checker (calculation validation)

**Fast-Path Optimization:**
- High-confidence Layer 0 results skip expensive Layer 1/LLM verification
- Reduces latency for "easy" questions
- Controlled by `FINBOUND_FAST_PATH_VERIFICATION` env var

---

## 3. Dataset Setup

### 3.1 FinQA
- Table + financial text reasoning
- Requires multi-step arithmetic reasoning
- Requires table citation
- **Use case**: Grounding accuracy evaluation

### 3.2 TAT-QA
- Table-plus-text LLM reasoning
- Multi-hop arithmetic questions
- Financial relationships (profit, YoY growth, ratio)
- **Use case**: Reasoning + numeric hallucination detection

### 3.3 SEC Filings (10-K, 10-Q)
Two tasks:
- **Task A**: Financial Evidence Retrieval (query → find correct paragraph/table)
- **Task B**: Scenario Narrative Consistency (macro scenario → explain impacted items)

---

## 4. Task Families (FinBound-Bench v1)

### Task Family F1: Financial Ground-Truth Reasoning
**Datasets**: FinQA + TAT-QA (arithmetic subset)

**Requirements**:
- Reasoning must be based on real numbers & citations
- No hallucinated values
- Citations must point to real table cells

**Metrics**: Grounding accuracy, numeric hallucination rate

**Current Results**: 81% accuracy, 97% grounding, 7% hallucination

### Task Family F2: Long-Context Retrieval Consistency
**Datasets**: TAT-QA (table-text subset)

Tests whether the model stably cites correct paragraphs in 50-200 page documents.

**Metrics**: Retrieval recall, citation correctness, interpretive drift

### Task Family F3: Explanation Verification
**Datasets**: TAT-QA (span/multi-span subset)

Each explanation must include:
- Cited paragraphs
- Logical chain
- Evidence hashes

**Metrics**: Explanation faithfulness, evidence consistency score

### Task Family F4: Scenario Consistency Checking
**Datasets**: TAT-QA (arithmetic + scale subset)

Given a scenario (earnings drop, interest rate shock, credit spread widening), LLM explains which financial items are affected.

Verification gate checks:
- Correct financial sections cited
- No invented dependencies
- Numbers from factual sources
- Stable across sampling

**Metrics**: Scenario coherence, volatility across seeds, hallucination rate

---

## 5. Evaluation Metrics

### 5.1 Grounding Accuracy (GA)
Are cited paragraphs/cells correct? FinQA/TAT-QA have gold evidence labels.

### 5.2 Hallucination Rate (HR)
Types:
- Numeric hallucination
- Financial term hallucination
- Accounting classification hallucination
- Scenario effect hallucination

### 5.3 Transparency Score (TS)
Checks for:
- Citations
- Evidence hashes
- Run logs
- Reasoning trace

Scored 0-1 following RAIRAB-style evaluation.

### 5.4 Auditability Metrics (AM)
Checks:
- Input reproducibility
- Retrieval reproducibility
- Evidence hash match
- Deterministic replay

### 5.5 Run-ID Fidelity
Validates:
- Run-ID is queryable
- Artifacts exist
- Parameters are logged

---

## 6. Current Results

| Model | Accuracy | GA↑ | HR↓ | TS↑ | AM↑ |
|-------|----------|-----|-----|-----|-----|
| GPT-4 baseline | - | 0.60 | 0.42 | 0.12 | 0.20 |
| RAG baseline | 78% | 0.74 | 0.30 | 0.32 | 0.35 |
| **FinBound (current)** | **81%** | **0.97** | **0.07** | **0.99** | **1.00** |
| FinBound (target) | 90%+ | 0.98 | 0.05 | 0.99 | 1.00 |

---

## 7. Key Contributions

1. **Three-Layer Correction Pipeline**: Progressive validation and auto-correction
2. **Fast-Path Routing**: Reduced latency for high-confidence answers
3. **FinBound-Bench**: Four task families for financial AI evaluation
4. **Evidence-Grounded Reasoning**: Chain-of-evidence with structured citations
5. **Auditability Framework**: Full reproducibility via MLflow integration