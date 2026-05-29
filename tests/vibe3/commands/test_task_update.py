"""Tests for task update command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.task import app as task_app

runner = CliRunner()


# ==============================================================================
# task update tests
# ==============================================================================


@patch("vibe3.commands.task_manage.GhIssueLabelPort")
def test_add_label(mock_port_cls) -> None:
    """task update --add-label should add label."""
    mock_port = MagicMock()
    mock_port_cls.return_value = mock_port

    # Mock successful add
    mock_port.add_issue_label.return_value = True

    result = runner.invoke(task_app, ["update", "123", "--add-label", "state/handoff"])

    assert result.exit_code == 0
    mock_port.add_issue_label.assert_called_once_with(123, "state/handoff")
    assert "✓ Added label 'state/handoff' to issue #123" in result.stdout


@patch("vibe3.commands.task_manage.GhIssueLabelPort")
def test_remove_label(mock_port_cls) -> None:
    """task update --remove-label should remove label."""
    mock_port = MagicMock()
    mock_port_cls.return_value = mock_port

    # Mock successful remove
    mock_port.remove_issue_label.return_value = True

    result = runner.invoke(
        task_app, ["update", "456", "--remove-label", "priority/low"]
    )

    assert result.exit_code == 0
    mock_port.remove_issue_label.assert_called_once_with(456, "priority/low")
    assert "✓ Removed label 'priority/low' from issue #456" in result.stdout


@patch("vibe3.commands.task_manage.GhIssueLabelPort")
def test_add_and_remove_labels(mock_port_cls) -> None:
    """task update with both --add-label and --remove-label."""
    mock_port = MagicMock()
    mock_port_cls.return_value = mock_port

    # Mock successful operations
    mock_port.add_issue_label.return_value = True
    mock_port.remove_issue_label.return_value = True

    result = runner.invoke(
        task_app,
        [
            "update",
            "789",
            "--add-label",
            "priority/high",
            "--remove-label",
            "priority/low",
        ],
    )

    assert result.exit_code == 0
    mock_port.add_issue_label.assert_called_once_with(789, "priority/high")
    mock_port.remove_issue_label.assert_called_once_with(789, "priority/low")


def test_update_without_labels() -> None:
    """task update without --add-label or --remove-label should fail."""
    result = runner.invoke(task_app, ["update", "123"])

    assert result.exit_code == 1
    assert "Must specify at least one" in result.stderr


@patch("vibe3.commands.task_manage.GhIssueLabelPort")
def test_add_label_failure(mock_port_cls) -> None:
    """task update should fail if add_issue_label returns False."""
    mock_port = MagicMock()
    mock_port_cls.return_value = mock_port

    # Mock failure
    mock_port.add_issue_label.return_value = False

    result = runner.invoke(task_app, ["update", "123", "--add-label", "test/label"])

    assert result.exit_code == 1
    assert "Failed to add label" in result.stderr


@patch("vibe3.commands.task_manage.GhIssueLabelPort")
def test_remove_label_failure(mock_port_cls) -> None:
    """task update should fail if remove_issue_label returns False."""
    mock_port = MagicMock()
    mock_port_cls.return_value = mock_port

    # Mock failure
    mock_port.remove_issue_label.return_value = False

    result = runner.invoke(task_app, ["update", "456", "--remove-label", "test/label"])

    assert result.exit_code == 1
    assert "Failed to remove label" in result.stderr


@patch("vibe3.commands.task_manage.GhIssueLabelPort")
def test_multiple_add_labels(mock_port_cls) -> None:
    """task update with multiple --add-label flags."""
    mock_port = MagicMock()
    mock_port_cls.return_value = mock_port

    # Mock successful adds
    mock_port.add_issue_label.return_value = True

    result = runner.invoke(
        task_app,
        ["update", "999", "--add-label", "label1", "--add-label", "label2"],
    )

    assert result.exit_code == 0
    assert mock_port.add_issue_label.call_count == 2
