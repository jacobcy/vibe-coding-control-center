"""Integration tests for Handoff commands - All CLI operations."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.handoff_render import _to_handoff_cmd

runner = CliRunner()


class TestHandoffAdvancedCommands:
    """Tests for advanced handoff CLI commands."""

    def test_to_handoff_cmd_wraps_relative_refs(self):
        # Canonical refs get alias substitution (now requires ref_field)
        assert (
            _to_handoff_cmd("docs/plans/test-plan.md", ref_field="plan_ref")
            == "vibe3 handoff show @plan"
        )
        # Shared artifacts get @ alias (not full path)
        assert (
            _to_handoff_cmd("vibe3/handoff/task-123/current.md", ref_field="report_ref")
            == "vibe3 handoff show @report"
        )
        # Canonical ref with branch uses --branch flag and alias
        assert (
            _to_handoff_cmd(
                "docs/plans/test-plan.md", branch="task/issue-123", ref_field="plan_ref"
            )
            == "vibe3 handoff show --branch task/issue-123 @plan"
        )

    @patch("vibe3.commands.handoff_read.HandoffStatusService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_renders_current_md_via_handoff_show(
        self,
        mock_flow_service_cls,
        mock_status_service_cls,
        tmp_path,
    ):
        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "task/issue-467"
        mock_flow_service_cls.return_value = mock_flow_service

        mock_status_service = MagicMock()
        mock_status_result = MagicMock()
        mock_status_result.flow_slug = "issue-467"
        mock_status_result.worktree_root = "/tmp/repo/.worktrees/task/issue-467"
        mock_status_result.events = []
        mock_status_result.latest_verdict = None
        mock_status_result.live_sessions = []
        mock_status_service.get_handoff_status.return_value = mock_status_result
        mock_status_service_cls.return_value = mock_status_service

        result = runner.invoke(app, ["handoff", "status", "task/issue-467"])

        assert result.exit_code == 0

    @patch("vibe3.commands.handoff_write.HandoffService")
    @patch("vibe3.services.FlowService")
    def test_handoff_append_command(self, mock_flow_service_class, mock_service_class):
        """Test handoff append command."""
        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "task/test-branch"
        mock_flow_service_class.return_value = mock_flow_service

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
            branch="task/test-branch",
        )

    @patch("vibe3.commands.handoff_write.HandoffService")
    @patch("vibe3.services.FlowService")
    def test_handoff_plan_command(self, mock_flow_service_class, mock_service_class):
        """Test handoff plan command."""
        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "task/test-branch"
        mock_flow_service_class.return_value = mock_flow_service

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
            "docs/plans/test-plan.md",
            "claude/sonnet-4.6",
            branch="task/test-branch",
        )

    @patch("vibe3.commands.handoff_write.HandoffService")
    @patch("vibe3.services.FlowService")
    def test_handoff_report_command(self, mock_flow_service_class, mock_service_class):
        """Test handoff report command."""
        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "task/test-branch"
        mock_flow_service_class.return_value = mock_flow_service

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "report",
                "docs/reports/test-report.md",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Report handoff recorded" in result.output
        mock_service.record_report.assert_called_once_with(
            "docs/reports/test-report.md",
            "claude/sonnet-4.6",
            branch="task/test-branch",
        )

    @patch("vibe3.commands.handoff_write.HandoffService")
    @patch("vibe3.services.FlowService")
    def test_handoff_audit_command(self, mock_flow_service_class, mock_service_class):
        """Test handoff audit command."""
        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "task/test-branch"
        mock_flow_service_class.return_value = mock_flow_service

        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "audit",
                "docs/audits/test-audit.md",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Audit handoff recorded" in result.output
        mock_service.record_audit.assert_called_once_with(
            "docs/audits/test-audit.md",
            "claude/sonnet-4.6",
            branch="task/test-branch",
        )

    def test_handoff_plan_rejects_legacy_next_step_option(self):
        result = runner.invoke(
            app,
            [
                "handoff",
                "plan",
                "docs/plans/test-plan.md",
                "--next-step",
                "Start implementation",
            ],
        )

        assert result.exit_code != 0

    def test_handoff_audit_rejects_legacy_blocked_by_option(self):
        result = runner.invoke(
            app,
            [
                "handoff",
                "audit",
                "docs/audits/test-audit.md",
                "--blocked-by",
                "Waiting for review",
            ],
        )

        assert result.exit_code != 0

    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_plan_with_explicit_branch(self, mock_service_class):
        """Test handoff plan with explicit --branch name."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app,
            [
                "handoff",
                "plan",
                "docs/plans/test-plan.md",
                "--branch",
                "task/custom-branch",
                "--actor",
                "claude/sonnet-4.6",
            ],
        )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Plan handoff recorded" in result.output
        mock_service.record_plan.assert_called_once_with(
            "docs/plans/test-plan.md",
            "claude/sonnet-4.6",
            branch="task/custom-branch",
        )

    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_report_with_issue_number(self, mock_service_class):
        """Test handoff report with --branch <digits> converts to task/issue-N."""
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service

        # Mock FlowService in branch_arg (resolver creates its own instance)
        mock_flow_service = MagicMock()
        mock_store = MagicMock()
        mock_store.get_flows_by_issue.return_value = [
            {"branch": "task/issue-473", "flow_status": "active"}
        ]
        mock_flow_service.store = mock_store

        with patch("vibe3.services.FlowService", return_value=mock_flow_service):
            result = runner.invoke(
                app,
                [
                    "handoff",
                    "report",
                    "docs/reports/test-report.md",
                    "--branch",
                    "473",
                    "--actor",
                    "claude/sonnet-4.6",
                ],
            )

        assert result.exit_code == 0
        assert "✓" in result.output
        assert "Report handoff recorded" in result.output
        mock_service.record_report.assert_called_once_with(
            "docs/reports/test-report.md",
            "claude/sonnet-4.6",
            branch="task/issue-473",
        )


