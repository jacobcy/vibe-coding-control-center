"""Test error severity enum and registry structure."""

import pytest
from pydantic import ValidationError

from vibe3.exceptions.error_severity import ErrorHandlingContract, ErrorSeverity


def test_error_severity_values():
    """Test that ErrorSeverity has exactly three levels."""
    assert ErrorSeverity.CRITICAL.value == "CRITICAL"
    assert ErrorSeverity.ERROR.value == "ERROR"
    assert ErrorSeverity.WARNING.value == "WARNING"
    assert len(ErrorSeverity) == 3


def test_error_severity_comparison():
    """Test severity ordering."""
    assert ErrorSeverity.CRITICAL > ErrorSeverity.ERROR
    assert ErrorSeverity.ERROR > ErrorSeverity.WARNING


def test_error_handling_contract_fields():
    """Test that ErrorHandlingContract has required fields."""
    contract = ErrorHandlingContract(
        code="E_TEST",
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
    )
    assert contract.code == "E_TEST"
    assert contract.severity == ErrorSeverity.WARNING
    assert contract.counts_toward_threshold is False
    assert contract.issue_action == "record_only"


def test_error_severity_all_comparison_operators():
    """Test all comparison operators for severity ordering."""
    # Greater than
    assert ErrorSeverity.CRITICAL > ErrorSeverity.ERROR
    assert ErrorSeverity.ERROR > ErrorSeverity.WARNING
    assert ErrorSeverity.CRITICAL > ErrorSeverity.WARNING

    # Less than
    assert ErrorSeverity.WARNING < ErrorSeverity.ERROR
    assert ErrorSeverity.ERROR < ErrorSeverity.CRITICAL
    assert ErrorSeverity.WARNING < ErrorSeverity.CRITICAL

    # Greater than or equal
    assert ErrorSeverity.CRITICAL >= ErrorSeverity.ERROR
    assert ErrorSeverity.CRITICAL >= ErrorSeverity.CRITICAL
    assert ErrorSeverity.ERROR >= ErrorSeverity.WARNING

    # Less than or equal
    assert ErrorSeverity.WARNING <= ErrorSeverity.ERROR
    assert ErrorSeverity.WARNING <= ErrorSeverity.WARNING
    assert ErrorSeverity.ERROR <= ErrorSeverity.CRITICAL


def test_error_severity_comparison_with_non_enum():
    """Test that comparison with non-ErrorSeverity types returns NotImplemented."""
    assert ErrorSeverity.CRITICAL.__gt__("ERROR") is NotImplemented
    assert ErrorSeverity.ERROR.__lt__("WARNING") is NotImplemented
    assert ErrorSeverity.WARNING.__ge__("CRITICAL") is NotImplemented
    assert ErrorSeverity.CRITICAL.__le__("ERROR") is NotImplemented


def test_error_handling_contract_all_issue_actions():
    """Test that all valid issue_action values are accepted."""
    for action in ["record_only", "block_flow", "fail_issue"]:
        contract = ErrorHandlingContract(
            code="E_TEST",
            severity=ErrorSeverity.ERROR,
            counts_toward_threshold=True,
            record_in_error_log=True,
            write_timeline_event=True,
            issue_action=action,
            gate_action="threshold",
        )
        assert contract.issue_action == action


def test_error_handling_contract_all_gate_actions():
    """Test that all valid gate_action values are accepted."""
    for action in ["ignore", "threshold", "immediate"]:
        contract = ErrorHandlingContract(
            code="E_TEST",
            severity=ErrorSeverity.CRITICAL,
            counts_toward_threshold=False,
            record_in_error_log=True,
            write_timeline_event=True,
            issue_action="fail_issue",
            gate_action=action,
        )
        assert contract.gate_action == action


def test_error_handling_contract_invalid_issue_action():
    """Test that invalid issue_action values are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ErrorHandlingContract(
            code="E_TEST",
            severity=ErrorSeverity.ERROR,
            counts_toward_threshold=True,
            record_in_error_log=True,
            write_timeline_event=True,
            issue_action="invalid_action",
            gate_action="threshold",
        )
    assert "issue_action" in str(exc_info.value)


def test_error_handling_contract_invalid_gate_action():
    """Test that invalid gate_action values are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ErrorHandlingContract(
            code="E_TEST",
            severity=ErrorSeverity.ERROR,
            counts_toward_threshold=True,
            record_in_error_log=True,
            write_timeline_event=True,
            issue_action="record_only",
            gate_action="invalid_action",
        )
    assert "gate_action" in str(exc_info.value)


def test_error_handling_contract_missing_required_fields():
    """Test that missing required fields are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ErrorHandlingContract(
            code="E_TEST",
            severity=ErrorSeverity.ERROR,
            # Missing other required fields
        )
    errors = exc_info.value.errors()
    field_names = {err["loc"][0] for err in errors}
    assert "counts_toward_threshold" in field_names
    assert "record_in_error_log" in field_names
    assert "write_timeline_event" in field_names
    assert "issue_action" in field_names
    assert "gate_action" in field_names


def test_error_handling_contract_optional_description():
    """Test that description field is optional with default empty string."""
    contract = ErrorHandlingContract(
        code="E_TEST",
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
    )
    assert contract.description == ""

    contract_with_desc = ErrorHandlingContract(
        code="E_TEST",
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
        description="Test description",
    )
    assert contract_with_desc.description == "Test description"
