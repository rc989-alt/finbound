from dataclasses import dataclass

from finbound.tasks import F1GroundTruthTask, TaskExecutor, TaskResult
from finbound.types import EvidenceContext, EvidenceContract, FinBoundResult, PolicyVerdict, StructuredRequest, VerificationResult


@dataclass
class DummyResult:
    verified: bool = True


class DummyFinBound:
    def run_unified_sample(self, sample, task_family: str = "F1"):
        verification = VerificationResult(verified=True, issues=[], status="PASS")
        return FinBoundResult(
            answer="10",
            verified=True,
            citations=["dummy"],
            reasoning="dummy reasoning",
            policy_verdict=PolicyVerdict(approved=True),
            verification_result=verification,
            raw_model_output={"layer1_issues": [], "layer2_issues": []},
        )


def test_task_executor_runs_samples(tmp_path, monkeypatch):
    # Use fixture data for loader
    from pathlib import Path
    from finbound.data import FinQALoader

    fixture_dir = Path("tests/fixtures")
    dataset_dir = tmp_path / "finqa"
    dataset_dir.mkdir()
    (dataset_dir / "train.json").write_text((fixture_dir / "finqa_sample.json").read_text())

    task = F1GroundTruthTask(dataset_dir=str(dataset_dir), limit=1)
    executor = TaskExecutor(DummyFinBound())
    results = executor.run(task)

    assert len(results) == 1
    assert isinstance(results[0], TaskResult)
