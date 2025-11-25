# FinBound Project Structure

## Recommended Directory Layout

```
finbound/
├── README.md
├── LICENSE
├── MILESTONES.md
├── CONTRIBUTING.md
├── .gitignore
├── .env.example
│
├── setup.py                          # Package setup
├── pyproject.toml                    # Poetry/modern Python packaging
├── requirements.txt                  # Core dependencies
├── requirements-dev.txt              # Development dependencies
│
├── docker/
│   ├── Dockerfile                    # Production container
│   ├── Dockerfile.dev                # Development container
│   └── docker-compose.yml            # Multi-service orchestration
│
├── .github/
│   ├── workflows/
│   │   ├── tests.yml                 # CI/CD for tests
│   │   ├── lint.yml                  # Code quality checks
│   │   └── publish.yml               # Package publishing
│   └── ISSUE_TEMPLATE/
│
├── config/
│   ├── approval_gate.yaml            # Approval gate policies
│   ├── verification_gate.yaml        # Verification rules
│   ├── models.yaml                   # LLM configurations
│   ├── datasets.yaml                 # Dataset configurations
│   └── experiments/                  # Experiment configs
│       ├── baseline_gpt4.yaml
│       ├── baseline_rag.yaml
│       └── finbound_full.yaml
│
├── data/                             # Data directory (gitignored)
│   ├── raw/
│   │   ├── finqa/
│   │   ├── tatqa/
│   │   └── sec_filings/
│   ├── processed/
│   │   ├── evidence_corpus/
│   │   ├── indexed/
│   │   └── embeddings/
│   └── results/
│       ├── baselines/
│       └── finbound/
│
├── finbound/                         # Main package
│   ├── __init__.py
│   ├── __version__.py
│   ├── config.py                     # Configuration loader
│   ├── constants.py                  # Global constants
│   ├── utils.py                      # Utility functions
│   │
│   ├── approval_gate/                # Milestone 2
│   │   ├── __init__.py
│   │   ├── request_parser.py         # Parse user requests
│   │   ├── policy_engine.py          # Policy checking
│   │   ├── evidence_contract.py      # Generate evidence contracts
│   │   └── validators/
│   │       ├── __init__.py
│   │       ├── regulatory.py         # SR 11-7, Basel checks
│   │       ├── scenario.py           # Scenario coherence
│   │       └── domain.py             # Domain constraints
│   │
│   ├── data/                         # Milestone 3
│   │   ├── __init__.py
│   │   ├── loaders/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Base loader interface
│   │   │   ├── finqa.py             # FinQA loader
│   │   │   ├── tatqa.py             # TAT-QA loader
│   │   │   └── sec_filings.py       # SEC EDGAR API
│   │   ├── processors/
│   │   │   ├── __init__.py
│   │   │   ├── table_parser.py      # Financial table parsing
│   │   │   ├── text_extractor.py    # Document text extraction
│   │   │   ├── section_splitter.py  # 10-K/10-Q section split
│   │   │   └── normalizer.py        # Data normalization
│   │   ├── index/
│   │   │   ├── __init__.py
│   │   │   ├── corpus_builder.py    # Build evidence corpus
│   │   │   ├── evidence_store.py    # Evidence storage/retrieval
│   │   │   └── embeddings.py        # Vector embeddings
│   │   └── schemas/
│   │       ├── finqa.py             # FinQA data schemas
│   │       ├── tatqa.py             # TAT-QA data schemas
│   │       └── sec.py               # SEC filing schemas
│   │
│   ├── reasoning/                    # Milestone 4
│   │   ├── __init__.py
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── retriever.py         # Evidence retriever
│   │   │   ├── generator.py         # LLM generation
│   │   │   ├── ranker.py            # Rerank retrieved docs
│   │   │   └── prompt_builder.py    # Prompt construction
│   │   ├── chain_of_evidence/
│   │   │   ├── __init__.py
│   │   │   ├── step.py              # Reasoning step class
│   │   │   ├── chain.py             # Chain of reasoning
│   │   │   ├── tracker.py           # Track evidence flow
│   │   │   └── constraints.py       # Step constraints
│   │   ├── gates/
│   │   │   ├── __init__.py
│   │   │   ├── layer1_local.py      # Lightweight local checks
│   │   │   └── layer2_stage.py      # Stage-critical gates
│   │   ├── citations/
│   │   │   ├── __init__.py
│   │   │   ├── citation.py          # Citation data structure
│   │   │   ├── formatter.py         # Citation formatting
│   │   │   └── validator.py         # Citation validation
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── openai_client.py     # OpenAI API wrapper
│   │       ├── anthropic_client.py  # Anthropic API wrapper
│   │       └── base.py              # Base LLM interface
│   │
│   ├── verification_gate/            # Milestone 5
│   │   ├── __init__.py
│   │   ├── gate.py                  # Main verification gate
│   │   ├── verifiers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Base verifier
│   │   │   ├── rule_based.py        # Rule-based checks
│   │   │   ├── retrieval.py         # Corpus verification
│   │   │   └── llm_consistency.py   # LLM self-consistency
│   │   ├── checkers/
│   │   │   ├── __init__.py
│   │   │   ├── grounding.py         # Grounding checker
│   │   │   ├── scenario.py          # Scenario consistency
│   │   │   ├── traceability.py      # Trace validation
│   │   │   ├── accounting.py        # Accounting identity checks
│   │   │   └── citation.py          # Citation verification
│   │   ├── audit/
│   │   │   ├── __init__.py
│   │   │   ├── logger.py            # Audit logging
│   │   │   ├── replay.py            # Deterministic replay
│   │   │   └── hasher.py            # Evidence hashing
│   │   └── retry/
│   │       ├── __init__.py
│   │       └── handler.py           # Retry mechanism
│   │
│   ├── tasks/                        # Milestone 6
│   │   ├── __init__.py
│   │   ├── base.py                  # Base task interface
│   │   ├── f1_ground_truth.py       # F1: Ground-truth reasoning
│   │   ├── f2_retrieval.py          # F2: Long-context retrieval
│   │   ├── f3_explanation.py        # F3: Explanation verification
│   │   ├── f4_scenario.py           # F4: Scenario consistency
│   │   ├── executor.py              # Task executor
│   │   └── registry.py              # Task registry
│   │
│   ├── evaluation/                   # Milestone 7
│   │   ├── __init__.py
│   │   ├── metrics/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Base metric
│   │   │   ├── grounding_accuracy.py
│   │   │   ├── hallucination_rate.py
│   │   │   ├── transparency_score.py
│   │   │   ├── auditability.py
│   │   │   └── reproducibility.py
│   │   ├── benchmark/
│   │   │   ├── __init__.py
│   │   │   ├── finbound_bench.py    # Main benchmark
│   │   │   ├── task_configs/        # Task YAML configs
│   │   │   └── scoring.py           # Scoring logic
│   │   ├── pipeline.py              # Evaluation pipeline
│   │   └── analyzer.py              # Results analysis
│   │
│   ├── tracking/                     # MLflow integration
│   │   ├── __init__.py
│   │   ├── mlflow_client.py         # MLflow wrapper
│   │   ├── experiment.py            # Experiment tracking
│   │   ├── artifacts.py             # Artifact logging
│   │   └── reproducibility.py       # Reproducibility utils
│   │
│   └── cli/                          # Command-line interface
│       ├── __init__.py
│       ├── main.py                  # Main CLI entry
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── run.py               # Run tasks
│       │   ├── eval.py              # Evaluate models
│       │   ├── benchmark.py         # Run benchmarks
│       │   └── serve.py             # API server
│       └── utils.py
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── unit/
│   │   ├── approval_gate/
│   │   ├── reasoning/
│   │   ├── verification_gate/
│   │   ├── data/
│   │   └── evaluation/
│   ├── integration/
│   │   ├── test_end_to_end.py
│   │   ├── test_pipeline.py
│   │   └── test_benchmark.py
│   └── fixtures/
│       ├── sample_requests.json
│       ├── sample_evidence.json
│       └── mock_responses.json
│
├── scripts/                          # Utility scripts
│   ├── setup_data.sh                # Download datasets
│   ├── run_baselines.py             # Run baseline experiments
│   ├── run_finbound.py              # Run FinBound experiments
│   ├── analyze_results.py           # Analyze experiment results
│   ├── generate_tables.py           # Generate paper tables
│   └── export_figures.py            # Export paper figures
│
├── notebooks/                        # Jupyter notebooks
│   ├── 01_data_exploration.ipynb
│   ├── 02_approval_gate_demo.ipynb
│   ├── 03_reasoning_engine_demo.ipynb
│   ├── 04_verification_gate_demo.ipynb
│   ├── 05_evaluation_analysis.ipynb
│   └── 06_results_visualization.ipynb
│
├── docs/                             # Documentation
│   ├── index.md
│   ├── getting_started.md
│   ├── architecture.md
│   ├── api/
│   │   ├── approval_gate.md
│   │   ├── reasoning.md
│   │   ├── verification_gate.md
│   │   └── evaluation.md
│   ├── tutorials/
│   │   ├── basic_usage.md
│   │   ├── custom_tasks.md
│   │   └── extending_finbound.md
│   └── paper/
│       ├── methodology.md
│       ├── experiments.md
│       └── results.md
│
├── experiments/                      # Experiment results (gitignored)
│   ├── baselines/
│   │   ├── gpt4/
│   │   └── rag/
│   ├── finbound/
│   │   ├── full/
│   │   └── ablations/
│   └── analysis/
│       ├── tables/
│       └── figures/
│
├── paper/                            # Research paper
│   ├── main.tex
│   ├── sections/
│   │   ├── abstract.tex
│   │   ├── introduction.tex
│   │   ├── related_work.tex
│   │   ├── methodology.tex
│   │   ├── experiments.tex
│   │   ├── results.tex
│   │   └── conclusion.tex
│   ├── figures/
│   └── tables/
│
└── mlruns/                           # MLflow tracking (gitignored)
    └── .gitkeep
```

