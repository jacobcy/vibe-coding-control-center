"""Unit tests for ref-check logic in no-op gate."""

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
    """Tests for required_ref_key logic in no-op gate."""

    def test_passes_when_state_changed_but_ref_missing(self) -> None:
        """Gate passes with warning when state changed but required ref is missing."""
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
                required_ref_key="plan_ref",
                flow_state={},  # plan_ref missing
            )

        mock_block.assert_not_called()
        # Should have two events: ref_missing warning and state_transitioned
        assert store.add_event.call_count == 2
        event_calls = [call[0][1] for call in store.add_event.call_args_list]
        assert "required_ref_missing" in event_calls
        assert "state_transitioned" in event_calls

    def test_blocks_when_ref_missing_and_state_unchanged(self) -> None:
        """Gate blocks when required ref is missing AND state unchanged."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            # State unchanged: before and after are the same
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
                required_ref_key="plan_ref",
                flow_state={},  # plan_ref missing
            )

        mock_block.assert_called_once()
        call_kwargs = mock_block.call_args[1]
        assert "required ref missing" in call_kwargs["reason"]
        assert "plan_ref" in call_kwargs["reason"]
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "required_ref_missing"

    def test_passes_when_ref_present_and_state_changed(self) -> None:
        """Gate passes when ref is present and state changed."""
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
                required_ref_key="report_ref",
                flow_state={"report_ref": "path/to/report.md"},
            )

        mock_block.assert_not_called()
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"

    def test_blocks_when_ref_present_but_state_unchanged(self) -> None:
        """Gate blocks when ref is present but state unchanged."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/review"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=55,
                branch="task/issue-55",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
                required_ref_key="audit_ref",
                flow_state={
                    "audit_ref": "path/to/audit.md",
                    "latest_verdict": json.dumps(
                        {
                            "verdict": "PASS",
                            "actor": "reviewer",
                            "role": "reviewer",
                            "timestamp": "2026-05-22T00:00:00+00:00",
                            "flow_branch": "task/issue-55",
                        }
                    ),
                },
            )

        mock_block.assert_called_once()
        call_kwargs = mock_block.call_args[1]
        assert "state unchanged" in call_kwargs["reason"]
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_unchanged"

    def test_reviewer_pass_without_audit_ref_is_allowed(self) -> None:
        """PASS verdict should not require audit_ref."""
        store = _make_mock_store()
        store.get_flow_state.return_value = {
            "latest_verdict": json.dumps(
                {
                    "verdict": "PASS",
                    "actor": "reviewer",
                    "role": "reviewer",
                    "timestamp": "2026-05-22T00:00:00+00:00",
                    "flow_branch": "task/issue-55",
                }
            )
        }

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            latest_verdict = store.get_flow_state.return_value["latest_verdict"]
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
                required_ref_key="audit_ref",
                flow_state={"latest_verdict": latest_verdict},
            )

        mock_block.assert_not_called()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"

    def test_reviewer_minor_without_audit_ref_blocks(self) -> None:
        """MINOR verdict still requires audit_ref."""
        store = _make_mock_store()
        store.get_flow_state.return_value = {
            "latest_verdict": json.dumps(
                {
                    "verdict": "MINOR",
                    "actor": "reviewer",
                    "role": "reviewer",
                    "timestamp": "2026-05-22T00:00:00+00:00",
                    "flow_branch": "task/issue-55",
                }
            )
        }

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            latest_verdict = store.get_flow_state.return_value["latest_verdict"]
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
                required_ref_key="audit_ref",
                flow_state={"latest_verdict": latest_verdict},
            )

        mock_block.assert_called_once()
        assert "audit_ref" in mock_block.call_args.kwargs["reason"]

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
                required_ref_key="audit_ref",
                flow_state={},
            )

        mock_block.assert_called_once()
        assert "latest verdict missing" in mock_block.call_args.kwargs["reason"]

    def test_manager_skips_ref_check_state_changed_passes(self) -> None:
        """Manager role skips ref check; only state change matters."""
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
                required_ref_key=None,  # manager has no required ref
                flow_state=None,
            )

        mock_block.assert_not_called()
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"
