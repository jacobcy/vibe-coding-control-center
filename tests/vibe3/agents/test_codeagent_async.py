"""Tests for CodeagentBackend - async command and streaming features."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.backends.async_launcher import (
    build_async_log_filter,
    build_async_shell_command,
    start_async_command,
)
from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.models.review_runner import AgentOptions


class TestStartAsyncCommand:
    def test_build_async_shell_command_exits_immediately_by_default(self) -> None:
        shell = build_async_shell_command(
            ["echo", "hello"],
            log_path=Path("/tmp/test.log"),
            keep_alive_seconds=0,
        )

        assert "cmd_status=${PIPESTATUS[0]:-$?}" in shell
        assert "command exited with status: ${cmd_status}" in shell
        assert "exit ${cmd_status}" in shell
        assert "; status=${PIPESTATUS[0]:-$?};" not in shell
        assert "keeping tmux session alive" not in shell
        assert "sleep 0" not in shell

    def test_build_async_shell_command_can_keep_session_when_requested(self) -> None:
        shell = build_async_shell_command(
            ["echo", "hello"],
            log_path=Path("/tmp/test.log"),
            keep_alive_seconds=5,
        )

        assert "keeping tmux session alive for 5s" in shell
        assert "sleep 5" in shell

    def test_build_async_log_filter_is_single_shell_line(self) -> None:
        filter_cmd = build_async_log_filter()

        assert filter_cmd[0] == "awk"
        assert "\n" not in filter_cmd[1]
        assert "END {;" not in filter_cmd[1]

    def test_build_async_shell_command_injects_env_overrides(self) -> None:
        shell = build_async_shell_command(
            ["uv", "run", "python", "src/vibe3/cli.py", "internal", "manager", "328"],
            log_path=Path("/tmp/test.log"),
            keep_alive_seconds=0,
            env={
                "VIBE3_ASYNC_CHILD": "1",
                "VIBE3_MANAGER_BACKEND": "opencode",
                "VIBE3_MANAGER_MODEL": "opencode/minimax-m2.5-free",
            },
        )

        assert "env VIBE3_ASYNC_CHILD=1" in shell
        assert "VIBE3_MANAGER_BACKEND=opencode" in shell
        assert "VIBE3_MANAGER_MODEL=opencode/minimax-m2.5-free" in shell

    def test_start_async_command_clears_existing_repo_log(
        self, monkeypatch, tmp_path
    ) -> None:
        log_dir = tmp_path / "temp" / "logs"
        stale_log = log_dir / "issues" / "issue-372" / "manager.async.log"
        stale_log.parent.mkdir(parents=True)
        stale_log.write_text("SESSION_ID: stale_session\n")

        monkeypatch.setattr(
            "vibe3.agents.backends.async_launcher.default_log_dir",
            lambda: log_dir,
        )

        # Mock subprocess.run - must return returncode != 0
        # to break _allocate_tmux_session_name loop
        def fake_run(*args, **kwargs):
            cmd = args[0] if args else []
            # tmux has-session should fail (session doesn't exist)
            if "has-session" in cmd:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr="no session",
                )
            # tmux new-session should succeed
            elif "new-session" in cmd:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="",
                    stderr="",
                )
            # Default: fail
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr="error",
            )

        with patch(
            "vibe3.agents.backends.async_launcher.subprocess.run", side_effect=fake_run
        ):
            # Also mock session.py subprocess.run to avoid actual tmux calls
            with patch(
                "vibe3.environment.session.subprocess.run", side_effect=fake_run
            ):
                start_async_command(
                    ["echo", "hello"],
                    execution_name="vibe3-manager-issue-372",
                )

        assert not stale_log.exists()

    def test_start_async_command_embeds_env_overrides_in_wrapper_script(
        self, monkeypatch, tmp_path
    ) -> None:
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr(
            "vibe3.agents.backends.async_launcher.default_log_dir",
            lambda: log_dir,
        )

        launched_scripts: list[Path] = []

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["tmux", "has-session", "-t"]:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr="no session",
                )
            if cmd[:4] == ["tmux", "new-session", "-d", "-s"]:
                launched_scripts.append(Path(cmd[6]))
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )

        with (
            patch(
                "vibe3.agents.backends.async_launcher.subprocess.run",
                side_effect=fake_run,
            ),
        ):
            start_async_command(
                [
                    "uv",
                    "run",
                    "python",
                    "src/vibe3/cli.py",
                    "internal",
                    "manager",
                    "328",
                ],
                execution_name="vibe3-manager-issue-328",
                env={
                    "VIBE3_ASYNC_CHILD": "1",
                    "VIBE3_MANAGER_BACKEND": "opencode",
                    "VIBE3_MANAGER_MODEL": "opencode/minimax-m2.5-free",
                },
            )

        assert launched_scripts
        wrapper_text = launched_scripts[0].read_text(encoding="utf-8")
        assert "VIBE3_MANAGER_BACKEND=opencode" in wrapper_text
        assert "VIBE3_MANAGER_MODEL=opencode/minimax-m2.5-free" in wrapper_text

    def test_start_async_command_uses_unique_tmux_session_when_name_exists(
        self, monkeypatch, tmp_path
    ) -> None:
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "vibe3.agents.backends.async_launcher.default_log_dir",
            lambda: log_dir,
        )

        # Mock subprocess.run to simulate session name collision
        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["tmux", "has-session", "-t"]:
                target = cmd[3]
                result = MagicMock()
                # 1st call: exists (0), 2nd call: doesn't exist (1)
                result.returncode = 0 if target == "vibe3-manager-issue-372" else 1
                return result
            # For tmux new-session, return success
            result = MagicMock()
            result.returncode = 0
            return result

        with patch(
            "vibe3.agents.backends.async_launcher.subprocess.run", side_effect=fake_run
        ):
            handle = start_async_command(
                ["echo", "hello"],
                execution_name="vibe3-manager-issue-372",
            )

        assert handle.tmux_session == "vibe3-manager-issue-372-2"
        assert (
            handle.log_path == log_dir / "issues" / "issue-372" / "manager-2.async.log"
        )

    def test_start_async_command_places_governance_logs_under_governance_dir(
        self, monkeypatch, tmp_path
    ) -> None:
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "vibe3.agents.backends.async_launcher.default_log_dir",
            lambda: log_dir,
        )

        # Mock subprocess.run to break _allocate_tmux_session_name loop
        def fake_run(*args, **kwargs):
            cmd = args[0] if args else []
            # tmux has-session should fail (session doesn't exist)
            if "has-session" in cmd:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr="no session",
                )
            # tmux new-session should succeed
            elif "new-session" in cmd:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="",
                    stderr="",
                )
            # Default: fail
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=1,
                stdout="",
                stderr="error",
            )

        with patch(
            "vibe3.agents.backends.async_launcher.subprocess.run", side_effect=fake_run
        ):
            # Also mock session.py subprocess.run
            with patch(
                "vibe3.environment.session.subprocess.run", side_effect=fake_run
            ):
                handle = start_async_command(
                    ["echo", "hello"],
                    execution_name="vibe3-governance-scan-20260405-114913-t1",
                )

        assert handle.log_path == (
            log_dir / "orchestra" / "governance" / "scan-20260405-114913-t1.async.log"
        )


class TestRunStreamingAndEdgeCases:
    def test_run_streams_output_while_capturing(self, capsys) -> None:
        """Runner should stream wrapper output to console and capture it."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "line one\nVERDICT: PASS\n"
        mock_result.stderr = ""

        with patch(
            "vibe3.agents.backends.codeagent.subprocess.run", return_value=mock_result
        ):
            backend = CodeagentBackend()
            result = backend.run("prompt body", AgentOptions(agent="code-reviewer"))

        captured = capsys.readouterr()
        assert "line one" in captured.out
        assert "VERDICT: PASS" in captured.out
        assert "line one" in result.stdout
        assert "VERDICT: PASS" in result.stdout

    def test_run_handles_none_stdout(self) -> None:
        """Runner should pass through None stdout."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = None
        mock_result.stderr = ""

        with patch(
            "vibe3.agents.backends.codeagent.subprocess.run", return_value=mock_result
        ):
            backend = CodeagentBackend()
            result = backend.run("prompt body", AgentOptions(agent="code-reviewer"))
        assert result.exit_code == 0
        assert result.stdout is None

    def test_run_handles_os_error(self) -> None:
        """Runner should handle OSError gracefully."""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("I/O error")

            backend = CodeagentBackend()
            with pytest.raises(OSError, match="I/O error"):
                backend.run("prompt body", AgentOptions(agent="code-reviewer"))

    @patch("vibe3.agents.backends.codeagent.subprocess.run")
    @patch("vibe3.agents.backends.codeagent.Path.mkdir")
    def test_run_creates_codeagent_agents_dir(self, mock_mkdir, mock_run) -> None:
        """Runner should ensure the codeagent agents directory exists."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        backend = CodeagentBackend()
        result = backend.run("prompt body", AgentOptions(agent="code-reviewer"))

        assert result.exit_code == 0
        mock_mkdir.assert_any_call(parents=True, exist_ok=True)

    @patch("vibe3.agents.backends.codeagent.subprocess.run")
    @patch("vibe3.agents.backends.codeagent.Path.mkdir")
    def test_run_uses_codeagent_agents_dir_for_prompt_file(
        self, mock_mkdir, mock_run
    ) -> None:
        """Runner should place prompt files under ~/.codeagent/agents."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        backend = CodeagentBackend()
        backend.run("prompt body", AgentOptions(agent="code-reviewer"))

        command = mock_run.call_args[0][0]
        prompt_file_idx = command.index("--prompt-file") + 1
        expected_dir = Path.home() / ".codeagent" / "agents"
        assert Path(command[prompt_file_idx]).parent == expected_dir
