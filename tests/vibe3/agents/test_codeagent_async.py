"""Tests for CodeagentBackend - async command and streaming features."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.backends.async_launcher import (
    build_tmux_log_filter,
    start_async_command,
)
from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.models.review_runner import AgentOptions


class TestStartAsyncCommand:
    def test_build_tmux_log_filter_is_valid_for_local_awk(self, tmp_path: Path) -> None:
        sample = tmp_path / "sample.log"
        sample.write_text(
            "noise 1\n"
            "Uninstalled 1 package in 11ms\n"
            "Installing wheels...\n"
            "[codeagent-wrapper]\n"
            "line one\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            ["awk", build_tmux_log_filter("test_session_id"), str(sample)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0
        assert result.stdout == ("noise 1\n" "[codeagent-wrapper]\n" "line one\n")

    def test_build_tmux_log_filter_filters_known_uv_noise_only(self) -> None:
        awk_script = build_tmux_log_filter("test_session_id")

        assert "Uninstalled" in awk_script
        assert "Installing wheels" in awk_script
        assert "Installed 1 package" in awk_script
        assert "skip_prompt = 1" in awk_script

    def test_start_async_command_clears_existing_repo_log(
        self, monkeypatch, tmp_path
    ) -> None:
        """When a log file exists, allocate_log_path returns a new unique path."""
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
                handle = start_async_command(
                    ["echo", "hello"],
                    execution_name="vibe3-manager-issue-372",
                )

        # The stale log should still exist (we don't delete old logs)
        # Instead, allocate_log_path returns a new unique path
        assert stale_log.exists()
        # The new log should have a -2 suffix
        assert (
            handle.log_path == log_dir / "issues" / "issue-372" / "manager-2.async.log"
        )

    def test_start_async_command_embeds_env_overrides_in_tmux_command(
        self, monkeypatch, tmp_path
    ) -> None:
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr(
            "vibe3.agents.backends.async_launcher.default_log_dir",
            lambda: log_dir,
        )

        tmux_commands: list[list[str]] = []

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["tmux", "has-session", "-t"]:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr="no session",
                )
            if cmd[:3] == ["tmux", "new-session", "-d"]:
                tmux_commands.append(cmd)
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

        assert tmux_commands
        final_cmd = tmux_commands[0]
        assert "env" in final_cmd
        assert "VIBE3_ASYNC_CHILD=1" in final_cmd
        assert "VIBE3_MANAGER_BACKEND=opencode" in final_cmd
        assert "VIBE3_MANAGER_MODEL=opencode/minimax-m2.5-free" in final_cmd
        assert "src/vibe3/cli.py" in final_cmd

    def test_start_async_command_preserves_path_for_tmux_session(
        self, monkeypatch, tmp_path
    ) -> None:
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)
        monkeypatch.setattr(
            "vibe3.agents.backends.async_launcher.default_log_dir",
            lambda: log_dir,
        )

        tmux_commands: list[list[str]] = []

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["tmux", "has-session", "-t"]:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr="no session",
                )
            if cmd[:3] == ["tmux", "new-session", "-d"]:
                tmux_commands.append(cmd)
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

        test_path = "/tmp/test-bin:/usr/local/bin"
        monkeypatch.setenv("PATH", test_path)

        with patch(
            "vibe3.agents.backends.async_launcher.subprocess.run",
            side_effect=fake_run,
        ):
            start_async_command(
                ["echo", "hello"],
                execution_name="vibe3-run-issue-417",
                env={"PATH": test_path, "VIBE3_ASYNC_CHILD": "1"},
            )

        assert tmux_commands
        final_cmd = tmux_commands[0]
        assert "env" in final_cmd
        assert f"PATH={test_path}" in final_cmd
        assert "VIBE3_ASYNC_CHILD=1" in final_cmd

    def test_start_async_command_rejects_duplicate_l3_session(
        self, monkeypatch, tmp_path
    ) -> None:
        """L3 roles (manager/plan/run/review) should reject duplicate sessions."""
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "vibe3.agents.backends.async_launcher.default_log_dir",
            lambda: log_dir,
        )

        # Mock subprocess.run to simulate session exists
        def fake_run(cmd, *args, **kwargs):
            # tmux ls returns session list (session exists)
            if cmd[:2] == ["tmux", "ls"]:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="vibe3-manager-issue-372: 1 windows\n",
                    stderr="",
                )
            # tmux has-session checks for specific session
            elif cmd[:3] == ["tmux", "has-session", "-t"]:
                result = MagicMock()
                # Session exists (returncode 0)
                result.returncode = 0
                return result
            # For tmux new-session, return success
            result = MagicMock()
            result.returncode = 0
            return result

        with patch(
            "vibe3.agents.backends.async_launcher.subprocess.run", side_effect=fake_run
        ):
            # Should raise RuntimeError because L3 roles reject duplicate sessions
            with pytest.raises(RuntimeError, match="already exists"):
                start_async_command(
                    ["echo", "hello"],
                    execution_name="vibe3-manager-issue-372",
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

    def test_start_async_command_pipe_pane_uses_filtered_log_capture(
        self, monkeypatch, tmp_path
    ) -> None:
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)

        monkeypatch.setattr(
            "vibe3.agents.backends.async_launcher.default_log_dir",
            lambda: log_dir,
        )

        tmux_commands: list[list[str]] = []

        def fake_run(cmd, *args, **kwargs):
            tmux_commands.append(cmd)
            if cmd[:3] == ["tmux", "has-session", "-t"]:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=1,
                    stdout="",
                    stderr="no session",
                )
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=0,
                stdout="",
                stderr="",
            )

        with patch(
            "vibe3.agents.backends.async_launcher.subprocess.run",
            side_effect=fake_run,
        ):
            handle = start_async_command(
                ["echo", "hello"],
                execution_name="vibe3-run-issue-348",
            )

        pipe_pane_cmd = next(
            cmd for cmd in tmux_commands if cmd[:2] == ["tmux", "pipe-pane"]
        )
        assert str(handle.log_path) in pipe_pane_cmd[-1]
        assert "Uninstalled" in pipe_pane_cmd[-1]
        assert "Installing wheels" in pipe_pane_cmd[-1]
        assert "skip_prompt = 1" in pipe_pane_cmd[-1]


class TestRunStreamingAndEdgeCases:
    def test_run_streams_output_while_capturing(self, capsys) -> None:
        """Runner should stream wrapper output to console and capture it."""

        class FakeStream:
            def __init__(self, chunks: list[bytes]) -> None:
                self._chunks = iter(chunks)

            def read(self, n: int) -> bytes:
                return next(self._chunks, b"")

            def read1(self, n: int) -> bytes:
                return self.read(n)

        class FakePopen:
            def __init__(self, *args, **kwargs) -> None:
                self.args = args[0]
                self.returncode = 0
                self.stdout = FakeStream(
                    [
                        b"-> Executing with gemini...\n",
                        b"line one\n",
                        b"VERDICT: PASS\n",
                        b"",
                    ]
                )
                self.stderr = FakeStream([b""])

            def wait(self, timeout: int | None = None) -> int:
                return self.returncode

        with patch("vibe3.agents.backends.codeagent.subprocess.Popen", FakePopen):
            backend = CodeagentBackend()
            result = backend.run("prompt body", AgentOptions(agent="vibe-reviewer"))

        captured = capsys.readouterr()
        assert "-> Executing with gemini" in captured.out
        assert "line one" in captured.out
        assert "VERDICT: PASS" in captured.out
        assert "-> Executing with gemini" in result.stdout
        assert "line one" in result.stdout
        assert "VERDICT: PASS" in result.stdout

    def test_run_handles_none_stdout(self) -> None:
        """Runner should pass through None stdout."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = None
        mock_result.stderr = ""

        with patch.object(
            CodeagentBackend, "_run_subprocess", return_value=(mock_result, None)
        ):
            backend = CodeagentBackend()
            result = backend.run("prompt body", AgentOptions(agent="vibe-reviewer"))
        assert result.exit_code == 0
        assert result.stdout is None

    def test_run_handles_os_error(self) -> None:
        """Runner should handle OSError gracefully."""

        with patch.object(CodeagentBackend, "_run_subprocess") as mock_run:
            mock_run.side_effect = OSError("I/O error")

            backend = CodeagentBackend()
            with pytest.raises(OSError, match="I/O error"):
                backend.run("prompt body", AgentOptions(agent="vibe-reviewer"))

    @patch.object(CodeagentBackend, "_run_subprocess")
    @patch("vibe3.agents.backends.codeagent.Path.mkdir")
    def test_run_creates_codeagent_agents_dir(self, mock_mkdir, mock_run) -> None:
        """Runner should ensure the codeagent agents directory exists."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        mock_run.return_value = (mock_result, None)

        backend = CodeagentBackend()
        result = backend.run("prompt body", AgentOptions(agent="vibe-reviewer"))

        assert result.exit_code == 0
        mock_mkdir.assert_any_call(parents=True, exist_ok=True)

    @patch.object(CodeagentBackend, "_run_subprocess")
    @patch("vibe3.agents.backends.codeagent.Path.mkdir")
    def test_run_uses_codeagent_agents_dir_for_prompt_file(
        self, mock_mkdir, mock_run
    ) -> None:
        """Runner should place prompt files under ~/.codeagent/agents."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        mock_run.return_value = (mock_result, None)

        backend = CodeagentBackend()
        backend.run("prompt body", AgentOptions(agent="vibe-reviewer"))

        command = mock_run.call_args[0][0]
        prompt_file_idx = command.index("--prompt-file") + 1
        expected_dir = Path.home() / ".codeagent" / "agents"
        assert Path(command[prompt_file_idx]).parent == expected_dir
