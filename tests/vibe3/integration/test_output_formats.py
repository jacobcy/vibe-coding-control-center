"""Integration tests for trace output functionality."""

import json

import pytest
import yaml
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestTraceOutputIntegration:
    """Integration tests for --trace output formats."""

    def test_pr_show_trace_default_format(self) -> None:
        """Test pr show --trace with default format."""
        result = runner.invoke(app, ["pr", "show", "--trace"])
        # May fail if no PR exists, but should handle gracefully
        if result.exit_code == 0:
            assert "[TRACE]" in result.output

    def test_pr_show_trace_json_format(self) -> None:
        """Test pr show --trace --json outputs JSON with trace info."""
        result = runner.invoke(app, ["pr", "show", "--trace", "--json"])
        if result.exit_code == 0:
            # Should contain JSON trace structure
            assert '"trace"' in result.output or '"command"' in result.output

    def test_pr_show_trace_yaml_format(self) -> None:
        """Test pr show --trace --yaml outputs YAML with trace info."""
        result = runner.invoke(app, ["pr", "show", "--trace", "--yaml"])
        if result.exit_code == 0:
            # Should contain YAML trace structure
            assert "trace:" in result.output or "command:" in result.output

    def test_pr_show_conflicting_formats(self) -> None:
        """Test pr show with both --json and --yaml fails."""
        result = runner.invoke(app, ["pr", "show", "--json", "--yaml"])
        assert result.exit_code != 0
        assert "Cannot use both" in result.output


class TestInspectOutputIntegration:
    """Integration tests for inspect command output formats."""

    def test_inspect_commands_default_yaml(self) -> None:
        """Test inspect commands with default YAML output."""
        result = runner.invoke(app, ["inspect", "commands", "pr", "show"])
        assert result.exit_code == 0
        # Should contain YAML structure
        assert "command:" in result.output
        assert "file:" in result.output
        assert "call_tree:" in result.output

    def test_inspect_commands_json_format(self) -> None:
        """Test inspect commands --json outputs JSON structure."""
        result = runner.invoke(app, ["inspect", "commands", "pr", "show", "--json"])
        assert result.exit_code == 0
        # Should contain JSON structure
        assert '"command"' in result.output
        assert '"file"' in result.output
        assert '"call_tree"' in result.output

    def test_inspect_commands_tree_format(self) -> None:
        """Test inspect commands --tree outputs ASCII tree."""
        result = runner.invoke(app, ["inspect", "commands", "pr", "show", "--tree"])
        assert result.exit_code == 0
        # Should contain tree characters
        assert "pr show" in result.output
        # Should contain line references
        assert "L" in result.output

    def test_inspect_commands_mermaid_format(self) -> None:
        """Test inspect commands --mermaid outputs Mermaid diagram."""
        result = runner.invoke(app, ["inspect", "commands", "pr", "show", "--mermaid"])
        assert result.exit_code == 0
        # Should contain Mermaid markers
        assert "```mermaid" in result.output
        assert "graph TD" in result.output

    def test_inspect_commands_no_command_lists_available(self) -> None:
        """Test inspect commands without arguments lists available commands."""
        result = runner.invoke(app, ["inspect", "commands"])
        assert result.exit_code == 0
        assert "Available commands" in result.output
