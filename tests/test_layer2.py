"""Tests for Layer 2 LLM-guided re-extraction."""

import pytest
from unittest.mock import Mock, patch

from finbound.correction.layer2 import (
    Layer2Input,
    Layer2Result,
    Layer2Corrector,
    should_trigger_layer2,
)


def test_should_trigger_on_recompute_mismatch():
    """Test that Layer 2 triggers on recompute mismatch issues."""
    assert should_trigger_layer2(
        layer1_issues=["recompute_mismatch: model answer deviates from formula recomputation."],
        formula_type="average",
        confidence="low"
    )


def test_should_trigger_on_missing_operands():
    """Test that Layer 2 triggers on missing operands."""
    assert should_trigger_layer2(
        layer1_issues=["missing_operands: formula=total"],
        formula_type="total",
        confidence="low"
    )


def test_should_trigger_on_low_confidence_average():
    """Test that Layer 2 triggers on low confidence for average questions."""
    assert should_trigger_layer2(
        layer1_issues=[],
        formula_type="average",
        confidence="low"
    )


def test_should_not_trigger_on_high_confidence():
    """Test that Layer 2 does not trigger on high confidence."""
    assert not should_trigger_layer2(
        layer1_issues=[],
        formula_type="average",
        confidence="high"
    )


def test_should_trigger_on_type_mismatch():
    """Test that Layer 2 triggers on type_mismatch (wrong formula type used)."""
    assert should_trigger_layer2(
        layer1_issues=["type_mismatch: auto-corrected by strip_percentage."],
        formula_type="absolute_change",
        confidence="low"
    )


def test_strategy_selection_table_sum():
    """Test that table_sum strategy is selected for total questions."""
    corrector = Layer2Corrector()
    input_data = Layer2Input(
        question="What is the total revenue for all regions?",
        evidence_text="Revenue by region",
        evidence_tables=[],
        formula_type="total",
        original_answer="100",
        original_operands=None,
        layer1_issues=["missing_operands"],
    )
    strategy = corrector._select_strategy(input_data)
    assert strategy == "table_sum"


def test_strategy_selection_formula_guided():
    """Test that formula_guided strategy is selected for change of averages."""
    corrector = Layer2Corrector()
    input_data = Layer2Input(
        question="What is the change between 2018 and 2019 average free cash flow?",
        evidence_text="Free cash flow data",
        evidence_tables=[],
        formula_type="change_of_averages",
        original_answer="100",
        original_operands=None,
        layer1_issues=["recompute_mismatch"],
    )
    strategy = corrector._select_strategy(input_data)
    assert strategy == "formula_guided"


def test_strategy_selection_focused():
    """Test that focused strategy is default for other cases."""
    corrector = Layer2Corrector()
    input_data = Layer2Input(
        question="What is the percentage change in revenue?",
        evidence_text="Revenue data",
        evidence_tables=[],
        formula_type="percentage_change",
        original_answer="10%",
        original_operands=None,
        layer1_issues=["recompute_mismatch"],
    )
    strategy = corrector._select_strategy(input_data)
    assert strategy == "focused"


def test_strategy_selection_absolute_change():
    """Test that absolute_change strategy is selected for 'change in X' questions."""
    corrector = Layer2Corrector()
    input_data = Layer2Input(
        question="What is the change in the average total current tax expense between 2017-2018, and 2018-2019?",
        evidence_text="Tax expense data",
        evidence_tables=[],
        formula_type="absolute_change",
        original_answer="2.1%",
        original_operands=None,
        layer1_issues=["type_mismatch: auto-corrected by strip_percentage."],
    )
    strategy = corrector._select_strategy(input_data)
    assert strategy == "absolute_change"


def test_strategy_selection_absolute_change_from_type_mismatch():
    """Test that absolute_change strategy is selected when type_mismatch detected."""
    corrector = Layer2Corrector()
    input_data = Layer2Input(
        question="What is the change between 2018 and 2019 average free cash flow?",
        evidence_text="FCF data",
        evidence_tables=[],
        formula_type=None,  # No formula type detected
        original_answer="383%",
        original_operands=None,
        layer1_issues=["type_mismatch: auto-corrected by strip_percentage."],
    )
    strategy = corrector._select_strategy(input_data)
    assert strategy == "absolute_change"


