"""Shell contract tests - Verify shell scripts use correct CLI commands.

These tests ensure the hook-CLI contract is enforced:
- pre-push.sh uses inspect + review commands directly
- review-gate is not part of this command surface
- Exit codes are correct
"""

import re
import subprocess
from pathlib import Path

import pytest


def _strip_ansi(text: str) -> str:
    """Remove ANSI color/style codes from subprocess help output."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestPrePushContract:
    """Tests for pre-push.sh script contract."""

    def test_pre_push_syntax_is_valid(self) -> None:
        """Verify pre-push.sh has no syntax errors."""
        result = subprocess.run(
            ["bash", "-n", "scripts/hooks/pre-push.sh"],
            capture_output=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr.decode()}"

    def test_pre_push_calls_inspect_base_json(self) -> None:
        """Verify pre-push.sh uses inspect base --json for risk assessment."""
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()
        assert "inspect base --json" in content

    def test_pre_push_calls_review_base_directly(self) -> None:
        """Verify pre-push.sh calls review base directly when needed."""
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()
        assert "review base" in content

    def test_pre_push_prints_review_output_when_review_runs(self) -> None:
        """Verify pre-push.sh prints review output in real-time using tee."""
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()
        # New implementation uses tee for real-time output
        assert 'tee "$REVIEW_REPORT_FILE"' in content

    def test_pre_push_saves_review_output_to_agent_reports(self) -> None:
        """Verify pre-push.sh persists local review output to .agent/reports/."""
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()
        assert "mkdir -p .agent/reports" in content
        assert ".agent/reports/pre-push-review-" in content
        # New implementation uses tee to save output in real-time
        assert 'tee "$REVIEW_REPORT_FILE"' in content

    def test_pre_push_prints_review_trigger_and_verdict_summary(self) -> None:
        """Verify pre-push.sh prints explicit observability summary lines."""
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()
        assert 'echo "  Review triggered: yes"' in content
        assert 'echo "  Review triggered: no"' in content
        assert 'echo "  Review triggered: recommended-manual"' in content
        assert 'echo "  Review verdict: $VERDICT"' in content

    def test_pre_push_prints_risk_reason_and_recommendations(self) -> None:
        """Verify pre-push.sh surfaces inspect explanations, not just score."""
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()
        assert "Risk reason:" in content
        assert "Trigger factors:" in content
        assert "Recommendations:" in content

    def test_pre_push_does_not_call_review_gate(self) -> None:
        """Verify pre-push.sh does not call review-gate."""
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()
        assert "review_gate" not in content
        assert "review-gate" not in content


@pytest.mark.regression("issue-210")
class TestReviewGateRemoved:
    """Tests for review-gate removal from the current command surface."""

    def test_review_gate_not_in_top_level_help(self) -> None:
        """Verify review-gate is NOT exposed as a public command."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())

        # review-gate should NOT appear as a top-level command
        lines = output.split("\n")
        for line in lines:
            if line.strip().startswith("review-gate"):
                pytest.fail(
                    f"'review-gate' should not be a public command. Found: {line}"
                )

    def test_review_gate_module_is_not_callable(self) -> None:
        """Verify review-gate module entry is not part of this cleanup branch."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "vibe3.commands.review_gate", "--help"],
            capture_output=True,
        )
        assert result.returncode != 0
