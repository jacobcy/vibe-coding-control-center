"""Tests for error_helpers.py convenience functions."""

from __future__ import annotations

from unittest.mock import ANY, MagicMock, patch

from vibe3.models import ExecutionLaunchResult
from vibe3.services.shared.errors import (
    log_dispatch_error,
    record_dispatch_failure_if_unexpected,
)


class TestRecordDispatchFailureIfUnexpected:
    """Tests for record_dispatch_failure_if_unexpected()."""

    def test_success_launch_not_recorded(self) -> None:
        """Verify successful launch is not recorded."""
        result = ExecutionLaunchResult(
            launched=True,
            skipped=False,
            reason="Session started",
            reason_code=None,
        )

        with patch("vibe3.services.shared.errors.record_error") as mock_record_error:
            record_dispatch_failure_if_unexpected(
                result=result,
                role="planner",
                issue_number=123,
                branch="dev/test",
            )

        mock_record_error.assert_not_called()

    def test_normal_throttling_not_recorded(self) -> None:
        """Verify capacity_full and duplicate_dispatch are not recorded."""
        # Test capacity_full
        result1 = ExecutionLaunchResult(
            launched=False,
            skipped=True,
            reason="Capacity limit reached",
            reason_code="capacity_full",
        )

        with patch("vibe3.services.shared.errors.record_error") as mock_record_error:
            record_dispatch_failure_if_unexpected(
                result=result1,
                role="executor",
                issue_number=456,
                branch="dev/test",
            )

        mock_record_error.assert_not_called()

        # Test duplicate_dispatch
        result2 = ExecutionLaunchResult(
            launched=False,
            skipped=True,
            reason="Session already exists",
            reason_code="duplicate_dispatch",
        )

        with patch("vibe3.services.shared.errors.record_error") as mock_record_error:
            record_dispatch_failure_if_unexpected(
                result=result2,
                role="reviewer",
                issue_number=789,
                branch="dev/test",
            )

        mock_record_error.assert_not_called()

    def test_unexpected_failure_recorded(self) -> None:
        """Verify worktree_unavailable is recorded."""
        # Test worktree_unavailable
        result = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Worktree not found",
            reason_code="worktree_unavailable",
        )

        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            record_dispatch_failure_if_unexpected(
                result=result,
                role="executor",
                issue_number=456,
                branch="dev/test",
            )

        mock_record_error.assert_called_once_with(
            error_code="E_DISPATCH_FAILURE",
            error_message=(
                "manual executor dispatch failed [worktree_unavailable]: "
                "Worktree not found"
            ),
            tick_id=0,  # Manual dispatch marker
            issue_number=456,
            branch="dev/test",
            store=ANY,
        )

    def test_error_message_format(self) -> None:
        """Verify error message format is correct."""
        result = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Unexpected error occurred",
            reason_code="unknown",
        )

        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            record_dispatch_failure_if_unexpected(
                result=result,
                role="reviewer",
                issue_number=999,
                branch="feature/test",
            )

        # Verify the call was made with correct parameters
        call_args = mock_record_error.call_args
        assert call_args[1]["error_code"] == "E_DISPATCH_FAILURE"
        assert (
            call_args[1]["error_message"]
            == "manual reviewer dispatch failed [unknown]: Unexpected error occurred"
        )
        assert call_args[1]["tick_id"] == 0  # Manual dispatch marker
        assert call_args[1]["issue_number"] == 999
        assert call_args[1]["branch"] == "feature/test"

    def test_none_issue_number_coerced_to_zero(self) -> None:
        """Verify None issue_number is coerced to 0 for manual dispatch."""
        result = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Worktree resolution failed",
            reason_code="worktree_unavailable",
        )

        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            record_dispatch_failure_if_unexpected(
                result=result,
                role="reviewer",
                issue_number=None,  # Base review without issue
                branch="dev/test",
            )

        mock_record_error.assert_called_once_with(
            error_code="E_DISPATCH_FAILURE",
            error_message=(
                "manual reviewer dispatch failed [worktree_unavailable]: "
                "Worktree resolution failed"
            ),
            tick_id=0,  # Manual dispatch marker
            issue_number=0,  # Coerced from None
            branch="dev/test",
            store=ANY,
        )

    def test_tick_id_always_zero_for_manual_dispatch(self) -> None:
        """Verify tick_id is always 0 for manual dispatch (not heartbeat)."""
        result = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Unexpected failure",
            reason_code="worktree_unavailable",
        )

        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            record_dispatch_failure_if_unexpected(
                result=result,
                role="planner",
                issue_number=123,
                branch="dev/test",
            )

        # Verify tick_id is explicitly 0, not default
        call_args = mock_record_error.call_args
        assert call_args[1]["tick_id"] == 0

    def test_exception_triggers_recording(self) -> None:
        """Verify exception param triggers record_error regardless of result."""
        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            record_dispatch_failure_if_unexpected(
                role="planner",
                issue_number=123,
                branch="dev/test",
                exception=RuntimeError("Dispatch failed"),
            )

        mock_record_error.assert_called_once()

    def test_exception_with_none_result(self) -> None:
        """Verify exception with result=None still works."""
        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            record_dispatch_failure_if_unexpected(
                result=None,
                role="executor",
                issue_number=456,
                branch="dev/test",
                exception=ValueError("Test error"),
            )

        # ValueError is unclassified, maps to E_EXEC_UNKNOWN (WARNING severity)
        mock_record_error.assert_called_once_with(
            error_code="E_EXEC_UNKNOWN",  # Classified by classify_error_hybrid
            error_message="manual executor dispatch failed [exception]: Test error",
            tick_id=0,
            issue_number=456,
            branch="dev/test",
            store=ANY,
        )

    def test_exception_error_message_format(self) -> None:
        """Verify [exception] format in error message."""
        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            record_dispatch_failure_if_unexpected(
                role="reviewer",
                issue_number=789,
                branch="feature/test",
                exception=RuntimeError("Unexpected error"),
            )

        call_args = mock_record_error.call_args
        # RuntimeError is unclassified, maps to E_EXEC_UNKNOWN (WARNING severity)
        assert (
            call_args[1]["error_code"] == "E_EXEC_UNKNOWN"
        )  # Classified by classify_error_hybrid
        assert (
            call_args[1]["error_message"]
            == "manual reviewer dispatch failed [exception]: Unexpected error"
        )
        assert call_args[1]["tick_id"] == 0
        assert call_args[1]["issue_number"] == 789
        assert call_args[1]["branch"] == "feature/test"

    def test_exception_takes_priority_over_result(self) -> None:
        """Verify when both provided, exception is recorded (result ignored)."""
        result = ExecutionLaunchResult(
            launched=False,
            skipped=False,
            reason="Result-level failure",
            reason_code="launch_failed",
        )
        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            record_dispatch_failure_if_unexpected(
                result=result,
                role="planner",
                issue_number=123,
                branch="dev/test",
                exception=RuntimeError("Exception-level failure"),
            )

        # Should record exception, not result
        call_args = mock_record_error.call_args
        assert "[exception]" in call_args[1]["error_message"]
        assert "Exception-level failure" in call_args[1]["error_message"]
        assert "Result-level failure" not in call_args[1]["error_message"]

    def test_neither_result_nor_exception_noop(self) -> None:
        """Verify both None results in no call to record_error."""
        with patch("vibe3.services.shared.errors.record_error") as mock_record_error:
            record_dispatch_failure_if_unexpected(
                result=None,
                role="planner",
                issue_number=123,
                branch="dev/test",
            )

        mock_record_error.assert_not_called()

    def test_magicmock_leak_skipped(self) -> None:
        """Verify MagicMock leaks are detected and skipped."""
        from unittest.mock import MagicMock

        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            # Create a MagicMock exception (simulating test leak)
            mock_exception = MagicMock()
            mock_exception.__str__ = lambda self: "MagicMock()"

            record_dispatch_failure_if_unexpected(
                role="manager",
                issue_number=42,
                branch="task/issue-42",
                exception=mock_exception,
            )

        # Should NOT record error for mock leaks
        mock_record_error.assert_not_called()

    def test_magicmock_in_error_message_skipped(self) -> None:
        """Verify exceptions with MagicMock in message are skipped."""
        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.SQLiteClient",
                return_value=mock_store,
            ),
        ):
            # Exception with "MagicMock" in string
            record_dispatch_failure_if_unexpected(
                role="executor",
                issue_number=123,
                branch="dev/test",
                exception=ValueError(
                    "Error binding parameter: type 'MagicMock' is not supported"
                ),
            )

        # Should NOT record error for mock leaks
        mock_record_error.assert_not_called()


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
