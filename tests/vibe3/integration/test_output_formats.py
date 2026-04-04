"""Integration tests for trace output functionality."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


@pytest.fixture
def stub_pr_show_usecase(monkeypatch):
    """Keep pr show output tests focused on formatting, not remote lookups."""
    mock_usecase = MagicMock()
    mock_usecase.resolve_target.return_value = SimpleNamespace(
        pr_number=123,
        branch=None,
        current_branch="task/test",
        from_flow=False,
    )
    mock_usecase.fetch_pr.return_value = SimpleNamespace(
        model_dump=lambda: {
            "number": 123,
            "title": "Test PR",
            "body": "Body",
            "state": "open",
            "head_branch": "task/test",
            "base_branch": "main",
            "url": "https://example.test/pr/123",
            "draft": True,
        }
    )
    mock_usecase.load_analysis_summary.return_value = {
        "raw": {},
        "score": {"level": "LOW", "score": 1},
    }
    mock_usecase.build_output_payload.return_value = {
        "number": 123,
        "title": "Test PR",
        "trace": {"command": "pr show"},
    }
    monkeypatch.setattr(
        "vibe3.commands.pr_query._build_pr_query_usecase",
        lambda: mock_usecase,
    )
    return mock_usecase


class TestTraceOutputIntegration:
    """Integration tests for --trace output formats."""

    def test_pr_show_trace_default_format(self, stub_pr_show_usecase) -> None:
        """Test pr show --trace with default format."""
        result = runner.invoke(app, ["pr", "show", "--trace"])
        assert result.exit_code == 0
        assert "[TRACE]" in result.output

    def test_pr_show_trace_json_format(self, stub_pr_show_usecase) -> None:
        """Test pr show --trace --json outputs JSON with trace info."""
        result = runner.invoke(app, ["pr", "show", "--trace", "--json"])
        assert result.exit_code == 0
        assert '"trace"' in result.output or '"command"' in result.output

    def test_pr_show_trace_yaml_format(self, stub_pr_show_usecase) -> None:
        """Test pr show --trace --yaml outputs YAML with trace info."""
        result = runner.invoke(app, ["pr", "show", "--trace", "--yaml"])
        assert result.exit_code == 0
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