def test_parse_json_response_clean():
    """Test parsing clean JSON response."""
    corrector = Layer2Corrector()
    response = '{"values": [{"label": "x", "value": 10}], "answer": 10}'
    parsed = corrector._parse_json_response(response)
    assert parsed is not None
    assert parsed["answer"] == 10


def test_parse_json_response_with_markdown():
    """Test parsing JSON wrapped in markdown code blocks."""
    corrector = Layer2Corrector()
    response = '''```json
{"values": [{"label": "x", "value": 10}], "answer": 10}
```'''
    parsed = corrector._parse_json_response(response)
    assert parsed is not None
    assert parsed["answer"] == 10


def test_format_tables():
    """Test table formatting for prompts."""
    corrector = Layer2Corrector()
    tables = [
        [["Header1", "Header2"], ["Row1", "100"], ["Row2", "200"]],
    ]
    formatted = corrector._format_tables(tables)
    assert "Table 1:" in formatted
    assert "Header1 | Header2" in formatted
    assert "Row1 | 100" in formatted


def test_format_tables_empty():
    """Test formatting empty tables."""
    corrector = Layer2Corrector()
    formatted = corrector._format_tables([])
    assert formatted == "No tables provided"


@patch.object(Layer2Corrector, '_call_llm')
def test_focused_extraction_success(mock_llm):
    """Test successful focused extraction."""
    mock_llm.return_value = '{"values": [{"label": "revenue 2019", "value": 100}], "calculation": "100 - 50 = 50", "answer": 50}'

    corrector = Layer2Corrector()
    input_data = Layer2Input(
        question="What is the change in revenue?",
        evidence_text="Revenue 2019: 100, Revenue 2018: 50",
        evidence_tables=[],
        formula_type="absolute_change",
        original_answer="5",  # Wrong answer
        original_operands=None,
        layer1_issues=["recompute_mismatch"],
    )

    result = corrector._run_focused_extraction(input_data)
    assert result.correction_applied
    assert result.corrected_answer == "50"
    assert result.strategy_used == "focused"


@patch.object(Layer2Corrector, '_call_llm')
def test_table_sum_extraction_success(mock_llm):
    """Test successful table sum extraction."""
    mock_llm.return_value = '{"rows_included": ["Q1", "Q2", "Q3", "Q4"], "values": [100, 200, 150, 250], "sum": 700, "answer": 700}'

    corrector = Layer2Corrector()
    input_data = Layer2Input(
        question="What is the total revenue?",
        evidence_text="Quarterly revenue",
        evidence_tables=[[["Quarter", "Revenue"], ["Q1", "100"], ["Q2", "200"], ["Q3", "150"], ["Q4", "250"]]],
        formula_type="total",
        original_answer="500",  # Wrong - missing some quarters
        original_operands=None,
        layer1_issues=["missing_operands"],
    )

    result = corrector._run_table_sum_extraction(input_data)
    assert result.correction_applied
    assert result.corrected_answer == "700"
    assert result.strategy_used == "table_sum"
    assert result.confidence >= 0.8  # High confidence when sum matches


@patch.object(Layer2Corrector, '_call_llm')
def test_formula_guided_extraction_success(mock_llm):
    """Test successful formula-guided extraction for change of averages."""
    mock_llm.return_value = '''{"values": [
        {"label": "FCF 2019", "value": 1000},
        {"label": "FCF 2018", "value": 800},
        {"label": "FCF 2017", "value": 600},
        {"label": "FCF 2016", "value": 500}
    ], "average_1": {"years": [2019, 2018], "value": 900},
    "average_2": {"years": [2017, 2016], "value": 550},
    "calculation": "(1000+800)/2 - (600+500)/2 = 900 - 550 = 350",
    "answer": 350}'''

    corrector = Layer2Corrector()
    input_data = Layer2Input(
        question="What is the change between 2018-2019 and 2016-2017 average free cash flow?",
        evidence_text="FCF data",
        evidence_tables=[],
        formula_type="change_of_averages",
        original_answer="200",  # Wrong answer
        original_operands=None,
        layer1_issues=["recompute_mismatch"],
    )

    result = corrector._run_formula_guided_extraction(input_data)
    assert result.correction_applied
    assert result.corrected_answer == "350"
    assert result.strategy_used == "formula_guided"
