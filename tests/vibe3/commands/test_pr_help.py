"""Tests for PR command help surface.

These tests define the expected command surface contract:
- pr --help shows only: create, ready, show
- pr draft is removed
- pr merge is removed from public CLI
- review-gate is not exposed publicly
"""

import re
import subprocess

import pytest


def _strip_ansi(text: str) -> str:
    """Remove ANSI color/style codes from subprocess help output."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestPRCommandSurface:
    """Tests for PR command surface contract."""

    def test_pr_help_shows_create_command(self) -> None:
        """pr --help shows 'create' command."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "pr", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())
        assert "create" in output, "pr --help should show 'create' command"

    def test_pr_help_shows_ready_command(self) -> None:
        """pr --help shows 'ready' command."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "pr", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())
        assert "ready" in output, "pr --help should show 'ready' command"

    def test_pr_help_shows_show_command(self) -> None:
        """pr --help shows 'show' command."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "pr", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())
        assert "show" in output, "pr --help should show 'show' command"

    def test_pr_help_does_not_show_draft_command(self) -> None:
        """pr --help does NOT show 'draft' as a separate command.

        'draft' functionality is now under 'create --draft'.
        """
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "pr", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())
        # Check that 'draft' is not a separate command in the Commands list
        # It should not appear as "draft" in the command list
        lines = output.split("\n")
        for line in lines:
            # Look for lines that define commands
            # (usually indented with the command name)
            if line.strip().startswith("draft") and "create" not in line:
                pytest.fail(f"'draft' should not be a separate command. Found: {line}")

    def test_pr_help_does_not_show_merge_command(self) -> None:
        """pr --help does NOT show 'merge' command.

        Merge is now handled by flow done / integrate, not pr merge.
        """
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "pr", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())
        # Check that 'merge' is not in the command list
        lines = output.split("\n")
        for line in lines:
            if line.strip().startswith("merge"):
                pytest.fail(
                    f"'merge' should not be in pr command surface. Found: {line}"
                )

    def test_pr_help_does_not_show_version_bump_command(self) -> None:
        """pr --help does NOT show 'version-bump' command.

        version-bump does not have clear project packaging value
        and should not be in the public PR command surface.
        """
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "pr", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())
        # Check that 'version-bump' is not in the command list
        lines = output.split("\n")
        for line in lines:
            if line.strip().startswith("version-bump"):
                pytest.fail(
                    f"'version-bump' should not be in pr command surface. Found: {line}"
                )


class TestTopLevelHelpSurface:
    """Tests for top-level CLI help surface."""

    def test_top_level_help_does_not_show_review_gate(self) -> None:
        """Top-level --help does NOT show 'review-gate' as a public command.

        review-gate is an internal entry for hooks, not a user command.
        """
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "--help"],
            capture_output=True,
        )
        assert result.returncode == 0
        output = _strip_ansi(result.stdout.decode())
        # review-gate should not appear in the top-level commands list
        lines = output.split("\n")
        for line in lines:
            if "review-gate" in line and "review" in line.lower():
                # Check if it's in the commands section (not in a description)
                if line.strip().startswith("review-gate"):
                    pytest.fail(
                        f"'review-gate' should not be a public command. Found: {line}"
                    )


class TestPRDraftCommandRemoved:
    """Tests verifying 'pr draft' command is removed."""

    def test_pr_draft_command_not_found(self) -> None:
        """Calling 'pr draft' should fail with 'no such command'."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "pr", "draft", "--help"],
            capture_output=True,
        )
        # Should fail because 'draft' is no longer a command
        assert result.returncode != 0
        output = _strip_ansi(result.stderr.decode() + result.stdout.decode())
        assert (
            "no such command" in output.lower()
            or "unknown" in output.lower()
            or "error" in output.lower()
        )


class TestPRMergeCommandRemoved:
    """Tests verifying 'pr merge' command is removed from public CLI."""

    def test_pr_merge_command_not_found(self) -> None:
        """Calling 'pr merge' should fail with 'no such command'."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "pr", "merge", "--help"],
            capture_output=True,
        )
        # Should fail because 'merge' is no longer a public command
        assert result.returncode != 0
        output = _strip_ansi(result.stderr.decode() + result.stdout.decode())
        assert (
            "no such command" in output.lower()
            or "unknown" in output.lower()
            or "error" in output.lower()
        )


class TestReviewGateNotPublic:
    """Tests verifying 'review-gate' is not a public command."""

    def test_review_gate_not_in_top_level_commands(self) -> None:
        """Calling 'review-gate' at top level should fail."""
        result = subprocess.run(
            ["uv", "run", "python", "src/vibe3/cli.py", "review-gate", "--help"],
            capture_output=True,
        )
        # Should fail because 'review-gate' is no longer a public command
        assert result.returncode != 0
        output = _strip_ansi(result.stderr.decode() + result.stdout.decode())
        assert (
            "no such command" in output.lower()
            or "unknown" in output.lower()
            or "error" in output.lower()
        )
