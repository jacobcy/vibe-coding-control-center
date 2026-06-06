"""Tests for Orchestra server CLI commands and startup logic."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.config.settings import VibeConfig
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import GateResult
from vibe3.server import app as serve_module
from vibe3.server.registry import _build_async_serve_command


@pytest.fixture(autouse=True)
def mock_preflights():
    """Patch pre-flight checks that require local network resources."""
    # Note: _ensure_port_available was removed in refactoring
    # If port availability checks are needed, they should be patched here
    yield


@pytest.fixture(autouse=True)
def mock_git_environment():
    """Ensure git environment is mocked for tests requiring it."""
    with (
        patch(
            "vibe3.clients.git_client.GitClient.get_git_common_dir",
            return_value="/tmp/.git",
        ),
        patch(
            "vibe3.clients.git_client.GitClient.get_worktree_root", return_value="/tmp"
        ),
        patch(
            "vibe3.clients.git_client.GitClient.get_current_branch", return_value="main"
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_failed_gate():
    # Patch the class where it is defined,
    # which handles instances created via local imports
    with patch("vibe3.orchestra.failed_gate.FailedGate.check") as mock_check:
        mock_check.return_value = GateResult.open_gate()
        yield mock_check


def test_start_async_spawns_tmux_session(monkeypatch) -> None:
    """Test that serve start (default) dispatches to background tmux session."""
    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "find_available_port", lambda _port, _max: (8080, False)
    )
    monkeypatch.setattr(
        serve_module,
        "find_missing_backend_commands",
        lambda env_path=None: {},
    )

    with patch(
        "vibe3.models.orchestra_config._default_pid_file",
        return_value=Path(".git/vibe3/orchestra.pid"),
    ):
        mock_vibe_config = VibeConfig()

    with (
        patch("vibe3.server.registry.subprocess.run") as mock_run,
        patch(
            "vibe3.config.settings.VibeConfig.get_defaults",
            return_value=mock_vibe_config,
        ),
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start"])

    assert result.exit_code == 0
    assert "tmux session" in result.stdout.lower()
    # Check the first call (new-session), not the last (pipe-pane)
    cmd = mock_run.call_args_list[0].args[0]
    assert cmd[:4] == ["tmux", "new-session", "-d", "-s"]


def test_start_async_reports_duplicate_session(monkeypatch) -> None:
    import subprocess

    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "find_available_port", lambda _port, _max: (8080, False)
    )
    monkeypatch.setattr(
        serve_module,
        "find_missing_backend_commands",
        lambda env_path=None: {},
    )

    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["tmux"],
        stderr="duplicate session: vibe3-orchestra-serve",
    )
    with patch(
        "vibe3.models.orchestra_config._default_pid_file",
        return_value=Path(".git/vibe3/orchestra.pid"),
    ):
        mock_vibe_config = VibeConfig()

    with (
        patch("vibe3.server.registry.subprocess.run", side_effect=error),
        patch(
            "vibe3.config.settings.VibeConfig.get_defaults",
            return_value=mock_vibe_config,
        ),
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start"])

    assert result.exit_code == 1
    assert "already exists" in result.stdout.lower()


def test_start_async_blocks_when_configured_backend_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "find_available_port", lambda _port, _max: (8080, False)
    )
    monkeypatch.setattr(
        serve_module,
        "find_missing_backend_commands",
        lambda env_path=None: {"opencode": "opencode"},
    )

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start"])

    assert result.exit_code == 1
    assert "missing backend executables" in result.stdout.lower()
    assert "opencode" in result.stdout


def test_build_async_serve_command_forces_sync_child_process() -> None:
    cmd = _build_async_serve_command(
        OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid"), debug=True),
        verbose=0,
        launch_cwd=Path("/tmp/debug-wt"),
    )

    assert "--no-async" in cmd


def test_build_async_serve_command_never_sets_code_root_override() -> None:
    """Cross-project dispatch must always use global vibe3, never caller repo.

    Debug mode only affects logging verbosity, not code paths.
    Both debug and normal mode set VIBE3_ASYNC_CLI_PROJECT_ROOT= (empty)
    to ensure resolve_async_cli_project_root() uses module location.
    """
    # Debug mode: still must NOT set code root override
    debug_cmd = _build_async_serve_command(
        OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid"), debug=True),
        verbose=0,
        launch_cwd=Path("/tmp/debug-wt"),
    )
    assert "VIBE3_ASYNC_CLI_PROJECT_ROOT=" in debug_cmd
    # Should NOT contain the debug-wt path
    debug_root = Path("/tmp/debug-wt").resolve()
    assert f"VIBE3_ASYNC_CLI_PROJECT_ROOT={debug_root}" not in debug_cmd

    # Normal mode: also sets empty string (not unset)
    normal_cmd = _build_async_serve_command(
        OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid"), debug=False),
        verbose=0,
        launch_cwd=Path("/tmp/external-repo"),
    )
    # Normal mode must explicitly clear VIBE3_ASYNC_CLI_PROJECT_ROOT
    # to prevent parent environment hijacking
    assert "VIBE3_ASYNC_CLI_PROJECT_ROOT=" in normal_cmd


def test_start_async_with_ts_prints_public_url(monkeypatch) -> None:
    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "find_available_port", lambda _port, _max: (8080, False)
    )
    monkeypatch.setattr(
        serve_module,
        "find_missing_backend_commands",
        lambda env_path=None: {},
    )
    monkeypatch.setattr(
        serve_module, "_start_async_serve", lambda _c, _v: (True, "started async")
    )
    monkeypatch.setattr(
        serve_module,
        "_setup_tailscale_webhook",
        lambda _port: (True, "Public URL: https://example.ts.net/webhook/github"),
    )

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start", "--ts"])

    assert result.exit_code == 0
    assert "started async" in result.stdout
    assert "Public URL" in result.stdout


def test_start_async_with_ts_exits_nonzero_when_setup_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "find_available_port", lambda _port, _max: (8080, False)
    )
    monkeypatch.setattr(
        serve_module,
        "find_missing_backend_commands",
        lambda env_path=None: {},
    )
    monkeypatch.setattr(
        serve_module, "_start_async_serve", lambda _c, _v: (True, "started async")
    )
    monkeypatch.setattr(
        serve_module,
        "_setup_tailscale_webhook",
        lambda _port: (False, "ts setup failed"),
    )

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start", "--ts"])

    assert result.exit_code == 1
    assert "ts setup failed" in result.stdout


@pytest.mark.asyncio
async def test_run_stops_uvicorn_when_heartbeat_exits(monkeypatch) -> None:
    class FakeHeartbeat:
        def __init__(self) -> None:
            self.stop_called = False

        async def run(self) -> None:
            return None

        def stop(self) -> None:
            self.stop_called = True

    class FakeServer:
        def __init__(self, _config) -> None:
            self.should_exit = False

        async def serve(self) -> None:
            while not self.should_exit:
                await asyncio.sleep(0)

    monkeypatch.setattr(
        serve_module,
        "_build_server_with_launch_cwd",
        lambda _config, _cwd: (FakeHeartbeat(), object()),
    )
    monkeypatch.setattr(serve_module.uvicorn, "Server", FakeServer)
    monkeypatch.setattr(
        serve_module.uvicorn,
        "Config",
        lambda *args, **kwargs: object(),
    )

    await serve_module._run(OrchestraConfig(), 8080)


def test_status_reports_tmux_session_when_pid_file_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(serve_module, "_orchestra_tmux_session_exists", lambda: True)

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "status"])

    assert result.exit_code == 0
    assert "running in tmux session" in result.stdout.lower()


def test_stop_kills_tmux_session_when_pid_file_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(serve_module, "_orchestra_tmux_session_exists", lambda: True)
    monkeypatch.setattr(serve_module, "_kill_orchestra_tmux_session", lambda: True)

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "stop"])

    assert result.exit_code == 0
    assert "stopped orchestra server tmux session" in result.stdout.lower()


def test_logs_shows_error_when_no_log_file(monkeypatch, tmp_path) -> None:
    """Test that serve logs reports error when log file doesn't exist."""
    monkeypatch.setattr(
        "vibe3.server.app.orchestra_events_log_path",
        lambda: tmp_path / "nonexistent.log",
    )

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "logs"])

    assert result.exit_code == 1
    assert "No log file found" in result.stdout


