"""Tests for AgentResult dataclass."""

from vibe3.models.review_runner import AgentResult


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_result_is_success(self) -> None:
        """is_success should return True for exit_code 0."""
        result = AgentResult(exit_code=0, stdout="", stderr="")
        assert result.is_success() is True

    def test_result_is_not_success(self) -> None:
        """is_success should return False for non-zero exit_code."""
        result = AgentResult(exit_code=1, stdout="", stderr="")
        assert result.is_success() is False
