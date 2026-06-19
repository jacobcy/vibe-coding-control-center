"""Tests for error_helpers.py convenience functions."""

from __future__ import annotations

from unittest.mock import patch

from vibe3.services.shared.errors import log_dispatch_error


class TestLogDispatchError:
    """Tests for log_dispatch_error()."""

    def test_github_error_logged_as_warning_without_traceback(self) -> None:
        """GitHubError logs via bind(external=True).warning, no traceback."""
        from vibe3.exceptions import GitHubError

        exc = GitHubError(status_code=403, message="rate limit exceeded")

        with patch("vibe3.services.shared.errors.logger") as mock_logger:
            log_dispatch_error("Manual plan dispatch failed", exc)

        mock_logger.bind.assert_called_once_with(external=True)
        mock_logger.bind.return_value.warning.assert_called_once_with(
            f"Manual plan dispatch failed: {exc}"
        )
        mock_logger.exception.assert_not_called()

    def test_called_process_error_logged_as_warning_without_traceback(self) -> None:
        """CalledProcessError logs via bind(external=True).warning, no traceback."""
        from subprocess import CalledProcessError

        exc = CalledProcessError(returncode=1, cmd=["gh", "pr", "create"])

        with patch("vibe3.services.shared.errors.logger") as mock_logger:
            log_dispatch_error("Manual run dispatch failed", exc)

        mock_logger.bind.assert_called_once_with(external=True)
        mock_logger.bind.return_value.warning.assert_called_once_with(
            f"Manual run dispatch failed: {exc}"
        )
        mock_logger.exception.assert_not_called()

    def test_generic_exception_logged_with_traceback(self) -> None:
        """Verify unclassified exceptions get a full traceback via logger.exception."""
        exc = ValueError("unexpected failure")

        with patch("vibe3.services.shared.errors.logger") as mock_logger:
            log_dispatch_error("Job execution failed", exc)

        mock_logger.exception.assert_called_once_with(
            "Job execution failed: unexpected failure"
        )
        mock_logger.bind.assert_not_called()

    def test_long_error_message_truncated(self) -> None:
        """Verify error text over 200 chars is truncated with an ellipsis."""
        from vibe3.exceptions import GitHubError

        exc = GitHubError(status_code=500, message="x" * 300)
        full_text = str(exc)
        assert len(full_text) > 200

        with patch("vibe3.services.shared.errors.logger") as mock_logger:
            log_dispatch_error("Review dispatch failed", exc)

        expected = f"Review dispatch failed: {full_text[:200]}..."
        mock_logger.bind.return_value.warning.assert_called_once_with(expected)
