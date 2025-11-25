# FinBound Quick Start Guide

## TL;DR
This project implements **FinBound**, a verification-gated AI governance framework for trustworthy financial reasoning. Start here to get up and running in 30 minutes.

---

## Prerequisites

**Required**:
- Python 3.10 or higher
- Git
- 16GB+ RAM recommended

**API Keys** (at least one):
- OpenAI API key (for GPT-4 experiments)
- Anthropic API key (alternative/optional)

---

## 30-Minute Quick Start

### Step 1: Clone & Setup (5 minutes)

```bash
# Clone the repository
git clone https://github.com/yourusername/finbound.git
cd finbound

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Copy environment template
cp .env.example .env
```

### Step 2: Configure Environment (5 minutes)

Edit `.env` file:
```bash
# Required: Add your API key
OPENAI_API_KEY=sk-your-key-here

# Optional: Customize paths
DATA_DIR=./data
RESULTS_DIR=./experiments
MLFLOW_TRACKING_URI=./mlruns
```

### Step 3: Download Sample Data (10 minutes)

```bash
# Download FinQA sample (small subset for testing)
python scripts/download_sample_data.py --dataset finqa --size small

# This downloads ~100 examples to data/raw/finqa/
```

### Step 4: Run First Example (10 minutes)

```bash
# Run a simple financial QA task
python examples/simple_query.py

# This will:
# 1. Parse the request through Approval Gate
# 2. Retrieve evidence and generate reasoning
# 3. Verify the output through Verification Gate
# 4. Log results to MLflow
```

**Expected Output**:
```
✅ Approval Gate: PASSED
📊 Evidence Retrieved: 3 relevant items
🧠 Reasoning Generated: 4 steps
✅ Verification Gate: PASSED
   - Grounding: ✓
   - Citations: ✓
   - Hallucinations: None detected

Result: The company's interest expense increased by $2.3M...
MLflow Run ID: abc123def456
```

### Step 5: View Results in MLflow

```bash
# Start MLflow UI
mlflow ui

# Visit http://localhost:5000 in browser
```

---

## Next Steps

### Option A: Run Sample Experiments (1 hour)

```bash
# Run baseline comparison
python scripts/run_comparison.py \
  --baselines gpt4 rag \
  --finbound \
  --dataset finqa \
  --sample-size 50

# View comparison report
python scripts/generate_report.py --experiment latest
```

### Option B: Interactive Tutorial (1 hour)

```bash
# Launch Jupyter
jupyter notebook

# Open notebooks/01_getting_started.ipynb
```

### Option C: Deep Dive Development (ongoing)

Follow the detailed [ROADMAP.md](ROADMAP.md) and [MILESTONES.md](MILESTONES.md).

---

## Project Structure Overview

```
finbound/
├── finbound/              # Main package
│   ├── approval_gate/     # Request validation
│   ├── reasoning/         # RAG + chain-of-evidence
│   ├── verification_gate/ # Output verification
│   ├── data/             # Dataset loaders
│   ├── evaluation/       # Metrics & benchmark
│   └── tracking/         # MLflow integration
├── tests/                # Test suite
├── scripts/              # Utility scripts
├── notebooks/            # Jupyter tutorials
├── config/               # YAML configurations
└── docs/                 # Documentation
```

---

## Common Commands

### Development
```bash
# Run all tests
pytest tests/ -v

# Run specific component tests
pytest tests/unit/approval_gate/ -v

# Code formatting
black finbound/ tests/
flake8 finbound/

# Type checking
mypy finbound/
```

### Experiments
```bash
# Run baseline (GPT-4 only)
python scripts/run_baselines.py --model gpt4

# Run FinBound full pipeline
python scripts/run_finbound.py --config config/finbound_full.yaml

# Run ablation (no verification gate)
python scripts/run_finbound.py --config config/ablation_no_verification.yaml
```

### Data Management
```bash
# Download all datasets (large, ~10GB)
python scripts/download_datasets.py --all

# Download specific dataset
python scripts/download_datasets.py --dataset tatqa

# Preprocess data
python scripts/preprocess_data.py --dataset finqa --output data/processed/
```

---

## Minimal Working Example

Here's a complete example you can run immediately:

```python
# examples/minimal_example.py

from finbound import FinBound
from finbound.data import FinQALoader

# Initialize FinBound
fb = FinBound(
    config_path="config/finbound_full.yaml",
    api_key="your-openai-key"
)

# Load a sample question
loader = FinQALoader("data/raw/finqa")
sample = loader.load_sample(index=0)

# Run through FinBound pipeline
result = fb.run(
    query=sample.question,
    context=sample.context,
    evidence=sample.table
)

# Check results
print(f"Answer: {result.answer}")
print(f"Grounding Score: {result.grounding_accuracy}")
print(f"Hallucinations: {result.hallucination_count}")
print(f"Verification: {'PASSED' if result.verified else 'FAILED'}")

# Access full audit trail
print(f"MLflow Run ID: {result.run_id}")
print(f"Evidence Citations: {len(result.citations)}")
```

---

## Configuration Quick Reference

### Minimal Configuration (`config/minimal.yaml`)

