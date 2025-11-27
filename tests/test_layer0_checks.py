from finbound.routing.layer0_checks import run_layer0_checks


def test_layer0_detects_percentage_mismatch():
    result = run_layer0_checks(
        question="What percentage change did revenue experience?",
        answer_text="42",
        reasoning_text="Revenue increased by forty two",
        evidence_text="Revenue in 2018 was 100 and in 2019 was 142.",
    )
    assert not result.passed
    assert any("type_mismatch" in issue for issue in result.issues)


def test_layer0_passes_consistent_answer():
    result = run_layer0_checks(
        question="How much was operating income?",
        answer_text="$2.5 million",
        reasoning_text="Operating income was two point five million dollars.",
        evidence_text="Operating income (millions): 2.5",
    )
    assert result.passed
    assert result.issues == []


def test_layer0_sign_mismatch():
    result = run_layer0_checks(
        question="By how much did costs decrease and decline overall?",
        answer_text="5",
        reasoning_text="Costs decreased and declined by five",
        evidence_text="Costs were 105 last year and 100 this year.",
    )
    assert any("sign_mismatch" in issue for issue in result.issues)


def test_layer0_autocorrects_percentage_for_absolute_question():
    result = run_layer0_checks(
        question="What is the change between 2018 and 2019 average free cash flow?",
        answer_text="183.5%",
        reasoning_text="Change computed as 183.5 percent.",
        evidence_text="Average free cash flow 2018: 100, 2019: 283.5",
    )
    assert result.correction_applied
    assert result.corrected_answer == "183.5"


def test_layer0_autocorrects_proportion_scaling():
    result = run_layer0_checks(
        question="What was the employee termination costs as a proportion of total costs in 2018?",
        answer_text="95.5",
        reasoning_text="Termination costs were 95.5 percent of total costs.",
        evidence_text="Termination costs 9.55, total costs 10.",
    )
    assert result.correction_applied
    assert result.corrected_answer.startswith("0.9")


def test_layer0_sign_autocorrect():
    result = run_layer0_checks(
        question="By how much did operating income decrease and decline year over year?",
        answer_text="12",
        reasoning_text="Operating income decreased and declined by twelve",
        evidence_text="Income moved from 100 to 88.",
    )
    assert result.correction_applied
    assert result.corrected_answer.startswith("-")


def test_layer0_autocorrects_decimal_to_percentage():
    """Test that decimal proportions are scaled to percentage for percentage questions."""
    result = run_layer0_checks(
        question="What was the percentage change in net debt from 2018 to 2019?",
        answer_text="0.25",
        reasoning_text="Calculated (295.2-235.8)/235.8 = 0.2519",
        evidence_text="Net debt 2019: 295.2, Net debt 2018: 235.8",
    )
    assert result.correction_applied
    assert result.correction_type == "scale_to_percentage"
    assert result.corrected_answer == "25"


# NOTE: Removed test_layer0_autocorrects_proportion_to_absolute and
# test_layer0_autocorrects_100x_scale_error because the evidence-based scaling
# logic they tested was causing significant regressions in the F1 benchmark:
# - Gold 172 → 1.72 (wrongly scaled down)
# - Gold -864 → -8.64 (wrongly scaled down)
# - Gold 0.51 → 51 (wrongly scaled up)
# The speculative scaling based on evidence magnitudes was too unreliable.


def test_layer0_does_not_overcorrect_small_values():
    """Test that small valid values are not incorrectly scaled."""
    result = run_layer0_checks(
        question="What was the change in interest rate from 2018 to 2019?",
        answer_text="0.5",
        reasoning_text="Interest rate changed",
        evidence_text="Interest rate 2018: 2.0, Interest rate 2019: 2.5",
    )
    assert not result.correction_applied
    assert result.corrected_answer is None
