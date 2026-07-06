"""Tests for flow update command spec_ref handling."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from vibe3.commands.flow_manage import update
from vibe3.exceptions import UserError


@patch("vibe3.commands.flow_manage.HandoffService")
@patch("vibe3.commands.flow_manage.FlowService")
def test_update_spec_delegates_to_canonical_writer(
    mock_flow_service_class, mock_handoff_class
) -> None:
    """FR-006: `flow update --spec <canonical>` delegates to
    HandoffService.record_spec — the same writer `handoff spec` uses —
    producing equivalent state/event semantics. Legacy bind_spec is NOT used."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "task/test-branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow
    mock_flow_service_class.return_value = mock_flow_service

    mock_handoff = MagicMock()
    mock_handoff_class.return_value = mock_handoff

    update(branch_arg="task/test-branch", spec=".specify/specs/012-foo/spec.md")

    mock_handoff.record_spec.assert_called_once_with(
        ".specify/specs/012-foo/spec.md", None, branch="task/test-branch"
    )
    # Legacy writer must NOT be used by the canonical `flow update --spec` path
    mock_flow_service.bind_spec.assert_not_called()


@patch("vibe3.commands.flow_manage.HandoffService")
@patch("vibe3.commands.flow_manage.FlowService")
def test_update_spec_passes_path_unmodified(
    mock_flow_service_class, mock_handoff_class
) -> None:
    """FR-006: the canonical relative path is forwarded as-is — no Path
    resolution to an absolute path (the old bind_spec behavior). The writer
    itself owns canonical validation per ADR-0006."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "task/test-branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow
    mock_flow_service_class.return_value = mock_flow_service

    mock_handoff = MagicMock()
    mock_handoff_class.return_value = mock_handoff

    canonical = ".specify/specs/012-foo/spec.md"
    update(branch_arg="task/test-branch", spec=canonical)

    args, kwargs = mock_handoff.record_spec.call_args
    assert args[0] == canonical  # forwarded unmodified
    assert "branch" in kwargs and kwargs["branch"] == "task/test-branch"


@patch("vibe3.commands.flow_manage.HandoffService")
@patch("vibe3.commands.flow_manage.FlowService")
def test_update_spec_propagates_validation_error(
    mock_flow_service_class, mock_handoff_class
) -> None:
    """When the canonical writer rejects the spec_ref (G1 write-strict),
    `flow update --spec` surfaces it as a non-zero exit — equivalent
    observable outcome to `handoff spec` rejecting the same input."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "task/test-branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow
    mock_flow_service_class.return_value = mock_flow_service

    mock_handoff = MagicMock()
    mock_handoff.record_spec.side_effect = UserError(
        "spec_ref must be a canonical repository-relative path"
    )
    mock_handoff_class.return_value = mock_handoff

    with pytest.raises(typer.Exit) as exc_info:
        update(branch_arg="task/test-branch", spec="#3310")

    assert exc_info.value.exit_code == 1
    mock_flow_service.bind_spec.assert_not_called()


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
        update(branch_arg="test/branch", spec="")

    # Verify: spec_ref cleared with None
    mock_flow_service.store.update_flow_state.assert_called_once_with(
        "test/branch", spec_ref=None
    )


def test_update_without_spec_does_not_modify() -> None:
    """Test update without --spec does not modify spec_ref."""
    mock_flow_service = MagicMock()
    mock_flow = MagicMock()
    mock_flow.branch = "test/branch"
    mock_flow_service.ensure_flow_for_branch.return_value = mock_flow

    with patch(
        "vibe3.commands.flow_manage.FlowService", return_value=mock_flow_service
    ):
        update(branch_arg="test/branch", spec=None)

    # Verify: bind_spec NOT called, update_flow_state NOT called for spec_ref
    mock_flow_service.bind_spec.assert_not_called()
    mock_flow_service.store.update_flow_state.assert_not_called()
