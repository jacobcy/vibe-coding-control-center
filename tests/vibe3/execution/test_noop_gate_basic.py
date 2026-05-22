"""Unit tests for basic no-op gate behavior and ref checking."""

import json
from unittest.mock import patch

from vibe3.execution.noop_gate import apply_unified_noop_gate

from .conftest import (
    _make_github_issue_payload,
    _make_mock_store,
)


class TestApplyUnifiedNoopGate:
    """Tests for the simplified no-op gate."""

    def test_missing_ref_still_blocks_when_state_unchanged(self) -> None:
        """Missing ref does not matter when state is unchanged: still block."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
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
            )

        mock_block.assert_called_once()
        call_kwargs = mock_block.call_args[1]
        assert call_kwargs["issue_number"] == 42
        assert "state unchanged" in call_kwargs["reason"]
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_unchanged"

    def test_ref_present_state_unchanged_blocks(self) -> None:
        """Ref presence does not matter when state is unchanged: block."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
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
            )

        mock_block.assert_called_once()
        call_kwargs = mock_block.call_args[1]
        assert "state unchanged" in call_kwargs["reason"]
        store.add_event.assert_called_once()

    def test_state_changed_passes(self) -> None:
        """State change is the only pass condition."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/ready"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_not_called()
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"
        assert "state/plan" in event_args[1]["detail"]
        assert "state/ready" in event_args[1]["detail"]

    def test_blocks_executor_when_state_unchanged(self) -> None:
        """Executor is blocked when state is unchanged."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/run"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=99,
                branch="task/issue-99",
                actor="agent:run",
                role="executor",
                before_state_label="state/run",
            )

        mock_block.assert_called_once()

    def test_blocks_manager_when_state_unchanged_and_passes_repo(self) -> None:
        """Manager block helper must receive repo to avoid post-gate crash."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_manager_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/ready"
            )
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:manager",
                role="manager",
                before_state_label="state/ready",
                repo="owner/repo",
            )

        mock_block.assert_called_once()
        assert mock_block.call_args.kwargs["repo"] == "owner/repo"

    def test_blocks_reviewer_when_state_unchanged(self) -> None:
        """Reviewer is blocked when state is unchanged."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
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
            )

        mock_block.assert_called_once()

    def test_blocks_when_github_returns_none(self) -> None:
        """Gate blocks when GitHub returns None (fail-safe)."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = None
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_called_once()
        assert "cannot verify remote state" in mock_block.call_args.kwargs["reason"]
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "cannot_verify_remote_state"

    def test_blocks_when_github_raises(self) -> None:
        """Gate blocks when GitHub call raises (fail-safe)."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.side_effect = Exception("timeout")
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_called_once()
        assert "cannot verify remote state" in mock_block.call_args.kwargs["reason"]
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "cannot_verify_remote_state"

    def test_blocks_when_state_label_disappears(self) -> None:
        """Gate blocks when state label disappears from issue after agent."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                ""
            )  # No state label
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
            )

        mock_block.assert_called_once()
        assert "disappeared" in mock_block.call_args.kwargs["reason"]
        store.add_event.assert_called_once()
        assert store.add_event.call_args[0][1] == "state_unchanged"

    def test_gate_skipped_when_no_state_label(self) -> None:
        """Gate skips when issue has no state/ label.

        Issues not managed by state machine (e.g. manual ``vibe3 run``)
        should bypass the no-op gate entirely.
        """
        store = _make_mock_store()

        with patch(
            "vibe3.services.issue_failure_service.block_executor_noop_issue"
        ) as mock_block:
            apply_unified_noop_gate(
                store=store,
                issue_number=99,
                branch="task/issue-99",
                actor="agent:run",
                role="executor",
                before_state_label="",  # No state label
            )

        # Gate should skip, not block
        mock_block.assert_not_called()
        store.add_event.assert_not_called()

    def test_gate_skipped_when_before_state_label_none(self) -> None:
        """Gate is skipped when before_state_label is None."""
        store = _make_mock_store()

        with patch(
            "vibe3.services.issue_failure_service.block_planner_noop_issue"
        ) as mock_block:
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label=None,  # None state label
            )

        # Gate should skip, not block
        mock_block.assert_not_called()
        store.add_event.assert_not_called()


class TestRefCheck:
    """Tests for required_ref_key logic in no-op gate."""

    def test_blocks_when_required_ref_missing_even_if_state_changed(self) -> None:
        """Gate blocks when required ref is missing, even if state changed."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
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
                "vibe3.services.issue_failure_service.block_executor_noop_issue"
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
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
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
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
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
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
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
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
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
                "vibe3.services.issue_failure_service.block_manager_noop_issue"
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
