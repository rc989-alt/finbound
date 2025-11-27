"""Tests for ReasoningEngine JSON parsing and citation normalization."""

import pytest

from finbound.reasoning.engine import ReasoningEngine


class TestParseModelJson:
    """Tests for _parse_model_json method."""

    @pytest.fixture
    def engine(self, monkeypatch):
        # Mock OpenAI client to avoid API key requirement
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        return ReasoningEngine()

    def test_parses_plain_json(self, engine):
        content = '{"answer": "42", "reasoning": "math", "citations": ["ref1"]}'
        result = engine._parse_model_json(content)
        assert result["answer"] == "42"
        assert result["citations"] == ["ref1"]

    def test_strips_markdown_code_fence(self, engine):
        content = '```json\n{"answer": "42", "citations": ["ref1"]}\n```'
        result = engine._parse_model_json(content)
        assert result["answer"] == "42"
        assert result["citations"] == ["ref1"]

    def test_strips_markdown_fence_without_language(self, engine):
        content = '```\n{"answer": "yes"}\n```'
        result = engine._parse_model_json(content)
        assert result["answer"] == "yes"

    def test_fallback_on_invalid_json(self, engine):
        content = "This is not JSON"
        result = engine._parse_model_json(content)
        assert result["answer"] == content
        assert result["citations"] == []


class TestNormalizeCitations:
    """Tests for _normalize_citations method."""

    @pytest.fixture
    def engine(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        return ReasoningEngine()

    def test_handles_list(self, engine):
        raw = ["citation 1", "citation 2"]
        result = engine._normalize_citations(raw)
        assert result == ["citation 1", "citation 2"]

    def test_handles_single_string(self, engine):
        raw = "Company guidance states revenue increased."
        result = engine._normalize_citations(raw)
        assert result == ["Company guidance states revenue increased."]

    def test_handles_json_encoded_list_string(self, engine):
        raw = '["ref1", "ref2"]'
        result = engine._normalize_citations(raw)
        assert result == ["ref1", "ref2"]

    def test_handles_none(self, engine):
        result = engine._normalize_citations(None)
        assert result == []

    def test_handles_empty_string(self, engine):
        result = engine._normalize_citations("")
        assert result == []

    def test_filters_empty_entries(self, engine):
        raw = ["valid", "", "  ", "also valid"]
        result = engine._normalize_citations(raw)
        assert result == ["valid", "also valid"]


class TestCalculationDetection:
    """Tests for calculation type detection and answer formatting."""

    @pytest.fixture
    def engine(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        return ReasoningEngine()

    def test_detects_change_between_years(self, engine):
        question = "Question: What is the change between 2018 and 2019 average free cash flow?"
        calc_types = engine._detect_calculation_type(question)
        assert "difference" in calc_types

    def test_detects_year_over_year_phrase(self, engine):
        question = "Question: Calculate the year-over-year percentage change in revenue."
        calc_types = engine._detect_calculation_type(question)
        assert "percentage_change" in calc_types

    def test_formats_percentage_answer(self, engine):
        formatted = engine._apply_answer_format_rules(
            "0.35",
            "percentage",
            "What percent of revenue is segment A?",
            ["ratio"],
            [],
        )
        assert formatted == "35%"

    def test_total_answer_sums_values(self, engine):
        values = [
            {"label": "2013 total debt", "value": 1356},
            {"label": "2012 total debt", "value": 2220},
        ]
        formatted = engine._apply_answer_format_rules(
            "2013: 1356 million, 2012: 2220 million",
            "absolute",
            "What is the total for 2013 and 2012 combined?",
            ["total"],
            values,
        )
        assert formatted.startswith("3576")

    def test_absolute_value_for_change_question(self, engine):
        formatted = engine._apply_answer_format_rules(
            "-3.39%",
            "percentage",
            "What is the change in total debt from 2014 to 2015?",
            ["percentage_change"],
            [],
        )
        # Generic percentage change questions should preserve sign;
        # magnitude-only behavior is reserved for explicit "decrease" wording.
        assert formatted == "-3.39%"

    def test_detect_expected_sign_absolute(self, engine):
        question = "How much did interest expense change between 2014 and 2015?"
        # Sign should be preserved unless the question explicitly asks for magnitude.
        assert engine._detect_expected_sign(question) is None

    def test_convert_percentage_to_absolute(self, engine):
        answer, note = engine._convert_answer_format(
            "35%",
            detected_type="percentage",
            expected_type="absolute",
        )
        assert answer == "35"
        assert note is not None

    def test_convert_absolute_to_percentage_warning(self, engine):
        answer, note = engine._convert_answer_format(
            "172",
            detected_type="absolute",
            expected_type="percentage",
        )
        assert answer == "172"
        assert note is not None

    def test_validate_answer_format_warns(self, engine):
        valid, warning = engine._validate_answer_format("172", "percentage")
        assert not valid
        assert warning

    def test_verify_sign_consistency_positive(self, engine):
        adjusted, note = engine._verify_sign_consistency(
            "-12.4%",
            "How much did revenue increase?",
            "Revenue increased by 12.4%",
            expected_sign="positive",
        )
        assert adjusted == "-12.4%"
        assert note is not None

    def test_denominator_warning_for_ratio(self, engine):
        warnings = engine._check_denominator_requirements(
            "What percentage of total revenue came from Europe?",
            [{"label": "Europe revenue", "value": 200}],
            ["percentage_of_total"],
        )
        assert warnings

    def test_extract_expected_count_from_question(self, engine):
        count = engine._extract_expected_count("Sum the results for the 5 regions.")
        assert count == 5

    def test_verify_sum_completeness_warns(self, engine):
        warnings = engine._verify_sum_completeness(
            [{"label": "Region A", "value": 10}],
            expected_count=3,
            calc_types=["total"],
        )
        assert warnings
