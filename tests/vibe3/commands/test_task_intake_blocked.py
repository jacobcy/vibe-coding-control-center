"""Tests for task intake command blocked-by flows."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner(env={"NO_COLOR": "1"})


def test_intake_with_blocked_by_creates_placeholder_flow():
    """--blocked-by parameter should create placeholder flow and set blocked label."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
        patch("vibe3.commands.task.load_issue_info") as mock_load_issue,
        patch("vibe3.commands.task.FlowOrchestratorService") as mock_orch_cls,
        patch("vibe3.commands.task.LabelService") as mock_label_cls,
        patch("vibe3.commands.task.IssueFlowService") as mock_issue_flow_cls,
    ):
        mock_config_obj = MagicMock()
        mock_config_obj.orchestra.repo = "owner/repo"
        mock_config.return_value = mock_config_obj
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = {
            "labels": [{"name": "state/ready"}],
            "assignees": [],
            "title": "Blocked issue",
            "state": "open",
        }
        mock_client.add_assignee.return_value = True
        mock_client_cls.return_value = mock_client

        from vibe3.models import IssueInfo

        mock_load_issue.return_value = IssueInfo(number=123, title="Blocked issue")

        mock_issue_flow = MagicMock()
        mock_issue_flow.canonical_branch_name.return_value = "task/issue-123"
        mock_issue_flow_cls.return_value = mock_issue_flow

        mock_orchestrator = MagicMock()
        mock_orchestrator.create_placeholder_flow.return_value = {
            "branch": "task/issue-123",
            "flow_status": "blocked",
        }
        mock_orch_cls.return_value = mock_orchestrator

        mock_label_service = MagicMock()
        mock_label_cls.return_value = mock_label_service

        result = runner.invoke(app, ["task", "intake", "123", "--blocked-by", "99"])

        assert result.exit_code == 0
        assert "#123 assigned to manager1" in result.output
        assert "Placeholder flow created (blocked by #99)" in result.output

        mock_orchestrator.create_placeholder_flow.assert_called_once()

        from vibe3.models import IssueState

        mock_label_service.set_state.assert_called_once_with(123, IssueState.BLOCKED)


def test_intake_rejects_blocked_by_and_reason_together():
    """--blocked-by and --blocked-reason should remain mutually exclusive."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
    ):
        mock_config.return_value = MagicMock(orchestra=MagicMock())
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = {
            "labels": [{"name": "state/ready"}],
            "assignees": [],
            "title": "Blocked issue",
            "state": "open",
        }
        mock_client_cls.return_value = mock_client

        result = runner.invoke(
            app,
            [
                "task",
                "intake",
                "123",
                "--blocked-by",
                "99",
                "--blocked-reason",
                "manual block",
            ],
        )

        assert result.exit_code == 1
        assert "不能同时指定" in result.output


def test_intake_without_blocked_by_no_placeholder():
    """Without --blocked-by, placeholder flow creation should not be called."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
        patch("vibe3.commands.task.FlowOrchestratorService") as mock_orch_cls,
    ):
        mock_config.return_value = MagicMock(orchestra=MagicMock())
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = {
            "labels": [{"name": "state/ready"}],
            "assignees": [],
            "title": "Normal issue",
        }
        mock_client.add_assignee.return_value = True
        mock_client_cls.return_value = mock_client

        mock_orchestrator = MagicMock()
        mock_orch_cls.return_value = mock_orchestrator

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 0
        assert "#123 assigned to manager1" in result.output

        mock_orchestrator.create_placeholder_flow.assert_not_called()


def test_intake_blocked_by_assignee_failure_skips_placeholder():
    """If assignee fails, placeholder flow should not be created."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
        patch("vibe3.commands.task.FlowOrchestratorService") as mock_orch_cls,
    ):
        mock_config.return_value = MagicMock(orchestra=MagicMock())
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = {
            "labels": [{"name": "state/ready"}],
            "assignees": [],
            "title": "Blocked issue",
        }
        mock_client.add_assignee.return_value = False
        mock_client_cls.return_value = mock_client

        mock_orchestrator = MagicMock()
        mock_orch_cls.return_value = mock_orchestrator

        result = runner.invoke(app, ["task", "intake", "123", "--blocked-by", "99"])

        assert result.exit_code == 1
        assert "Failed to assign #123" in result.output

        mock_orchestrator.create_placeholder_flow.assert_not_called()


def test_intake_blocked_by_placeholder_creation_failure():
    """If placeholder flow creation fails, warn and propagate error."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
        patch("vibe3.commands.task.load_issue_info") as mock_load_issue,
        patch("vibe3.commands.task.FlowOrchestratorService") as mock_orch_cls,
        patch("vibe3.commands.task.IssueFlowService") as mock_issue_flow_cls,
    ):
        mock_config_obj = MagicMock()
        mock_config_obj.orchestra.repo = "owner/repo"
        mock_config.return_value = mock_config_obj
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = {
            "labels": [{"name": "state/ready"}],
            "assignees": [],
            "title": "Blocked issue",
            "state": "open",
        }
        mock_client.add_assignee.return_value = True
        mock_client_cls.return_value = mock_client

        from vibe3.models import IssueInfo

        mock_load_issue.return_value = IssueInfo(number=123, title="Blocked issue")

        mock_issue_flow = MagicMock()
        mock_issue_flow.canonical_branch_name.return_value = "task/issue-123"
        mock_issue_flow_cls.return_value = mock_issue_flow

        mock_orchestrator = MagicMock()
        mock_orchestrator.create_placeholder_flow.side_effect = RuntimeError(
            "DB connection lost"
        )
        mock_orch_cls.return_value = mock_orchestrator

        result = runner.invoke(app, ["task", "intake", "123", "--blocked-by", "99"])

        assert result.exit_code == 1
        assert "#123 assigned to manager1" in result.output
        assert "Warning: Placeholder flow creation failed" in result.output
