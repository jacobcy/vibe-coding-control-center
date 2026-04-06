"""Tests for orchestra serve command wiring and toggles."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vibe3.orchestra.config import (
    AssigneeDispatchConfig,
    CommentReplyConfig,
    GovernanceConfig,
    OrchestraConfig,
    PRReviewDispatchConfig,
    StateLabelDispatchConfig,
    SupervisorHandoffConfig,
)
from vibe3.orchestra.failed_gate import GateResult
from vibe3.server.app import (
    app,
)
from vibe3.server.registry import (
    _build_async_serve_command,
    _build_server,
    _resolve_dispatcher_models_root,
    _resolve_orchestra_log_dir,
    _resolve_orchestra_repo_root,
    _setup_tailscale_webhook,
    _validate_pid_file,
)


@pytest.fixture(autouse=True)
def mock_failed_gate():
    with patch("vibe3.orchestra.failed_gate.FailedGate.check") as mock_check:
        mock_check.return_value = GateResult.open()
        yield mock_check


def test_build_server_registers_only_enabled_services() -> None:
    cfg = OrchestraConfig(
        assignee_dispatch=AssigneeDispatchConfig(enabled=False),
        comment_reply=CommentReplyConfig(enabled=False),
        pr_review_dispatch=PRReviewDispatchConfig(enabled=True),
    )
    heartbeat, _ = _build_server(cfg)
    assert "PRReviewDispatchService" in heartbeat.service_names
    assert "GovernanceService" in heartbeat.service_names
    assert "StateLabelDispatchService(manager:ready)" in heartbeat.service_names
    assert "StateLabelDispatchService(manager:handoff)" in heartbeat.service_names
    assert "StateLabelDispatchService(plan:claimed)" in heartbeat.service_names
    assert "StateLabelDispatchService(run:in-progress)" in heartbeat.service_names
    assert "StateLabelDispatchService(review:review)" in heartbeat.service_names
    assert "SupervisorHandoffService" in heartbeat.service_names


def test_resolve_orchestra_repo_root_prefers_git_common_dir_parent(monkeypatch) -> None:
    import vibe3.server.registry as registry_module

    monkeypatch.setattr(
        registry_module.GitClient,
        "get_git_common_dir",
        lambda self: "/repo/.git",
    )

    assert _resolve_orchestra_repo_root() == Path("/repo")


def test_resolve_dispatcher_models_root_prefers_main_repo_when_not_debug(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "vibe3.server.registry._resolve_orchestra_repo_root",
        lambda: Path("/main-repo"),
    )

    assert _resolve_dispatcher_models_root(
        OrchestraConfig(debug=False),
        launch_cwd=Path("/debug-wt"),
    ) == Path("/main-repo")


def test_resolve_dispatcher_models_root_uses_launch_cwd_in_debug() -> None:
    assert _resolve_dispatcher_models_root(
        OrchestraConfig(debug=True),
        launch_cwd=Path("/debug-wt"),
    ) == Path("/debug-wt")


def test_resolve_orchestra_log_dir_uses_launch_cwd() -> None:
    assert _resolve_orchestra_log_dir(Path("/debug-wt")) == Path("/debug-wt/temp/logs")


def test_build_server_governance_disabled() -> None:
    cfg = OrchestraConfig(
        assignee_dispatch=AssigneeDispatchConfig(enabled=False),
        comment_reply=CommentReplyConfig(enabled=False),
        pr_review_dispatch=PRReviewDispatchConfig(enabled=False),
        governance=GovernanceConfig(enabled=False),
        state_label_dispatch=StateLabelDispatchConfig(enabled=False),
        supervisor_handoff=SupervisorHandoffConfig(enabled=False),
    )
    heartbeat, _ = _build_server(cfg)
    assert heartbeat.service_names == []


def test_start_exits_when_orchestra_disabled(monkeypatch) -> None:
    import vibe3.server.app as serve_module

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
    import vibe3.server.app as serve_module
    import vibe3.server.registry as utils_module

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

    with patch("vibe3.server.registry.subprocess.run") as mock_run:
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
    import vibe3.server.app as serve_module
    import vibe3.server.registry as utils_module

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
    with patch("vibe3.server.registry.subprocess.run", side_effect=error):
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


def test_build_async_command_exports_models_root_and_log_dir(monkeypatch) -> None:
    monkeypatch.setattr(
        "vibe3.server.registry._resolve_dispatcher_models_root",
        lambda _config, launch_cwd: Path("/main-repo"),
    )
    monkeypatch.setattr(
        "vibe3.server.registry._resolve_orchestra_log_dir",
        lambda launch_cwd: Path("/debug-wt/temp/logs"),
    )

    cmd = _build_async_serve_command(
        OrchestraConfig(enabled=True, polling_interval=75, port=9090),
        verbose=0,
        launch_cwd=Path("/debug-wt"),
    )

    assert "VIBE3_REPO_MODELS_ROOT=/main-repo" in cmd
    assert "VIBE3_ASYNC_LOG_DIR=/debug-wt/temp/logs" in cmd


def test_build_async_command_includes_debug_flag() -> None:
    cfg = OrchestraConfig(
        enabled=True,
        polling_interval=60,
        port=8080,
        debug=True,
    )

    cmd = _build_async_serve_command(cfg, verbose=0)

    assert "--debug" in cmd


def test_start_help_mentions_config_port_and_current_repo_defaults() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["start", "--help"])

    assert result.exit_code == 0
    assert "config/settings.yaml" in result.stdout
    assert "current repository" in result.stdout.lower()


def test_start_debug_overrides_interval_and_scene_base(monkeypatch) -> None:
    import vibe3.server.app as serve_module

    captured = {}

    async def _fake_run(config, port):
        captured["config"] = config
        captured["port"] = port
        raise KeyboardInterrupt

    monkeypatch.setattr(serve_module, "setup_logging", lambda verbose=0: None)
    monkeypatch.setattr(
        serve_module.OrchestraConfig,
        "from_settings",
        classmethod(
            lambda cls: OrchestraConfig(
                enabled=True,
                polling_interval=900,
                debug_polling_interval=60,
                port=8080,
                scene_base_ref="origin/main",
            )
        ),
    )
    monkeypatch.setattr(
        serve_module.GitClient, "get_current_branch", lambda self: "dev/post-437-debug"
    )
    monkeypatch.setattr(serve_module, "_validate_pid_file", lambda _: (None, False))
    monkeypatch.setattr(serve_module, "_run", _fake_run)

    runner = CliRunner()
    result = runner.invoke(app, ["start", "--debug"])

    assert result.exit_code == 0
    config = captured["config"]
    assert config.debug is True
    assert config.polling_interval == 60
    assert config.scene_base_ref == "dev/post-437-debug"
    assert "scene_base: dev/post-437-debug" in result.stdout
    assert "Main log:" in result.stdout
    assert "Log dir:" in result.stdout


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
    import vibe3.server.registry as utils_module

    monkeypatch.setattr(
        utils_module,
        "_resolve_tsu_script",
        lambda: Path("/tmp/tsu.sh"),
    )

    with patch("vibe3.server.registry.subprocess.run") as mock_run:
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
    import vibe3.server.registry as utils_module

    monkeypatch.setattr(utils_module, "_resolve_tsu_script", lambda: None)

    ok, msg = _setup_tailscale_webhook(8080)
    assert ok is False
    assert "scripts/tsu.sh" in msg


def test_start_async_with_ts_prints_public_url(monkeypatch) -> None:
    import vibe3.server.app as serve_module

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
    import vibe3.server.app as serve_module

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
