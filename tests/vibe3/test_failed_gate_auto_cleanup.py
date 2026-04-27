"""Test FailedGate auto-cleanup of state/failed labels without reason."""

import json
from unittest.mock import MagicMock, patch

import pytest

from vibe3.orchestra.failed_gate import FailedGate


def test_failed_gate_auto_removes_label_without_reason():
    """FailedGate should auto-remove state/failed label when no failed_reason."""
    gate = FailedGate()

    # Mock _list_failed_issues to return one failed issue
    mock_issue = {"number": 123, "title": "Test Issue"}

    # Mock _check_failed_reason to return False (no reason)
    # Mock _remove_failed_label to track calls

    with patch.object(gate, "_list_failed_issues", return_value=[mock_issue]):
        with patch.object(gate, "_check_failed_reason", return_value=False):
            with patch.object(gate, "_remove_failed_label") as mock_remove:
                result = gate.check()

    # Should return not blocked
    assert result.blocked is False
    assert result.issue_number is None

    # Should have called _remove_failed_label
    mock_remove.assert_called_once_with(123)


def test_failed_gate_blocks_when_reason_exists():
    """FailedGate should block when issue has a valid failed_reason."""
    gate = FailedGate()

    mock_issue = {"number": 456, "title": "Issue With Reason"}

    with patch.object(gate, "_list_failed_issues", return_value=[mock_issue]):
        with patch.object(gate, "_check_failed_reason", return_value=True):
            with patch.object(
                gate, "_extract_reason", return_value=("Test reason", "http://url")
            ):
                result = gate.check()

    # Should block
    assert result.blocked is True
    assert result.issue_number == 456
    assert result.reason == "Test reason"


def test_check_failed_reason_detects_reason():
    """Test _check_failed_reason correctly parses issue body."""
    gate = FailedGate()

    # Mock gh issue view response
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(
        {"body": "**failed_reason**: network timeout\n\nSome other content"}
    )

    with patch("subprocess.run", return_value=mock_result):
        has_reason = gate._check_failed_reason(123)

    assert has_reason is True


def test_check_failed_reason_returns_false_for_empty():
    """Test _check_failed_reason returns False for empty/null reasons."""
    gate = FailedGate()

    # Mock gh issue view response with None
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps(
        {"body": "**failed_reason**: None\n\nOther content"}
    )

    with patch("subprocess.run", return_value=mock_result):
        has_reason = gate._check_failed_reason(123)

    assert has_reason is False


def test_check_failed_reason_returns_false_for_missing():
    """Test _check_failed_reason returns False when field is missing."""
    gate = FailedGate()

    # Mock gh issue view response without failed_reason
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"body": "Issue body without failed_reason field"})

    with patch("subprocess.run", return_value=mock_result):
        has_reason = gate._check_failed_reason(123)

    assert has_reason is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
