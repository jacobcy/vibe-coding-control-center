"""Integration tests for Handoff commands - All CLI operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.handoff_render import _to_handoff_cmd
from vibe3.models.flow import FlowState

runner = CliRunner()


class TestHandoffBasicCommands:
    """Tests for basic handoff CLI commands."""

    @pytest.mark.parametrize("force,expected_force", [(False, False), (True, True)])
    @patch("vibe3.commands.handoff_write.HandoffService")
    @patch("vibe3.utils.branch_arg.GitClient")
    def test_handoff_init_command(
        self, mock_git_class, mock_service_class, force, expected_force
    ):
        """Test handoff init command."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/test-branch"
        mock_git_class.return_value = mock_git

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
            force=expected_force, branch="task/test-branch"
        )

    @patch("vibe3.commands.handoff_read.HandoffStatusService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_command(
        self, mock_flow_service_class, mock_status_service_class
    ):
        """Test handoff status command shows agent chain and events."""
        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "feature/test"
        mock_flow_service_class.return_value = mock_flow_service

        mock_status_service = MagicMock()
        mock_status_result = MagicMock()
        mock_status_result.flow_slug = "feature-test"
        mock_status_result.worktree_root = "/path/to/worktree"
        mock_status_result.state = FlowState(
            branch="feature/test",
            flow_slug="feature-test",
            flow_status="active",
        )
        mock_status_result.events = []
        mock_status_result.latest_verdict = None
        mock_status_result.live_sessions = []
        mock_status_service.get_handoff_status.return_value = mock_status_result
        mock_status_service_class.return_value = mock_status_service

        result = runner.invoke(app, ["handoff", "status"])

        assert result.exit_code == 0
        assert "Handoff" in result.output
        # get_current_branch is called twice: once in resolve_command_branch fallback,
        # and once for conditional --branch hint logic
        assert mock_flow_service.get_current_branch.call_count == 2
        mock_status_service.get_handoff_status.assert_called_once()

    @patch("vibe3.commands.handoff_read.HandoffStatusService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_numeric_issue_resolves_branch(
        self, mock_flow_service_class, mock_status_service_class
    ):
        """handoff status 436 should resolve to task/dev issue branch."""
        mock_flow_service = MagicMock()

        # Mock store with flow binding
        mock_store = MagicMock()
        mock_store.get_flows_by_issue.return_value = [
            {"branch": "task/issue-436", "flow_status": "active"}
        ]
        mock_flow_service.store = mock_store

        mock_flow_service.get_flow_state.side_effect = lambda branch: (
            FlowState(branch=branch, flow_slug="issue-436", flow_status="active")
            if branch == "task/issue-436"
            else None
        )
        mock_flow_service_class.return_value = mock_flow_service

        mock_status_service = MagicMock()
        mock_status_result = MagicMock()
        mock_status_result.flow_slug = "issue-436"
        mock_status_result.worktree_root = "/path/to/worktree"
        mock_status_result.state = FlowState(
            branch="task/issue-436",
            flow_slug="issue-436",
            flow_status="active",
        )
        mock_status_result.events = []
        mock_status_result.latest_verdict = None
        mock_status_result.live_sessions = []
        mock_status_result.recent_updates = []
        mock_status_service.get_handoff_status.return_value = mock_status_result
        mock_status_service_class.return_value = mock_status_service

        result = runner.invoke(app, ["handoff", "status", "436"])

        assert result.exit_code == 0
        mock_status_service.get_handoff_status.assert_called_once_with(
            "task/issue-436", limit=2
        )

    def test_handoff_show_without_target_shows_help(self):
        """Test handoff show without target displays help message."""
        result = runner.invoke(app, ["handoff", "show"])

        assert result.exit_code == 0
        assert "Usage: vibe3 handoff show <target>" in result.output
        assert "@key" in result.output
        assert "relative/path" in result.output
        assert "/abs/path" in result.output
        assert "Examples:" in result.output

    @patch("vibe3.commands.handoff_read.render_handoff_detail")
    def test_handoff_show_artifact(self, mock_render_detail):
        """Test handoff show <artifact> renders single artifact."""
        with runner.isolated_filesystem():
            artifact = Path("artifact.md")
            artifact.write_text("# artifact", encoding="utf-8")

            result = runner.invoke(app, ["handoff", "show", str(artifact)])

        assert result.exit_code == 0
        mock_render_detail.assert_called_once()

    @patch("vibe3.commands.handoff_read.render_handoff_detail")
    @patch("vibe3.commands.handoff_read.GitClient")
    def test_handoff_show_shared_artifact_at_prefix(
        self, mock_git_client_class, mock_render_detail, tmp_path
    ):
        """Test handoff show @key resolves shared artifact via @ prefix."""
        artifact = (
            tmp_path
            / "vibe3"
            / "handoff"
            / "task-issue-340-d347bc95"
            / "run-2026-04-21T05:19:28.md"
        )
        artifact.parent.mkdir(parents=True)
        artifact.write_text("# artifact", encoding="utf-8")

        mock_git = MagicMock()
        mock_git.get_git_common_dir.return_value = str(tmp_path)
        mock_git.get_worktree_root.return_value = str(tmp_path)
        mock_git.find_worktree_path_for_branch.return_value = None
        mock_git_client_class.return_value = mock_git

        result = runner.invoke(
            app,
            [
                "handoff",
                "show",
                "@task-issue-340-d347bc95/run-2026-04-21T05:19:28.md",
            ],
        )

        assert result.exit_code == 0
        mock_render_detail.assert_called_once()

    @patch("vibe3.commands.handoff_read.render_handoff_detail")
    @patch("vibe3.commands.handoff_read.FlowService")
    @patch("vibe3.commands.handoff_read.GitClient")
    def test_handoff_show_branch_numeric_id_resolves(
        self, mock_git_cls, mock_flow_cls, mock_render_detail, tmp_path
    ):
        """Test handoff show --branch <id> resolves numeric ID."""
        branch_wt = tmp_path / "wt-branch"
        ref_file = branch_wt / "docs" / "report.md"
        ref_file.parent.mkdir(parents=True)
        ref_file.write_text("content")

        mock_flow = MagicMock()

        # Mock store with flow binding
        mock_store = MagicMock()
        mock_store.get_flows_by_issue.return_value = [
            {"branch": "task/issue-304", "flow_status": "active"}
        ]
        mock_flow.store = mock_store

        mock_flow.get_flow_state.side_effect = lambda b: (
            {"branch": b} if b == "task/issue-304" else None
        )
        mock_flow_cls.return_value = mock_flow

        mock_git = MagicMock()
        mock_git.get_git_common_dir.return_value = str(tmp_path / ".git")
        mock_git.get_worktree_root.return_value = str(tmp_path / "wt-main")
        mock_git.find_worktree_path_for_branch.return_value = branch_wt
        mock_git_cls.return_value = mock_git

        result = runner.invoke(
            app,
            ["handoff", "show", "--branch", "304", "docs/report.md"],
        )

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

    @patch("vibe3.commands.handoff_read.HandoffStatusService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_format_json(
        self, mock_flow_service_class, mock_handoff_status_service_class
    ):
        """Test handoff status --format json outputs JSON."""
        from vibe3.services.handoff_status_service import HandoffStatusResult

        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "feature/test"
        mock_flow_service_class.return_value = mock_flow_service

        mock_status_service = MagicMock()
        mock_status_result = HandoffStatusResult(
            flow_slug="feature-test",
            worktree_root=None,
            state=FlowState(
                branch="feature/test",
                flow_slug="feature-test",
                flow_status="active",
            ),
            events=[],
            latest_verdict=None,
            live_sessions=[],
            recent_updates=[],
        )
        mock_status_service.get_handoff_status.return_value = mock_status_result
        mock_handoff_status_service_class.return_value = mock_status_service

        result = runner.invoke(app, ["handoff", "status", "--format", "json"])

        assert result.exit_code == 0
        import json

        output = json.loads(result.output)
        assert "state" in output
        assert "events" in output
        assert output["state"]["branch"] == "feature/test"

    @patch("vibe3.commands.handoff_read.HandoffStatusService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_format_yaml(
        self, mock_flow_service_class, mock_handoff_status_service_class
    ):
        """Test handoff status --format yaml outputs YAML."""
        from vibe3.services.handoff_status_service import HandoffStatusResult

        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "feature/test"
        mock_flow_service_class.return_value = mock_flow_service

        mock_status_service = MagicMock()
        mock_status_result = HandoffStatusResult(
            flow_slug="feature-test",
            worktree_root=None,
            state=FlowState(
                branch="feature/test",
                flow_slug="feature-test",
                flow_status="active",
            ),
            events=[],
            latest_verdict=None,
            live_sessions=[],
            recent_updates=[],
        )
        mock_status_service.get_handoff_status.return_value = mock_status_result
        mock_handoff_status_service_class.return_value = mock_status_service

        result = runner.invoke(app, ["handoff", "status", "--format", "yaml"])

        assert result.exit_code == 0
        assert "state:" in result.output
        assert "events:" in result.output
        assert "branch: feature/test" in result.output

    @patch("vibe3.commands.handoff_read.HandoffStatusService")
    @patch("vibe3.commands.handoff_read.FlowService")
    def test_handoff_status_deprecated_json_flag(
        self, mock_flow_service_class, mock_handoff_status_service_class
    ):
        """Test handoff status --json shows deprecation warning."""
        from vibe3.services.handoff_status_service import HandoffStatusResult

        mock_flow_service = MagicMock()
        mock_flow_service.get_current_branch.return_value = "feature/test"
        mock_flow_service_class.return_value = mock_flow_service

        mock_status_service = MagicMock()
        mock_status_result = HandoffStatusResult(
            flow_slug="feature-test",
            worktree_root=None,
            state=FlowState(
                branch="feature/test",
                flow_slug="feature-test",
                flow_status="active",
            ),
            events=[],
            latest_verdict=None,
            live_sessions=[],
            recent_updates=[],
        )
        mock_status_service.get_handoff_status.return_value = mock_status_result
        mock_handoff_status_service_class.return_value = mock_status_service

        result = runner.invoke(app, ["handoff", "status", "--json"])

        assert result.exit_code == 0
        assert "deprecated" in result.stderr.lower()
        import json

        # Output should still be valid JSON
        output = json.loads(result.stdout)
        assert "state" in output


