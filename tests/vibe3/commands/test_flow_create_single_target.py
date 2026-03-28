"""Tests for flow create single-target governance."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import CreateDecision, FlowState

runner = CliRunner()


class TestFlowCreateSingleTarget:
    """Tests for flow create single-target governance."""

    @patch("vibe3.commands.flow.HandoffService")
    @patch("vibe3.commands.flow.FlowService")
    def test_flow_create_rejects_when_current_flow_is_active(
        self, mock_service_class, mock_handoff_class
    ):
        """Active flow should reject create in same worktree."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "task/active-flow"
        mock_service.can_create_from_current_worktree.return_value = CreateDecision(
            allowed=False,
            reason="Current flow is active - cannot create new flow",
            requires_new_worktree=True,
            guidance="Use 'vibe3 wtnew <name>' to create a new worktree",
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "create", "new-feature"])

        assert result.exit_code == 1
        assert (
            "wtnew" in result.output.lower() or "new worktree" in result.output.lower()
        )
        mock_service.create_flow_with_branch.assert_not_called()

    @patch("vibe3.commands.flow.HandoffService")
    @patch("vibe3.commands.flow.FlowService")
    def test_flow_create_defaults_to_current_branch_when_blocked(
        self, mock_service_class, mock_handoff_class
    ):
        """Blocked flow should allow create from current branch."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "task/blocked-flow"
        mock_service.can_create_from_current_worktree.return_value = CreateDecision(
            allowed=True,
            reason="Current flow is blocked - spawn downstream",
            start_ref="task/blocked-flow",
            allow_base_current=True,
            requires_new_worktree=False,
        )
        mock_service.create_flow_with_branch.return_value = FlowState(
            branch="task/new-feature",
            flow_slug="new-feature",
            flow_status="active",
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "create", "new-feature"])

        assert result.exit_code == 0
        mock_service.create_flow_with_branch.assert_called_once_with(
            slug="new-feature",
            start_ref="task/blocked-flow",
            actor=None,
        )

    @patch("vibe3.commands.flow.HandoffService")
    @patch("vibe3.commands.flow.FlowService")
    def test_flow_create_allows_base_current_when_flow_is_blocked(
        self, mock_service_class, mock_handoff_class
    ):
        """Blocked flow should explicitly allow --base current."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "task/blocked-flow"
        mock_service.can_create_from_current_worktree.return_value = CreateDecision(
            allowed=True,
            reason="Current flow is blocked - spawn downstream",
            start_ref="task/blocked-flow",
            allow_base_current=True,
            requires_new_worktree=False,
        )
        mock_service.create_flow_with_branch.return_value = FlowState(
            branch="task/new-feature",
            flow_slug="new-feature",
            flow_status="active",
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app, ["flow", "create", "new-feature", "--base", "current"]
        )

        assert result.exit_code == 0
        mock_service.create_flow_with_branch.assert_called_once_with(
            slug="new-feature",
            start_ref="task/blocked-flow",
            actor=None,
        )

    @patch("vibe3.commands.flow.HandoffService")
    @patch("vibe3.commands.flow.FlowService")
    def test_flow_create_guides_wtnew_for_new_feature(
        self, mock_service_class, mock_handoff_class
    ):
        """When no flow exists but user wants independent feature, guide to wtnew."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "main"
        mock_service.can_create_from_current_worktree.return_value = CreateDecision(
            allowed=True,
            reason="No active flow in current worktree",
            start_ref="origin/main",
            allow_base_current=False,
            requires_new_worktree=False,
        )
        mock_service.create_flow_with_branch.return_value = FlowState(
            branch="task/new-feature",
            flow_slug="new-feature",
            flow_status="active",
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "create", "new-feature"])

        assert result.exit_code == 0
        mock_service.create_flow_with_branch.assert_called_once_with(
            slug="new-feature",
            start_ref="origin/main",
            actor=None,
        )

    @patch("vibe3.commands.flow.HandoffService")
    @patch("vibe3.commands.flow.FlowService")
    def test_flow_create_done_flow_uses_origin_main(
        self, mock_service_class, mock_handoff_class
    ):
        """Done flow should start new flow from origin/main."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "task/done-flow"
        mock_service.can_create_from_current_worktree.return_value = CreateDecision(
            allowed=True,
            reason="Current flow is done - safe to start new target",
            start_ref="origin/main",
            allow_base_current=False,
            requires_new_worktree=False,
        )
        mock_service.create_flow_with_branch.return_value = FlowState(
            branch="task/new-feature",
            flow_slug="new-feature",
            flow_status="active",
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(app, ["flow", "create", "new-feature"])

        assert result.exit_code == 0
        mock_service.create_flow_with_branch.assert_called_once_with(
            slug="new-feature",
            start_ref="origin/main",
            actor=None,
        )

    @patch("vibe3.commands.flow.HandoffService")
    @patch("vibe3.commands.flow.FlowService")
    def test_flow_create_rejects_base_current_when_flow_not_blocked(
        self, mock_service_class, mock_handoff_class
    ):
        """--base current should be rejected unless current flow is blocked."""
        mock_service = MagicMock()
        mock_service.get_current_branch.return_value = "task/done-flow"
        mock_service.can_create_from_current_worktree.return_value = CreateDecision(
            allowed=True,
            reason="Current flow is done - safe to start new target",
            start_ref="origin/main",
            allow_base_current=False,
            requires_new_worktree=False,
        )
        mock_service_class.return_value = mock_service

        result = runner.invoke(
            app, ["flow", "create", "new-feature", "--base", "current"]
        )

        assert result.exit_code == 1
        assert "only allowed when current flow is blocked" in result.output
        mock_service.create_flow_with_branch.assert_not_called()
