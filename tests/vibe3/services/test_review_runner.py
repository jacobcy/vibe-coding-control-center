"""Tests for review_runner service - codeagent-wrapper runner.

Tests the core runner functionality with extensible interface design.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.exceptions import AgentExecutionError
from vibe3.models.review_runner import (
    AgentOptions,
)
from vibe3.services.review_runner import (
    run_review_agent,
)


class TestRunReviewAgent:
    """Tests for run_review_agent function."""

    def test_run_review_uses_codeagent_wrapper_with_agent_and_model(self) -> None:
        """Runner should call codeagent-wrapper with correct arguments."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(
                agent="code-reviewer",
            )
            result = run_review_agent("prompt body", options)

        assert result.exit_code == 0
        assert "VERDICT: PASS" in result.stdout

        # Verify command structure
        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "codeagent-wrapper" in command[0]
        assert "--agent" in command
        assert "code-reviewer" in command

    def test_run_review_without_model(self) -> None:
        """Runner should work without model override."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            result = run_review_agent("prompt body", options)

        assert result.exit_code == 0

        # Verify no --model flag when model is None
        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "--model" not in command

    def test_run_review_non_zero_exit_raises_error(self) -> None:
        """Runner should raise error on non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Error: something failed\n"
        mock_result.stderr = ""

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")

            with pytest.raises(AgentExecutionError) as exc_info:
                run_review_agent("prompt body", options)

        assert "codeagent-wrapper failed" in str(exc_info.value)
        assert "something failed" in str(exc_info.value)

    def test_run_review_non_zero_exit_prefers_stderr_in_message(self) -> None:
        """Runner should surface stderr details when available."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "stdout ignored\n"
        mock_result.stderr = "wrapper stderr details\n"

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")

            with pytest.raises(AgentExecutionError) as exc_info:
                run_review_agent("prompt body", options)

        assert "wrapper stderr details" in str(exc_info.value)

    def test_run_review_wrapper_not_found(self) -> None:
        """Runner should give clear error when wrapper not found."""
        from vibe3.exceptions import AgentExecutionError

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("codeagent-wrapper not found")
            options = AgentOptions(agent="code-reviewer")

            with pytest.raises(AgentExecutionError) as exc_info:
                run_review_agent("prompt body", options)

        assert "codeagent-wrapper not found" in str(exc_info.value)

    def test_run_review_timeout(self) -> None:
        """Runner should timeout after specified seconds."""
        import subprocess

        from vibe3.exceptions import AgentExecutionError

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["codeagent-wrapper"], timeout=300
            )
            options = AgentOptions(
                agent="code-reviewer",
                timeout_seconds=300,
            )

            with pytest.raises(AgentExecutionError) as exc_info:
                run_review_agent("prompt body", options)

        assert "timed out" in str(exc_info.value)

    def test_run_review_uses_prompt_file(self) -> None:
        """Runner should pass prompt via temporary file."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result\n"
        mock_result.stderr = ""

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            options = AgentOptions(agent="code-reviewer")
            run_review_agent("my prompt file content", options, task="custom task")

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

    def test_run_review_adds_worktree_flag_for_new_session(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            run_review_agent(
                "prompt body",
                AgentOptions(agent="code-reviewer", worktree=True),
            )

        command = mock_run.call_args[0][0]
        assert "--worktree" in command

    def test_run_review_skips_worktree_flag_for_resume_session(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.return_value = mock_result
            run_review_agent(
                "prompt body",
                AgentOptions(agent="code-reviewer", worktree=True),
                session_id="262f0fea-eacb-4223-b842-b5b5097f94e8",
            )

        command = mock_run.call_args[0][0]
        assert "--worktree" not in command

    def test_run_review_streams_output_while_capturing(self, capsys) -> None:
        """Runner should stream wrapper output to console and capture it."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "line one\nVERDICT: PASS\n"
        mock_result.stderr = ""

        with patch(
            "vibe3.services.review_runner.subprocess.run", return_value=mock_result
        ):
            result = run_review_agent(
                "prompt body", AgentOptions(agent="code-reviewer")
            )

        captured = capsys.readouterr()
        assert "line one" in captured.out
        assert "VERDICT: PASS" in captured.out
        assert "line one" in result.stdout
        assert "VERDICT: PASS" in result.stdout

    def test_run_review_handles_none_stdout(self) -> None:
        """Runner should pass through None stdout."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = None
        mock_result.stderr = ""

        with patch(
            "vibe3.services.review_runner.subprocess.run", return_value=mock_result
        ):
            result = run_review_agent(
                "prompt body", AgentOptions(agent="code-reviewer")
            )
        assert result.exit_code == 0
        assert result.stdout is None

    def test_run_review_handles_os_error(self) -> None:
        """Runner should handle OSError gracefully."""

        with patch("vibe3.services.review_runner.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("I/O error")

            with pytest.raises(OSError, match="I/O error"):
                run_review_agent("prompt body", AgentOptions(agent="code-reviewer"))

    @patch("vibe3.services.review_runner.subprocess.run")
    @patch("vibe3.services.review_runner.Path.mkdir")
    def test_run_review_creates_codeagent_agents_dir(
        self, mock_mkdir, mock_run
    ) -> None:
        """Runner should ensure the codeagent agents directory exists."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = run_review_agent("prompt body", AgentOptions(agent="code-reviewer"))

        assert result.exit_code == 0
        mock_mkdir.assert_any_call(parents=True, exist_ok=True)

    @patch("vibe3.services.review_runner.subprocess.run")
    @patch("vibe3.services.review_runner.Path.mkdir")
    def test_run_review_uses_codeagent_agents_dir_for_prompt_file(
        self, mock_mkdir, mock_run
    ) -> None:
        """Runner should place prompt files under ~/.codeagent/agents."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "VERDICT: PASS\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        run_review_agent("prompt body", AgentOptions(agent="code-reviewer"))

        command = mock_run.call_args[0][0]
        prompt_file_idx = command.index("--prompt-file") + 1
        expected_dir = Path.home() / ".codeagent" / "agents"
        assert Path(command[prompt_file_idx]).parent == expected_dir
