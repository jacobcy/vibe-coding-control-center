"""Test error severity enum and registry structure."""

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
