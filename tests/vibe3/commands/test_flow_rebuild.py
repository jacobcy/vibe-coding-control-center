"""Tests for flow rebuild command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


@patch("vibe3.commands.flow_lifecycle.FlowRebuildUsecase")
@patch("vibe3.commands.flow_lifecycle.load_issue_info")
@patch("vibe3.clients.github_client.GitHubClient")
@patch("vibe3.commands.flow_lifecycle.load_orchestra_config")
def test_flow_rebuild_position_arg(
    load_config: MagicMock,
    github_client: MagicMock,
    load_issue: MagicMock,
    rebuild_usecase_cls: MagicMock,
) -> None:
    """Existing behavior with positional issue number."""
    # Mock config
    load_config.return_value = MagicMock()

    # Mock issue info
    issue = MagicMock()
    issue.number = 123
    load_issue.return_value = issue

    # Mock rebuild usecase
    rebuild_usecase = MagicMock()
    rebuild_usecase.rebuild_issue_flow.return_value = {"status": "success"}
    rebuild_usecase_cls.return_value = rebuild_usecase

    result = runner.invoke(app, ["flow", "rebuild", "123", "--yes"])

    assert result.exit_code == 0
    assert "Rebuilt flow for issue #123" in result.output
    rebuild_usecase.rebuild_issue_flow.assert_called_once()


@patch("vibe3.commands.flow_lifecycle.FlowService")
@patch("vibe3.commands.flow_lifecycle.FlowRebuildUsecase")
@patch("vibe3.commands.flow_lifecycle.load_issue_info")
@patch("vibe3.clients.github_client.GitHubClient")
@patch("vibe3.commands.flow_lifecycle.load_orchestra_config")
@patch("vibe3.commands.flow_lifecycle.resolve_command_branch")
def test_flow_rebuild_branch_option(
    resolve_branch: MagicMock,
    load_config: MagicMock,
    github_client: MagicMock,
    load_issue: MagicMock,
    rebuild_usecase_cls: MagicMock,
    flow_service_cls: MagicMock,
) -> None:
    """`--branch task/issue-123` resolves correctly."""
    # Mock branch resolution
    resolve_branch.return_value = "task/issue-123"

    # Mock flow service and issue parsing
    flow_service = MagicMock()
    flow_service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 123}
    ]
    flow_service_cls.return_value = flow_service

    # Mock config
    load_config.return_value = MagicMock()

    # Mock issue info
    issue = MagicMock()
    issue.number = 123
    load_issue.return_value = issue

    # Mock rebuild usecase
    rebuild_usecase = MagicMock()
    rebuild_usecase.rebuild_issue_flow.return_value = {"status": "success"}
    rebuild_usecase_cls.return_value = rebuild_usecase

    result = runner.invoke(
        app, ["flow", "rebuild", "--branch", "task/issue-123", "--yes"]
    )

    assert result.exit_code == 0
    assert "Rebuilt flow for issue #123" in result.output
    rebuild_usecase.rebuild_issue_flow.assert_called_once()
    # Verify the branch was passed correctly
    call_kwargs = rebuild_usecase.rebuild_issue_flow.call_args.kwargs
    assert call_kwargs["branch"] == "task/issue-123"


@patch("vibe3.commands.flow_lifecycle.FlowService")
@patch("vibe3.commands.flow_lifecycle.FlowRebuildUsecase")
@patch("vibe3.commands.flow_lifecycle.load_issue_info")
@patch("vibe3.clients.github_client.GitHubClient")
@patch("vibe3.commands.flow_lifecycle.load_orchestra_config")
@patch("vibe3.commands.flow_lifecycle.resolve_command_branch")
def test_flow_rebuild_pr_option(
    resolve_branch: MagicMock,
    load_config: MagicMock,
    github_client: MagicMock,
    load_issue: MagicMock,
    rebuild_usecase_cls: MagicMock,
    flow_service_cls: MagicMock,
) -> None:
    """`--pr 456` resolves PR to branch."""
    # Mock branch resolution from PR
    resolve_branch.return_value = "task/issue-456"

    # Mock flow service and issue parsing
    flow_service = MagicMock()
    flow_service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]
    flow_service_cls.return_value = flow_service

    # Mock config
    load_config.return_value = MagicMock()

    # Mock issue info
    issue = MagicMock()
    issue.number = 456
    load_issue.return_value = issue

    # Mock rebuild usecase
    rebuild_usecase = MagicMock()
    rebuild_usecase.rebuild_issue_flow.return_value = {"status": "success"}
    rebuild_usecase_cls.return_value = rebuild_usecase

    result = runner.invoke(app, ["flow", "rebuild", "--pr", "456", "--yes"])

    assert result.exit_code == 0
    assert "Rebuilt flow for issue #456" in result.output
    rebuild_usecase.rebuild_issue_flow.assert_called_once()
    # Verify the branch was passed correctly
    call_kwargs = rebuild_usecase.rebuild_issue_flow.call_args.kwargs
    assert call_kwargs["branch"] == "task/issue-456"


def test_flow_rebuild_no_target() -> None:
    """No args should error."""
    result = runner.invoke(app, ["flow", "rebuild"])

    assert result.exit_code != 0
    assert "Must specify issue number, --branch, or --pr" in result.output


def test_flow_rebuild_conflict_branch_and_position() -> None:
    """`--branch 123 456` should error."""
    result = runner.invoke(
        app, ["flow", "rebuild", "--branch", "task/issue-123", "456"]
    )

    assert result.exit_code != 0
    assert "不能同时使用" in result.output


@patch("vibe3.commands.flow_lifecycle.FlowService")
@patch("vibe3.commands.flow_lifecycle.resolve_command_branch")
def test_flow_rebuild_non_issue_branch_error(
    resolve_branch: MagicMock,
    flow_service_cls: MagicMock,
) -> None:
    """Non-issue branch should error."""
    # Mock branch resolution to non-issue branch
    resolve_branch.return_value = "main"

    # Mock flow service and issue parsing (no issue number found)
    flow_service = MagicMock()
    flow_service.store.get_issue_links.return_value = []
    flow_service_cls.return_value = flow_service

    result = runner.invoke(app, ["flow", "rebuild", "--branch", "main", "--yes"])

    assert result.exit_code != 0
    assert "无法从分支 'main' 解析 issue 编号" in result.output