## Key Design Principles

### 1. Modularity
- Each component (Approval Gate, Reasoning Engine, Verification Gate) is independent
- Clear interfaces between components
- Easy to swap implementations (e.g., different LLM providers)

### 2. Configurability
- All policies, rules, and parameters in YAML configs
- No hardcoded values in core logic
- Easy to customize for different use cases

### 3. Reproducibility
- MLflow tracks all experiments
- Run IDs for every execution
- Evidence hashes for traceability
- Deterministic replay capability

### 4. Extensibility
- Plugin architecture for new verifiers
- Task registry for custom tasks
- Metric system for new evaluation measures

### 5. Testability
- High test coverage (>90%)
- Unit tests for all components
- Integration tests for pipelines
- Mock data for rapid testing

## Environment Variables

```bash
# .env.example

# LLM API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# MLflow Configuration
MLFLOW_TRACKING_URI=http://localhost:5000
MLFLOW_EXPERIMENT_NAME=finbound

# Data Directories
DATA_DIR=/path/to/data
CACHE_DIR=/path/to/cache
RESULTS_DIR=/path/to/results

# SEC EDGAR API
SEC_USER_AGENT=your_name your_email
SEC_API_RATE_LIMIT=10  # requests per second

# Model Configuration
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4-turbo
MAX_TOKENS=4096
TEMPERATURE=0.0  # Deterministic

# Verification Settings
ENABLE_APPROVAL_GATE=true
ENABLE_VERIFICATION_GATE=true
ENABLE_AUDIT_LOGGING=true
MAX_RETRIES=3

# Performance
BATCH_SIZE=32
NUM_WORKERS=4
USE_GPU=false
```

