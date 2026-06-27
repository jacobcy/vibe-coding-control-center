"""State-sensitive dispatch health check scenarios.

Tests for terminal states, aborted flow recovery, missing flow context,
and entry-state edge cases.
"""

import pytest

from tests.vibe3.orchestra.helpers.dispatch_health import (
    make_check_result,
    make_health_coordinator,
    make_issue,
)
from vibe3.models.orchestration import IssueState


class TestPreDispatchHealthStates:
    """State-sensitive health check scenarios."""

    def test_health_check_skips_block_for_terminal_states(self) -> None:
        """When flow is in terminal state (done/stale/review),
        health check should skip dispatch without calling block_flow.

        Note: "aborted" is NOT treated as terminal here - it returns True
        to allow flow_manager.create_flow_for_issue() to handle recovery
        (rebuild if branch missing). See flow_manager.py lines 221-232.
        """
        coord, mocks = make_health_coordinator(
            store_flow_state={"branch": "task/issue-1629", "flow_status": "done"},
            check_result=make_check_result(
                is_valid=False,
                issues=["Task issue #1629 is CLOSED (no open PR found)"],
                branch="task/issue-1629",
            ),
        )

        issue = make_issue(1629, state=IssueState.DONE, github_state="CLOSED")
        result = coord._check_dispatch_health(issue)

        assert result is False, "Health check should return False for terminal states"
        mocks["flow_blocker"].block_flow.assert_not_called()

    def test_health_check_allows_aborted_for_recovery(self) -> None:
        """Aborted flow returns True to let flow_manager handle recovery.

        flow_manager.create_flow_for_issue() has logic at lines 221-232
        to rebuild the flow if the branch is missing.
        """
        coord, _ = make_health_coordinator(
            store_flow_state={"branch": "task/issue-2871", "flow_status": "aborted"},
        )

        issue = make_issue(
            2871,
            state=IssueState.READY,
            labels=["state/ready", "orchestra-governed"],
        )
        result = coord._check_dispatch_health(issue)

        assert result is True, "Aborted should return True for flow_manager recovery"

    @pytest.mark.parametrize("flow_status", ["review", "failed"])
    def test_health_check_rejects_pr_terminal_states(
        self,
        flow_status: str,
    ) -> None:
        """PR-backed terminal flows must not emit new dispatch work."""
        coord, mocks = make_health_coordinator(
            store_flow_state={
                "branch": "task/issue-3189",
                "flow_status": flow_status,
            },
        )

        issue = make_issue(
            3189,
            state=IssueState.READY,
            labels=["state/ready", "orchestra-governed"],
        )

        assert coord._check_dispatch_health(issue) is False
        mocks["flow_blocker"].block_flow.assert_not_called()

    def test_health_check_rejects_missing_flow_context(self) -> None:
        """Empty branch + non-entry state should skip dispatch."""
        coord, _ = make_health_coordinator(flow_context_branch="")

        issue = make_issue(995, state=IssueState.IN_PROGRESS)
        result = coord._check_dispatch_health(issue)

        assert result is False, "Should return False for missing flow context"

    def test_health_check_passes_with_empty_branch_and_entry_state(self) -> None:
        """Empty branch + entry state (READY) should pass."""
        coord, _ = make_health_coordinator(flow_context_branch="")

        issue = make_issue(996, state=IssueState.READY)
        result = coord._check_dispatch_health(issue)

        assert result is True, "Should pass for READY state even without branch"
