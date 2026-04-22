"""Tests for Orchestra server CLI commands and startup logic."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import vibe3.server.app as serve_module
from vibe3.cli import app
from vibe3.config.settings import VibeConfig
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import GateResult
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
        mock_check.return_value = GateResult.open()
        yield mock_check


def test_start_async_spawns_tmux_session(monkeypatch) -> None:
    """Test that serve start (default) dispatches to background tmux session."""
    from vibe3.server import registry as utils_module

    monkeypatch.setattr(
        "vibe3.config.orchestra_settings.load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(utils_module, "_validate_pid_file", lambda _: (None, False))
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

    from vibe3.server import registry as utils_module

    monkeypatch.setattr(
        "vibe3.config.orchestra_settings.load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(utils_module, "_validate_pid_file", lambda _: (None, False))
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
        "vibe3.config.orchestra_settings.load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        "vibe3.orchestra.failed_gate.FailedGate.check",
        lambda self: GateResult.open(),
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


def test_start_async_with_ts_prints_public_url(monkeypatch) -> None:
    monkeypatch.setattr(
        "vibe3.config.orchestra_settings.load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
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
        "vibe3.config.orchestra_settings.load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
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
        "vibe3.config.orchestra_settings.load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
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
        "vibe3.config.orchestra_settings.load_orchestra_config",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(serve_module, "_orchestra_tmux_session_exists", lambda: True)
    monkeypatch.setattr(serve_module, "_kill_orchestra_tmux_session", lambda: True)

    with patch(
        "vibe3.config.settings.VibeConfig.get_defaults", return_value=VibeConfig()
    ):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "stop"])

    assert result.exit_code == 0
    assert "stopped orchestra server tmux session" in result.stdout.lower()
