"""Integration tests for Handoff commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestHandoffCommands:
    """Tests for handoff CLI commands."""

    @pytest.mark.parametrize("force,expected_force", [(False, False), (True, True)])
    @patch("vibe3.commands.handoff.HandoffService")
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

    @patch("vibe3.commands.handoff.SQLiteClient")
    @patch("vibe3.commands.handoff.GitClient")
    def test_handoff_show_command(self, mock_git_class, mock_store_class):
        """Test handoff show command shows agent chain and events."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {
            "branch": "feature/test",
            "flow_slug": "feature-test",
            "flow_status": "active",
            "spec_ref": None,
            "plan_ref": None,
            "report_ref": None,
            "audit_ref": None,
        }
        mock_store.get_events.return_value = []
        mock_store_class.return_value = mock_store

        result = runner.invoke(app, ["handoff", "show"])

        assert result.exit_code == 0
        assert "Handoff" in result.output
        assert "Agent Chain" in result.output
        assert "spec_ref" in result.output
        mock_store.get_flow_state.assert_called_once()
        mock_store.get_events.assert_called_once()

    @patch("vibe3.commands.handoff.render_handoff_summary")
    @patch("vibe3.commands.handoff.render_handoff_list")
    @patch("vibe3.commands.handoff.SQLiteClient")
    @patch("vibe3.commands.handoff.GitClient")
    def test_handoff_list_command(
        self,
        mock_git_class,
        mock_store_class,
        mock_render_list,
        mock_render_summary,
    ):
        """Test handoff list command renders filtered handoff events."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "feature/test"
        mock_git_class.return_value = mock_git

        mock_store = MagicMock()
        mock_store.get_events.return_value = [
            {
                "event_type": "handoff_plan",
                "actor": "planner",
                "detail": "Plan completed",
                "created_at": "2026-03-26T11:00:00",
            },
            {
                "event_type": "handoff_run",
                "actor": "executor",
                "detail": "Run completed",
                "created_at": "2026-03-26T11:10:00",
            },
        ]
        mock_store_class.return_value = mock_store

        result = runner.invoke(app, ["handoff", "list", "--kind", "run"])

        assert result.exit_code == 0
        mock_store.get_events.assert_called_once_with(
            "feature/test", event_type_prefix="handoff_"
        )
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

    @patch("vibe3.commands.handoff.render_handoff_detail")
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

    @patch("vibe3.commands.handoff.HandoffService")
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

    @patch("vibe3.commands.handoff.HandoffService")
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

    @patch("vibe3.commands.handoff.HandoffService")
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

    @patch("vibe3.commands.handoff.HandoffService")
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

    @patch("vibe3.commands.handoff.HandoffService")
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
