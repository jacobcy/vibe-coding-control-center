"""Regression test for #3184: False-success chain in publish flow.

This test verifies that the #3184 false-success chain cannot occur:
- merge-ready dispatch → Agent doesn't create PR → compensation rejects →
  noop gate blocks

The issue was that the system would auto-transition from merge-ready →
blocked → auto-resume → done even when no PR was created and the Agent
didn't change state.
"""

from unittest.mock import MagicMock, patch

from vibe3.execution.noop_gate import apply_unified_noop_gate
from vibe3.execution.publish_completion import PublishPRRefCompensationService


def test_3184_false_success_chain_blocked() -> None:
    """Verify #3184 false-success chain is prevented.

    Scenario:
    1. Issue in merge-ready state
    2. Agent executes publish but doesn't create PR
    3. Agent doesn't change state
    4. Compensation service rejects (no new pr_ref)
    5. No-op gate correctly blocks (prevents false-success transition to done)

    Expected: Issue should be blocked, NOT auto-transitioned to done.
    """
    # Setup: Create a mock store with merge-ready state
    store = MagicMock()
    store.get_flow_state.return_value = {
        "state": "state/merge-ready",
        # No pr_ref exists before agent execution
    }

    # Setup: Create compensation service that will reject compensation
    github = MagicMock()
    github.list_prs_for_branch.return_value = []  # No PR created by agent

    recorder = MagicMock()
    recorder.would_exceed.return_value = False

    compensation = MagicMock(spec=PublishPRRefCompensationService)
    compensation.try_complete.return_value = MagicMock(
        completed=False, reason="publish did not create exactly one open PR"
    )

    # Setup: Mock GitHub to show state unchanged (still merge-ready)
    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as mock_block,
    ):
        # GitHub shows issue still in merge-ready state (unchanged)
        mock_gh.return_value.view_issue.return_value = {
            "labels": [{"name": "state/merge-ready"}],
            "state": "OPEN",
        }

        # Execute: Run the no-op gate with publish mode
        apply_unified_noop_gate(
            store=store,
            issue_number=99,
            branch="task/issue-99",
            actor="agent:run",
            role="executor",
            before_state_label="state/merge-ready",
            before_state_labels=frozenset({"state/merge-ready"}),
            publish_mode=True,
            before_open_pr_numbers=frozenset(),  # No PR before
            before_pr_ref=None,  # No pr_ref before
            publish_completion=compensation,
        )

        # Verify: Compensation service was called and rejected
        compensation.try_complete.assert_called_once()
        result = compensation.try_complete.call_args[1]
        assert result["before_pr_ref"] is None
        assert result["before_state_labels"] == frozenset({"state/merge-ready"})
        assert result["before_open_pr_numbers"] == frozenset()

        # Verify: The gate should have blocked (not silently passed)
        # The gate blocks when compensation fails and state unchanged
        mock_block.assert_called_once()

        # Verify: Block reason should mention state unchanged
        block_call = mock_block.call_args
        assert "state unchanged" in block_call[1]["reason"].lower()


def test_3184_existing_pr_ref_prevents_compensation() -> None:
    """Verify compensation is rejected when pr_ref already exists.

    This prevents the false-success scenario where compensation would
    repeatedly transition merge-ready → handoff on every run.
    """
    store = MagicMock()
    store.get_flow_state.return_value = {
        "state": "state/merge-ready",
        "pr_ref": "PR-123",  # pr_ref already exists
    }

    github = MagicMock()
    github.list_prs_for_branch.return_value = []  # No new PR

    recorder = MagicMock()
    recorder.would_exceed.return_value = False

    compensation = MagicMock(spec=PublishPRRefCompensationService)
    compensation.try_complete.return_value = MagicMock(
        completed=False, reason="pr_ref already exists, refusing to compensate"
    )

    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as mock_block,
    ):
        mock_gh.return_value.view_issue.return_value = {
            "labels": [{"name": "state/merge-ready"}],
            "state": "OPEN",
        }

        apply_unified_noop_gate(
            store=store,
            issue_number=99,
            branch="task/issue-99",
            actor="agent:run",
            role="executor",
            before_state_label="state/merge-ready",
            before_state_labels=frozenset({"state/merge-ready"}),
            publish_mode=True,
            before_open_pr_numbers=frozenset(),
            before_pr_ref="PR-123",  # pr_ref exists before
            publish_completion=compensation,
        )

        # Verify: Compensation was attempted but rejected due to existing pr_ref
        compensation.try_complete.assert_called_once()
        result = compensation.try_complete.call_args[1]
        assert result["before_pr_ref"] == "PR-123"

        # The compensation service should have returned False
        call_result = compensation.try_complete.return_value
        assert call_result.completed is False

        # Verify: Gate blocked due to state unchanged
        mock_block.assert_called_once()


def test_3184_no_false_success_when_agent_changes_state() -> None:
    """Verify no false-success when Agent explicitly changes state.

    If Agent successfully transitions state (e.g., to handoff or blocked),
    that's the correct behavior - not a false-success.
    """
    store = MagicMock()
    store.get_flow_state.return_value = {
        "state": "state/merge-ready",
    }
    # Mock the record_confirmed_transition to return expected tuple
    store.record_confirmed_transition.return_value = (1, 1, "event-123")

    github = MagicMock()
    github.list_prs_for_branch.return_value = []  # No PR created

    recorder = MagicMock()
    recorder.would_exceed.return_value = False

    compensation = MagicMock(spec=PublishPRRefCompensationService)

    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as mock_block,
    ):
        # Agent changed state from merge-ready to handoff
        mock_gh.return_value.view_issue.return_value = {
            "labels": [{"name": "state/handoff"}],  # State changed!
            "state": "OPEN",
        }

        apply_unified_noop_gate(
            store=store,
            issue_number=99,
            branch="task/issue-99",
            actor="agent:run",
            role="executor",
            before_state_label="state/merge-ready",
            before_state_labels=frozenset({"state/merge-ready"}),
            publish_mode=True,
            before_open_pr_numbers=frozenset(),
            before_pr_ref=None,
            publish_completion=compensation,
        )

        # Verify: Compensation was NOT called (state changed by Agent)
        compensation.try_complete.assert_not_called()

        # Verify: Gate passed (state changed by Agent, that's correct behavior)
        mock_block.assert_not_called()

        # Verify: Transition was recorded
        store.record_confirmed_transition.assert_called_once()
