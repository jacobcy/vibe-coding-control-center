"""Tests for flow add status checking logic."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


class TestFlowAddStatusCheck:
    """Tests for flow add status checking."""

    @patch("vibe3.commands.flow.FlowService")
    def test_active_flow_blocks_creation(self, mock_service_class):
        """Active flow should block creation."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "feature/test"
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "active"
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow"])

        assert result.exit_code == 1
        assert "has active flow" in result.output.lower()
        mock_service.create_flow.assert_not_called()

    @patch("vibe3.commands.flow.FlowService")
    def test_active_flow_force_create(self, mock_service_class):
        """Active flow with --yes should force create."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "feature/test"
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "active"
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow", "--yes"])

        assert result.exit_code == 0
        mock_service.create_flow.assert_called_once()

    @patch("vibe3.commands.flow.FlowService")
    def test_done_flow_allows_creation(self, mock_service_class):
        """Done flow should allow creation with warning."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "feature/test"
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "done"
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        mock_service.create_flow.assert_called_once()

    @patch("vibe3.commands.flow.FlowService")
    def test_aborted_flow_allows_creation(self, mock_service_class):
        """Aborted flow should allow creation with warning."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "feature/test"
        mock_flow = MagicMock(spec=FlowStatusResponse)
        mock_flow.flow_status = "aborted"
        mock_flow.flow_slug = "test-flow"
        mock_service.get_flow_status.return_value = mock_flow
        mock_service.create_flow.return_value = MagicMock(
            flow_slug="new-flow", branch="feature/test"
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "add", "new-flow"])

        assert result.exit_code == 0
        assert "warning" in result.output.lower()
        mock_service.create_flow.assert_called_once()
