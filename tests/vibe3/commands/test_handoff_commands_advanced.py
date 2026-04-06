"""Integration tests for Handoff commands - Advanced operations."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.handoff_read import (
    UPDATE_LOG_MESSAGE_PREVIEW_LIMIT,
    _preview_update_message,
    _render_updates_log,
)

runner = CliRunner()


class TestHandoffAdvancedCommands:
    """Tests for advanced handoff CLI commands."""

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
