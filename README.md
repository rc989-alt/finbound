# FinBound: A Verification-Gated AI Governance Framework

**FinBound** is a verification-gated AI governance framework for evidence-grounded financial reasoning, designed to ensure minimal hallucinations and complete auditability in financial AI applications.

## 🎯 Key Results

| Method | Accuracy ↑ | Grounding ↑ | Hallucination Rate ↓ | Transparency ↑ | Auditability ↑ |
|--------|-----------|------------|---------------------|----------------|----------------|
| **FinBound** | **81%** | **96%** | **10%** | **99%** | **100%** |
| GPT-4 Zero-shot | 61% | 89% | 14% | 0% | 0% |
| Claude Zero-shot | 61% | 90% | 15% | 0% | 0% |
| GPT-4 Few-shot | 60% | 92% | 16% | 0% | 0% |
| RAG No Verify | 60% | 94% | 14% | 0% | 0% |

**Key Achievement**: FinBound achieves **+20 percentage points accuracy** over baselines (81% vs 60-61%), with **96% grounding accuracy** and only **10% hallucination rate** while maintaining **100% auditability** - making it suitable for regulated financial environments where accuracy and transparency matter more than speed.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- OpenAI API key
- 16GB+ RAM

### Installation
```bash
git clone https://github.com/rc989-alt/finbound.git
cd finbound
pip install -r requirements.txt
pip install -e .
```

### Quick Example
```python
from finbound import FinBound

# Initialize FinBound
fb = FinBound(openai_api_key="your-key")

# Process a financial question with evidence
result = fb.process(
    question="What was the percentage change in revenue from 2018 to 2019?",
    evidence="Revenue was $100M in 2018 and $120M in 2019."
)

# Check results
print(f"Answer: {result.answer}")           # "20%"
print(f"Verified: {result.verified}")       # True
print(f"Citations: {result.citations}")     # ["Revenue was $100M in 2018..."]
print(f"Confidence: {result.confidence}")   # "high"
```

### Run Experiments
```bash
# Run on curated benchmark (100 samples)
python experiments/run_experiments.py --methods finbound --task F1 --curated

# Run with all baselines
python experiments/run_experiments.py --methods finbound gpt4_zeroshot rag_no_verify --task F1 --curated
```

## ⚡ Parallel Processing (v0.2.0)

FinBound v0.2.0 introduces parallel processing for **10x throughput improvement**.

### Performance Comparison

| Configuration | 100 Samples | Improvement |
|--------------|-------------|-------------|
| Sequential (v0.1) | ~30 min | baseline |
| Parallel 10x low_latency | ~3 min | **10x faster** |
| Parallel 20x ultra | ~1.5 min | **20x faster** |

### Quick Start - Parallel Processing

```python
from finbound.parallel import ParallelRunner

async with ParallelRunner(
    max_concurrent=10,           # Process 10 requests concurrently
    execution_mode="low_latency", # low_latency or ultra_low_latency
) as runner:
    results = await runner.run_batch(samples, task_family="F1")
    print(f"Processed {results.success_count} in {results.total_time_ms}ms")
```

### Execution Modes

| Mode | Per-Sample | Use Case |
|------|------------|----------|
| `normal` | ~17s | Full 3-pass verification, maximum accuracy |
| `low_latency` | ~6s | Single-pass verification, balanced |
| `ultra_low_latency` | ~3s | Minimal verification, maximum speed |

### Benchmark Script

```bash
# Quick test (10 samples)
python experiments/benchmark_latency.py --quick

# Full benchmark (100 samples, all modes)
python experiments/benchmark_latency.py --samples 100 --modes all
```

### Azure OpenAI Support

FinBound supports both OpenAI and Azure OpenAI. Configure via environment variables:

```bash
# Option 1: OpenAI
export OPENAI_API_KEY="sk-your-key"

# Option 2: Azure OpenAI
export AZURE_OPENAI_API_KEY="your-azure-key"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_DEPLOYMENT_GPT4O="gpt-4o"
export AZURE_OPENAI_DEPLOYMENT_GPT4O_MINI="gpt-4o-mini"
```

See `.env.example` for full configuration options.

## 🏗️ System Architecture

```
User Request
    ↓
┌─────────────────────────┐
│   APPROVAL GATE         │  Pre-execution validation
│  • Request Parser       │  - Validates request format
│  • Policy Engine        │  - Checks regulatory constraints
│  • Evidence Contract    │  - Specifies required evidence
└─────────┬───────────────┘
          ↓
┌─────────────────────────┐
│  REASONING ENGINE       │  Evidence-grounded reasoning
│  • RAG Pipeline         │  - Retrieves relevant evidence
│  • Chain-of-Evidence    │  - Tracks reasoning steps
│  • Multi-hop Reasoning  │  - Handles complex questions
└─────────┬───────────────┘
          ↓
┌─────────────────────────┐
│  VERIFICATION GATE      │  Post-execution verification
│  • Layer 0: Auto-Fix    │  - Format/scale corrections
│  • Layer 1: Recompute   │  - Deterministic verification
│  • Layer 2: LLM Verify  │  - Multi-pass consensus
│  • Hallucination Check  │  - Evidence grounding
└─────────┬───────────────┘
          ↓
    Verified Answer + Audit Trail
```

## 📊 Benchmark Results

### F1: Financial Ground-Truth Reasoning (100 curated samples)

**Curated benchmark**: 50 FinQA + 50 TAT-QA samples for balanced evaluation.

