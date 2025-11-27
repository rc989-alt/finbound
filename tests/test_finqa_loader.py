from pathlib import Path

from finbound.data import FinQALoader

FIXTURE_DIR = Path("tests/fixtures")


def test_finqa_loader_reads_sample(tmp_path):
    dataset_dir = tmp_path / "finqa"
    dataset_dir.mkdir()
    (dataset_dir / "train.json").write_text(
        (FIXTURE_DIR / "finqa_sample.json").read_text(), encoding="utf-8"
    )

    loader = FinQALoader(dataset_dir=dataset_dir)
    sample = loader.load()

    assert sample.question.startswith("What happened")
    assert sample.table[0][0] == "Metric"
    assert sample.program_result is not None
