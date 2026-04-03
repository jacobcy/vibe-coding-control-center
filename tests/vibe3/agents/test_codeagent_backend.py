"""Tests for CodeagentBackend - codeagent-wrapper runner.

Tests the core runner functionality with extensible interface design.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.exceptions import AgentExecutionError
from vibe3.models.review_runner import (
    AgentOptions,
)


class TestCodeagentBackend:
    """Tests for CodeagentBackend.run method."""

    def test_run_uses_repo_models_mapping_for_agent_preset(
        self, tmp_path: Path
    ) -> None:
        """Agent preset should resolve through repo-local config/models.json."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        repo_models = tmp_path / "models.json"
        repo_models.write_text(
            '{"agents":{"code-reviewer":{"backend":"claude","model":"claude-sonnet-4-6"}}}'
        )

        with (
            patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run,
            patch("vibe3.agents.backends.codeagent.REPO_MODELS_JSON_PATH", repo_models),
        ):
            mock_run.return_value = mock_result
            options = AgentOptions(
                agent="code-reviewer",
            )
            backend = CodeagentBackend()
            result = backend.run("prompt body", options)

        assert result.exit_code == 0
        assert "VERDICT: PASS" in result.stdout

        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "codeagent-wrapper" in command[0]
        assert "--agent" not in command
        assert "--backend" in command
        assert "claude" in command
        assert "--model" in command
        assert "claude-sonnet-4-6" in command

    def test_run_falls_back_to_agent_flag_when_repo_mapping_missing(
        self, tmp_path: Path
    ) -> None:
        """Unknown repo-local preset mapping should fall back to raw --agent mode."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        repo_models = tmp_path / "models.json"
        repo_models.write_text('{"agents":{"other":{"backend":"claude"}}}')

        with (
            patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run,
            patch("vibe3.agents.backends.codeagent.REPO_MODELS_JSON_PATH", repo_models),
        ):
            mock_run.return_value = mock_result
            backend = CodeagentBackend()
            result = backend.run("prompt body", AgentOptions(agent="code-reviewer"))

        assert result.exit_code == 0
        command = mock_run.call_args[0][0]
        assert "--agent" in command
        assert "code-reviewer" in command

    def test_run_without_model_when_repo_mapping_missing(self, tmp_path: Path) -> None:
        """Fallback agent mode should omit --model when repo mapping is absent."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        repo_models = tmp_path / "models.json"
        repo_models.write_text("{}")

        with (
            patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run,
            patch("vibe3.agents.backends.codeagent.REPO_MODELS_JSON_PATH", repo_models),
        ):
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()
            result = backend.run("prompt body", options)

        assert result.exit_code == 0

        # Verify no --model flag when model is None
        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "--model" not in command

    def test_run_uses_explicit_cwd_when_provided(self) -> None:
        """Runner should execute in the provided cwd when specified."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            backend = CodeagentBackend()
            backend.run(
                "prompt body",
                AgentOptions(agent="code-reviewer"),
                cwd=Path("/tmp/worktree-430"),
            )

        assert mock_run.call_args.kwargs["cwd"] == "/tmp/worktree-430"

    def test_run_non_zero_exit_raises_error(self) -> None:
        """Runner should raise error on non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Error: something failed\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError) as exc_info:
                backend.run("prompt body", options)

        assert "codeagent-wrapper failed" in str(exc_info.value)
        assert "something failed" in str(exc_info.value)

    def test_run_non_zero_exit_prefers_stderr_in_message(self) -> None:
        """Runner should surface stderr details when available."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "stdout ignored\n"
        mock_result.stderr = "wrapper stderr details\n"

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError) as exc_info:
                backend.run("prompt body", options)

        assert "wrapper stderr details" in str(exc_info.value)

    def test_run_wrapper_not_found(self) -> None:
        """Runner should give clear error when wrapper not found."""
        from vibe3.exceptions import AgentExecutionError

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("codeagent-wrapper not found")
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError) as exc_info:
                backend.run("prompt body", options)

        assert "codeagent-wrapper not found" in str(exc_info.value)

    def test_run_timeout(self) -> None:
        """Runner should timeout after specified seconds."""
        import subprocess

        from vibe3.exceptions import AgentExecutionError

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["codeagent-wrapper"], timeout=300
            )
            options = AgentOptions(
                agent="code-reviewer",
                timeout_seconds=300,
            )
            backend = CodeagentBackend()

            with pytest.raises(AgentExecutionError) as exc_info:
                backend.run("prompt body", options)

        assert "timed out" in str(exc_info.value)

    def test_run_uses_prompt_file(self) -> None:
        """Runner should pass prompt via temporary file."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            backend = CodeagentBackend()
            backend.run("my prompt file content", options, task="custom task")

        # Check that command includes --prompt-file
        call_args = mock_run.call_args[0]
        command = call_args[0]
        assert "--prompt-file" in command
        # The prompt file path should be created under ~/.codeagent/agents
        prompt_file_idx = command.index("--prompt-file") + 1
        expected_dir = Path.home() / ".codeagent" / "agents"
        assert Path(command[prompt_file_idx]).parent == expected_dir
        # The last argument should be the custom task
        assert command[-1] == "custom task"

    def test_run_adds_worktree_flag_for_new_session(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            backend = CodeagentBackend()
            backend.run(
                "prompt body",
                AgentOptions(agent="code-reviewer", worktree=True),
            )

        command = mock_run.call_args[0][0]
        assert "--worktree" in command

    def test_run_skips_worktree_flag_for_resume_session(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.agents.backends.codeagent.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            backend = CodeagentBackend()
            backend.run(
                "prompt body",
                AgentOptions(agent="code-reviewer", worktree=True),
                session_id="262f0fea-eacb-4223-b842-b5b5097f94e8",
            )

        command = mock_run.call_args[0][0]
        assert "--worktree" not in command

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

    def test_start_async_command_clears_existing_repo_log(
        self, monkeypatch, tmp_path
    ) -> None:
        backend = CodeagentBackend()
        log_dir = tmp_path / "temp" / "logs"
        log_dir.mkdir(parents=True)
        stale_log = log_dir / "vibe3-manager-issue-372.async.log"
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
        assert handle.log_path == log_dir / "vibe3-manager-issue-372-2.async.log"

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
