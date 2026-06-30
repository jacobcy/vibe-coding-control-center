"""Tests for dispatch_preflight error logging to error_log table."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.domain.dispatch_preflight import DispatchPreflightService
from vibe3.models import IssueInfo, IssueState


@pytest.fixture
def mock_qualify_gate():
    """Create a mock QualifyGateLike."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_flow_context():
    """Create a mock flow context resolver."""
    return lambda issue_number: ("task/issue-456", {"flow_status": "active"})


@pytest.fixture
def mock_structural_check():
    """Create a mock structural check that always passes."""
    return lambda issue: True


@pytest.mark.regression("issue-3250")
def test_qualify_blocked_records_error_on_exception(
    mock_qualify_gate, mock_flow_context, mock_structural_check
):
    """Verify qualify_blocked exception triggers record_error."""
    issue = IssueInfo(
        number=123,
        title="Test blocked issue",
        state=IssueState.BLOCKED,
        labels=["state/blocked"],
        assignees=["manager-bot"],
    )

    # Mock qualify_gate to raise exception
    mock_qualify_gate.qualify_blocked_issue.side_effect = RuntimeError(
        "no such column: aup_rejection_count"
    )

    service = DispatchPreflightService(
        qualify_gate=mock_qualify_gate,
        flow_context=mock_flow_context,
        structural_check=mock_structural_check,
    )

    with patch("vibe3.domain.dispatch_preflight.record_error") as mock_record_error:
        result = service._qualify_blocked(issue)

    # Verify behavior preserved: returns None
    assert result is None

    # Verify record_error was called with correct parameters
    mock_record_error.assert_called_once()
    call_args = mock_record_error.call_args[1]
    assert call_args["error_code"] == "E_DISPATCH_FAILURE"
    assert call_args["issue_number"] == 123
    assert "no such column: aup_rejection_count" in call_args["error_message"]
    assert "blocked qualify gate failed" in call_args["error_message"]


@pytest.mark.regression("issue-3250")
def test_qualify_active_records_error_on_exception(
    mock_qualify_gate, mock_flow_context, mock_structural_check
):
    """Verify qualify_active exception triggers record_error."""
    issue = IssueInfo(
        number=456,
        title="Test active issue",
        state=IssueState.IN_PROGRESS,
        labels=["state/in-progress"],
        assignees=["manager-bot"],
    )

    # Mock run_qualify_gate to raise exception
    mock_qualify_gate.run_qualify_gate.side_effect = RuntimeError(
        "qualify gate internal error"
    )

    service = DispatchPreflightService(
        qualify_gate=mock_qualify_gate,
        flow_context=mock_flow_context,
        structural_check=mock_structural_check,
    )

    with patch("vibe3.domain.dispatch_preflight.record_error") as mock_record_error:
        result = service._qualify_active(issue)

    # Verify behavior preserved: returns None
    assert result is None

    # Verify record_error was called with correct parameters
    mock_record_error.assert_called_once()
    call_args = mock_record_error.call_args[1]
    assert call_args["error_code"] == "E_DISPATCH_FAILURE"
    assert call_args["issue_number"] == 456
    assert "qualify gate internal error" in call_args["error_message"]
    assert "active qualify gate failed" in call_args["error_message"]


@pytest.mark.regression("issue-3250")
def test_qualify_blocked_survives_when_record_error_fails(
    mock_qualify_gate, mock_flow_context, mock_structural_check
):
    """Verify preflight decision preserved when record_error itself fails."""
    issue = IssueInfo(
        number=789,
        title="Test blocked issue",
        state=IssueState.BLOCKED,
        labels=["state/blocked"],
        assignees=["manager-bot"],
    )

    # Mock qualify_gate to raise original exception
    mock_qualify_gate.qualify_blocked_issue.side_effect = RuntimeError(
        "original qualify gate error"
    )

    service = DispatchPreflightService(
        qualify_gate=mock_qualify_gate,
        flow_context=mock_flow_context,
        structural_check=mock_structural_check,
    )

    # Mock record_error to also fail
    with patch(
        "vibe3.domain.dispatch_preflight.record_error",
        side_effect=Exception("DB write failed"),
    ) as mock_record_error:
        with patch("vibe3.domain.dispatch_preflight.logger") as mock_logger:
            result = service._qualify_blocked(issue)

    # Verify behavior preserved: still returns None (not raising)
    assert result is None

    # Verify record_error was attempted
    mock_record_error.assert_called_once()

    # Verify fallback logger warning was emitted
    bound_logger = mock_logger.bind.return_value
    bound_logger.warning.assert_called()
    warning_calls = [str(call) for call in bound_logger.warning.call_args_list]
    assert any(
        "Failed to record dispatch_preflight error" in call for call in warning_calls
    )
