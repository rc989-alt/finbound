from finbound.routing.layer1 import Layer1Input, detect_formula_type, run_layer1


def test_detect_formula_type_percentage_change():
    formula = detect_formula_type("What was the percentage change in revenue year over year?")
    assert formula == "percentage_change"


def test_run_layer1_recompute_average():
    input_data = Layer1Input(
        question="What is the average free cash flow?",
        reasoning="Average of 4411 and 4044 gives 4227.5",
        model_answer="4227.5",
        values_used=[
            {"label": "2019", "value": 4411},
            {"label": "2018", "value": 4044},
        ],
    )
    result = run_layer1(input_data)
    assert result.formula_type == "average"
    assert result.operands_complete
    assert result.recomputed_value == (4411 + 4044) / 2
    assert result.confidence == "high"


def test_detect_formula_type_absolute_change():
    formula = detect_formula_type("What is the change between 2018 and 2019 average free cash flow?")
    assert formula == "absolute_change"


def test_detect_formula_type_proportion():
    formula = detect_formula_type("What was the employee termination costs as a proportion of total costs in 2018?")
    assert formula == "proportion"


def test_run_layer1_absolute_change_recompute():
    input_data = Layer1Input(
        question="What is the change between 2018 and 2019 average free cash flow?",
        reasoning="Change between two averages.",
        model_answer="50",
        values_used=[
            {"label": "2018", "value": 120},
            {"label": "2019", "value": 170},
        ],
    )
    result = run_layer1(input_data)
    assert result.formula_type == "absolute_change"
    assert result.operands_complete
    assert result.recomputed_value == 50


def test_run_layer1_proportion_recompute():
    input_data = Layer1Input(
        question="What was the employee termination costs as a proportion of total costs in 2018?",
        reasoning="Proportion of termination costs over total costs.",
        model_answer="0.95",
        values_used=[
            {"label": "Termination", "value": 95.5},
            {"label": "Total", "value": 100.0},
        ],
    )
    result = run_layer1(input_data)
    assert result.formula_type == "proportion"
    assert result.operands_complete
    assert abs(result.recomputed_value - 0.955) < 1e-6


def test_operand_order_mismatch_ratio():
    input_data = Layer1Input(
        question="What is the liability to asset ratio?",
        reasoning="Ratio computed from liabilities and assets.",
        model_answer="4.0",
        values_used=[
            {"label": "Liabilities", "value": 100.0},
            {"label": "Assets", "value": 400.0},
        ],
    )
    result = run_layer1(input_data)
    assert result.formula_type == "ratio"
    assert any("operand_order_mismatch" in issue for issue in result.issues)
    # Verify auto-correction is applied
    assert result.correction_applied
    # Expected: 100/400 = 0.25 = 25% (model had 400/100 = 4.0)
    assert "25" in result.final_answer


def test_operand_order_mismatch_ratio_service_cost():
    """Test case based on BDX/2018/page_82.pdf-2 failure."""
    input_data = Layer1Input(
        question="in 2018 what was the ratio of the service cost to the interest cost",
        reasoning="Ratio of service cost to interest cost.",
        model_answer="1.51",
        values_used=[
            {"label": "service cost", "value": 90.0},
            {"label": "interest cost", "value": 136.0},
        ],
    )
    result = run_layer1(input_data)
    assert result.formula_type == "ratio"
    assert result.correction_applied
    assert any("operand_order_mismatch" in issue for issue in result.issues)
    # Expected: 90/136 = 0.6617 = 66.2% (model had 136/90 = 1.51)
    assert "66" in result.final_answer
