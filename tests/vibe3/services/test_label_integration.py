"""Tests for label integration helpers."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services.label_integration import (
    transition_issue_state,
    transition_to_claimed,
    transition_to_in_progress,
    transition_to_review,
)


class TestTransitionIssueState:
    """Tests for transition_issue_state function."""

    def test_returns_false_when_issue_is_none(self):
        """Test that function returns success=False when issue_number is None."""
        result = transition_issue_state(None, IssueState.CLAIMED, "agent:plan")
        assert result.success is False
        assert result.error == "no_issue_bound"

    @patch("vibe3.services.label_integration.LabelService")
    def test_returns_true_on_success(self, mock_service_class: MagicMock):
        """Test that function returns success=True on successful transition."""
        mock_service = MagicMock()
        mock_service.confirm_issue_state.return_value = "advanced"
        mock_service_class.return_value = mock_service

        result = transition_issue_state(123, IssueState.CLAIMED, "agent:plan")

        mock_service.confirm_issue_state.assert_called_once_with(
            123, IssueState.CLAIMED, "agent:plan"
        )
        assert result.success is True
        assert result.issue_number == 123

    @patch("vibe3.services.label_integration.LabelService")
    def test_returns_false_on_blocked(self, mock_service_class: MagicMock):
        """Test that function returns success=False on blocked transition."""
        mock_service = MagicMock()
        mock_service.confirm_issue_state.return_value = "blocked"
        mock_service_class.return_value = mock_service

        result = transition_issue_state(123, IssueState.CLAIMED, "agent:plan")

        assert result.success is False
        assert result.error == "state_transition_blocked"

    @patch("vibe3.services.label_integration.LabelService")
    def test_returns_false_on_exception(self, mock_service_class: MagicMock):
        """Test that function returns success=False on unexpected exception."""
        mock_service = MagicMock()
        mock_service.confirm_issue_state.side_effect = Exception("API error")
        mock_service_class.return_value = mock_service

        result = transition_issue_state(123, IssueState.CLAIMED, "agent:plan")

        assert result.success is False
        assert "API error" in result.error


class TestTransitionHelpers:
    """Tests for transition helper functions."""

    @patch("vibe3.services.label_integration.transition_issue_state")
    def test_transition_to_claimed(self, mock_transition: MagicMock):
        """Test transition_to_claimed calls with correct parameters."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_transition.return_value = mock_result

        result = transition_to_claimed(123)

        mock_transition.assert_called_once_with(123, IssueState.CLAIMED, "agent:plan")
        assert result.success is True

    @patch("vibe3.services.label_integration.transition_issue_state")
    def test_transition_to_in_progress(self, mock_transition: MagicMock):
        """Test transition_to_in_progress calls with correct parameters."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_transition.return_value = mock_result

        result = transition_to_in_progress(123)

        mock_transition.assert_called_once_with(
            123, IssueState.IN_PROGRESS, "agent:run"
        )
        assert result.success is True

    @patch("vibe3.services.label_integration.transition_issue_state")
    def test_transition_to_review(self, mock_transition: MagicMock):
        """Test transition_to_review calls with correct parameters."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_transition.return_value = mock_result

        result = transition_to_review(123)

        mock_transition.assert_called_once_with(123, IssueState.REVIEW, "agent:review")
        assert result.success is True

    @patch("vibe3.services.label_integration.transition_issue_state")
    def test_helpers_return_false_for_none_issue(self, mock_transition: MagicMock):
        """Test that helpers return success=False when issue is None."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_transition.return_value = mock_result

        assert transition_to_claimed(None).success is False
        assert transition_to_in_progress(None).success is False
        assert transition_to_review(None).success is False
