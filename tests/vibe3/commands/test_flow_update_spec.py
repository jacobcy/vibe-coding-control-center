"""Tests for flow update command spec_ref handling."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from vibe3.commands.flow_manage import update


def test_update_clear_spec_ref_with_empty_string() -> None:
    """Test --spec '' clears spec_ref."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "test/branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow
    mock_flow_service.get_current_branch.return_value = "test/branch"

    with patch(
        "vibe3.commands.flow_manage.FlowService", return_value=mock_flow_service
    ):
        with patch("vibe3.commands.flow_manage.trace_scope"):
            update(branch="test/branch", spec="")

    # Verify: spec_ref cleared with None
    mock_flow_service.store.update_flow_state.assert_called_once_with(
        "test/branch", spec_ref=None
    )


def test_update_with_issue_number_rejected() -> None:
    """Test --spec 123 (issue number) is rejected with helpful error."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "test/branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow
    mock_flow_service.get_current_branch.return_value = "test/branch"

    with patch(
        "vibe3.commands.flow_manage.FlowService", return_value=mock_flow_service
    ):
        with patch("vibe3.commands.flow_manage.trace_scope"):
            with pytest.raises(typer.Exit) as exc_info:
                update(branch="test/branch", spec="123")

    # Verify: exit code 1
    assert exc_info.value.exit_code == 1


def test_update_with_valid_file_path() -> None:
    """Test --spec with existing file path binds successfully."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "test/branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow

    with patch(
        "vibe3.commands.flow_manage.FlowService", return_value=mock_flow_service
    ):
        with patch("vibe3.commands.flow_manage.trace_scope"):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "is_file", return_value=True):
                    with patch.object(
                        Path, "resolve", return_value=Path("/abs/docs/spec.md")
                    ):
                        update(branch="test/branch", spec="docs/spec.md")

    # Verify: bind_spec called with absolute path
    mock_flow_service.bind_spec.assert_called_once()


def test_update_with_invalid_file_path_raises_error() -> None:
    """Test --spec with non-existent file raises error."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "test/branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow

    with patch(
        "vibe3.commands.flow_manage.FlowService", return_value=mock_flow_service
    ):
        with patch("vibe3.commands.flow_manage.trace_scope"):
            with patch.object(Path, "exists", return_value=False):
                with pytest.raises(typer.Exit) as exc_info:
                    update(branch="test/branch", spec="nonexistent.md")

    # Verify: exit code 1
    assert exc_info.value.exit_code == 1


def test_update_without_spec_does_not_modify() -> None:
    """Test update without --spec does not modify spec_ref."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "test/branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow

    with patch(
        "vibe3.commands.flow_manage.FlowService", return_value=mock_flow_service
    ):
        with patch("vibe3.commands.flow_manage.trace_scope"):
            update(branch="test/branch", spec=None)

    # Verify: bind_spec NOT called, update_flow_state NOT called for spec_ref
    mock_flow_service.bind_spec.assert_not_called()
    mock_flow_service.store.update_flow_state.assert_not_called()
