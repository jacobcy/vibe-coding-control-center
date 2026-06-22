"""Tests for services/shared/actors.py formatting functions."""

from vibe3.services.shared.actors import format_dry_run_header


class TestFormatDryRunHeader:
    def test_normal_case(self):
        result = format_dry_run_header(
            "planner", 42, "task/issue-42", "claude/sonnet-4.6"
        )
        assert "-> planner run: issue #42 (dry-run)" in result
        assert "   branch: task/issue-42" in result
        assert "   actor:  claude/sonnet-4.6" in result

    def test_async_mode(self):
        result = format_dry_run_header(
            "executor",
            10,
            "task/issue-10",
            "gemini/gemini-pro",
            dry_run_mode="async dry-run",
        )
        assert "(async dry-run)" in result

    def test_adhoc_no_issue(self):
        result = format_dry_run_header("reviewer", None, "main", "claude/haiku-4.5")
        assert "adhoc" in result
        assert "issue #" not in result

    def test_output_format_structure(self):
        result = format_dry_run_header("planner", 1, "b", "actor")
        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0].startswith("-> ")
        assert lines[1].startswith("   branch:")
        assert lines[2].startswith("   actor:")
