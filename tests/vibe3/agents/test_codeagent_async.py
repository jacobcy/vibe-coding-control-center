"""Tests for CodeagentBackend - async, session, and streaming features."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.models.review_runner import AgentOptions


class TestSessionIdExtraction:
    def test_extract_session_id_supports_modern_wrapper_format(self) -> None:
        from vibe3.agents.backends.codeagent import extract_session_id

        output = "some text\nSESSION_ID: ses_2aea4d6b6ffexDUssWC9tEP4Nh\nmore text\n"

        assert extract_session_id(output) == "ses_2aea4d6b6ffexDUssWC9tEP4Nh"

    def test_extract_session_id_supports_wrapper_json_event(self) -> None:
        from vibe3.agents.backends.codeagent import extract_session_id

        output = '{"type":"step_start","sessionID":"ses_2ae4422c7ffeYDHGar7ZxRsnTC"}'

        assert extract_session_id(output) == "ses_2ae4422c7ffeYDHGar7ZxRsnTC"

    def test_extract_session_id_supports_escaped_wrapper_json_event(self) -> None:
        from vibe3.agents.backends.codeagent import extract_session_id

        output = (
            '{"message":"{\\"type\\":\\"step_start\\",'
            '\\"sessionID\\":\\"ses_2ae0c24f2ffehx2ejWE21YTtHi\\"}"}'
        )

        assert extract_session_id(output) == "ses_2ae0c24f2ffehx2ejWE21YTtHi"


class TestStartAsyncCommand:
    def test_start_async_command_clears_existing_repo_log(
        self, monkeypatch, tmp_path
    ) -> None:
        backend = CodeagentBackend()
        log_dir = tmp_path / "temp" / "logs"
        stale_log = log_dir / "issues" / "issue-372" / "manager.async.log"
        stale_log.parent.mkdir(parents=True)
        stale_log.write_text("SESSION_ID: stale_session\n")

        monkeypatch.setattr(
            backend,
            "_default_log_dir",
            lambda: log_dir,
        )

        # Mock subprocess.run - must return returncode != 0
        # to break _allocate_tmux_session_name loop
        def fake_run(*args, **kwargs):
            result = MagicMock()
            result.returncode = (
                1  # Simulate "tmux has-session" failing (no session exists)
            )
            return result

        with patch(
            "vibe3.agents.backends.codeagent.subprocess.run", side_effect=fake_run
        ):
            backend.start_async_command(
                ["echo", "hello"],
                execution_name="vibe3-manager-issue-372",
            )

        assert not stale_log.exists()

    def test_start_async_command_uses_unique_tmux_session_when_name_exists(
        self, monkeypatch, tmp_path
    ) -> None:
        backend = CodeagentBackend()
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)

        monkeypatch.setattr(backend, "_default_log_dir", lambda: log_dir)

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
            "vibe3.agents.backends.codeagent.subprocess.run", side_effect=fake_run
        ):
            handle = backend.start_async_command(
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
        backend = CodeagentBackend()
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)

        monkeypatch.setattr(backend, "_default_log_dir", lambda: log_dir)

        # Mock subprocess.run to break _allocate_tmux_session_name loop
        def fake_run(*args, **kwargs):
            result = MagicMock()
            # Simulate "tmux has-session" failing (no session exists)
            result.returncode = 1
            return result

        with patch(
            "vibe3.agents.backends.codeagent.subprocess.run", side_effect=fake_run
        ):
            handle = backend.start_async_command(
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


class TestAsyncLogFilter:
    def test_async_log_filter_strips_agent_prompt_block(self, tmp_path: Path) -> None:
        """Async log filter should remove <agent-prompt> blocks."""
        backend = CodeagentBackend()
        filter_cmd = backend._build_async_log_filter()

        # Create test input file
        input_file = tmp_path / "input.log"
        input_text = """SESSION_ID: ses_test123
<agent-prompt>
This is the full prompt content that should not appear in logs.
It may contain sensitive information or be very long.
</agent-prompt>
[vibe3 async] command exited with status: 0
"""
        input_file.write_text(input_text)

        # Run the filter
        import subprocess

        result = subprocess.run(
            filter_cmd + [str(input_file)],
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout

        assert "<agent-prompt>" not in output
        assert "</agent-prompt>" not in output
        assert "full prompt content" not in output
        # But should keep control info
        assert "SESSION_ID: ses_test123" in output
        assert "command exited with status: 0" in output
        # Should report suppression
        assert "suppressed" in output and "agent-prompt" in output

    def test_async_log_filter_keeps_session_id_and_exit_status_lines(
        self, tmp_path: Path
    ) -> None:
        """Filter should preserve session ID, exit status, and other diagnostics."""
        backend = CodeagentBackend()
        filter_cmd = backend._build_async_log_filter()

        input_file = tmp_path / "input.log"
        input_text = """SESSION_ID: ses_abc123
Some wrapper output line
[vibe3 async] command exited with status: 0
[vibe3 async] suppressed output summary: 150 lines
"""
        input_file.write_text(input_text)

        import subprocess

        result = subprocess.run(
            filter_cmd + [str(input_file)],
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout

        # All diagnostic lines should be preserved
        assert "SESSION_ID: ses_abc123" in output
        assert "[vibe3 async] command exited with status: 0" in output
        assert "[vibe3 async] suppressed output summary: 150 lines" in output
        assert "Some wrapper output line" in output
