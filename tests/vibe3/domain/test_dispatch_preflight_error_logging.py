"""Tests for dispatch_preflight error logging.

Verifies that qualify-gate exceptions are routed through
record_dispatch_failure_if_unexpected with classified error codes.
"""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.domain.dispatch_preflight import DispatchPreflightService
from vibe3.exceptions import AgentPresetNotFoundError
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
    """Verify qualify_blocked exception triggers helper with classified code."""
    issue = IssueInfo(
        number=123,
        title="Test blocked issue",
        state=IssueState.BLOCKED,
        labels=["state/blocked"],
        assignees=["manager-bot"],
    )

    # Mock qualify_gate to raise exception
    # RuntimeError -> E_EXEC_UNKNOWN (unclassified, not promoted)
    mock_qualify_gate.qualify_blocked_issue.side_effect = RuntimeError(
        "no such column: aup_rejection_count"
    )

    service = DispatchPreflightService(
        qualify_gate=mock_qualify_gate,
        flow_context=mock_flow_context,
        structural_check=mock_structural_check,
    )

    mock_store = MagicMock()
    # Patch the underlying record_error (called by the helper)
    with (
        patch(
            "vibe3.services.orchestra.error_recording.record_error"
        ) as mock_record_error,
        patch("vibe3.clients.SQLiteClient", return_value=mock_store),
    ):
        result = service._qualify_blocked(issue)

    # Verify behavior preserved: returns None
    assert result is None

    # Verify inner record_error received classified code
    mock_record_error.assert_called_once()
    call_args = mock_record_error.call_args[1]
    # RuntimeError is not a permanent code error → stays E_EXEC_UNKNOWN
    assert call_args["error_code"] == "E_EXEC_UNKNOWN"
    assert call_args["issue_number"] == 123
    assert "preflight dispatch dispatch failed" in call_args["error_message"]


@pytest.mark.regression("issue-3250")
def test_qualify_active_records_error_on_exception(
    mock_qualify_gate, mock_flow_context, mock_structural_check
):
    """Verify qualify_active exception triggers helper with classified code."""
    issue = IssueInfo(
        number=456,
        title="Test active issue",
        state=IssueState.IN_PROGRESS,
        labels=["state/in-progress"],
        assignees=["manager-bot"],
    )

    # Mock run_qualify_gate to raise exception
    # RuntimeError -> E_EXEC_UNKNOWN (unclassified, not promoted)
    mock_qualify_gate.run_qualify_gate.side_effect = RuntimeError(
        "qualify gate internal error"
    )

    service = DispatchPreflightService(
        qualify_gate=mock_qualify_gate,
        flow_context=mock_flow_context,
        structural_check=mock_structural_check,
    )

    mock_store = MagicMock()
    # Patch the underlying record_error (called by the helper)
    with (
        patch(
            "vibe3.services.orchestra.error_recording.record_error"
        ) as mock_record_error,
        patch("vibe3.clients.SQLiteClient", return_value=mock_store),
    ):
        result = service._qualify_active(issue)

    # Verify behavior preserved: returns None
    assert result is None

    # Verify inner record_error received classified code
    mock_record_error.assert_called_once()
    call_args = mock_record_error.call_args[1]
    # RuntimeError is not a permanent code error → stays E_EXEC_UNKNOWN
    assert call_args["error_code"] == "E_EXEC_UNKNOWN"
    assert call_args["issue_number"] == 456
    assert "preflight dispatch dispatch failed" in call_args["error_message"]


@pytest.mark.regression("issue-3250")
def test_qualify_blocked_survives_when_record_error_fails(
    mock_qualify_gate, mock_flow_context, mock_structural_check
):
    """Verify preflight decision preserved when helper itself fails."""
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

    # Mock helper to also fail
    with (
        patch(
            "vibe3.domain.dispatch_preflight.record_dispatch_failure_if_unexpected",
            side_effect=Exception("DB write failed"),
        ) as mock_helper,
        patch("vibe3.domain.dispatch_preflight.logger") as mock_logger,
    ):
        result = service._qualify_blocked(issue)

    # Verify behavior preserved: still returns None (not raising)
    assert result is None

    # Verify helper was attempted
    mock_helper.assert_called_once()

    # Verify fallback logger warning was emitted
    bound_logger = mock_logger.bind.return_value
    bound_logger.warning.assert_called()
    warning_calls = [str(call) for call in bound_logger.warning.call_args_list]
    assert any(
        "Failed to record dispatch_preflight error" in call for call in warning_calls
    )


@pytest.mark.regression("issue-3272")
@pytest.mark.parametrize(
    "exception,expected_code",
    [
        (ConnectionError("transient network"), "E_API_NETWORK"),
        (AgentPresetNotFoundError("preset not found"), "E_MODEL_CONFIG"),
        (ValueError("invalid value"), "E_DISPATCH_CODE_ERROR"),
        (RuntimeError("unknown error"), "E_EXEC_UNKNOWN"),
    ],
)
def test_dispatch_preflight_classified_exception(exception, expected_code):
    """Verify preflight routing surfaces classified code, not E_DISPATCH_FAILURE."""
    mock_store = MagicMock()

    with (
        patch(
            "vibe3.services.orchestra.error_recording.record_error"
        ) as mock_record_error,
        patch("vibe3.clients.SQLiteClient", return_value=mock_store),
    ):
        from vibe3.services.orchestra.error_recording import (
            record_dispatch_failure_if_unexpected,
        )

        record_dispatch_failure_if_unexpected(
            role="dispatch",
            issue_number=555,
            exception=exception,
            dispatch_source="preflight",
        )

    # Verify inner record_error received classified code
    mock_record_error.assert_called_once()
    call_args = mock_record_error.call_args[1]
    assert call_args["error_code"] == expected_code
    assert call_args["issue_number"] == 555
    # dispatch_source embedded in message string, not a separate kwarg
    assert "preflight dispatch dispatch failed" in call_args["error_message"]
