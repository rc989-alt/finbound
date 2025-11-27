"""Tests for TAT-QA loader with actual dataset structure."""

import json
from pathlib import Path

from finbound.data import TATQALoader, TATQASample


def test_tatqa_loader_reads_sample(tmp_path):
    """Test TAT-QA loader with official dataset structure."""
    dataset_dir = tmp_path / "tatqa"
    dataset_dir.mkdir()

    # Create sample in official TAT-QA format
    sample_data = [
        {
            "table": {
                "uid": "tbl-001",
                "table": [
                    ["Metric", "Value"],
                    ["Revenue", "50"],
                ],
            },
            "paragraphs": [
                {"uid": "p1", "text": "The company reported revenue of 50 in Q1."}
            ],
            "questions": [
                {
                    "uid": "q-001",
                    "question": "What is the revenue?",
                    "answer": "50",
                    "answer_type": "span",
                    "scale": "",
                    "derivation": "",
                    "answer_from": "table",
                    "order": 1,
                }
            ],
        }
    ]

    (dataset_dir / "tatqa_dataset_train.json").write_text(
        json.dumps(sample_data), encoding="utf-8"
    )

    loader = TATQALoader(dataset_dir=dataset_dir)
    sample = loader.load()

    assert isinstance(sample, TATQASample)
    assert sample.question == "What is the revenue?"
    assert sample.answer == "50"
    assert sample.paragraphs == ["The company reported revenue of 50 in Q1."]
    assert sample.table[1][0] == "Revenue"
    assert sample.answer_type == "span"
    assert sample.answer_from == "table"
