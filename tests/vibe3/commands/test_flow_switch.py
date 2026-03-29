"""Tests for flow switch command behavior."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowState
from vibe3.models.pr import PRResponse, PRState

runner = CliRunner()


def test_flow_switch_supports_pr_option() -> None:
    """--pr should resolve head branch and switch to that flow."""
    flow_service = MagicMock()
    flow_service.switch_flow.return_value = FlowState(
        branch="task/from-pr",
        flow_slug="from-pr",
    )
    pr_service = MagicMock()
    pr_service.get_pr.return_value = PRResponse(
        number=123,
        title="Test PR",
        body="",
        state=PRState.OPEN,
        head_branch="task/from-pr",
        base_branch="main",
        url="https://example.com/pr/123",
        merged_at=None,
    )

    with (
        patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service),
        patch("vibe3.commands.flow_lifecycle.PRService", return_value=pr_service),
    ):
        result = runner.invoke(app, ["flow", "switch", "--pr", "123"])

    assert result.exit_code == 0
    pr_service.get_pr.assert_called_once_with(pr_number=123)
    flow_service.switch_flow.assert_called_once_with("task/from-pr")


def test_flow_switch_rejects_branch_and_pr_together() -> None:
    """--branch and --pr are mutually exclusive."""
    result = runner.invoke(
        app,
        ["flow", "switch", "--branch", "task/demo", "--pr", "123"],
    )

    assert result.exit_code == 1
    assert "不能同时指定 --branch 与 --pr" in result.output


def test_flow_switch_requires_existing_pr_with_pr_option() -> None:
    """--pr should fail clearly when PR number cannot be resolved."""
    pr_service = MagicMock()
    pr_service.get_pr.return_value = None

    with patch("vibe3.commands.flow_lifecycle.PRService", return_value=pr_service):
        result = runner.invoke(app, ["flow", "switch", "--pr", "123"])

    assert result.exit_code == 1
    assert "未找到 PR #123" in result.output
