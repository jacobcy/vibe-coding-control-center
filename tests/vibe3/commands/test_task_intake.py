"""Tests for task intake command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner(env={"NO_COLOR": "1"})


def test_intake_happy_path():
    """Happy path: issue is state/ready with no assignees → assigns successfully."""
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
        }
        mock_client.add_assignee.return_value = True
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 0
        assert "#123 assigned to manager1" in result.output
        mock_client.add_assignee.assert_called_once_with(123, "manager1")


def test_intake_already_assigned_to_same_manager():
    """Already assigned to same manager: no guard needed, confirms assignment."""
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
            "assignees": [{"login": "manager1"}],
        }
        mock_client.add_assignee.return_value = True
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 0
        assert "#123 assigned to manager1" in result.stdout


def test_intake_non_ready_state_guard():
    """Non-ready state guard: issue has state/in-progress → exits 1 without --yes."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
    ):
        mock_config.return_value = MagicMock(orchestra=MagicMock())
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = {
            "labels": [{"name": "state/in-progress"}],
            "assignees": [],
        }
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 1
        assert "state/in-progress" in result.output
        assert "Use --yes to force reassignment" in result.output
        mock_client.add_assignee.assert_not_called()


def test_intake_different_assignee_guard():
    """Different assignee guard: issue assigned to other user.

    Exits 1 without --yes.
    """
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
            "assignees": [{"login": "other-user"}],
        }
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 1
        assert "assigned to other-user" in result.output
        assert "Use --yes to force reassignment" in result.output
        mock_client.add_assignee.assert_not_called()


def test_intake_force_with_yes():
    """Force with --yes: non-ready state + different assignee + --yes → assigns."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
    ):
        mock_config.return_value = MagicMock(orchestra=MagicMock())
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = {
            "labels": [{"name": "state/in-progress"}],
            "assignees": [{"login": "other-user"}],
        }
        mock_client.add_assignee.return_value = True
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["task", "intake", "123", "--yes"])

        assert result.exit_code == 0
        assert "#123 reassigned to manager1 (was other-user)" in result.output
        mock_client.add_assignee.assert_called_once_with(123, "manager1")


def test_intake_issue_not_found():
    """Issue not found: exits 1."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
    ):
        mock_config.return_value = MagicMock(orchestra=MagicMock())
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = None
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 1
        assert "Issue #123 not found" in result.output


def test_intake_network_error():
    """Network error: exits 1."""
    with (
        patch("vibe3.commands.task.GitHubClient") as mock_client_cls,
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
    ):
        mock_config.return_value = MagicMock(orchestra=MagicMock())
        mock_managers.return_value = ["manager1"]

        mock_client = MagicMock()
        mock_client.view_issue.return_value = "network_error"
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 1
        assert "Could not fetch issue #123 (network/auth)" in result.output


def test_intake_no_manager_configured():
    """No manager configured: exits 1."""
    with (
        patch("vibe3.commands.task.get_manager_usernames") as mock_managers,
        patch("vibe3.commands.task.get_config_with_env_override") as mock_config,
    ):
        mock_config.return_value = MagicMock(orchestra=MagicMock())
        mock_managers.return_value = []

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 1
        assert "No manager usernames configured" in result.output


def test_intake_add_assignee_failure():
    """add_assignee failure: exits 1."""
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
        }
        mock_client.add_assignee.return_value = False
        mock_client_cls.return_value = mock_client

        result = runner.invoke(app, ["task", "intake", "123"])

        assert result.exit_code == 1
        assert "Failed to assign #123" in result.output
