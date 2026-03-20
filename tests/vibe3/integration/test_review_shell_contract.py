"""Shell contract tests - Verify shell scripts use correct CLI commands.

These tests ensure the hook-CLI contract is enforced:
- pre-push.sh calls review-gate, not review base --agent
- No stale parameters are used
- Exit codes are correct
"""

import subprocess
from pathlib import Path

import pytest


class TestPrePushContract:
    """Tests for pre-push.sh script contract."""

    def test_pre_push_syntax_is_valid(self) -> None:
        """Verify pre-push.sh has no syntax errors."""
        result = subprocess.run(
            ["bash", "-n", "scripts/hooks/pre-push.sh"],
            capture_output=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr.decode()}"

    def test_pre_push_calls_review_gate_command(self) -> None:
        """Verify pre-push.sh calls review-gate, not review base --agent.

        This is a contract test: the hook should not use stale parameters
        or call commands directly.
        """
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()

        # Should call review-gate
        assert "review-gate" in content, "pre-push.sh should call review-gate command"

        # Should NOT use --agent (stale parameter from old hook)
        assert (
            "--agent" not in content
        ), "pre-push.sh should not use --agent (not a valid CLI option)"

        # Should use --check-block for blocking behavior
        assert "--check-block" in content, "pre-push.sh should use --check-block option"

    def test_pre_push_does_not_call_review_base_directly(self) -> None:
        """Verify pre-push.sh does not call 'review base' directly.

        The hook should go through review-gate abstraction.
        """
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()

        # Should not call "review base" directly
        # (review-gate handles the risk-based dispatch)
        lines = content.split("\n")
        for line in lines:
            # Skip comments
            if line.strip().startswith("#"):
                continue
            # If line calls python cli.py, it should be review-gate
            if "python" in line and "cli.py" in line:
                assert (
                    "review-gate" in line
                ), f"Should call review-gate, not review base: {line}"


@pytest.mark.regression("issue-210")
class TestReviewGateContract:
    """Regression tests for issue #210: Hook-CLI parameter mismatch."""

    def test_review_gate_exists(self) -> None:
        """Verify review-gate command exists in CLI."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = result.stdout.decode()
        assert "review-gate" in output, "review-gate command should exist"

    def test_review_gate_has_check_block_option(self) -> None:
        """Verify review-gate has --check-block option."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "review-gate", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = result.stdout.decode()
        assert "--check-block" in output, "review-gate should have --check-block option"
