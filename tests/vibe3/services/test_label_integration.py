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
        """Test that function returns False when issue_number is None."""
        result = transition_issue_state(None, IssueState.CLAIMED, "agent:plan")
        assert result is False

    @patch("vibe3.services.label_integration.LabelService")
    def test_returns_true_on_success(self, mock_service_class: MagicMock):
        """Test that function returns True on successful transition."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = transition_issue_state(123, IssueState.CLAIMED, "agent:plan")

        mock_service.transition.assert_called_once_with(
            123, IssueState.CLAIMED, "agent:plan"
        )
        assert result is True

    @patch("vibe3.services.label_integration.LabelService")
    def test_returns_false_on_exception(self, mock_service_class: MagicMock):
        """Test that function returns False on exception."""
        mock_service = MagicMock()
        mock_service.transition.side_effect = Exception("API error")
        mock_service_class.return_value = mock_service

        result = transition_issue_state(123, IssueState.CLAIMED, "agent:plan")

        assert result is False


class TestTransitionHelpers:
    """Tests for transition helper functions."""

    @patch("vibe3.services.label_integration.transition_issue_state")
    def test_transition_to_claimed(self, mock_transition: MagicMock):
        """Test transition_to_claimed calls with correct parameters."""
        mock_transition.return_value = True

        result = transition_to_claimed(123)

        mock_transition.assert_called_once_with(123, IssueState.CLAIMED, "agent:plan")
        assert result is True

    @patch("vibe3.services.label_integration.transition_issue_state")
    def test_transition_to_in_progress(self, mock_transition: MagicMock):
        """Test transition_to_in_progress calls with correct parameters."""
        mock_transition.return_value = True

        result = transition_to_in_progress(123)

        mock_transition.assert_called_once_with(
            123, IssueState.IN_PROGRESS, "agent:run"
        )
        assert result is True

    @patch("vibe3.services.label_integration.transition_issue_state")
    def test_transition_to_review(self, mock_transition: MagicMock):
        """Test transition_to_review calls with correct parameters."""
        mock_transition.return_value = True

        result = transition_to_review(123)

        mock_transition.assert_called_once_with(123, IssueState.REVIEW, "agent:review")
        assert result is True

    @patch("vibe3.services.label_integration.transition_issue_state")
    def test_helpers_return_false_for_none_issue(self, mock_transition: MagicMock):
        """Test that helpers return False when issue is None."""
        mock_transition.return_value = False

        assert transition_to_claimed(None) is False
        assert transition_to_in_progress(None) is False
        assert transition_to_review(None) is False
