"""Tests for orchestra serve command wiring and toggles."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.orchestra.config import (
    AssigneeDispatchConfig,
    CommentReplyConfig,
    OrchestraConfig,
    PRReviewDispatchConfig,
)
from vibe3.orchestra.serve import (
    _build_server,
    app,
)
from vibe3.orchestra.serve_utils import (
    _build_async_serve_command,
    _setup_tailscale_webhook,
    _validate_pid_file,
)


def test_build_server_registers_only_enabled_services() -> None:
    cfg = OrchestraConfig(
        assignee_dispatch=AssigneeDispatchConfig(enabled=False),
        comment_reply=CommentReplyConfig(enabled=False),
        pr_review_dispatch=PRReviewDispatchConfig(enabled=True),
    )
    heartbeat, _ = _build_server(cfg)
    # GovernanceService is always registered (tick-based)
    assert heartbeat.service_names == ["PRReviewDispatchService", "GovernanceService"]


def test_start_exits_when_orchestra_disabled(monkeypatch) -> None:
    import vibe3.orchestra.serve as serve_module

    monkeypatch.setattr(serve_module, "setup_logging", lambda verbose=0: None)
    monkeypatch.setattr(
        serve_module.OrchestraConfig,
        "from_settings",
        classmethod(lambda cls: OrchestraConfig(enabled=False)),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["start"])

    assert result.exit_code == 1
    assert "disabled" in result.stdout.lower()


def test_start_async_spawns_tmux_session(monkeypatch) -> None:
    import vibe3.orchestra.serve as serve_module
    import vibe3.orchestra.serve_utils as utils_module

    monkeypatch.setattr(serve_module, "setup_logging", lambda verbose=0: None)
    monkeypatch.setattr(
        serve_module.OrchestraConfig,
        "from_settings",
        classmethod(
            lambda cls: OrchestraConfig(
                enabled=True,
                polling_interval=60,
                port=8080,
                repo="jacobcy/vibe-coding-control-center",
            )
        ),
    )
    monkeypatch.setattr(utils_module, "_validate_pid_file", lambda _: (None, False))

    with patch("vibe3.orchestra.serve_utils.subprocess.run") as mock_run:
        runner = CliRunner()
        result = runner.invoke(app, ["start", "--async"])

    assert result.exit_code == 0
    assert "tmux session" in result.stdout.lower()
    cmd = mock_run.call_args.args[0]
    assert cmd[:4] == ["tmux", "new-session", "-d", "-s"]
    assert "serve" in cmd
    assert "start" in cmd
    assert "--async" not in cmd


def test_start_async_reports_duplicate_session(monkeypatch) -> None:
    import vibe3.orchestra.serve as serve_module
    import vibe3.orchestra.serve_utils as utils_module

    monkeypatch.setattr(serve_module, "setup_logging", lambda verbose=0: None)
    monkeypatch.setattr(
        serve_module.OrchestraConfig,
        "from_settings",
        classmethod(lambda cls: OrchestraConfig(enabled=True)),
    )
    monkeypatch.setattr(utils_module, "_validate_pid_file", lambda _: (None, False))

    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["tmux"],
        stderr="duplicate session: vibe3-orchestra-serve",
    )
    with patch("vibe3.orchestra.serve_utils.subprocess.run", side_effect=error):
        runner = CliRunner()
        result = runner.invoke(app, ["start", "--async"])

    assert result.exit_code == 1
    assert "already exists" in result.stdout.lower()


def test_build_async_command_uses_config_port_and_skips_repo_when_none() -> None:
    cfg = OrchestraConfig(
        enabled=True,
        polling_interval=75,
        port=9090,
        repo=None,
    )

    cmd = _build_async_serve_command(cfg, verbose=0)

    assert "--port" in cmd
    assert "9090" in cmd
    assert "--interval" in cmd
    assert "75" in cmd
    assert "--repo" not in cmd


def test_start_help_mentions_config_port_and_current_repo_defaults() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["start", "--help"])

    assert result.exit_code == 0
    assert "config/settings.yaml" in result.stdout
    assert "current repository" in result.stdout.lower()


def test_validate_pid_file_handles_read_errors(
    tmp_path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    pid_file = tmp_path / "orchestra.pid"
    pid_file.write_text("123")

    def _boom(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise FileNotFoundError("simulated race")

    monkeypatch.setattr(type(pid_file), "read_text", _boom)

    pid, is_valid = _validate_pid_file(pid_file)
    assert pid is None
    assert is_valid is False


def test_setup_tailscale_webhook_runs_tsu_start_and_webhook(monkeypatch) -> None:
    import vibe3.orchestra.serve_utils as utils_module

    monkeypatch.setattr(
        utils_module,
        "_resolve_tsu_script",
        lambda: Path("/tmp/tsu.sh"),
    )

    with patch("vibe3.orchestra.serve_utils.subprocess.run") as mock_run:
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=["/tmp/tsu.sh", "start"], returncode=0),
            subprocess.CompletedProcess(
                args=["/tmp/tsu.sh", "serve", "webhook", "8080"],
                returncode=0,
                stdout="Public URL: https://example.ts.net/webhook/github\n",
            ),
        ]
        ok, msg = _setup_tailscale_webhook(8080)

    assert ok is True
    assert "Public URL" in msg
    assert mock_run.call_args_list[0].args[0] == ["/tmp/tsu.sh", "start"]
    assert mock_run.call_args_list[1].args[0] == [
        "/tmp/tsu.sh",
        "serve",
        "webhook",
        "8080",
    ]


def test_setup_tailscale_webhook_returns_error_when_script_missing(monkeypatch) -> None:
    import vibe3.orchestra.serve_utils as utils_module

    monkeypatch.setattr(utils_module, "_resolve_tsu_script", lambda: None)

    ok, msg = _setup_tailscale_webhook(8080)
    assert ok is False
    assert "scripts/tsu.sh" in msg


def test_start_async_with_ts_prints_public_url(monkeypatch) -> None:
    import vibe3.orchestra.serve as serve_module

    monkeypatch.setattr(serve_module, "setup_logging", lambda verbose=0: None)
    monkeypatch.setattr(
        serve_module.OrchestraConfig,
        "from_settings",
        classmethod(
            lambda cls: OrchestraConfig(
                enabled=True,
                polling_interval=60,
                port=8080,
                repo=None,
            )
        ),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "_start_async_serve", lambda _cfg, _v: (True, "started async")
    )
    monkeypatch.setattr(
        serve_module,
        "_setup_tailscale_webhook",
        lambda _port: (True, "Public URL: https://example.ts.net/webhook/github"),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["start", "--async", "--ts"])

    assert result.exit_code == 0
    assert "started async" in result.stdout
    assert "Public URL" in result.stdout


def test_start_async_with_ts_exits_nonzero_when_setup_fails(monkeypatch) -> None:
    import vibe3.orchestra.serve as serve_module

    monkeypatch.setattr(serve_module, "setup_logging", lambda verbose=0: None)
    monkeypatch.setattr(
        serve_module.OrchestraConfig,
        "from_settings",
        classmethod(lambda cls: OrchestraConfig(enabled=True)),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(
        serve_module, "_start_async_serve", lambda _cfg, _v: (True, "started async")
    )
    monkeypatch.setattr(
        serve_module,
        "_setup_tailscale_webhook",
        lambda _port: (False, "ts setup failed"),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["start", "--async", "--ts"])

    assert result.exit_code == 1
    assert "ts setup failed" in result.stdout