| Method | Accuracy | Avg Latency | Notes |
|--------|----------|-------------|-------|
| **FinBound Low-Latency v5** | **78%** | 10,911 ms | +8% over GPT-4 |
| GPT-4 Zero-Shot | 70% | ~2,152 ms | Baseline |
| FinBound FULL on GPT-4 Failures | 50% | ~15,000 ms | 15/30 recovered |

**Dataset Breakdown:**
| Dataset | Correct | Failed | Accuracy |
|---------|---------|--------|----------|
| FinQA (50) | 42 | 8 | 84% |
| TAT-QA (50) | 36 | 14 | 72% |
| **Total** | **78** | **22** | **78%** |

### Error Analysis (22 remaining failures)

| Error Category | Count | % of Failures |
|----------------|-------|---------------|
| Wrong calculation/formula | 6 | 27.3% |
| Sign error | 4 | 18.2% |
| Wrong interpretation | 3 | 13.6% |
| Close but wrong | 2 | 9.1% |
| Wrong values | 2 | 9.1% |
| Scale/format errors | 5 | 22.7% |

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [MILESTONES.md](MILESTONES.md) | Detailed milestone tracking |
| [MILESTONES_2.0.md](MILESTONES_2.0.md) | Correction architecture tasks |
| [purposal.md](purposal.md) | Research proposal |
| [docs/](docs/) | API documentation |

## 🎯 Research Questions

1. **RQ1**: Does a verification-gated reasoning workflow significantly reduce hallucinations and improve grounding accuracy in financial tasks compared to standard RAG?
   - **Answer**: Yes. FinBound achieves 97% grounding (vs 35% for RAG) and 9% hallucination rate (vs 20% for RAG).

2. **RQ2**: What is the latency–accuracy trade-off of FinBound under real-world financial constraints?
   - **Answer**: FinBound Low-Latency takes ~11s per query (vs ~2s for GPT-4 zero-shot) but provides complete auditability and verification. This trade-off is acceptable for regulated environments.

## 🎓 Key Innovations

1. **Three-Layer Verification**: Layer 0 (auto-fix) → Layer 1 (recompute) → Layer 2 (LLM consensus)
2. **Evidence Contracts**: Pre-execution specification of required evidence
3. **Multi-Pass Verification**: 3-pass consensus voting for complex calculations
4. **Formula Templates**: Deterministic recomputation for common financial formulas
5. **Complete Auditability**: Full audit trail with MLflow integration

## 📦 Project Structure

```
finbound/
├── approval_gate/          # Pre-execution validation
│   ├── request_parser.py
│   ├── policy_engine.py
│   └── evidence_contract.py
├── reasoning/              # Core reasoning engine
│   ├── engine.py           # Main reasoning orchestrator
│   ├── rag/                # Retrieval-augmented generation
│   └── chain_of_evidence/  # Evidence tracking
├── routing/                # Answer type detection & correction
│   └── layer0_checks.py    # Format/scale auto-corrections
├── verification_gate/      # Post-execution verification
│   ├── verifiers/
│   └── checkers/
├── parallel/               # Parallel processing (v0.2.0)
│   ├── runner.py           # ParallelRunner for concurrent execution
│   ├── rate_limiter.py     # AsyncRateLimiter for API throttling
│   └── batch_processor.py  # BatchProcessor for large workloads
├── utils/                  # Utilities
│   ├── openai_client.py    # OpenAI/Azure client factory
│   └── answer_normalizer.py
└── core.py                 # Main FinBound class

experiments/
├── run_experiments.py      # Experiment runner
├── benchmark_latency.py    # Latency benchmark script (v0.2.0)
├── eval_harness.py         # Evaluation framework
├── baselines/              # Baseline implementations
└── F1_result/              # Experiment results
```

## 🚀 Current Status

**Phase**: Milestone 3.0 (QuantLib Integration) Complete ✅
**Current Work**: Sign error fixes and TAT-QA optimization
**Latest Accuracy**: 78% (100 curated samples, F1 task) - **+8 pp over GPT-4 zero-shot**

### Completed Milestones
- [x] M1: Foundation & Infrastructure
- [x] M2: Approval Gate Implementation
- [x] M3: Data Pipeline Setup
- [x] M4: Evidence-Grounded Reasoning Engine
- [x] M5: Verification Gate Implementation
- [x] M6: Task Families Implementation
- [x] M7: Evaluation Metrics & Benchmark
- [x] M8: Baseline Experiments
- [x] M8.5: Accuracy Gap Analysis
- [x] M9: Enhanced Calculation Accuracy
- [x] M10: Grounding Optimization
- [x] M11: Multi-Pass Verification
- [x] M11.5: TAT-QA Improvements
- [x] M11.6: FinQA Improvements
- [x] M3.0: QuantLib Integration & Low-Latency Mode

### In Progress
- [ ] M3.1: Sign Error Fixes & TAT-QA Optimization
- [ ] M12: Paper Writing & Code Release

## 🤝 Contributing

Contributions welcome!

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

MIT License - See `LICENSE` file

## 📧 Contact

- **GitHub**: [@rc989-alt](https://github.com/rc989-alt)
- **Issues**: [GitHub Issues](https://github.com/rc989-alt/finbound/issues)

## 🙏 Acknowledgments

- **Datasets**: FinQA, TAT-QA, SEC EDGAR
- **Frameworks**: OpenAI, Anthropic, MLflow
- **Community**: Financial NLP research community

## 📖 Citation

```bibtex
@inproceedings{finbound2025,
  title={FinBound: A Verification-Gated AI Governance Framework for Evidence-Grounded Financial Reasoning},
  author={TBD},
  booktitle={Proceedings of ACL 2025},
  year={2025}
}
```

---

**Ready to build trustworthy AI for finance? Get started above! 🚀**
