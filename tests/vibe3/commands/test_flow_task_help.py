"""Tests for flow/task command help and issue parsing semantics."""

from typer.testing import CliRunner

from vibe3.commands.flow import app as flow_app
from vibe3.commands.task import app as task_app
from vibe3.commands.task import parse_issue_ref

runner = CliRunner()


def test_flow_new_help_uses_issue_option_and_optional_name() -> None:
    """flow new help should expose the new parameter names."""
    result = runner.invoke(flow_app, ["new", "--help"])

    assert result.exit_code == 0
    assert "--issue" in result.output
    assert "--task-issue" not in result.output
    assert "[NAME]" in result.output


def test_flow_bind_help_uses_issue_and_role() -> None:
    """flow bind help should describe issue-based binding."""
    result = runner.invoke(flow_app, ["bind", "--help"])

    assert result.exit_code == 0
    assert "ISSUE" in result.output
    assert "TASK_ID" not in result.output
    assert "--role" in result.output
    assert "--branch" in result.output
    assert "related" in result.output
    assert "dependency" in result.output


def test_task_link_help_drops_repo_role() -> None:
    """task link help should only expose issue-to-issue roles."""
    result = runner.invoke(task_app, ["link", "--help"])

    assert result.exit_code == 0
    assert "ISSUE" in result.output
    assert "ISSUE_URL" not in result.output
    assert "related" in result.output
    assert "dependency" in result.output
    assert "repo" not in result.output


def test_parse_issue_ref_supports_number_and_url() -> None:
    """Issue parsing should accept both plain numbers and GitHub URLs."""
    assert parse_issue_ref("219") == 219
    assert parse_issue_ref("https://github.com/owner/repo/issues/219") == 219
