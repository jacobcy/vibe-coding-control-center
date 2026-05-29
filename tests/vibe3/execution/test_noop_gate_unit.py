"""Unit tests for the unified no-op gate (noop_gate module)."""

from unittest.mock import MagicMock, patch

import pytest

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


class TestApplyUnifiedNoopGate:
    """Tests for the simplified no-op gate."""

    def test_missing_ref_still_blocks_when_state_unchanged(self) -> None:
        """Missing ref does not matter when state is unchanged: still block."""
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
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
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
                "vibe3.services.role_policy_helpers.block_executor_noop_issue"
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
                "vibe3.services.role_policy_helpers.block_manager_noop_issue"
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
            )

        mock_block.assert_called_once()

    def test_retries_when_github_returns_none(self) -> None:
        """Gate retries when GitHub returns None (runtime error with retry limit)."""
        from vibe3.exceptions.runtime_errors import GitHubAPIError

        store = _make_mock_store()
        flow_state = {}  # Track retry count

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = None
            # First retry: should raise GitHubAPIError, not block
            try:
                apply_unified_noop_gate(
                    store=store,
                    issue_number=42,
                    branch="task/issue-42",
                    actor="agent:plan",
                    role="planner",
                    before_state_label="state/plan",
                    flow_state=flow_state,
                )
                assert False, "Expected GitHubAPIError"
            except GitHubAPIError as e:
                assert "Malformed GitHub response" in str(e)

        # Should NOT block on first retry
        mock_block.assert_not_called()
        # Should increment retry count
        assert flow_state.get("noop_gate_malformed_retry_count") == 1

    def test_retries_when_github_raises(self) -> None:
        """Gate retries when GitHub call raises (runtime error with retry limit)."""
        from vibe3.exceptions.runtime_errors import GitHubAPIError

        store = _make_mock_store()
        flow_state = {}  # Track retry count

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.side_effect = Exception("timeout")
            # First retry: should raise GitHubAPIError, not block
            try:
                apply_unified_noop_gate(
                    store=store,
                    issue_number=42,
                    branch="task/issue-42",
                    actor="agent:plan",
                    role="planner",
                    before_state_label="state/plan",
                    flow_state=flow_state,
                )
                assert False, "Expected GitHubAPIError"
            except GitHubAPIError as e:
                assert "Cannot verify remote state" in str(e)

        # Should NOT block on first retry
        mock_block.assert_not_called()
        # Should increment retry count
        assert flow_state.get("noop_gate_github_retry_count") == 1

    def test_records_error_after_github_api_retry_limit(self) -> None:
        """Gate records error (not blocks) after 3 retries for GitHub API failures."""
        from vibe3.exceptions.runtime_errors import GitHubAPIError

        store = _make_mock_store()
        flow_state = {"noop_gate_github_retry_count": 3}  # Already at limit

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.side_effect = Exception("timeout")

            # NEW: Should raise GitHubAPIError (not block flow)
            try:
                apply_unified_noop_gate(
                    store=store,
                    issue_number=42,
                    branch="task/issue-42",
                    actor="agent:plan",
                    role="planner",
                    before_state_label="state/plan",
                    flow_state=flow_state,
                )
                pytest.fail("Should have raised GitHubAPIError")
            except GitHubAPIError as e:
                assert "Cannot verify remote state" in str(e)
                assert "after 3 retries" in str(e)

        # NEW: Should NOT block flow (runtime error, not business logic)
        mock_block.assert_not_called()
        # NEW: Error recorded (FailedGate will control dispatch)
        # Note: ErrorTrackingService recording tested in integration tests

    def test_records_error_after_malformed_response_retry_limit(self) -> None:
        """Gate records error (not blocks) after 3 retries for malformed responses."""
        from vibe3.exceptions.runtime_errors import GitHubAPIError

        store = _make_mock_store()
        flow_state = {"noop_gate_malformed_retry_count": 3}  # Already at limit

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = None  # Malformed

            try:
                apply_unified_noop_gate(
                    store=store,
                    issue_number=42,
                    branch="task/issue-42",
                    actor="agent:plan",
                    role="planner",
                    before_state_label="state/plan",
                    flow_state=flow_state,
                )
                pytest.fail("Should have raised GitHubAPIError")
            except GitHubAPIError as e:
                assert "Malformed GitHub response" in str(e)
                assert "after 3 retries" in str(e)

        # Should NOT block flow (runtime error, not business logic)
        mock_block.assert_not_called()

    def test_blocks_when_state_label_disappears(self) -> None:
        """Gate blocks when state label disappears from issue after agent."""
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
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
            "vibe3.services.role_policy_helpers.block_executor_noop_issue"
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
            "vibe3.services.role_policy_helpers.block_planner_noop_issue"
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

    def test_issue_closed_during_execution_bypasses_state_unchanged_block(
        self,
    ) -> None:
        """Issue closed during execution is a terminal transition.

        Bypasses state unchanged block even when state label is unchanged.
        """
        store = _make_mock_store()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
            ) as mock_block,
        ):
            # Single call: check issue closed state (returns closed)
            # Also extracts after_state_label from same payload
            # (not used since issue closed)
            mock_gh.return_value.view_issue.return_value = {
                "state": "CLOSED",
                "labels": [{"name": "state/plan"}],  # State label unchanged
            }
            apply_unified_noop_gate(
                store=store,
                issue_number=42,
                branch="task/issue-42",
                actor="agent:plan",
                role="planner",
                before_state_label="state/plan",
                before_issue_is_closed=False,  # Issue was open before execution
            )

        # Should NOT block, even though state label is unchanged
        mock_block.assert_not_called()
        # Should record terminal transition event
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"
        assert "closed" in event_args[1]["detail"]
        assert "terminal transition" in event_args[1]["detail"]
