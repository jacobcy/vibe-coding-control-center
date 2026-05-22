"""Unit tests for the unified no-op gate (noop_gate module)."""

import json
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from vibe3.clients.sqlite_schema import init_schema
from vibe3.execution.noop_gate import apply_unified_noop_gate


def _make_mock_conn() -> MagicMock:
    """Create a mock sqlite connection for transition_history operations."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (1,)  # event_id
    mock_cursor.execute.return_value = mock_cursor  # Return same cursor for chaining
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn


def _make_mock_store() -> MagicMock:
    """Create a mock SQLiteClient."""
    store = MagicMock()
    store.get_flow_state.return_value = {}
    store.count_specific_pair.return_value = 0  # No previous transitions
    store.record_transition.return_value = None  # Mock record_transition
    store.db_path = ":memory:"  # Use in-memory database for tests
    return store


def _make_github_issue_payload(state_label: str = "state/plan") -> dict:
    """Build a GitHub issue payload dict with given state label."""
    labels = [{"name": state_label}] if state_label else []
    return {"labels": labels, "state": "open"}


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


class TestTransitionCount:
    """Tests for transition_count increment and limit checking."""

    def test_transition_count_incremented_on_state_change(self) -> None:
        """transition_count is incremented when state changes."""
        store = _make_mock_store()
        flow_state = {"transition_count": 3}
        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_not_called()
        assert flow_state["transition_count"] == 4
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"

    def test_transition_count_not_incremented_on_state_unchanged(self) -> None:
        """transition_count is NOT incremented when state is unchanged."""
        store = _make_mock_store()
        flow_state = {"transition_count": 3}

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
                flow_state=flow_state,
            )

        mock_block.assert_called_once()
        assert flow_state["transition_count"] == 3  # Unchanged
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_unchanged"

    def test_transition_count_hard_limit_blocks(self) -> None:
        """Gate blocks when transition_count reaches hard limit (20)."""
        store = _make_mock_store()
        flow_state = {"transition_count": 19}

        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_called_once()
        call_kwargs = mock_block.call_args[1]
        assert "transition count exceeded" in call_kwargs["reason"]
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "transition_count_exceeded"

    def test_transition_count_soft_limit_warns_no_block(self) -> None:
        """Soft limit (10) only warns, does not block."""
        store = _make_mock_store()
        flow_state = {"transition_count": 9}

        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        # Soft limit does NOT block
        mock_block.assert_not_called()
        assert flow_state["transition_count"] == 10
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"

    def test_transition_count_below_soft_limit_no_warning(self) -> None:
        """No warning when transition_count below soft limit."""
        store = _make_mock_store()
        flow_state = {"transition_count": 3}

        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_not_called()
        assert flow_state["transition_count"] == 4
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"

    def test_transition_count_none_flow_state_skips_check(self) -> None:
        """transition_count logic is skipped when flow_state is None."""
        store = _make_mock_store()
        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=None,
            )

        mock_block.assert_not_called()
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"

    def test_transition_count_hard_limit_checked_before_state_change(self) -> None:
        """Hard limit is checked BEFORE state change increment."""
        store = _make_mock_store()
        flow_state = {"transition_count": 19}

        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_called_once()
        # Event should be transition_count_exceeded, not state_transitioned
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "transition_count_exceeded"

    def test_transition_count_defaults_to_zero_when_missing(self) -> None:
        """transition_count defaults to 0 when missing from flow_state."""
        store = _make_mock_store()
        flow_state: dict[str, int] = {}  # No transition_count key

        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_not_called()
        assert flow_state["transition_count"] == 1  # 0 + 1 = 1
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"

    # --- Single-step transition limit tests (mock) ---

    def test_single_step_pair_two_times_passes(self) -> None:
        """Test that a transition pair occurring 2 times does NOT block."""
        store = _make_mock_store()
        store.count_specific_pair = Mock(return_value=2)  # Below limit
        store.record_transition = Mock()
        flow_state: dict[str, int] = {}
        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_not_called()
        store.record_transition.assert_called_once()

    def test_single_step_limit_blocks_on_third_occurrence(self) -> None:
        """Test that a transition pair occurring 3 times blocks."""
        store = _make_mock_store()
        store.count_specific_pair = Mock(return_value=3)  # At limit
        store.record_transition = Mock()
        flow_state: dict[str, int] = {}
        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_called_once()
        store.record_transition.assert_not_called()

    def test_single_step_different_pairs_counted_separately(self) -> None:
        """Test different transition pairs have independent counts."""
        store = _make_mock_store()
        store.count_specific_pair = Mock(return_value=2)  # Below limit
        store.record_transition = Mock()
        flow_state: dict[str, int] = {}
        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_not_called()
        store.count_specific_pair.assert_called_once()
        call_kwargs = store.count_specific_pair.call_args[1]
        assert call_kwargs["from_state"] == "state/plan"
        assert call_kwargs["to_state"] == "state/ready"
        assert call_kwargs["branch"] == "task/issue-42"

    def test_single_step_transition_recorded_after_pass(self) -> None:
        """Test that record_transition is called after a successful state change."""
        store = _make_mock_store()
        store.count_specific_pair = Mock(return_value=0)  # No previous occurrences
        store.record_transition = Mock()
        flow_state: dict[str, int] = {}
        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_not_called()
        store.record_transition.assert_called_once()
        call_kwargs = store.record_transition.call_args[1]
        assert call_kwargs["from_state"] == "state/plan"
        assert call_kwargs["to_state"] == "state/ready"
        assert call_kwargs["actor"] == "agent:plan"
        assert call_kwargs["branch"] == "task/issue-42"


class TestSingleStepLimitIntegration:
    """Integration tests for single-step transition limit in no-op gate."""

    def test_single_step_limit_blocks_after_3_occurrences(self) -> None:
        """Block when the same transition pair has occurred 3+ times."""
        # Create in-memory database with full schema
        db_conn = sqlite3.connect(":memory:")
        init_schema(db_conn)

        # Insert 3 previous (state/handoff -> state/in-progress) transitions
        now = datetime.now().isoformat()
        db_conn.executemany(
            """
            INSERT INTO transition_history
                (branch, from_state, to_state, created_at, actor)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    "task/issue-1034",
                    "state/handoff",
                    "state/in-progress",
                    now,
                    "executor:run1",
                ),
                (
                    "task/issue-1034",
                    "state/handoff",
                    "state/in-progress",
                    now,
                    "executor:run2",
                ),
                (
                    "task/issue-1034",
                    "state/handoff",
                    "state/in-progress",
                    now,
                    "executor:run3",
                ),
            ],
        )
        db_conn.commit()

        # Insert flow_state row with transition_count=0
        now_dt = datetime.now().isoformat()
        db_conn.execute(
            """
            INSERT INTO flow_state (branch, flow_slug, transition_count, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            ("task/issue-1034", "task/issue-1034", 0, now_dt),
        )
        db_conn.commit()

        # Mock store with real db_path
        mock_store = MagicMock()
        mock_store.db_path = ":memory:"

        # Mock GitHub to return state/in-progress label
        mock_block_fn = MagicMock()

        with (
            patch(
                "vibe3.execution.noop_gate.get_role_block_function",
                return_value=mock_block_fn,
            ),
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=db_conn),
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/in-progress"
            )

            # Mock store methods that need to work with real DB
            def mock_count_specific_pair(
                conn: sqlite3.Connection, branch: str, from_state: str, to_state: str
            ) -> int:
                cursor = conn.cursor()
                row = cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM transition_history
                    WHERE branch = ? AND from_state = ? AND to_state = ?
                    """,
                    (branch, from_state, to_state),
                ).fetchone()
                return row[0] if row else 0

            mock_store.count_specific_pair = mock_count_specific_pair

            apply_unified_noop_gate(
                store=mock_store,
                issue_number=1034,
                branch="task/issue-1034",
                actor="executor:run3",
                role="executor",
                before_state_label="state/handoff",
            )

        # Assert block_fn called with reason containing single-step limit
        mock_block_fn.assert_called_once()
        call_args = mock_block_fn.call_args
        reason = call_args.kwargs.get("reason", "")
        assert "single-step limit exceeded" in reason
        assert "state/handoff -> state/in-progress" in reason
        assert "3 times" in reason

        db_conn.close()

    def test_single_step_limit_allows_2_occurrences(self) -> None:
        """Allow transition when pair has occurred less than 3 times."""
        # Create in-memory database with full schema
        db_conn = sqlite3.connect(":memory:")
        init_schema(db_conn)

        # Insert 1 previous transition
        now = datetime.now().isoformat()
        db_conn.execute(
            """
            INSERT INTO transition_history
                (branch, from_state, to_state, created_at, actor)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "task/issue-1034",
                "state/handoff",
                "state/in-progress",
                now,
                "executor:run1",
            ),
        )
        db_conn.commit()

        # Insert flow_state row with transition_count=0
        now_dt = datetime.now().isoformat()
        db_conn.execute(
            """
            INSERT INTO flow_state (branch, flow_slug, transition_count, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            ("task/issue-1034", "task/issue-1034", 0, now_dt),
        )
        db_conn.commit()

        # Mock store with real db_path
        mock_store = MagicMock()
        mock_store.db_path = ":memory:"

        # Mock GitHub to return state/in-progress label
        mock_block_fn = MagicMock()

        with (
            patch(
                "vibe3.execution.noop_gate.get_role_block_function",
                return_value=mock_block_fn,
            ),
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=db_conn),
        ):
            mock_gh.return_value.view_issue.return_value = _make_github_issue_payload(
                "state/in-progress"
            )

            # Mock store methods that need to work with real DB
            def mock_count_specific_pair(
                conn: sqlite3.Connection, branch: str, from_state: str, to_state: str
            ) -> int:
                cursor = conn.cursor()
                row = cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM transition_history
                    WHERE branch = ? AND from_state = ? AND to_state = ?
                    """,
                    (branch, from_state, to_state),
                ).fetchone()
                return row[0] if row else 0

            def mock_record_transition(
                conn: sqlite3.Connection,
                branch: str,
                from_state: str,
                to_state: str,
                actor: str,
                event_id: int | None = None,
            ) -> None:
                conn.execute(
                    """
                    INSERT INTO transition_history
                        (branch, from_state, to_state, created_at, actor, event_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        branch,
                        from_state,
                        to_state,
                        datetime.now().isoformat(),
                        actor,
                        event_id,
                    ),
                )

            def mock_add_event(
                branch: str,
                event_type: str,
                actor: str,
                detail: str = "",
                refs: dict | None = None,
            ) -> None:
                # Simplified: just insert a row to satisfy the code
                cursor = db_conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO flow_events
                        (branch, event_type, actor, detail, refs, created_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (branch, event_type, actor, detail, str(refs) if refs else None),
                )

            mock_store.count_specific_pair = mock_count_specific_pair
            mock_store.record_transition = mock_record_transition
            mock_store.add_event = mock_add_event

            apply_unified_noop_gate(
                store=mock_store,
                issue_number=1034,
                branch="task/issue-1034",
                actor="executor:run2",
                role="executor",
                before_state_label="state/handoff",
            )

        # Assert block_fn NOT called
        mock_block_fn.assert_not_called()

        # Verify transition was recorded (pair_count should now be 2)
        cursor = db_conn.cursor()
        row = cursor.execute(
            """
            SELECT COUNT(*)
            FROM transition_history
            WHERE branch = ? AND from_state = ? AND to_state = ?
            """,
            ("task/issue-1034", "state/handoff", "state/in-progress"),
        ).fetchone()

        assert row[0] == 2, f"Expected 2 transitions, got {row[0]}"

        db_conn.close()
