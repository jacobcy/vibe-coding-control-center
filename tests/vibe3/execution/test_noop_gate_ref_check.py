"""Unit tests for contract-driven ref-check logic in no-op gate."""

import json
from unittest.mock import MagicMock, patch

from vibe3.execution.noop_gate import apply_unified_noop_gate


def _make_mock_store() -> MagicMock:
    """Create a mock SQLiteClient."""
    store = MagicMock()
    store.get_flow_state.return_value = {}
    return store


def _make_github_issue_payload(state_label: str = "state/plan") -> dict:
    """Build a GitHub issue payload dict with given state label."""
    labels = [{"name": state_label}] if state_label else []
    return {"labels": labels, "state": "open"}


class TestRefCheck:
    """Tests for contract-driven output checks in no-op gate.

    Contracts (defined in config/role_policy.py ROLE_OUTPUT_CONTRACTS):
      planner  → required_ref="plan_ref"  (hard: block if missing)
      executor → no required_ref          (state change sufficient)
      reviewer → requires_verdict=True    (audit_ref not required)
      manager  → no requirements          (state change sufficient)
    """

    def test_planner_blocks_when_plan_ref_missing_even_if_state_changed(self) -> None:
        """Planner gate BLOCKS when plan_ref is absent, even if state changed.

        plan_ref is a hard requirement per PLANNER_ROLE output_contract.
        """
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
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
                flow_state={},  # plan_ref missing
            )

        mock_block.assert_called_once()
        assert "required ref missing" in mock_block.call_args[1]["reason"]
        assert "plan_ref" in mock_block.call_args[1]["reason"]
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "required_ref_missing"

    def test_planner_blocks_when_ref_missing_and_state_unchanged(self) -> None:
        """Gate blocks when required ref is missing AND state unchanged."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/plan"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
                flow_state={},  # plan_ref missing
            )

        mock_block.assert_called_once()
        call_kwargs = mock_block.call_args[1]
        assert "required ref missing" in call_kwargs["reason"]
        assert "plan_ref" in call_kwargs["reason"]

    def test_planner_passes_when_plan_ref_present_and_state_changed(self) -> None:
        """Gate passes when plan_ref is present and state changed."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
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
                flow_state={"plan_ref": "docs/plans/plan.md"},
            )

        mock_block.assert_not_called()
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "state_transitioned"

    def test_executor_passes_without_report_ref_when_state_changed(self) -> None:
        """Executor has no required_ref; state change alone passes the gate."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/review"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=99,
                branch="task/issue-99",
                actor="agent:run",
                role="executor",
                before_state_label="state/run",
                flow_state={},  # no report_ref — that is fine for executor
            )

        mock_block.assert_not_called()
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "state_transitioned"

    def test_executor_blocks_when_state_unchanged(self) -> None:
        """Gate blocks executor when state is unchanged (even with report_ref)."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/run"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=55,
                branch="task/issue-55",
                actor="agent:run",
                role="executor",
                before_state_label="state/run",
                flow_state={"report_ref": "path/to/report.md"},
            )

        mock_block.assert_called_once()
        assert "state unchanged" in mock_block.call_args[1]["reason"]

    def test_reviewer_pass_verdict_no_audit_ref_passes(self) -> None:
        """PASS verdict passes gate without audit_ref (audit_ref not required)."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/handoff"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=55,
                branch="task/issue-55",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
                flow_state={
                    "latest_verdict": json.dumps(
                        {
                            "verdict": "PASS",
                            "actor": "reviewer",
                            "role": "reviewer",
                            "timestamp": "2026-05-22T00:00:00+00:00",
                            "flow_branch": "task/issue-55",
                        }
                    )
                },
            )

        mock_block.assert_not_called()
        assert store.add_event.call_args[0][1] == "state_transitioned"

    def test_reviewer_minor_without_audit_ref_passes(self) -> None:
        """MINOR verdict passes gate without audit_ref (audit_ref not required)."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/handoff"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=55,
                branch="task/issue-55",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
                flow_state={
                    "latest_verdict": json.dumps(
                        {
                            "verdict": "MINOR",
                            "actor": "reviewer",
                            "role": "reviewer",
                            "timestamp": "2026-05-22T00:00:00+00:00",
                            "flow_branch": "task/issue-55",
                        }
                    )
                },
            )

        mock_block.assert_not_called()
        assert store.add_event.call_args[0][1] == "state_transitioned"

    def test_reviewer_missing_verdict_blocks_even_if_state_changed(self) -> None:
        """Reviewer must persist a verdict before passing the gate."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/handoff"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=55,
                branch="task/issue-55",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
                flow_state={},
            )

        mock_block.assert_called_once()
        assert "latest verdict missing" in mock_block.call_args[1]["reason"]

    def test_manager_skips_ref_check_state_changed_passes(self) -> None:
        """Manager role has no required outputs; only state change matters."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_manager_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/handoff"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:manager",
                role="manager",
                before_state_label="state/ready",
                flow_state=None,
            )

        mock_block.assert_not_called()
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "state_transitioned"
