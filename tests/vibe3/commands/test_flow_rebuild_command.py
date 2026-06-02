"""Tests for flow rebuild command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState

runner = CliRunner()


@patch("vibe3.commands.flow_lifecycle.FlowRebuildUsecase")
@patch("vibe3.commands.flow_lifecycle.resolve_branch_arg")
@patch("vibe3.commands.flow_lifecycle.load_orchestra_config")
@patch("vibe3.commands.flow_lifecycle.load_issue_info")
def test_flow_rebuild_invokes_explicit_rebuild(
    load_issue_info: MagicMock,
    load_config: MagicMock,
    resolve_branch_arg_mock: MagicMock,
    rebuild_cls: MagicMock,
) -> None:
    config = OrchestraConfig(repo="owner/repo")
    load_config.return_value = config
    resolve_branch_arg_mock.return_value = "feature/303"
    issue = IssueInfo(
        number=303,
        title="Rebuild me",
        state=IssueState.READY,
        labels=[IssueState.READY.to_label()],
    )
    load_issue_info.return_value = issue
    rebuild = rebuild_cls.return_value
    rebuild.rebuild_issue_flow.return_value = {"branch": "feature/303"}

    result = runner.invoke(app, ["flow", "rebuild", "303", "--yes"])

    assert result.exit_code == 0
    load_issue_info.assert_called_once()
    assert load_issue_info.call_args.kwargs["config"] is config
    rebuild.rebuild_issue_flow.assert_called_once()
    call = rebuild.rebuild_issue_flow.call_args.kwargs
    assert call["issue"] == issue
    assert call["branch"] == "feature/303"
    assert call["include_remote"] is True
    assert call["ensure_worktree"] is True


@patch("vibe3.commands.flow_lifecycle.ConventionResolver")
def test_flow_rebuild_branch_extracts_issue_number(
    convention_resolver_cls: MagicMock,
) -> None:
    """`--branch task/issue-123` should be equivalent to `123`."""
    # Setup convention resolver mock
    convention = MagicMock()
    convention.parse_issue_number.return_value = 123
    convention.canonical_branch.return_value = "task/issue-123"
    resolver = MagicMock()
    resolver.branch = convention
    convention_resolver_cls.from_repo.return_value.resolve.return_value = resolver

    result = runner.invoke(app, ["flow", "rebuild", "--branch", "task/issue-123"])

    # Should be in dry-run mode
    assert result.exit_code == 0
    assert "Would hard rebuild issue #123" in result.output
    # Verify parse_issue_number was called with the branch name
    convention.parse_issue_number.assert_called_once_with("task/issue-123")


def test_flow_rebuild_branch_conflicts_with_positional() -> None:
    """Cannot specify both --branch and positional issue number."""
    result = runner.invoke(
        app, ["flow", "rebuild", "--branch", "task/issue-123", "123"]
    )

    assert result.exit_code == 1
    assert "不能同时指定 --branch 和位置参数" in result.output


def test_flow_rebuild_no_args() -> None:
    """Must specify either issue number or --branch."""
    result = runner.invoke(app, ["flow", "rebuild"])

    assert result.exit_code == 1
    assert "需要指定 issue number 或 --branch" in result.output


@patch("vibe3.commands.flow_lifecycle.ConventionResolver")
def test_flow_rebuild_branch_invalid_name(convention_resolver_cls: MagicMock) -> None:
    """Invalid branch name should error."""
    # Setup convention resolver mock
    convention = MagicMock()
    convention.parse_issue_number.return_value = None  # Cannot parse
    resolver = MagicMock()
    resolver.branch = convention
    convention_resolver_cls.from_repo.return_value.resolve.return_value = resolver

    result = runner.invoke(app, ["flow", "rebuild", "--branch", "invalid-name"])

    assert result.exit_code == 1
    assert "无法从 'invalid-name' 提取 issue number" in result.output


@patch("vibe3.commands.flow_lifecycle.ConventionResolver")
def test_flow_rebuild_positional_still_works(
    convention_resolver_cls: MagicMock,
) -> None:
    """Backward compatibility: positional argument still works."""
    # Setup convention resolver mock
    convention = MagicMock()
    convention.canonical_branch.return_value = "task/issue-123"
    resolver = MagicMock()
    resolver.branch = convention
    convention_resolver_cls.from_repo.return_value.resolve.return_value = resolver

    result = runner.invoke(app, ["flow", "rebuild", "123"])

    # Should be in dry-run mode
    assert result.exit_code == 0
    assert "Would hard rebuild issue #123" in result.output
    # Verify parse_issue_number was NOT called (we used positional arg)
    convention.parse_issue_number.assert_not_called()
