"""Regression: no-op gate stays authoritative for absent role output (FR-012).

Boundary locked by spec 012 US2 — two independent subsystems must not shadow
each other:
- no-op gate (execution/noop_gate.py): runtime output-contract enforcement.
  A planner that omits plan_ref hits this gate via EVENT_REQUIRED_REF_MISSING,
  regardless of worktree health.
- artifact blocker (services/flow/consistency.py MISSING_ARTIFACT): a
  previously-recorded artifact file that later disappeared (file-system loss).

They inspect different signals: the gate checks whether the flow_state ref
FIELD is non-empty; consistency checks whether a non-empty ref VALUE resolves
to an existing file. So an absent plan_ref (empty field) is owned by the
no-op gate and is NEVER reclassified as MISSING_ARTIFACT (empty fields are
skipped by the consistency ref loop). Spec 012 US2, FR-012, SC-002.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.execution.noop_gate import apply_unified_noop_gate
from vibe3.services.flow.consistency import (
    FlowConsistencyCode,
    check_flow_consistency,
)


def _make_mock_store() -> MagicMock:
    store = MagicMock()
    store.get_flow_state.return_value = {}
    store.record_confirmed_transition.return_value = (1, 1, 1)
    return store


def _make_github_issue_payload(state_label: str = "state/plan") -> dict:
    labels = [{"name": state_label}] if state_label else []
    return {"labels": labels, "state": "open"}


def test_planner_missing_plan_ref_blocks_at_noop_gate() -> None:
    """FR-012: a planner that omits plan_ref is blocked by the no-op gate
    with EVENT_REQUIRED_REF_MISSING — the runtime contract stays authoritative
    and is not bypassed by the new artifact-blocker path (spec 012 US2)."""
    store = _make_mock_store()
    with (
        patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
        patch("vibe3.services.issue.failure.block_planner_noop_issue") as mock_block,
    ):
        mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
            "state/in-progress"
        )
        apply_unified_noop_gate(
            store=store,
            issue_number=42,
            branch="task/issue-42",
            actor="agent:plan",
            role="planner",
            before_state_label="state/plan",
            flow_state={},  # plan_ref absent — runtime contract violated
        )

    mock_block.assert_called_once()
    assert "plan_ref" in mock_block.call_args[1]["reason"]
    emitted = [
        c.args[1] if len(c.args) > 1 else c.kwargs.get("event")
        for c in store.add_event.call_args_list
    ]
    assert "required_ref_missing" in emitted


def test_empty_plan_ref_not_classified_as_artifact_blocker() -> None:
    """The MISSING_ARTIFACT classification only fires when a NON-EMPTY ref
    fails to resolve. An absent (empty) plan_ref is skipped by the consistency
    ref loop, so it never becomes an artifact blocker — leaving the no-op gate
    as the sole owner of that signal (FR-012 boundary)."""
    git = MagicMock()
    git.find_worktree_path_for_branch.return_value = Path("/wt/task/issue-42")
    git.branch_exists.return_value = True
    state = {"worktree_path": "/wt/task/issue-42"}  # plan_ref absent

    result = check_flow_consistency("task/issue-42", state, git_client=git)

    assert result.code == FlowConsistencyCode.OK
    assert not result.needs_rebuild
