"""Complete state-label set regressions for the unified noop gate."""

from unittest.mock import MagicMock, patch

from vibe3.execution.noop_gate import apply_unified_noop_gate


def test_added_state_label_passes_when_stale_label_remains() -> None:
    store = MagicMock()
    store.get_flow_state.return_value = {}
    store.record_confirmed_transition.return_value = (1, 1, 1)

    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_github,
        patch("vibe3.services.issue.failure.block_executor_noop_issue") as mock_block,
    ):
        mock_github.return_value.view_issue.return_value = {
            "labels": [
                {"name": "state/in-progress"},
                {"name": "state/handoff"},
            ],
            "state": "open",
        }
        apply_unified_noop_gate(
            store=store,
            issue_number=42,
            branch="task/issue-42",
            actor="agent:run",
            role="executor",
            before_state_label="state/in-progress",
            before_state_labels=frozenset({"state/in-progress"}),
        )

    mock_block.assert_not_called()
    record_kwargs = store.record_confirmed_transition.call_args.kwargs
    assert record_kwargs["to_state"] == "state/handoff"
