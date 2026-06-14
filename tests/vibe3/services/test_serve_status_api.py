"""Tests for fetch_serve_status_data API function."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.models import OrchestraConfig
from vibe3.services.orchestra.serve_status import fetch_serve_status_data


@pytest.fixture
def config() -> OrchestraConfig:
    """Create a minimal OrchestraConfig for testing."""
    return OrchestraConfig(
        port=8420,
        pid_file=Path("/tmp/test_orchestra.pid"),
        polling_interval=10,
        repo="test/repo",
        max_concurrent_flows=3,
    )


def _setup_common_mocks() -> dict:
    """Setup mock dependency instances shared across tests."""
    mock_err_instance = MagicMock()
    mock_err_instance.get_all_errors_status.return_value = {
        "total_errors": 0,
        "critical_count": 0,
        "error_count": 0,
        "warning_count": 0,
    }
    mock_err_instance.get_status.return_value = {
        "total_errors": 0,
        "time_window_minutes": 15,
        "threshold": 10,
    }
    mock_err_instance.get_recent_errors.return_value = []

    mock_failed_gate_instance = MagicMock()
    mock_failed_gate_instance.get_status.return_value = MagicMock(
        is_active=False,
        reason=None,
        triggered_at=None,
        triggered_by_error_code=None,
        cleared_at=None,
        cleared_by=None,
        cleared_reason=None,
        blocked_ticks=0,
    )
    mock_failed_gate = MagicMock(return_value=mock_failed_gate_instance)

    mock_job_svc = MagicMock()
    mock_job_svc.snapshot.return_value = MagicMock(
        active_jobs=[],
        recent_jobs=[],
        running_count=0,
        completed_count=0,
        failed_count=0,
    )

    mock_execution = MagicMock()
    mock_execution.JobMonitorService.return_value = mock_job_svc
    mock_failed_gate_mod = MagicMock()
    mock_failed_gate_mod.FailedGate = mock_failed_gate

    return {
        "err_instance": mock_err_instance,
        "failed_gate": mock_failed_gate,
        "job_svc": mock_job_svc,
        "execution": mock_execution,
        "failed_gate_mod": mock_failed_gate_mod,
    }


def _enter_patches(stack, pid_value, is_running, tmux_exists, mocks):
    """Enter all patches needed for fetch_serve_status_data tests."""
    stack.enter_context(
        patch(
            "vibe3.services.orchestra.serve_status.validate_pid_file",
            return_value=(pid_value, is_running),
        )
    )
    stack.enter_context(
        patch(
            "vibe3.services.orchestra.serve_status.orchestra_tmux_session_exists",
            return_value=tmux_exists,
        )
    )
    stack.enter_context(
        patch(
            "vibe3.services.orchestra.serve_status.orchestra_events_log_path",
            return_value=Path("/tmp/nonexistent_events.log"),
        )
    )
    stack.enter_context(
        patch(
            "vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot",
            return_value=None,
        )
    )
    stack.enter_context(
        patch(
            "vibe3.services.orchestra.serve_status.ErrorTrackingService.get_instance",
            return_value=mocks["err_instance"],
        )
    )
    stack.enter_context(
        patch(
            "importlib.import_module",
            side_effect=lambda name: {
                "vibe3.execution": mocks["execution"],
                "vibe3.domain.failed_gate": mocks["failed_gate_mod"],
            }[name],
        )
    )


def test_fetch_serve_status_data_structure(config: OrchestraConfig) -> None:
    """Verify fetch_serve_status_data returns expected top-level keys."""
    mocks = _setup_common_mocks()

    with ExitStack() as stack:
        _enter_patches(stack, None, False, False, mocks)
        result = fetch_serve_status_data(config)

    assert set(result.keys()) == {
        "daemon",
        "heartbeat",
        "dispatch_activity",
        "failed_gate",
        "error_tracking",
        "jobs",
    }
    assert result["daemon"]["pid"] is None
    assert not result["daemon"]["is_valid"]
    assert not result["daemon"]["tmux_exists"]
    assert result["heartbeat"]["tick_count"] == 0
    assert result["dispatch_activity"] == []
    assert not result["failed_gate"]["is_active"]
    assert result["error_tracking"]["total_errors"] == 0
    assert result["jobs"]["active"] == []
    assert result["jobs"]["summary"]["running"] == 0


def test_fetch_serve_status_daemon_running(config: OrchestraConfig) -> None:
    """Daemon status reflects running server correctly."""
    mocks = _setup_common_mocks()
    mock_info = MagicMock()
    mock_info.pid = 12345

    with ExitStack() as stack:
        _enter_patches(stack, mock_info, True, True, mocks)
        result = fetch_serve_status_data(config)

    assert result["daemon"]["pid"] == 12345
    assert result["daemon"]["is_valid"]
    assert result["daemon"]["tmux_exists"]


def test_fetch_serve_status_error_handling(config: OrchestraConfig) -> None:
    """Returns valid structure even when events.log doesn't exist."""
    mocks = _setup_common_mocks()

    with ExitStack() as stack:
        _enter_patches(stack, None, False, False, mocks)
        result = fetch_serve_status_data(config)

    assert result["heartbeat"]["tick_count"] == 0
    assert result["dispatch_activity"] == []
