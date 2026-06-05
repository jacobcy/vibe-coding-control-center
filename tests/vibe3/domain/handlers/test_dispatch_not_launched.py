"""Tests for dispatch not launched scenario.

Verifies that when coordinator does not launch, handler logs warning without error.
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events import PlannerDispatchIntent
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest


def _make_mock_request(
    role: str,
    issue_number: int,
    **overrides: object,
) -> ExecutionRequest:
    """Create a minimal ExecutionRequest for testing."""
    defaults = {
        "role": role,
        "target_branch": f"task/issue-{issue_number}",
        "target_id": issue_number,
        "execution_name": f"vibe3-{role}-issue-{issue_number}",
        "repo_path": "/tmp/repo",
    }
    defaults.update(overrides)
    return ExecutionRequest(**defaults)  # type: ignore[arg-type]


class TestDispatchNotLaunched:
    """When coordinator does not launch, handler should log warning without error."""

    @patch("vibe3.roles.plan.build_plan_request")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.dispatch.get_store")
    @patch("vibe3.domain.handlers.dispatch.load_issue_info")
    @patch("vibe3.domain.handlers.dispatch.load_orchestra_config")
    def test_dispatch_not_launched_logs_warning(
        self,
        mock_config_cls: MagicMock,
        mock_load_issue: MagicMock,
        mock_get_store: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.dispatch import handle_planner_dispatch_intent

        config = MagicMock(dry_run=False, repo="owner/repo")
        mock_config_cls.return_value = config

        mock_issue = MagicMock(number=42, title="Test issue")
        mock_load_issue.return_value = mock_issue

        # Mock get_store
        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = None
        mock_get_store.return_value.__enter__ = MagicMock(return_value=mock_store)
        mock_get_store.return_value.__exit__ = MagicMock(return_value=None)

        mock_build_request.return_value = _make_mock_request("planner", 42)

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False,
            reason="capacity exceeded",
            reason_code="capacity",
        )
        mock_coordinator_cls.return_value = mock_coordinator

        # Should not raise
        handle_planner_dispatch_intent(
            PlannerDispatchIntent(
                issue_number=42,
                branch="task/issue-42",
                trigger_state="claimed",
            )
        )

        mock_coordinator.dispatch_execution.assert_called_once()
