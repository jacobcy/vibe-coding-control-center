"""Integration tests for Handoff commands - Advanced operations."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.handoff_render import _to_handoff_cmd

runner = CliRunner()


class TestHandoffAdvancedCommands:
    """Tests for advanced handoff CLI commands."""

    def test_to_handoff_cmd_wraps_relative_refs(self):
        assert (
            _to_handoff_cmd("docs/plans/test-plan.md")
            == "vibe3 handoff show docs/plans/test-plan.md"
        )
        # Shared artifacts get @ prefix
        assert (
            _to_handoff_cmd("vibe3/handoff/task-123/current.md")
            == "vibe3 handoff show @task-123/current.md"
        )
        # Canonical ref with branch uses --branch flag
        assert (
            _to_handoff_cmd("docs/plans/test-plan.md", branch="task/issue-123")
            == "vibe3 handoff show --branch task/issue-123 docs/plans/test-plan.md"
        )

    @patch("vibe3.commands.handoff_read.VerdictService")
    @patch("vibe3.commands.handoff_read.HandoffService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_renders_current_md_via_handoff_show(
        self,
        mock_flow_service_cls,
        mock_handoff_service_cls,
        mock_verdict_service_cls,
        tmp_path,
    ):
        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "task/issue-467"
        mock_flow_service.get_git_common_dir.return_value = "/tmp/repo/.git"
        mock_flow_service.git_client.find_worktree_path_for_branch.return_value = (
            "/tmp/repo/.worktrees/task/issue-467"
        )
        mock_flow_service.git_client.get_worktree_root.return_value = (
            "/tmp/repo/.worktrees/wt-claude-v3"
        )
        mock_flow_service.store = MagicMock()
        mock_flow_service.get_flow_state.return_value = MagicMock(flow_slug="issue-467")
        mock_flow_service_cls.return_value = mock_flow_service

        mock_handoff_service = MagicMock()
        mock_handoff_service.get_handoff_events.return_value = []
        mock_handoff_service_cls.return_value = mock_handoff_service

        mock_verdict_service = MagicMock()
        mock_verdict_service.get_latest_verdict.return_value = None
        mock_verdict_service_cls.return_value = mock_verdict_service

        result = runner.invoke(app, ["handoff", "status", "task/issue-467"])

        assert result.exit_code == 0

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
        assert flow_state is not None
        assert flow_state["audit_ref"] == audit_ref
        assert flow_state["next_step"] == "Finalize PR"
        assert flow_state["reviewer_actor"] == "test-actor"
