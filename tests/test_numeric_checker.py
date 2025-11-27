from finbound.verification_gate.numeric_checker import NumericChecker


def test_addition_check_passes():
    checker = NumericChecker()
    reasoning = "The sum of $300 million and $80 million gives $380 million."
    issues = checker.check("$380 million", reasoning)
    assert issues == []


def test_addition_check_flags_mismatch():
    checker = NumericChecker()
    reasoning = "Adding $300 million and $80 million results in $380 million."
    issues = checker.check("$3.8 million", reasoning)
    assert issues, "Expected mismatch when answer units are incorrect."


def test_division_check_passes():
    checker = NumericChecker()
    reasoning = "We divide 3.8 by 0.01 to obtain 380."
    issues = checker.check("380", reasoning)
    assert issues == []


def test_magnitude_check_flags_10x_error():
    checker = NumericChecker()
    reasoning = (
        "The table shows 196000 in 2013, 197000 in 2014 and 198000 in 2015."
    )
    # Answer is off by 10x (19700 vs ~197000)
    issues = checker.check("19700", reasoning)
    assert any("10x" in msg or "10x" in msg.lower() or "magnitude" in msg.lower() for msg in issues)
