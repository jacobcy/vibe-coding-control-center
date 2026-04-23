"""Integration tests for Handoff commands - Basic operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowState

runner = CliRunner()


class TestHandoffBasicCommands:
    """Tests for basic handoff CLI commands."""

    @pytest.mark.parametrize("force,expected_force", [(False, False), (True, True)])
    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_init_command(self, mock_service_class, force, expected_force):
        """Test handoff init command."""
        mock_service = MagicMock()
        mock_service.storage.ensure_current_handoff.return_value = "/path/to/current.md"
        mock_service_class.return_value = mock_service

        args = ["handoff", "init"]
        if force:
            args.append("--yes")
        result = runner.invoke(app, args)

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Handoff file ready" in result.output
        mock_service.storage.ensure_current_handoff.assert_called_once_with(
            force=expected_force
        )

    @patch("vibe3.commands.handoff_read.HandoffService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_command(
        self, mock_flow_service_class, mock_handoff_service_class
    ):
        """Test handoff status command shows agent chain and events."""
        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "feature/test"
        mock_flow_service.get_flow_state.return_value = FlowState(
            branch="feature/test",
            flow_slug="feature-test",
            flow_status="active",
        )
        mock_flow_service.get_git_common_dir.return_value = "/path/to/.git"
        mock_flow_service_class.return_value = mock_flow_service
        mock_handoff_service = MagicMock()
        mock_handoff_service.get_handoff_events.return_value = []
        mock_handoff_service_class.return_value = mock_handoff_service

        with patch(
            "vibe3.commands.handoff_read.get_branch_handoff_dir"
        ) as mock_get_dir:
            mock_get_dir.return_value = Path("/path/to/handoff")
            with patch.object(Path, "exists", return_value=False):
                result = runner.invoke(app, ["handoff", "status"])

        assert result.exit_code == 0
        assert "Handoff" in result.output
        mock_flow_service.get_flow_state.assert_called_once()
        mock_handoff_service.get_handoff_events.assert_called_once()

    @patch("vibe3.commands.handoff_read.HandoffService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_numeric_issue_resolves_branch(
        self, mock_flow_service_class, mock_handoff_service_class
    ):
        """handoff status 436 should resolve to task/dev issue branch."""
        mock_flow_service = MagicMock()
        mock_flow_service.get_flow_state.side_effect = lambda branch: (
            FlowState(branch=branch, flow_slug="issue-436", flow_status="active")
            if branch == "task/issue-436"
            else None
        )
        mock_flow_service.get_git_common_dir.return_value = "/path/to/.git"
        mock_flow_service_class.return_value = mock_flow_service
        mock_handoff_service = MagicMock()
        mock_handoff_service.get_handoff_events.return_value = []
        mock_handoff_service_class.return_value = mock_handoff_service

        with patch(
            "vibe3.commands.handoff_read.get_branch_handoff_dir"
        ) as mock_get_dir:
            mock_get_dir.return_value = Path("/path/to/handoff")
            with patch.object(Path, "exists", return_value=False):
                result = runner.invoke(app, ["handoff", "status", "436"])

        assert result.exit_code == 0
        mock_flow_service.get_flow_state.assert_any_call("task/issue-436")
        mock_handoff_service.get_handoff_events.assert_called_once_with(
            "task/issue-436", limit=5
        )

    @patch("vibe3.commands.handoff_read.render_handoff_detail")
    def test_handoff_show_artifact(self, mock_render_detail):
        """Test handoff show <artifact> renders single artifact."""
        with runner.isolated_filesystem():
            artifact = Path("artifact.md")
            artifact.write_text("# artifact", encoding="utf-8")

            result = runner.invoke(app, ["handoff", "show", str(artifact)])

        assert result.exit_code == 0
        mock_render_detail.assert_called_once()

    def test_handoff_show_artifact_not_found(self):
        """Test handoff show <artifact> reports missing files."""
        result = runner.invoke(app, ["handoff", "show", "missing.md"])

        assert result.exit_code != 0
        assert "artifact not found" in result.output.lower()

    def test_handoff_show_artifact_rejects_directory(self):
        """Test handoff show <artifact> rejects non-file paths."""
        with runner.isolated_filesystem():
            Path("artifact_dir").mkdir()
            result = runner.invoke(app, ["handoff", "show", "artifact_dir"])

        assert result.exit_code != 0
        assert "not a file" in result.output.lower()
