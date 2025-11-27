from finbound.data.validators import assert_required_fields, validate_required_fields


def test_validate_required_fields_detects_missing():
    record = {"a": 1}
    missing = validate_required_fields(record, ["a", "b"])
    assert missing == ["b"]


def test_assert_required_fields_raises():
    record = {}
    try:
        assert_required_fields(record, ["x"])
    except ValueError as exc:
        assert "Missing required fields" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
