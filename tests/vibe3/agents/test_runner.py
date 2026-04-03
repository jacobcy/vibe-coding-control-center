"""Tests for agent runner async self-invocation behavior."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.agents.models import create_codeagent_command
from vibe3.agents.runner import CodeagentExecutionService
from vibe3.config.settings import VibeConfig


class TestCodeagentExecutionService:
    def test_build_self_invocation_appends_sync_for_tmux_child(self) -> None:
        cmd = CodeagentExecutionService.build_self_invocation(
            ["run", "--plan", "/tmp/demo.md"]
        )

        assert cmd[:4] == ["uv", "run", "python", "src/vibe3/cli.py"]
        assert "--sync" in cmd

    def test_build_self_invocation_drops_async_and_keeps_sync_single(self) -> None:
        cmd = CodeagentExecutionService.build_self_invocation(
            ["review", "base", "--async", "--sync"]
        )

        assert "--async" not in cmd
        assert cmd.count("--sync") == 1

    def test_execute_async_prints_tmux_session_and_log(self, monkeypatch) -> None:
        service = CodeagentExecutionService(VibeConfig.get_defaults())
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-executor-dev-issue-424",
            log_path=Path("temp/logs/vibe3-executor-dev-issue-424.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        echo_messages: list[str] = []

        monkeypatch.setattr("vibe3.agents.runner.CodeagentBackend", lambda: backend)
        monkeypatch.setattr(
            "vibe3.agents.runner.persist_execution_lifecycle_event",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "vibe3.agents.runner.SQLiteClient",
            lambda: MagicMock(),
        )
        monkeypatch.setattr(
            "vibe3.agents.runner.echo",
            lambda message: echo_messages.append(message),
        )

        command = create_codeagent_command(
            role="executor",
            context_builder=lambda: "prompt",
            task="run task",
            config=service.config,
            branch="dev/issue-424",
        )

        result = service.execute_async(command, "dev/issue-424")

        assert result.tmux_session == "vibe3-executor-dev-issue-424"
        assert result.log_path == Path(
            "temp/logs/vibe3-executor-dev-issue-424.async.log"
        )
        expected_tmux = "Tmux session: vibe3-executor-dev-issue-424"
        expected_log = "Session log: temp/logs/vibe3-executor-dev-issue-424.async.log"
        assert any(expected_tmux in message for message in echo_messages)
        assert any(expected_log in message for message in echo_messages)
