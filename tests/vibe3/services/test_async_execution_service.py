"""Tests for async execution service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.backends.codeagent import AsyncExecutionHandle
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
    def mock_backend(self):
        backend = MagicMock()
        backend.start_async_command.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-reviewer-feature-test",
            log_path=Path("temp/logs/vibe3-reviewer-feature-test.async.log"),
            prompt_file_path=Path(""),
        )
        return backend

    @pytest.fixture
    def service(self, mock_store, mock_backend):
        """Create service with mock store."""
        return AsyncExecutionService(store=mock_store, backend=mock_backend)

    def test_start_async_execution_updates_status(
        self, service, mock_store, mock_backend
    ):
        """Starting execution should persist the lower-level async handle."""
        service.start_async_execution(
            role="reviewer",
            command=["vibe3", "review", "base"],
            branch="feature/test",
        )

        mock_backend.start_async_command.assert_called_once_with(
            ["vibe3", "review", "base"],
            execution_name="vibe3-reviewer-feature/test",
            env=None,
        )
        assert mock_store.update_flow_state.called
        assert mock_store.add_event.called
        refs = mock_store.add_event.call_args.kwargs["refs"]
        assert refs["tmux_session"] == "vibe3-reviewer-feature-test"
        assert refs["log_path"].endswith(
            "temp/logs/vibe3-reviewer-feature-test.async.log"
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
        backend = MagicMock()
        backend.start_async_command.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-reviewer-feature-test",
            log_path=Path("temp/logs/vibe3-reviewer-feature-test.async.log"),
            prompt_file_path=Path(""),
        )
        service = AsyncExecutionService(store=store, backend=backend)

        pid = service.start_async_execution(
            role="reviewer",
            command=[
                "uv",
                "run",
                "python",
                "src/vibe3/cli.py",
                "review",
                "base",
            ],
            branch="feature/test",
        )

        assert pid == 0
        backend.start_async_command.assert_called_once()
        state = store.get_flow_state("feature/test")
        assert state["reviewer_status"] == "running"
        events = store.get_events("feature/test")
        assert events[0]["event_type"] == "review_started"
        assert events[0]["refs"]["tmux_session"] == "vibe3-reviewer-feature-test"
        assert events[0]["refs"]["log_path"].endswith(
            "temp/logs/vibe3-reviewer-feature-test.async.log"
        )
