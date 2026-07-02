"""Pair-loop behavior at the no-op integration boundary."""

from unittest.mock import MagicMock, patch

from vibe3.execution.noop_gate import apply_unified_noop_gate


def test_third_existing_pair_allows_one_observed_transition() -> None:
    store = MagicMock()
    store.record_confirmed_transition.return_value = (3, 3, 1)

    with (
        patch("vibe3.clients.github_client.GitHubClient") as github_cls,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as block,
    ):
        github_cls.return_value.view_issue.return_value = {
            "labels": [{"name": "state/in-progress"}],
            "state": "open",
        }
        apply_unified_noop_gate(
            store=store,
            issue_number=1034,
            branch="task/issue-1034",
            actor="agent:executor",
            role="executor",
            before_state_label="state/handoff",
        )

    block.assert_not_called()


def test_fourth_observed_pair_is_recorded_then_blocks() -> None:
    store = MagicMock()
    store.record_confirmed_transition.return_value = (4, 4, 1)

    with (
        patch("vibe3.clients.github_client.GitHubClient") as github_cls,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as block,
    ):
        github_cls.return_value.view_issue.return_value = {
            "labels": [{"name": "state/in-progress"}],
            "state": "open",
        }
        apply_unified_noop_gate(
            store=store,
            issue_number=1034,
            branch="task/issue-1034",
            actor="agent:executor",
            role="executor",
            before_state_label="state/handoff",
        )

    store.record_confirmed_transition.assert_called_once()
    block.assert_called_once()
