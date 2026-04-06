"""Integration tests for Handoff commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.handoff_read import (
    UPDATE_LOG_MESSAGE_PREVIEW_LIMIT,
    _preview_update_message,
    _render_updates_log,
)
from vibe3.models.flow import FlowState

runner = CliRunner()


class TestHandoffCommands:
    """Tests for handoff CLI commands."""

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

    def test_handoff_update_log_truncates_messages_by_default(self):
        """Test Update Log preview truncates long messages to 80 chars."""
        message = "x" * (UPDATE_LOG_MESSAGE_PREVIEW_LIMIT + 25)

        assert (
            _preview_update_message(message, truncate=True)
            == "x" * UPDATE_LOG_MESSAGE_PREVIEW_LIMIT + "..."
        )

        with patch("vibe3.commands.handoff_read.console.print") as mock_print:
            _render_updates_log(
                [
                    {
                        "timestamp": "2026-03-26T11:00:00",
                        "actor": "planner",
                        "kind": "finding",
                        "message": message,
                    }
                ]
            )

        printed_lines = [
            call.args[0] for call in mock_print.call_args_list if call.args
        ]
        assert any(
            "x" * UPDATE_LOG_MESSAGE_PREVIEW_LIMIT + "..." in line
            for line in printed_lines
        )
        assert all(message not in line for line in printed_lines)

    def test_handoff_update_log_shows_full_message_with_all(self):
        """Test Update Log renders the full message when truncation is disabled."""
        message = "y" * (UPDATE_LOG_MESSAGE_PREVIEW_LIMIT + 25)

        assert _preview_update_message(message, truncate=False) == message

        with patch("vibe3.commands.handoff_read.console.print") as mock_print:
            _render_updates_log(
                [
                    {
                        "timestamp": "2026-03-26T11:00:00",
                        "actor": "planner",
                        "kind": "finding",
                        "message": message,
                    }
                ],
                truncate=False,
            )

        printed_lines = [
            call.args[0] for call in mock_print.call_args_list if call.args
        ]
        assert any(message in line for line in printed_lines)

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

    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_append_command(self, mock_service_class):
        """Test handoff append command."""
        mock_service = MagicMock()
        mock_service.append_current_handoff.return_value = "/path/to/current.md"
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "append",
                "Need to align event taxonomy",
                "--actor",
                "codex/gpt-5.4",
                "--kind",
                "finding",
            ],
        )

        assert result.exit_code == 0
        assert "Appended handoff update" in result.output
        mock_service.append_current_handoff.assert_called_once_with(
            "Need to align event taxonomy",
            "codex/gpt-5.4",
            "finding",
        )

    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_plan_command(self, mock_service_class):
        """Test handoff plan command."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "plan",
                "docs/plans/test-plan.md",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Plan handoff recorded" in result.output
        mock_service.record_plan.assert_called_once_with(
            "docs/plans/test-plan.md", None, None, "claude/sonnet-4.6"
        )

    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_report_command(self, mock_service_class):
        """Test handoff report command."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "report",
                "docs/reports/test-report.md",
                "--next-step",
                "Address feedback",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Report handoff recorded" in result.output
        mock_service.record_report.assert_called_once_with(
            "docs/reports/test-report.md",
            "Address feedback",
            None,
            "claude/sonnet-4.6",
        )

    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_audit_command(self, mock_service_class):
        """Test handoff audit command."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "audit",
                "docs/audits/test-audit.md",
                "--blocked-by",
                "Waiting for review",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Audit handoff recorded" in result.output
        mock_service.record_audit.assert_called_once_with(
            "docs/audits/test-audit.md",
            None,
            "Waiting for review",
            "claude/sonnet-4.6",
        )

    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_with_options(self, mock_service_class):
        """Test handoff commands with optional parameters."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "plan",
                "docs/plans/test-plan.md",
                "--next-step",
                "Start implementation",
                "--blocked-by",
                "API key needed",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        mock_service.record_plan.assert_called_once_with(
            "docs/plans/test-plan.md",
            "Start implementation",
            "API key needed",
            "claude/sonnet-4.6",
        )

    def test_handoff_audit_command_real_service_path(self, tmp_path, monkeypatch):
        """Test the real service path for handoff audit command with minimal mocking."""
        # Setup temporary directories for git and sqlite
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "vibe3").mkdir()

        # Patch GitClient to return our temp paths
        from vibe3.clients.git_client import GitClient

        monkeypatch.setattr(GitClient, "get_git_common_dir", lambda self: str(git_dir))
        monkeypatch.setattr(GitClient, "get_current_branch", lambda self: "main")

        # Use real SQLiteClient with our temp git dir
        from vibe3.clients import SQLiteClient

        real_store = SQLiteClient()

        # Pre-seed flow state if needed, though record_audit should handle it
        audit_ref = ".agent/reports/audit-result.md"

        # Run the command
        result = runner.invoke(
            app,
            [
                "handoff",
                "audit",
                audit_ref,
                "--next-step",
                "Finalize PR",
                "--actor",
                "test-actor",
            ],
        )

        assert result.exit_code == 0
        assert "Audit handoff recorded" in result.output

        # Verify side effects on filesystem
        # Find the handoff directory (it has a hash suffix)
        handoff_root = git_dir / "vibe3" / "handoff"
        assert handoff_root.exists()
        handoff_dirs = list(handoff_root.iterdir())
        assert len(handoff_dirs) == 1
        handoff_file = handoff_dirs[0] / "current.md"
        assert handoff_file.exists()
        content = handoff_file.read_text()
        assert audit_ref in content
        assert "Finalize PR" in content
        assert "test-actor" in content

        # Verify side effects in database
        flow_state = real_store.get_flow_state("main")
        assert flow_state["audit_ref"] == audit_ref
        assert flow_state["next_step"] == "Finalize PR"

        # Verify event was recorded
        events = real_store.get_events(branch="main", event_type="handoff_audit")
        assert len(events) == 1
        assert events[0]["actor"] == "test-actor"
        assert events[0]["refs"]["ref"] == audit_ref
