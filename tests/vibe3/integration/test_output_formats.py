"""Integration tests for trace output functionality."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


@pytest.fixture
def stub_pr_show_service(monkeypatch):
    """Keep pr show output tests focused on formatting, not remote lookups."""
    mock_service = MagicMock()
    target = SimpleNamespace(
        pr_number=123,
        branch=None,
        current_branch="task/test",
        from_flow=False,
    )
    pr = SimpleNamespace(
        number=123,
        title="Test PR",
        body="Body",
        state="open",
        head_branch="task/test",
        base_branch="main",
        url="https://example.test/pr/123",
        draft=True,
        model_dump=lambda: {
            "number": 123,
            "title": "Test PR",
            "body": "Body",
            "state": "open",
            "head_branch": "task/test",
            "base_branch": "main",
            "url": "https://example.test/pr/123",
            "draft": True,
        },
    )
    payload = {
        "number": 123,
        "title": "Test PR",
        "trace": {"command": "pr show"},
    }
    monkeypatch.setattr(
        "vibe3.commands.pr_query.PRService",
        lambda: mock_service,
    )
    monkeypatch.setattr("vibe3.commands.pr_query._resolve_pr_target", lambda *_: target)
    monkeypatch.setattr(
        "vibe3.commands.pr_query._fetch_pr_or_raise",
        lambda *_args, **_kwargs: pr,
    )
    monkeypatch.setattr(
        "vibe3.commands.pr_query._load_local_review_observation",
        lambda *_: None,
    )
    monkeypatch.setattr(
        "vibe3.commands.pr_query._build_pr_output_payload",
        lambda *_: payload,
    )
    return mock_service


class TestTraceOutputIntegration:
    """Integration tests for --trace output formats."""

    def test_pr_show_trace_default_format(self, stub_pr_show_service) -> None:
        """Test pr show --trace with default format."""
        result = runner.invoke(app, ["pr", "show", "--trace"])
        assert result.exit_code == 0
        assert "[TRACE]" in result.output

    def test_pr_show_trace_json_format(self, stub_pr_show_service) -> None:
        """Test pr show --trace --json outputs JSON with trace info."""
        result = runner.invoke(app, ["pr", "show", "--trace", "--json"])
        assert result.exit_code == 0
        assert '"trace"' in result.output or '"command"' in result.output

    def test_pr_show_trace_yaml_format(self, stub_pr_show_service) -> None:
        """Test pr show --trace --yaml outputs YAML with trace info."""
        result = runner.invoke(app, ["pr", "show", "--trace", "--yaml"])
        assert result.exit_code == 0
        assert "trace:" in result.output or "command:" in result.output

    def test_pr_show_conflicting_formats(self) -> None:
        """Test pr show with both --json and --yaml fails."""
        result = runner.invoke(app, ["pr", "show", "--json", "--yaml"])
        assert result.exit_code != 0
        assert "Cannot use both" in result.output
