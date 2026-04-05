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

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            backend.start_async_command(
                ["echo", "hello"],
                execution_name="vibe3-manager-issue-372",
            )

        assert not stale_log.exists()
        assert mock_run.called

    def test_start_async_command_uses_unique_tmux_session_when_name_exists(
        self, monkeypatch, tmp_path
    ) -> None:
        backend = CodeagentBackend()
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)

        monkeypatch.setattr(backend, "_default_log_dir", lambda: log_dir)

        def fake_run(cmd, *args, **kwargs):
            if cmd[:3] == ["tmux", "has-session", "-t"]:
                target = cmd[3]
                result = MagicMock()
                result.returncode = 0 if target == "vibe3-manager-issue-372" else 1
                return result
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

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
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