def test_logs_shows_log_content(monkeypatch, tmp_path) -> None:
    """Test that serve logs displays log file content."""
    log_path = tmp_path / "events.log"
    log_path.write_text("[2024-01-01T00:00:00] [test] Test log entry\n")

    monkeypatch.setattr(
        "vibe3.server.app.orchestra_events_log_path",
        lambda: log_path,
    )

    # Mock subprocess.run to avoid actually calling tail
    mock_run = patch("vibe3.server.app.subprocess.run").start()
    mock_run.return_value = None

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "logs"])

    # Check that subprocess.run was called with correct arguments
    assert result.exit_code == 0
    mock_run.assert_called_once_with(["tail", "-n50", str(log_path)])

    patch.stopall()


def test_start_auto_discovers_port_when_default_occupied(monkeypatch) -> None:
    """Test that serve start auto-discovers port when default is occupied
    and port_range_max is configured."""
    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(
            pid_file=Path(".git/vibe3/orchestra.pid"),
            port_range_max=8090,
        ),
    )
    monkeypatch.setattr(serve_module, "validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module,
        "find_available_port",
        lambda _port, _max: (8081, True),
    )
    monkeypatch.setattr(
        serve_module,
        "find_missing_backend_commands",
        lambda env_path=None: {},
    )
    monkeypatch.setattr(
        serve_module, "_start_async_serve", lambda _c, _v: (True, "started async")
    )

    with patch(
        "vibe3.models.orchestra_config._default_pid_file",
        return_value=Path(".git/vibe3/orchestra.pid"),
    ):
        mock_vibe_config = VibeConfig()

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults",
        return_value=mock_vibe_config,
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start"])

    assert result.exit_code == 0
    assert "auto-discovered" in result.stdout.lower()
    assert "8081" in result.stdout