# Standalone tests for handoff next command
def test_handoff_next_sets_next_step_for_numeric_branch() -> None:
    service = MagicMock()

    # Mock store with flow binding
    mock_store = MagicMock()
    mock_store.get_flows_by_issue.return_value = [
        {"branch": "task/issue-235", "flow_status": "active"}
    ]
    service.store = mock_store

    # Mock FlowService in both locations (handoff_write uses resolve_branch_arg)
    mock_flow_service = MagicMock()
    mock_flow_service.store = mock_store

    with (
        patch("vibe3.commands.handoff_write.HandoffService", return_value=service),
        patch("vibe3.services.FlowService", return_value=mock_flow_service),
    ):
        result = runner.invoke(
            app,
            [
                "handoff",
                "next",
                "Finalize PR",
                "--branch",
                "235",
                "--actor",
                "test-actor",
            ],
        )

    assert result.exit_code == 0
    service.record_next_step.assert_called_once_with(
        "task/issue-235",
        "Finalize PR",
        "test-actor",
    )


def test_handoff_next_rejects_nonexistent_flow() -> None:
    """Should fail-fast if no flow state exists for the resolved branch."""
    service = MagicMock()

    # Mock store with no flow binding and no unbound candidates
    mock_store = MagicMock()
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = (
        None  # No unbound candidates, no flow state
    )
    service.store = mock_store

    # Mock FlowService in branch_arg (resolver creates its own instance)
    mock_flow_service = MagicMock()
    mock_flow_service.store = mock_store

    with (
        patch("vibe3.commands.handoff_write.HandoffService", return_value=service),
        patch("vibe3.services.FlowService", return_value=mock_flow_service),
    ):
        result = runner.invoke(
            app,
            ["handoff", "next", "message", "--branch", "999"],
        )

    # With canonical_fallback=True, resolver returns "task/issue-999"
    # But command should still fail because there's no flow state
    assert result.exit_code == 1
    assert "没有 flow" in result.output
    # Should NOT call record_next_step when flow state doesn't exist
    service.record_next_step.assert_not_called()


# Integration test - keep at end
def test_handoff_audit_command_real_service_path(tmp_path, monkeypatch):
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
    assert "test-actor" in content

    # Verify side effects in database
    flow_state = real_store.get_flow_state("main")
    assert flow_state is not None
    assert flow_state["audit_ref"] == audit_ref
    assert flow_state["next_step"] is None
