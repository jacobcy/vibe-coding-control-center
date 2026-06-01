"""Tests for flow rebuild command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.orchestration import IssueInfo, IssueState

runner = CliRunner()


@patch("vibe3.commands.flow_lifecycle.FlowRebuildUsecase")
@patch("vibe3.commands.flow_lifecycle.load_issue_info")
def test_flow_rebuild_invokes_explicit_rebuild(
    load_issue_info: MagicMock,
    rebuild_cls: MagicMock,
) -> None:
    issue = IssueInfo(
        number=303,
        title="Rebuild me",
        state=IssueState.READY,
        labels=[IssueState.READY.to_label()],
    )
    load_issue_info.return_value = issue
    rebuild = rebuild_cls.return_value
    rebuild.rebuild_issue_flow.return_value = {"branch": "task/issue-303"}

    result = runner.invoke(app, ["flow", "rebuild", "303", "--yes"])

    assert result.exit_code == 0
    rebuild.rebuild_issue_flow.assert_called_once()
    call = rebuild.rebuild_issue_flow.call_args.kwargs
    assert call["issue"] == issue
    assert call["branch"] == "task/issue-303"
    assert call["include_remote"] is True
    assert call["ensure_worktree"] is True