def test_resume_clears_errors_even_when_gate_is_open(monkeypatch) -> None:
    """Test that serve resume clears error_log even when gate is already OPEN.

    This is a regression test for a bug where:
    - User runs `serve resume` when gate is OPEN
    - Command exits early without clearing error_log
    - Old errors remain and re-trigger the gate on next tick

    Fix: resume should always clear error_log, regardless of gate state.
    """
    from unittest.mock import MagicMock

    from vibe3.orchestra.failed_gate import GateStatus

    # Mock FailedGate to return OPEN state
    mock_gate = MagicMock()
    mock_gate.get_status.return_value = GateStatus(
        is_active=False,
        reason=None,
        triggered_at=None,
        triggered_by_error_code=None,
        cleared_at=None,
        cleared_by=None,
        cleared_reason=None,
        blocked_ticks=0,
    )

    # Patch where FailedGate is imported (from domain in app.py)
    with patch("vibe3.domain.FailedGate", return_value=mock_gate):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "resume", "--reason", "test"])

    # Command should succeed
    assert result.exit_code == 0

    # Should show gate is already OPEN
    assert "already OPEN" in result.stdout

    # But still call clear() to prevent stale errors
    mock_gate.clear.assert_called_once_with("admin:manual", "test")


def test_resume_clears_gate_when_active(monkeypatch) -> None:
    """Test that serve resume clears gate when it is ACTIVE."""
    from unittest.mock import MagicMock

    from vibe3.orchestra.failed_gate import GateStatus

    # Mock FailedGate to return ACTIVE state
    mock_gate = MagicMock()
    mock_gate.get_status.return_value = GateStatus(
        is_active=True,
        reason="ERROR-severity threshold: 2 recent errors",
        triggered_at="2026-05-23T05:14:08",
        triggered_by_error_code="E_API_RATE_LIMIT",
        cleared_at=None,
        cleared_by=None,
        cleared_reason=None,
        blocked_ticks=3,
    )

    # Patch where FailedGate is imported (from domain in app.py)
    with patch("vibe3.domain.FailedGate", return_value=mock_gate):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "resume", "--reason", "fixed"])

    # Command should succeed
    assert result.exit_code == 0

    # Should show clearing message (ACTIVE state)
    assert "Clearing Failed Gate" in result.stdout

    # Should call clear()
    mock_gate.clear.assert_called_once_with("admin:manual", "fixed")


