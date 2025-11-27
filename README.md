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

### F1: Financial Ground-Truth Reasoning (100 samples)

**FinBound wins on 19 samples where ALL baselines failed** - demonstrating the power of tool-based calculations and multi-pass verification.

| Milestone | Accuracy | Grounding | Hallucination | Key Improvements |
|-----------|----------|-----------|---------------|------------------|
| **Current (M11.6)** | **81%** | **96%** | **10%** | All methods comparison |
| M10 | 91% | 98% | 3% | Grounding metric fix |
| M9 | 79% | 37% | 7% | Calculation improvements |
| M8.5 Baseline | 82% | 37% | 21% | Initial framework |

### Error Analysis (19 remaining failures)

| Error Category | Count | Description |
|----------------|-------|-------------|
| Calculation (moderate) | 5 | Multi-step calculation errors |
| Format (% vs absolute) | 4 | Percentage/absolute confusion |
| Sign error | 3 | Wrong sign on percentage changes |
| Other | 4 | Complex value interpretation |
| Scale (100x) | 2 | Off by factor of 100 |
| Calculation (close) | 2 | Within rounding tolerance |

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
   - **Answer**: FinBound takes ~19s per query (vs ~2s for baselines) but provides complete auditability and verification. This trade-off is acceptable for regulated environments.

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
├── utils/                  # Utilities
│   └── answer_normalizer.py
└── core.py                 # Main FinBound class

experiments/
├── run_experiments.py      # Experiment runner
├── eval_harness.py         # Evaluation framework
├── baselines/              # Baseline implementations
└── F1_result/              # Experiment results
```

## 🚀 Current Status

**Phase**: Milestone 11.6 Complete ✅
**Current Work**: Accuracy optimization and error analysis
**Latest Accuracy**: 81% (100 samples, F1 task) - **+20 pp over baselines**

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

### In Progress
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
