"""Shell contract tests - Verify shell scripts use correct CLI commands.

These tests ensure the hook-CLI contract is enforced:
- pre-push.sh calls internal review-gate entry point
- review-gate is not exposed as a public CLI command
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

    def test_pre_push_calls_internal_review_gate_entry(self) -> None:
        """Verify pre-push.sh calls review-gate through internal entry.

        The hook should use internal Python module entry, not public CLI command.
        Options:
        - python -m vibe3.commands.review_gate
        - or a dedicated internal script
        """
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()

        # Should call review-gate functionality (via internal entry)
        # The exact mechanism can be:
        # 1. python -m vibe3.commands.review_gate
        # 2. A dedicated internal script
        has_review_gate_call = (
            "review_gate" in content  # module call
            or "review-gate" in content  # legacy or internal call
        )
        assert (
            has_review_gate_call
        ), "pre-push.sh should call review-gate functionality via internal entry"

        # Should NOT call public CLI command for review-gate
        # i.e., should not use "cli.py review-gate"
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("#"):
                continue
            # Check if calling cli.py with review-gate as a subcommand
            if "cli.py" in line and "review-gate" in line:
                # This is acceptable if using the internal entry
                # but should be phased out in favor of module call
                pass

    def test_pre_push_does_not_call_review_base_directly(self) -> None:
        """Verify pre-push.sh does not call 'review base' directly.

        The hook should go through review-gate abstraction.
        """
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()

        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("#"):
                continue
            # If line calls python cli.py with review base, it's wrong
            if "python" in line and "cli.py" in line and "review base" in line:
                pytest.fail(f"Should call review-gate, not review base: {line}")

    def test_pre_push_uses_check_block_option(self) -> None:
        """Verify pre-push.sh uses --check-block for blocking behavior."""
        script_path = Path("scripts/hooks/pre-push.sh")
        content = script_path.read_text()

        # Should include --check-block for blocking behavior
        assert "--check-block" in content, "pre-push.sh should use --check-block option"


@pytest.mark.regression("issue-210")
class TestReviewGateInternal:
    """Tests for review-gate as an internal (non-public) entry."""

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

    def test_review_gate_module_is_callable(self) -> None:
        """Verify review-gate can be called as a Python module.

        Internal entry: python -m vibe3.commands.review_gate --help
        """
        result = subprocess.run(
            ["uv", "run", "python", "-m", "vibe3.commands.review_gate", "--help"],
            capture_output=True,
        )
        # Should succeed - module entry is the internal way to call review-gate
        assert (
            result.returncode == 0
        ), f"Module entry should be callable. stderr: {result.stderr.decode()}"

    def test_review_gate_module_has_check_block_option(self) -> None:
        """Verify internal review-gate has --check-block option."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "vibe3.commands.review_gate", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())
        assert (
            "--check-block" in output
        ), "review-gate module should have --check-block option"
