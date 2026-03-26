"""Tests for flow add status checking logic."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


class TestFlowAddStatusCheck:
    """Tests for flow add status checking."""

    @patch("vibe3.commands.flow.HandoffService")
    @patch("vibe3.commands.flow.FlowService")
    def test_unregistered_branch_creates_flow(
        self, mock_service_class, mock_handoff_class
    ):
        """A branch without any flow record should create a new flow."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "feature/test"
        mock_service.get_flow_status.return_value = None
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow"])

        assert result.exit_code == 0
        mock_service.create_flow.assert_called_once_with(
            slug="new-flow",
            branch="feature/test",
        )

    @pytest.mark.parametrize("flow_status", ["active", "done", "aborted", "stale"])
    @patch("vibe3.commands.flow.FlowService")
    def test_existing_flow_blocks_creation(self, mock_service_class, flow_status: str):
        """Any existing flow record should block creation."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "feature/test"
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = flow_status
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow"])

        assert result.exit_code == 1
        assert "already has flow" in result.output.lower()
        mock_service.create_flow.assert_not_called()
