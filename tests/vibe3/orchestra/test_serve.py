"""Tests for Orchestra server CLI commands and startup logic."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import vibe3.server.app as serve_module
from vibe3.cli import app
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.failed_gate import GateResult


@pytest.fixture(autouse=True)
def mock_preflights():
    """Patch pre-flight checks that require local network resources."""
    with patch("vibe3.server.app._ensure_port_available", return_value=None):
        yield


@pytest.fixture(autouse=True)
def mock_failed_gate():
    with patch("vibe3.orchestra.failed_gate.FailedGate.check") as mock_check:
        mock_check.return_value = GateResult.open()
        yield mock_check


def test_start_async_spawns_tmux_session(monkeypatch) -> None:
    """Test that serve start (default) dispatches to background tmux session."""
    from vibe3.server import registry as utils_module

    monkeypatch.setattr(
        OrchestraConfig,
        "from_settings",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(utils_module, "_validate_pid_file", lambda _: (None, False))

    with patch("vibe3.server.registry.subprocess.run") as mock_run:
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start"])

    assert result.exit_code == 0
    assert "tmux session" in result.stdout.lower()
    cmd = mock_run.call_args.args[0]
    assert cmd[:4] == ["tmux", "new-session", "-d", "-s"]


def test_start_async_reports_duplicate_session(monkeypatch) -> None:
    import subprocess

    from vibe3.server import registry as utils_module

    monkeypatch.setattr(
        OrchestraConfig,
        "from_settings",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(utils_module, "_validate_pid_file", lambda _: (None, False))

    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["tmux"],
        stderr="duplicate session: vibe3-orchestra-serve",
    )
    with patch("vibe3.server.registry.subprocess.run", side_effect=error):
        runner = CliRunner()
        result = runner.invoke(app, ["serve", "start"])

    assert result.exit_code == 1
    assert "already exists" in result.stdout.lower()


def test_start_debug_overrides_interval_and_scene_base(monkeypatch) -> None:
    captured = {}

    async def _fake_run(config, port):
        captured["config"] = config

    monkeypatch.setattr(
        OrchestraConfig,
        "from_settings",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(serve_module, "_run", _fake_run)

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "start", "--debug", "--no-async"])

    assert result.exit_code == 0
    config = captured["config"]
    assert config.debug is True
    assert config.polling_interval == 60


def test_start_honors_settings_debug_for_scene_base_and_interval(monkeypatch) -> None:
    captured = {}

    async def _fake_run(config, port):
        captured["config"] = config

    monkeypatch.setattr(
        OrchestraConfig,
        "from_settings",
        lambda: OrchestraConfig(debug=True, pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(serve_module, "_run", _fake_run)

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "start", "--no-async"])

    assert result.exit_code == 0
    config = captured["config"]
    assert config.debug is True
    assert config.polling_interval == 60


def test_start_async_with_ts_prints_public_url(monkeypatch) -> None:
    monkeypatch.setattr(
        OrchestraConfig,
        "from_settings",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "_start_async_serve", lambda _c, _v: (True, "started async")
    )
    monkeypatch.setattr(
        serve_module,
        "_setup_tailscale_webhook",
        lambda _port: (True, "Public URL: https://example.ts.net/webhook/github"),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "start", "--ts"])

    assert result.exit_code == 0
    assert "started async" in result.stdout
    assert "Public URL" in result.stdout


def test_start_async_with_ts_exits_nonzero_when_setup_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        OrchestraConfig,
        "from_settings",
        lambda: OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid")),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "_start_async_serve", lambda _c, _v: (True, "started async")
    )
    monkeypatch.setattr(
        serve_module,
        "_setup_tailscale_webhook",
        lambda _port: (False, "ts setup failed"),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["serve", "start", "--ts"])

    assert result.exit_code == 1
    assert "ts setup failed" in result.stdout
