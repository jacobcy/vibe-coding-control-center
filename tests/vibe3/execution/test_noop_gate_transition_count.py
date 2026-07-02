"""No-op integration tests for confirmed transition accounting."""

from unittest.mock import MagicMock, patch

from vibe3.execution.noop_gate import apply_unified_noop_gate


def _payload(label: str) -> dict:
    return {"labels": [{"name": label}], "state": "open"}


def _store(total: int, pair: int) -> MagicMock:
    store = MagicMock()
    store.record_confirmed_transition.return_value = (total, pair, 1)
    return store


def test_confirmed_state_change_uses_persisted_total() -> None:
    store = _store(total=4, pair=1)
    flow_state = {"transition_count": 3}

    with (
        patch("vibe3.clients.github_client.GitHubClient") as github_cls,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as block,
    ):
        github_cls.return_value.view_issue.return_value = _payload("state/review")
        apply_unified_noop_gate(
            store=store,
            issue_number=42,
            branch="task/issue-42",
            actor="agent:executor",
            role="executor",
            before_state_label="state/in-progress",
            flow_state=flow_state,
        )

    assert flow_state["transition_count"] == 4
    store.record_confirmed_transition.assert_called_once()
    block.assert_not_called()


def test_observed_transition_is_recorded_before_total_limit_blocks() -> None:
    store = _store(total=20, pair=1)
    flow_state = {"transition_count": 19}

    with (
        patch("vibe3.clients.github_client.GitHubClient") as github_cls,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as block,
    ):
        github_cls.return_value.view_issue.return_value = _payload("state/review")
        apply_unified_noop_gate(
            store=store,
            issue_number=42,
            branch="task/issue-42",
            actor="agent:executor",
            role="executor",
            before_state_label="state/in-progress",
            flow_state=flow_state,
        )

    store.record_confirmed_transition.assert_called_once()
    block.assert_called_once()
    assert "total=20" in block.call_args.kwargs["reason"]


def test_observed_transition_is_recorded_before_pair_limit_blocks() -> None:
    store = _store(total=4, pair=4)

    with (
        patch("vibe3.clients.github_client.GitHubClient") as github_cls,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as block,
    ):
        github_cls.return_value.view_issue.return_value = _payload("state/review")
        apply_unified_noop_gate(
            store=store,
            issue_number=42,
            branch="task/issue-42",
            actor="agent:executor",
            role="executor",
            before_state_label="state/in-progress",
        )

    store.record_confirmed_transition.assert_called_once()
    block.assert_called_once()
    assert "pair=4" in block.call_args.kwargs["reason"]


def test_unchanged_state_does_not_record_transition() -> None:
    store = _store(total=1, pair=1)

    with (
        patch("vibe3.clients.github_client.GitHubClient") as github_cls,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as block,
    ):
        github_cls.return_value.view_issue.return_value = _payload("state/in-progress")
        apply_unified_noop_gate(
            store=store,
            issue_number=42,
            branch="task/issue-42",
            actor="agent:executor",
            role="executor",
            before_state_label="state/in-progress",
        )

    store.record_confirmed_transition.assert_not_called()
    block.assert_called_once()
