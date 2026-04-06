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
        mock_service.ensure_current_handoff.return_value = "/path/to/current.md"
        mock_service_class.return_value = mock_service

        args = ["handoff", "init"]
        if force:
            args.append("--yes")
        result = runner.invoke(app, args)

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Handoff file ready" in result.output
        mock_service.ensure_current_handoff.assert_called_once_with(
            force=expected_force
        )

    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_show_command(self, mock_service_class):
        """Test handoff show command shows agent chain and events."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "feature/test"
        mock_service.get_flow_state.return_value = FlowState(
            branch="feature/test",
            flow_slug="feature-test",
            flow_status="active",
        )
        mock_service.get_handoff_events.return_value = []
        mock_service.get_git_common_dir.return_value = "/path/to/.git"
        mock_service_class.return_value = mock_service

        with patch(
            "vibe3.commands.handoff_read.get_branch_handoff_dir"
        ) as mock_get_dir:
            mock_get_dir.return_value = Path("/path/to/handoff")
            with patch.object(Path, "exists", return_value=False):
                result = runner.invoke(app, ["handoff", "show"])

        assert result.exit_code == 0
        assert "Handoff" in result.output
        mock_service.get_flow_state.assert_called_once()
        mock_service.get_handoff_events.assert_called_once()

    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_show_numeric_issue_resolves_branch(self, mock_service_class):
        """handoff show 436 should resolve to task/dev issue branch."""
        mock_service = MagicMock()
        mock_service.get_flow_state.side_effect = lambda branch: (
            FlowState(branch=branch, flow_slug="issue-436", flow_status="active")
            if branch == "task/issue-436"
            else None
        )
        mock_service.get_handoff_events.return_value = []
        mock_service.get_git_common_dir.return_value = "/path/to/.git"
        mock_service_class.return_value = mock_service

        with patch(
            "vibe3.commands.handoff_read.get_branch_handoff_dir"
        ) as mock_get_dir:
            mock_get_dir.return_value = Path("/path/to/handoff")
            with patch.object(Path, "exists", return_value=False):
                result = runner.invoke(app, ["handoff", "show", "436"])

        assert result.exit_code == 0
        mock_service.get_flow_state.assert_any_call("task/issue-436")
        mock_service.get_handoff_events.assert_called_once_with(
            "task/issue-436", limit=5
        )

    @patch("vibe3.commands.handoff_read.render_handoff_summary")
    @patch("vibe3.commands.handoff_read.render_handoff_list")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_list_command(
        self,
        mock_service_class,
        mock_render_list,
        mock_render_summary,
    ):
        """Test handoff list command renders filtered handoff events."""
        from vibe3.models.flow import FlowEvent

        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "feature/test"
        mock_service.get_handoff_events.return_value = [
            FlowEvent(
                branch="feature/test",
                event_type="handoff_plan",
                actor="planner",
                detail="Plan completed",
                created_at="2026-03-26T11:00:00",
            ),
            FlowEvent(
                branch="feature/test",
                event_type="handoff_run",
                actor="executor",
                detail="Run completed",
                created_at="2026-03-26T11:10:00",
            ),
        ]
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["handoff", "list", "--kind", "run"])

        assert result.exit_code == 0
        mock_service.get_handoff_events.assert_called_once()
        mock_render_list.assert_called_once()
        handoffs = mock_render_list.call_args.args[1]
        assert len(handoffs) == 1
        assert handoffs[0]["kind"] == "run"
        mock_render_summary.assert_called_once()

    def test_handoff_list_rejects_invalid_kind(self):
        """Test handoff list validates kind option."""
        result = runner.invoke(app, ["handoff", "list", "--kind", "invalid"])

        assert result.exit_code != 0
        assert "must be one of" in result.output

    @patch("vibe3.commands.handoff_read.render_handoff_detail")
    def test_handoff_show_artifact(self, mock_render_detail):
        """Test handoff show --artifact renders single artifact."""
        with runner.isolated_filesystem():
            artifact = Path("artifact.md")
            artifact.write_text("# artifact", encoding="utf-8")

            result = runner.invoke(
                app, ["handoff", "show", "--artifact", str(artifact)]
            )

        assert result.exit_code == 0
        mock_render_detail.assert_called_once()

    def test_handoff_show_artifact_not_found(self):
        """Test handoff show --artifact reports missing files."""
        result = runner.invoke(app, ["handoff", "show", "--artifact", "missing.md"])

        assert result.exit_code != 0
        assert "artifact not found" in result.output.lower()

    def test_handoff_show_artifact_rejects_directory(self):
        """Test handoff show --artifact rejects non-file paths."""
        with runner.isolated_filesystem():
            Path("artifact_dir").mkdir()
            result = runner.invoke(
                app, ["handoff", "show", "--artifact", "artifact_dir"]
            )

        assert result.exit_code != 0
        assert "not a file" in result.output.lower()