## Development Workflow

### 1. Initial Setup
```bash
# Clone repository
git clone https://github.com/yourusername/finbound.git
cd finbound

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt
pip install -e .

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Download datasets
bash scripts/setup_data.sh

# Start MLflow server
mlflow server --backend-store-uri sqlite:///mlflow.db --default-artifact-root ./mlruns
```

### 2. Development
```bash
# Run tests
pytest tests/ -v --cov=finbound

# Run linting
black finbound/ tests/
flake8 finbound/ tests/
mypy finbound/

# Run specific component tests
pytest tests/unit/approval_gate/ -v
```

### 3. Running Experiments
```bash
# Run baseline
python scripts/run_baselines.py --model gpt4 --dataset finqa

# Run FinBound
python scripts/run_finbound.py --config config/experiments/finbound_full.yaml

# Analyze results
python scripts/analyze_results.py --experiment finbound_v1
```

### 4. Building Documentation
```bash
cd docs/
mkdocs build
mkdocs serve  # Visit http://localhost:8000
```

## Continuous Integration

### GitHub Actions Workflows

**tests.yml**:
- Run on: Push, Pull Request
- Python versions: 3.10, 3.11, 3.12
- Steps: Install, Lint, Test, Coverage

**lint.yml**:
- Run on: Push, Pull Request
- Steps: black, flake8, mypy, isort

**publish.yml**:
- Run on: Release tag
- Steps: Build, Test, Publish to PyPI

## Docker Setup

### Development Container
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Install package
RUN pip install -e .

# Expose MLflow port
EXPOSE 5000

CMD ["bash"]
```

### Docker Compose
```yaml
version: '3.8'

services:
  finbound:
    build:
      context: .
      dockerfile: docker/Dockerfile.dev
    volumes:
      - .:/app
      - ./data:/app/data
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    depends_on:
      - mlflow

  mlflow:
    image: python:3.11-slim
    command: mlflow server --host 0.0.0.0 --port 5000
    ports:
      - "5000:5000"
    volumes:
      - ./mlruns:/mlruns
```

## Package Distribution

### PyPI Publishing
```bash
# Build package
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

### Installation
```bash
# From PyPI (when published)
pip install finbound

# From source
pip install git+https://github.com/yourusername/finbound.git

# Development mode
git clone https://github.com/yourusername/finbound.git
cd finbound
pip install -e ".[dev]"
```

---

## Next Actions

1. **Create repository** on GitHub/GitLab
2. **Set up project** with initial structure
3. **Configure CI/CD** pipelines
4. **Begin Milestone 1** implementation
5. **Document progress** in project tracking system
