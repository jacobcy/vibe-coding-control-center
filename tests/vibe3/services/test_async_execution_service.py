"""Tests for async execution service."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.async_execution_service import (
    AsyncExecutionService,
)


class TestAsyncExecutionService:
    """Tests for AsyncExecutionService."""

    @pytest.fixture
    def mock_store(self):
        """Create mock store."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_store):
        """Create service with mock store."""
        return AsyncExecutionService(store=mock_store)

    def test_start_async_execution_updates_status(self, service, mock_store):
        """Starting execution should update flow state."""
        with (
            patch("subprocess.Popen") as mock_popen,
            patch.object(service, "_start_completion_watcher"),
        ):
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            pid = service.start_async_execution(
                role="reviewer",
                command=["vibe3", "review", "base", "--no-async"],
                branch="feature/test",
            )

        assert pid == 12345
        mock_store.update_flow_state.assert_called()
        assert mock_store.add_event.call_args.args[1] == "review_started"
        assert (
            mock_store.add_event.call_args.kwargs["detail"] == "Started async reviewer"
        )

    def test_check_execution_status_running(self, service):
        """Check status returns running for active process."""
        with patch("os.kill") as mock_kill:
            mock_kill.return_value = None  # Process exists
            status = service.check_execution_status(12345)

        assert status == "running"

    def test_check_execution_status_done(self, service):
        """Check status returns done for non-existent process."""
        with patch("os.kill") as mock_kill:
            mock_kill.side_effect = OSError("No such process")
            status = service.check_execution_status(12345)

        assert status == "done"

    def test_complete_execution_success(self, service, mock_store):
        """Complete execution should update status."""
        service.complete_execution(
            role="reviewer",
            branch="feature/test",
            success=True,
        )

        mock_store.update_flow_state.assert_called()
        assert mock_store.add_event.call_args.args[1] == "review_completed"
        assert mock_store.add_event.call_args.kwargs["refs"]["status"] == "done"

    def test_complete_execution_crashed(self, service, mock_store):
        """Complete execution with failure should set crashed status."""
        service.complete_execution(
            role="reviewer",
            branch="feature/test",
            success=False,
        )

        mock_store.update_flow_state.assert_called()
        assert mock_store.add_event.call_args.args[1] == "review_aborted"
        assert mock_store.add_event.call_args.kwargs["refs"]["status"] == "crashed"

    def test_start_async_execution_persists_state(self, tmp_path):
        """Starting execution should persist running state in SQLite store."""
        db_path = tmp_path / "handoff.db"
        store = SQLiteClient(db_path=str(db_path))
        service = AsyncExecutionService(store=store)

        process = MagicMock()
        process.pid = 4321

        with patch("subprocess.Popen", return_value=process):
            with patch.object(service, "_start_completion_watcher") as watcher:
                pid = service.start_async_execution(
                    role="reviewer",
                    command=[
                        "uv",
                        "run",
                        "python",
                        "src/vibe3/cli.py",
                        "review",
                        "base",
                        "--no-async",
                    ],
                    branch="feature/test",
                )

        assert pid == 4321
        watcher.assert_called_once()
        state = store.get_flow_state("feature/test")
        assert state["reviewer_status"] == "running"
        assert state["execution_pid"] == 4321
        assert state["execution_started_at"] is not None
        events = store.get_events("feature/test")
        assert events[0]["event_type"] == "review_started"

    def test_wait_for_process_marks_completion(self, tmp_path):
        """Watcher should mark completion state on exit."""
        db_path = tmp_path / "handoff.db"
        store = SQLiteClient(db_path=str(db_path))
        service = AsyncExecutionService(store=store)

        process = MagicMock()
        process.wait.return_value = 0

        service._wait_for_process(process, "planner", "feature/x")

        state = store.get_flow_state("feature/x")
        assert state["planner_status"] == "done"
        assert state["execution_pid"] is None
        assert state["execution_completed_at"] is not None
        events = store.get_events("feature/x")
        assert events[0]["event_type"] == "plan_completed"

    def test_wait_for_process_marks_aborted_on_failure(self, tmp_path):
        """Watcher should record aborted state on non-zero exit."""
        db_path = tmp_path / "handoff.db"
        store = SQLiteClient(db_path=str(db_path))
        service = AsyncExecutionService(store=store)

        process = MagicMock()
        process.wait.return_value = 1

        service._wait_for_process(process, "executor", "feature/x")

        state = store.get_flow_state("feature/x")
        assert state["executor_status"] == "crashed"
        events = store.get_events("feature/x")
        assert events[0]["event_type"] == "run_aborted"

    def test_cancel_execution_updates_state(self, tmp_path):
        """Cancel should handle dict rows and clear pid."""
        db_path = tmp_path / "handoff.db"
        store = SQLiteClient(db_path=str(db_path))
        service = AsyncExecutionService(store=store)
        store.update_flow_state(
            "feature/x",
            flow_slug="feature-x",
            reviewer_status="running",
            execution_pid=9999,
        )

        with patch("os.getpgid", return_value=9999), patch("os.killpg") as killpg:
            cancelled = service.cancel_execution("reviewer", "feature/x")

        assert cancelled is True
        state = store.get_flow_state("feature/x")
        assert state["reviewer_status"] == "crashed"
        assert state["execution_pid"] is None
        assert state["execution_completed_at"] is not None
        events = store.get_events("feature/x")
        assert events[0]["event_type"] == "review_aborted"
        killpg.assert_called_once()
