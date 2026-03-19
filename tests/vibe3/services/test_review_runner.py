"""Tests for review_runner service - codeagent-wrapper runner.

Tests the core runner functionality with extensible interface design.
"""

from dataclasses import FrozenInstanceError
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.review_runner import (
    ReviewAgentOptions,
    ReviewAgentResult,
    run_review_agent,
)


class TestReviewAgentOptions:
    """Tests for ReviewAgentOptions dataclass - immutable configuration."""

    def test_default_options(self) -> None:
        """Default options should be code-reviewer agent with default settings."""
        options = ReviewAgentOptions()
        assert options.agent == "code-reviewer"
        assert options.model is None
        assert options.timeout_seconds == 600

    def test_custom_options(self) -> None:
        """Should support custom agent, model."""
        options = ReviewAgentOptions(
            agent="code-reviewer",
            model="gpt-5.4",
            timeout_seconds=300,
        )
        assert options.agent == "code-reviewer"
        assert options.model == "gpt-5.4"
        assert options.timeout_seconds == 300

    def test_options_are_frozen(self) -> None:
        """Options should be immutable (frozen dataclass)."""
        options = ReviewAgentOptions()
        with pytest.raises(FrozenInstanceError):
            options.agent = "other"  # type: ignore

    def test_model_can_be_overridden(self) -> None:
        """Model can be set to override default."""
        options = ReviewAgentOptions(model="claude-3-opus")
        assert options.model == "claude-3-opus"


class TestRunReviewAgent:
    """Tests for run_review_agent function."""

    def test_run_review_uses_codeagent_wrapper_with_agent_and_model(self) -> None:
        """Runner should call codeagent-wrapper with correct arguments."""
        with patch("vibe3.services.review_runner.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                args=[], returncode=0, stdout="VERDICT: PASS", stderr=""
            )
            options = ReviewAgentOptions(
                agent="code-reviewer",
                model="gpt-5.4",
            )
            result = run_review_agent("prompt body", options)

        assert result.exit_code == 0
        assert "VERDICT: PASS" in result.stdout

        # Verify command structure
        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "codeagent-wrapper" in command[0]
        assert "--agent" in command
        assert "--model" in command

    def test_run_review_without_model(self) -> None:
        """Runner should work without model override."""
        with patch("vibe3.services.review_runner.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                args=[], returncode=0, stdout="VERDICT: PASS", stderr=""
            )
            options = ReviewAgentOptions(agent="code-reviewer")
            result = run_review_agent("prompt body", options)

        assert result.exit_code == 0

        # Verify no --model flag when model is None
        call_args = mock_run.call_args
        command = call_args[0][0]
        assert "--model" not in command

    def test_run_review_non_zero_exit_raises_error(self) -> None:
        """Runner should raise error on non-zero exit code."""
        with patch("vibe3.services.review_runner.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                args=[], returncode=1, stdout="", stderr="Error: something failed"
            )
            options = ReviewAgentOptions(agent="code-reviewer")

            with pytest.raises(RuntimeError) as exc_info:
                run_review_agent("prompt body", options)

        assert "codeagent-wrapper failed" in str(exc_info.value)
        assert "something failed" in str(exc_info.value)

    def test_run_review_wrapper_not_found(self) -> None:
        """Runner should give clear error when wrapper not found."""
        with patch("vibe3.services.review_runner.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("codeagent-wrapper not found")
            options = ReviewAgentOptions(agent="code-reviewer")

            with pytest.raises(FileNotFoundError) as exc_info:
                run_review_agent("prompt body", options)

        assert "codeagent-wrapper not found" in str(exc_info.value)

    def test_run_review_timeout(self) -> None:
        """Runner should timeout after specified seconds."""
        import subprocess

        with patch("vibe3.services.review_runner.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["codeagent-wrapper"], timeout=300
            )
            options = ReviewAgentOptions(
                agent="code-reviewer",
                timeout_seconds=300,
            )

            with pytest.raises(subprocess.TimeoutExpired):
                run_review_agent("prompt body", options)

    def test_run_review_passes_prompt_as_stdin(self) -> None:
        """Runner should pass prompt as stdin input."""
        with patch("vibe3.services.review_runner.run") as mock_run:
            mock_run.return_value = CompletedProcess(
                args=[], returncode=0, stdout="Result", stderr=""
            )
            options = ReviewAgentOptions(agent="code-reviewer")
            run_review_agent("my custom prompt", options)

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["input"] == "my custom prompt"


class TestReviewAgentResult:
    """Tests for ReviewAgentResult dataclass."""

    def test_result_from_completed_process(self) -> None:
        """Result should be created from CompletedProcess."""
        cp = CompletedProcess(
            args=["cmd"],
            returncode=0,
            stdout="Output text",
            stderr="",
        )
        result = ReviewAgentResult.from_completed_process(cp)
        assert result.exit_code == 0
        assert result.stdout == "Output text"
        assert result.stderr == ""

    def test_result_is_success(self) -> None:
        """is_success should return True for exit_code 0."""
        result = ReviewAgentResult(exit_code=0, stdout="", stderr="")
        assert result.is_success() is True

    def test_result_is_not_success(self) -> None:
        """is_success should return False for non-zero exit_code."""
        result = ReviewAgentResult(exit_code=1, stdout="", stderr="")
        assert result.is_success() is False