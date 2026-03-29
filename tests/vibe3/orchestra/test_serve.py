"""Tests for orchestra serve command wiring and toggles."""

import subprocess
from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.orchestra.config import (
    AssigneeDispatchConfig,
    CommentReplyConfig,
    OrchestraConfig,
    PRReviewDispatchConfig,
)
from vibe3.orchestra.serve import _build_server, app


def test_build_server_registers_only_enabled_services() -> None:
    cfg = OrchestraConfig(
        assignee_dispatch=AssigneeDispatchConfig(enabled=False),
        comment_reply=CommentReplyConfig(enabled=False),
        pr_review_dispatch=PRReviewDispatchConfig(enabled=True),
    )
    heartbeat, _ = _build_server(cfg)
    assert heartbeat.service_names == ["PRReviewDispatchService"]


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
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))

    with patch("vibe3.orchestra.serve.subprocess.run") as mock_run:
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

    monkeypatch.setattr(serve_module, "setup_logging", lambda verbose=0: None)
    monkeypatch.setattr(
        serve_module.OrchestraConfig,
        "from_settings",
        classmethod(lambda cls: OrchestraConfig(enabled=True)),
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))

    error = subprocess.CalledProcessError(
        returncode=1,
        cmd=["tmux"],
        stderr="duplicate session: vibe3-orchestra-serve",
    )
    with patch("vibe3.orchestra.serve.subprocess.run", side_effect=error):
        runner = CliRunner()
        result = runner.invoke(app, ["start", "--async"])

    assert result.exit_code == 1
    assert "already exists" in result.stdout.lower()
