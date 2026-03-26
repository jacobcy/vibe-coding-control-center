"""Tests for async execution service."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.async_execution_service import (
    AsyncExecutionService,
    ExecutionRole,
    ExecutionStatus,
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
        with patch("subprocess.Popen") as mock_popen:
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
        mock_store.add_event.assert_called_once()

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
        args = mock_store.update_flow_state.call_args[1]
        assert args["reviewer_status"] == "done"
        assert args["execution_pid"] is None

    def test_complete_execution_crashed(self, service, mock_store):
        """Complete execution with failure should set crashed status."""
        service.complete_execution(
            role="reviewer",
            branch="feature/test",
            success=False,
        )

        mock_store.update_flow_state.assert_called()
        args = mock_store.update_flow_state.call_args[1]
        assert args["reviewer_status"] == "crashed"
