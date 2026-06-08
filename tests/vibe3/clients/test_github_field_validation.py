"""Tests for GitHub issue field validation."""

from unittest.mock import MagicMock

import pytest

from vibe3.clients.github_field_constants import GITHUB_KNOWN_ISSUE_FIELDS
from vibe3.clients.github_issues_ops import _validate_issue_fields


class TestFieldValidation:
    """Tests for _validate_issue_fields function."""

    def test_validate_all_known_fields_pass(self) -> None:
        """All 21 known fields should pass validation without error."""
        # This should not raise any exception
        _validate_issue_fields(list(GITHUB_KNOWN_ISSUE_FIELDS))

    def test_validate_empty_fields_pass(self) -> None:
        """Empty list should pass validation (edge case)."""
        # This should not raise any exception
        _validate_issue_fields([])

    def test_validate_typo_detected_with_suggestion(self) -> None:
        """Typo 'commnts' should raise ValueError suggesting 'comments'."""
        with pytest.raises(ValueError) as exc_info:
            _validate_issue_fields(["commnts"])

        error_msg = str(exc_info.value)
        assert "Unknown GitHub issue field(s)" in error_msg
        assert "'commnts'" in error_msg
        assert "'comments'" in error_msg
        assert "did you mean" in error_msg

    def test_validate_multiple_invalid_fields(self) -> None:
        """Multiple invalid fields should all be listed in error."""
        with pytest.raises(ValueError) as exc_info:
            _validate_issue_fields(["bad1", "bad2"])

        error_msg = str(exc_info.value)
        assert "'bad1'" in error_msg
        assert "'bad2'" in error_msg

    def test_validate_mixed_valid_invalid(self) -> None:
        """Mixed valid/invalid fields should raise error for invalid only."""
        with pytest.raises(ValueError) as exc_info:
            _validate_issue_fields(["number", "bad"])

        error_msg = str(exc_info.value)
        assert "'bad'" in error_msg
        assert "'number'" not in error_msg  # Valid field should not be listed

    def test_view_issue_validates_fields(self) -> None:
        """view_issue should call validation for invalid fields."""
        from vibe3.clients.github_issues_ops import IssuesMixin

        # Create a mock instance with necessary attributes
        mock_instance = MagicMock(spec=IssuesMixin)
        mock_instance._run_gh_command = MagicMock(
            return_value=MagicMock(returncode=0, stdout="{}", stderr="")
        )

        # Call view_issue with invalid fields
        with pytest.raises(ValueError) as exc_info:
            IssuesMixin.view_issue(mock_instance, 123, fields=["commnts"])

        error_msg = str(exc_info.value)
        assert "commnts" in error_msg
        assert "comments" in error_msg

    def test_view_issue_skips_validation_with_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """view_issue should skip validation when VIBE_SKIP_FIELD_VALIDATION is set."""
        from vibe3.clients.github_issues_ops import IssuesMixin

        # Set environment variable
        monkeypatch.setenv("VIBE_SKIP_FIELD_VALIDATION", "1")

        # Create a mock instance with necessary attributes
        mock_instance = MagicMock(spec=IssuesMixin)
        mock_instance._run_gh_command = MagicMock(
            return_value=MagicMock(returncode=0, stdout="{}", stderr="")
        )

        # This should NOT raise ValueError because validation is skipped
        result = IssuesMixin.view_issue(mock_instance, 123, fields=["commnts"])
        # The function will return empty dict due to mock, but no ValueError
        assert result is not None or result == {} or isinstance(result, dict)

    def test_view_issue_no_fields_no_validation(self) -> None:
        """view_issue should not validate when fields=None (default)."""
        from vibe3.clients.github_issues_ops import IssuesMixin

        # Create a mock instance with necessary attributes
        mock_instance = MagicMock(spec=IssuesMixin)
        mock_instance._run_gh_command = MagicMock(
            return_value=MagicMock(returncode=0, stdout="{}", stderr="")
        )

        # This should NOT raise ValueError because fields=None uses default set
        result = IssuesMixin.view_issue(mock_instance, 123)
        # The function will return empty dict due to mock, but no ValueError
        assert result is not None or result == {} or isinstance(result, dict)
