"""Tests for task show command behavior."""

from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.task import app
from vibe3.models.task_bridge import HydrateError

runner = CliRunner()


def test_task_show_remote_binding_invalid_exits() -> None:
    """Broken remote binding should surface as an error, not offline output."""
    with patch("vibe3.commands.task.TaskService") as service_cls:
        service = service_cls.return_value
        service.hydrate.return_value = HydrateError(
            type="binding_invalid",
            message="GitHub Project item 'PVTI_123' no longer exists",
        )

        result = runner.invoke(app, ["show", "task/test-branch"])

    assert result.exit_code == 1
    assert "binding_invalid" in result.output
    assert "no longer exists" in result.output


def test_task_show_defaults_to_current_branch_when_missing_argument() -> None:
    """task show without BRANCH should fallback to current git branch."""
    with (
        patch("vibe3.commands.task.GitClient") as git_cls,
        patch("vibe3.commands.task.TaskService") as service_cls,
    ):
        git = git_cls.return_value
        git.get_current_branch.return_value = "task/set-default-flow"

        service = service_cls.return_value
        service.hydrate.return_value = HydrateError(
            type="binding_invalid",
            message="GitHub Project item 'PVTI_123' no longer exists",
        )

        result = runner.invoke(app, ["show"])

    assert result.exit_code == 1
    service.hydrate.assert_called_once_with("task/set-default-flow")
