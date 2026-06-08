"""Tests for internal commands (hidden from users)."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app as cli_app

runner = CliRunner()


def test_internal_manager_dispatch():
    """测试 internal manager 命令参数解析和调用."""
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(cli_app, ["internal", "manager", "123", "--no-async"])

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["dry_run"] is False
        assert mock_run.call_args.kwargs["show_prompt"] is False
        assert mock_run.call_args.kwargs["fresh_session"] is False
        assert mock_run.call_args.kwargs["spec"].role_name == "manager"


def test_internal_manager_dry_run():
    """测试 internal manager --dry-run 参数透传."""
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app, ["internal", "manager", "123", "--no-async", "--dry-run"]
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["dry_run"] is True
        assert mock_run.call_args.kwargs["show_prompt"] is False


def test_internal_manager_show_prompt():
    """测试 internal manager --show-prompt 参数透传."""
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "manager", "123", "--no-async", "--dry-run", "--show-prompt"],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["dry_run"] is True
        assert mock_run.call_args.kwargs["show_prompt"] is True


def test_internal_manager_branch_override():
    """测试 internal manager --branch 参数透传 (sync path)."""
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            [
                "internal",
                "manager",
                "123",
                "--no-async",
                "--dry-run",
                "--branch",
                "task/issue-1905",
            ],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["branch"] == "task/issue-1905"


def test_internal_manager_branch_override_async():
    """测试 internal manager --branch 参数透传 (async path)."""
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_async"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "manager", "123", "--branch", "task/issue-1905"],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 123
        assert mock_run.call_args.kwargs["branch"] == "task/issue-1905"
        assert mock_run.call_args.kwargs["dry_run"] is False


def test_internal_manager_branch_numeric():
    """测试 --branch 接受 issue number，CLI 层透传原始值由 runner 解析."""
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "manager", "123", "--no-async", "--branch", "1905"],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["branch"] == "1905"


def test_internal_apply_dispatch():
    """测试 internal apply 命令参数解析和调用."""
    with patch(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync"
    ) as mock_run:
        result = runner.invoke(
            cli_app,
            ["internal", "apply", "42", "--no-async"],
        )

        assert result.exit_code == 0
        assert mock_run.call_args.kwargs["issue_number"] == 42
        assert mock_run.call_args.kwargs["dry_run"] is False
        assert mock_run.call_args.kwargs["fresh_session"] is True
        assert mock_run.call_args.kwargs["spec"].role_name == "supervisor"


def test_internal_governance_dispatch_forwards_tick_and_material():
    """测试 internal governance 会透传 tick 和 material."""
    with patch(
        "vibe3.roles.scan_service.dispatch_governance_execution"
    ) as mock_dispatch:
        result = runner.invoke(
            cli_app,
            ["internal", "governance", "8", "0", "--material", "roadmap-intake"],
        )

        assert result.exit_code == 0
        mock_dispatch.assert_called_once_with(
            tick_count=8,
            execution_count=0,
            material_override="roadmap-intake",
        )


def test_internal_hidden_from_help():
    """测试 internal 命令对用户不可见."""
    result = runner.invoke(cli_app, ["--help"])
    # internal 命令应该出现在帮助信息中,但标注为 hidden
    assert "internal" not in result.stdout or "Internal" in result.stdout


def test_internal_bootstrap_dispatch() -> None:
    """internal bootstrap should call shared bootstrap service."""
    issue_payload = {
        "number": 123,
        "title": "Bootstrap me",
        "state": "OPEN",
        "labels": [{"name": "state/claimed"}],
        "assignees": [],
        "comments": [],
    }

    with patch("vibe3.commands.internal.load_orchestra_config") as load_config:
        load_config.return_value = MagicMock(repo="owner/repo")
        with patch("vibe3.clients.sqlite_client.SQLiteClient"):
            with patch("vibe3.clients.git_client.GitClient"):
                with patch("vibe3.clients.github_client.GitHubClient") as github_cls:
                    with patch("vibe3.services.FlowOrchestratorService") as service_cls:
                        github = MagicMock()
                        github.view_issue.return_value = issue_payload
                        github_cls.return_value = github
                        service = MagicMock()
                        service.bootstrap_issue_flow.return_value = {
                            "branch": "dev/issue-123",
                            "worktree_path": "/tmp/dev-issue-123",
                        }
                        service_cls.return_value = service

                        result = runner.invoke(
                            cli_app,
                            [
                                "internal",
                                "bootstrap",
                                "123",
                                "--branch",
                                "dev/issue-123",
                                "--worktree",
                                "--related",
                                "456",
                                "--dependency",
                                "789",
                            ],
                        )

    assert result.exit_code == 0
    service.bootstrap_issue_flow.assert_called_once()
    call = service.bootstrap_issue_flow.call_args
    issue_info = call.args[0]
    assert issue_info.number == 123
    assert call.kwargs["branch"] == "dev/issue-123"
    assert call.kwargs["ensure_worktree"] is True
    assert call.kwargs["related_issue_numbers"] == (456,)
    assert call.kwargs["dependency_issue_numbers"] == (789,)
    payload = json.loads(result.stdout)
    assert payload["branch"] == "dev/issue-123"