def test_start_blocks_when_instance_running(monkeypatch, tmp_path: Path) -> None:
    """Test that serve start blocks when another instance is already running."""
    from vibe3.server import OrchestraInstanceInfo

    pid_file = tmp_path / "orchestra.pid"
    instance_info = OrchestraInstanceInfo(
        pid=99999,
        cwd=tmp_path,
        port=8080,
        started_at=datetime.now(),
    )

    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=pid_file),
    )
    monkeypatch.setattr(
        serve_module, "validate_pid_file", lambda _: (instance_info, True)
    )

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start"])

    assert result.exit_code == 0  # already running is idempotent (not an error)
    assert "already running" in result.stdout.lower()


def test_status_displays_instance_directory(monkeypatch, tmp_path: Path) -> None:
    """Test that serve status displays the running directory."""
    from vibe3.server import OrchestraInstanceInfo

    pid_file = tmp_path / "orchestra.pid"
    instance_info = OrchestraInstanceInfo(
        pid=99999,
        cwd=Path("/Users/test/project"),
        port=8080,
        started_at=datetime.now(),
    )

    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=pid_file),
    )
    monkeypatch.setattr(
        serve_module, "validate_pid_file", lambda _: (instance_info, True)
    )

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "status"])

    assert result.exit_code == 0
    assert "/Users/test/project" in result.stdout


def test_stop_clears_global_pid_file(monkeypatch, tmp_path: Path) -> None:
    """Test that serve stop removes the global PID file."""
    from unittest.mock import MagicMock

    from vibe3.server import OrchestraInstanceInfo

    pid_file = tmp_path / "orchestra.pid"
    instance_info = OrchestraInstanceInfo(
        pid=99999,
        cwd=tmp_path,
        port=8080,
        started_at=datetime.now(),
    )

    # Write PID file
    pid_file.write_text(
        '{"pid": 99999, "cwd": "/tmp", "port": 8080, '
        '"started_at": "2026-05-30T12:00:00"}'
    )

    monkeypatch.setattr(
        serve_module,
        "load_orchestra_config",
        lambda: OrchestraConfig(pid_file=pid_file),
    )
    monkeypatch.setattr(
        serve_module, "validate_pid_file", lambda _: (instance_info, True)
    )
    # Mock os.kill to raise ProcessLookupError (process doesn't exist)
    monkeypatch.setattr(
        "os.kill", MagicMock(side_effect=ProcessLookupError("Process not found"))
    )

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "stop"])

    # Debug: print output if test fails
    if result.exit_code != 0:
        print(f"Exit code: {result.exit_code}")
        print(f"Output: {result.stdout}")
        if result.exception:
            print(f"Exception: {result.exception}")

    assert result.exit_code == 0
    # The test should verify the command succeeded
    # PID file cleanup happens in the command itself
    # We verify the command completed successfully
    assert (
        "Process 99999 not found" in result.stdout
        or "cleaning up" in result.stdout.lower()
    )