```yaml
approval_gate:
  enabled: true
  validators:
    - regulatory
    - scenario_coherence

reasoning:
  model: gpt-4-turbo
  temperature: 0.0
  max_tokens: 2048
  retrieval:
    top_k: 5
    method: hybrid  # dense + bm25

verification_gate:
  enabled: true
  verifiers:
    - rule_based
    - retrieval
  auto_retry: true
  max_retries: 2

mlflow:
  experiment_name: finbound_minimal
  tracking_uri: ./mlruns
```

### Full Configuration (`config/finbound_full.yaml`)

See `config/finbound_full.yaml` for all options.

---

## Troubleshooting

### Issue: "OpenAI API key not found"
**Solution**: Set `OPENAI_API_KEY` in `.env` file or export as environment variable:
```bash
export OPENAI_API_KEY=sk-your-key-here
```

### Issue: "Dataset not found"
**Solution**: Download datasets first:
```bash
python scripts/download_sample_data.py --dataset finqa
```

### Issue: "MLflow server not accessible"
**Solution**: Check MLflow is running:
```bash
mlflow ui --host 0.0.0.0 --port 5000
```

### Issue: "Out of memory"
**Solution**: Reduce batch size in config:
```yaml
reasoning:
  batch_size: 8  # Reduce from 32
```

### Issue: "Tests failing"
**Solution**: Ensure all dependencies installed:
```bash
pip install -r requirements-dev.txt
pytest tests/ -v --log-cli-level=DEBUG
```

---

## Docker Quick Start (Alternative)

Prefer Docker? Use this instead:

```bash
# Build image
docker build -t finbound:latest .

# Run container
docker run -it \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/mlruns:/app/mlruns \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  finbound:latest

# Inside container
python examples/simple_query.py
```

---

## Development Workflow

### Daily Development Loop

1. **Pull latest changes**
   ```bash
   git pull origin main
   ```

2. **Create feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

3. **Write code**
   - Follow structure in `PROJECT_STRUCTURE.md`
   - Add tests for new features
   - Update docstrings

4. **Test locally**
   ```bash
   pytest tests/ -v
   black finbound/
   ```

5. **Commit and push**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   git push origin feature/my-feature
   ```

6. **Create pull request**
   - GitHub/GitLab UI
   - Wait for CI/CD checks
   - Request review

---

## Key Files to Read

**Start here**:
1. `README.md` - Project overview
2. `QUICK_START.md` - This file
3. `purposal.md` - Research proposal
4. `MILESTONES.md` - Development milestones

**For developers**:
5. `PROJECT_STRUCTURE.md` - Code organization
6. `ROADMAP.md` - Week-by-week implementation plan
7. `docs/architecture.md` - System architecture
8. `docs/api/` - API documentation

**For researchers**:
9. `paper/main.tex` - Research paper
10. `notebooks/05_evaluation_analysis.ipynb` - Results analysis

---

## Getting Help

### Documentation
- **API Docs**: `docs/api/`
- **Tutorials**: `notebooks/`
- **Architecture**: `docs/architecture.md`

### Community
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: finbound-dev@yourdomain.com

### Support
- **Bug reports**: Use issue template
- **Feature requests**: Use feature template
- **Questions**: Use discussions

---

## Contribution Guidelines

We welcome contributions! See `CONTRIBUTING.md` for:
- Code style guide
- Testing requirements
- Pull request process
- Community guidelines

**Quick contribution checklist**:
- [ ] Tests pass (`pytest tests/`)
- [ ] Code formatted (`black finbound/`)
- [ ] Docstrings added
- [ ] Type hints included
- [ ] Changelog updated
- [ ] PR description complete

---

## License

This project is licensed under the Apache 2.0 License - see `LICENSE` file.

---

## Citation

If you use FinBound in your research, please cite:

```bibtex
@inproceedings{finbound2025,
  title={FinBound: A Verification-Gated AI Governance Framework for Evidence-Grounded Financial Reasoning},
  author={Your Name and Collaborators},
  booktitle={Proceedings of ACL 2025},
  year={2025}
}
```

---

## What's Next?

You've completed the quick start! Here are suggested next steps:

### For Users
✅ Run example experiments
✅ Explore Jupyter notebooks
✅ Try your own financial questions

### For Developers
✅ Review `ROADMAP.md` for implementation plan
✅ Pick a milestone from `MILESTONES.md`
✅ Start with Milestone 1 (Foundation)

### For Researchers
✅ Read the full proposal in `purposal.md`
✅ Review evaluation metrics
✅ Plan experiments

---

## Quick Reference Card

| Task | Command |
|------|---------|
| Install | `pip install -e .` |
| Test | `pytest tests/` |
| Format | `black finbound/` |
| Run example | `python examples/simple_query.py` |
| Start MLflow | `mlflow ui` |
| Run baseline | `python scripts/run_baselines.py --model gpt4` |
| Run FinBound | `python scripts/run_finbound.py` |
| Generate report | `python scripts/generate_report.py` |

---

**Ready to build trustworthy AI for finance? Let's go! 🚀**

For detailed guidance, see:
- Implementation: [ROADMAP.md](ROADMAP.md)
- Milestones: [MILESTONES.md](MILESTONES.md)
- Structure: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)