class TestHandoffAdvancedCommands:
    """Tests for advanced handoff CLI commands."""

    def test_to_handoff_cmd_wraps_relative_refs(self):
        # Canonical refs get alias substitution
        assert _to_handoff_cmd("docs/plans/test-plan.md") == "vibe3 handoff show @plan"
        # Shared artifacts get @ prefix
        assert (
            _to_handoff_cmd("vibe3/handoff/task-123/current.md")
            == "vibe3 handoff show @task-123/current.md"
        )
        # Canonical ref with branch uses --branch flag and alias
        assert (
            _to_handoff_cmd("docs/plans/test-plan.md", branch="task/issue-123")
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
    @patch("vibe3.utils.branch_arg.GitClient")
    def test_handoff_append_command(self, mock_git_class, mock_service_class):
        """Test handoff append command."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/test-branch"
        mock_git_class.return_value = mock_git

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
    @patch("vibe3.utils.branch_arg.GitClient")
    def test_handoff_plan_command(self, mock_git_class, mock_service_class):
        """Test handoff plan command."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/test-branch"
        mock_git_class.return_value = mock_git

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
    @patch("vibe3.utils.branch_arg.GitClient")
    def test_handoff_report_command(self, mock_git_class, mock_service_class):
        """Test handoff report command."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/test-branch"
        mock_git_class.return_value = mock_git

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
    @patch("vibe3.utils.branch_arg.GitClient")
    def test_handoff_audit_command(self, mock_git_class, mock_service_class):
        """Test handoff audit command."""
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/test-branch"
        mock_git_class.return_value = mock_git

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

        with patch(
            "vibe3.utils.branch_arg.FlowService", return_value=mock_flow_service
        ):
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
        patch("vibe3.utils.branch_arg.FlowService", return_value=mock_flow_service),
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
    """Should fail-fast with UserError if no flow found."""
    service = MagicMock()

    # Mock store with no flow binding and no unbound candidates
    mock_store = MagicMock()
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = None  # No unbound candidates either
    service.store = mock_store

    # Mock FlowService in branch_arg (resolver creates its own instance)
    mock_flow_service = MagicMock()
    mock_flow_service.store = mock_store

    with (
        patch("vibe3.commands.handoff_write.HandoffService", return_value=service),
        patch("vibe3.utils.branch_arg.FlowService", return_value=mock_flow_service),
    ):
        result = runner.invoke(
            app,
            ["handoff", "next", "message", "--branch", "999"],
        )

    assert result.exit_code == 1
    # UserError should be captured in the exception attribute
    assert result.exception is not None
    assert "No flow found for issue #999" in str(result.exception)
    # Should NOT call record_next_step when flow doesn't exist
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
