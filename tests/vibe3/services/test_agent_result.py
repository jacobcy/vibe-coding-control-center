"""Tests for AgentResult dataclass."""

from subprocess import CompletedProcess

from vibe3.models.review_runner import AgentResult


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_result_from_completed_process(self) -> None:
        """Result should be created from CompletedProcess."""
        cp = CompletedProcess(
            args=["cmd"],
            returncode=0,
            stdout="Output text",
            stderr="",
        )
        result = AgentResult.from_completed_process(cp)
        assert result.exit_code == 0
        assert result.stdout == "Output text"
        assert result.stderr == ""

    def test_result_is_success(self) -> None:
        """is_success should return True for exit_code 0."""
        result = AgentResult(exit_code=0, stdout="", stderr="")
        assert result.is_success() is True

    def test_result_is_not_success(self) -> None:
        """is_success should return False for non-zero exit_code."""
        result = AgentResult(exit_code=1, stdout="", stderr="")
        assert result.is_success() is False
