from finbound.tools.calculator import Calculator


def test_basis_point_inference():
    calc = Calculator()
    result = calc.infer_from_basis_point_change(
        "change by $3.8 million", "100 basis points"
    )
    assert result is not None
    inferred_value, change = result
    assert round(inferred_value, 2) == 380.0
    assert round(change.value, 1) == 3.8
