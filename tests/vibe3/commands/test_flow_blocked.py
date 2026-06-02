"""Tests for flow blocked command guards."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


def test_flow_blocked_rejects_missing_flow() -> None:
    """Blocking a branch with no flow should fail with clear error."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "do/20260329-5f79a6"
    flow_service.get_flow_status.return_value = None

    with patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service):
        result = runner.invoke(
            app, ["flow", "blocked", "--branch", "do/20260329-5f79a6"]
        )

    assert result.exit_code == 1
    assert "没有 flow" in result.output
    flow_service.block_flow.assert_not_called()


def test_flow_blocked_succeeds_when_flow_exists() -> None:
    """Blocking a branch with an existing flow should proceed."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=None,
        issues=[],
    )

    with patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service):
        result = runner.invoke(
            app, ["flow", "blocked", "--branch", "task/demo", "--reason", "waiting"]
        )

    assert result.exit_code == 0
    flow_service.block_flow.assert_called_once_with(
        "task/demo", reason="waiting", blocked_by_issue=None
    )


def test_flow_blocked_resolves_numeric_branch_to_canonical_task_branch() -> None:
    """Numeric --branch should normalize to canonical task branch before block."""
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/issue-235",
        flow_slug="issue-235",
        flow_status="active",
        task_issue_number=235,
        issues=[],
    )

    # Mock store with flow binding
    mock_store = MagicMock()
    mock_store.get_flows_by_issue.return_value = [
        {"branch": "task/issue-235", "flow_status": "active"}
    ]
    flow_service.store = mock_store

    # Patch both FlowService import locations
    with (
        patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service),
        patch("vibe3.services.branch_arg.FlowService", return_value=flow_service),
    ):
        result = runner.invoke(
            app, ["flow", "blocked", "--branch", "235", "--task", "246"]
        )

    assert result.exit_code == 0
    flow_service.block_flow.assert_called_once_with(
        "task/issue-235", reason=None, blocked_by_issue=246
    )


def test_flow_blocked_rejects_reason_and_task_together() -> None:
    """--reason and --task are mutually exclusive for blocked."""
    result = runner.invoke(
        app,
        ["flow", "blocked", "--branch", "235", "--task", "246", "--reason", "wait"],
    )

    assert result.exit_code == 1
    assert "--reason" in result.output
    assert "--task" in result.output


def test_flow_blocked_no_longer_supports_pr_option() -> None:
    """CLI should reject removed --pr option."""
    result = runner.invoke(app, ["flow", "blocked", "--pr", "789", "--reason", "x"])

    assert result.exit_code != 0


def test_flow_blocked_no_longer_supports_by_alias() -> None:
    """CLI should reject removed --by alias."""
    result = runner.invoke(app, ["flow", "blocked", "--by", "246"])

    assert result.exit_code != 0


def test_flow_blocked_auto_creates_flow_for_issue_branch() -> None:
    """Auto-create flow when branch matches issue convention and no flow exists."""
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = None  # No flow exists

    # Mock flow update command
    mock_update = MagicMock()

    with (
        patch("vibe3.commands.flow_lifecycle.FlowService", return_value=flow_service),
        patch("vibe3.commands.flow_manage.update", mock_update),
    ):
        result = runner.invoke(
            app, ["flow", "blocked", "--branch", "task/issue-1212", "--task", "467"]
        )

    assert result.exit_code == 0
    # flow update should be called to create flow
    mock_update.assert_called_once_with(
        branch_arg="1212",
        name="issue-1212",
        actor=None,
        spec=None,
        trace=False,
        output_format="table",
        json_output=False,
    )
    # block_flow should be called after flow creation
    flow_service.block_flow.assert_called_once_with(
        "task/issue-1212", reason=None, blocked_by_issue=467
    )
