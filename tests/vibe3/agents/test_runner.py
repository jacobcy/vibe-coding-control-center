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

        assert cmd[:3] == ["uv", "run", "--project"]
        assert cmd[4:6] == ["python", str(CodeagentExecutionService._cli_entry())]
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
        backend.start_async_command.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-executor-dev-issue-424",
            log_path=Path("temp/logs/issues/issue-424/run.async.log"),
            prompt_file_path=Path(""),
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

        monkeypatch.setattr("vibe3.agents.runner.sys.argv", ["pytest"])

        result = service.execute_async(command, "dev/issue-424")

        assert result.tmux_session == "vibe3-executor-dev-issue-424"
        assert result.log_path == Path("temp/logs/issues/issue-424/run.async.log")
        backend.start_async_command.assert_called_once()
        called_command = backend.start_async_command.call_args.args[0]
        assert called_command[:3] == ["uv", "run", "--project"]
        assert called_command[4:6] == [
            "python",
            str(CodeagentExecutionService._cli_entry()),
        ]
        assert "--sync" in called_command
        backend.start_async.assert_not_called()
        expected_tmux = "Tmux session: vibe3-executor-dev-issue-424"
        expected_log = "Session log: temp/logs/issues/issue-424/run.async.log"
        assert any(expected_tmux in message for message in echo_messages)
        assert any(expected_log in message for message in echo_messages)

    def test_execute_async_prefers_explicit_cli_args(self, monkeypatch) -> None:
        service = CodeagentExecutionService(VibeConfig.get_defaults())
        backend = MagicMock()
        backend.start_async_command.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-planner-task-issue-42",
            log_path=Path("temp/logs/issues/issue-42/plan.async.log"),
            prompt_file_path=Path(""),
        )

        monkeypatch.setattr("vibe3.agents.runner.CodeagentBackend", lambda: backend)
        monkeypatch.setattr(
            "vibe3.agents.runner.persist_execution_lifecycle_event",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "vibe3.agents.runner.SQLiteClient",
            lambda: MagicMock(),
        )

        command = create_codeagent_command(
            role="planner",
            context_builder=lambda: "prompt",
            task="extra guidance",
            config=service.config,
            branch="task/issue-42",
            cli_args=["plan", "--issue", "42", "--async"],
        )

        service.execute_async(command, "task/issue-42")

        called_command = backend.start_async_command.call_args.args[0]
        assert called_command == [
            "uv",
            "run",
            "--project",
            str(CodeagentExecutionService._repo_root()),
            "python",
            str(CodeagentExecutionService._cli_entry()),
            "plan",
            "--issue",
            "42",
            "--sync",
        ]

    def test_execute_async_passes_explicit_worktree_root_as_cwd(
        self,
        monkeypatch,
    ) -> None:
        service = CodeagentExecutionService(VibeConfig.get_defaults())
        backend = MagicMock()
        backend.start_async_command.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-planner-task-issue-42",
            log_path=Path("temp/logs/issues/issue-42/plan.async.log"),
            prompt_file_path=Path(""),
        )

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
            "vibe3.agents.runner.GitClient",
            lambda: MagicMock(
                get_worktree_root=MagicMock(return_value="/repo/worktree")
            ),
            raising=False,
        )

        command = create_codeagent_command(
            role="planner",
            context_builder=lambda: "prompt",
            task="extra guidance",
            config=service.config,
            branch="task/issue-42",
        )

        monkeypatch.setattr("vibe3.agents.runner.sys.argv", ["pytest"])

        service.execute_async(command, "task/issue-42")

        assert backend.start_async_command.call_args.kwargs["cwd"] == Path(
            "/repo/worktree"
        )
