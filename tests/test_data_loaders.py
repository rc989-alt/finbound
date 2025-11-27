"""Tests for data loaders and unified sample conversion."""

import pytest

from finbound.data import (
    FinQALoader,
    FinQASample,
    TATQASample,
    UnifiedSample,
    to_unified,
)


class TestFinQALoader:
    """Tests for FinQA loader."""

    def test_loader_initializes(self):
        loader = FinQALoader(dataset_dir="data/raw/FinQA/dataset", split="train")
        assert loader.split == "train"

    def test_load_sample(self):
        loader = FinQALoader(dataset_dir="data/raw/FinQA/dataset", split="train")
        sample = loader.load(0)
        assert isinstance(sample, FinQASample)
        assert sample.question
        assert sample.answer


class TestUnifiedSample:
    """Tests for unified sample conversion."""

    def test_from_finqa(self):
        finqa_sample = FinQASample(
            question="What is the revenue?",
            answer="100 million",
            context_snippets=["Revenue was $100 million in Q4."],
            evidence_texts=["Table shows revenue figures."],
            table=[["Year", "Revenue"], ["2023", "$100M"]],
            steps=[],
            program="",
            program_result=None,
            id="test-001",
            filename="ACME/2023/page_1.pdf",
            issuer="ACME",
        )

        unified = to_unified(finqa_sample)

        assert isinstance(unified, UnifiedSample)
        assert unified.source == "finqa"
        assert unified.question == "What is the revenue?"
        assert unified.gold_answer == "100 million"
        assert len(unified.text_evidence) == 2
        assert unified.has_table
        assert unified.evidence_type == "table-text"

    def test_from_tatqa(self):
        tatqa_sample = TATQASample(
            question="What is the net income change?",
            answer="15.5",
            answer_type="arithmetic",
            scale="million",
            derivation="subtract(100, 84.5)",
            answer_from="table-text",
            paragraphs=["Net income increased significantly."],
            table=[["Year", "Net Income"], ["2022", "84.5"], ["2023", "100"]],
            table_id="tbl-001",
            question_id="q-001",
            doc_id="doc-001",
        )

        unified = to_unified(tatqa_sample)

        assert isinstance(unified, UnifiedSample)
        assert unified.source == "tatqa"
        assert unified.answer_type == "arithmetic"
        assert unified.scale == "million"
        assert unified.derivation == "subtract(100, 84.5)"
        assert unified.evidence_type == "table-text"

    def test_evidence_context_conversion(self):
        finqa_sample = FinQASample(
            question="Test question",
            answer="42",
            context_snippets=["Evidence text."],
            evidence_texts=[],
            table=[["A", "B"], ["1", "2"]],
            steps=[],
            program="",
            program_result=None,
            id="test-002",
            filename="TEST/2023.pdf",
            issuer="TEST",
        )

        unified = to_unified(finqa_sample)
        evidence_ctx = unified.to_evidence_context()

        assert evidence_ctx.text_blocks == ["Evidence text."]
        assert evidence_ctx.tables == [["A", "B"], ["1", "2"]]
        assert evidence_ctx.metadata["source"] == "finqa"


class TestTATQASample:
    """Tests for TAT-QA sample properties."""

    def test_scaled_answer(self):
        sample = TATQASample(
            question="Test",
            answer="100",
            answer_type="span",
            scale="million",
            derivation="",
            answer_from="table",
            paragraphs=[],
            table=[],
            table_id="",
            question_id="",
            doc_id="",
        )

        assert sample.scaled_answer == "100 million"

    def test_scaled_answer_no_scale(self):
        sample = TATQASample(
            question="Test",
            answer="42",
            answer_type="span",
            scale="",
            derivation="",
            answer_from="text",
            paragraphs=["Some text"],
            table=[],
            table_id="",
            question_id="",
            doc_id="",
        )

        assert sample.scaled_answer == "42"
