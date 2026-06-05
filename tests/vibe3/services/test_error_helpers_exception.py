"""Tests for error_helpers exception handling."""

from unittest.mock import MagicMock, patch

from vibe3.execution.contracts import ExecutionLaunchResult
from vibe3.services.shared.errors import record_dispatch_failure_if_unexpected


class TestRecordDispatchFailureException:
    """Tests for exception-based dispatch failure recording."""

    def test_exception_triggers_recording(self) -> None:
        """Verify exception param triggers record_error regardless of result."""
        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.sqlite_client.SQLiteClient",
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
                "vibe3.clients.sqlite_client.SQLiteClient",
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
            store=mock_store,
        )

    def test_exception_error_message_format(self) -> None:
        """Verify [exception] format in error message."""
        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.sqlite_client.SQLiteClient",
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
            reason_code="worktree_unavailable",
        )
        mock_store = MagicMock()

        with (
            patch("vibe3.services.shared.errors.record_error") as mock_record_error,
            patch(
                "vibe3.clients.sqlite_client.SQLiteClient",
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
