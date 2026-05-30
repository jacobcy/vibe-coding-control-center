"""Unit tests for transition_count logic in no-op gate."""

from unittest.mock import MagicMock, Mock, patch

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


class TestTransitionCount:
    """Tests for transition_count increment and limit checking."""

    def test_transition_count_incremented_on_state_change(self) -> None:
        """transition_count is incremented when state changes."""
        store = _make_mock_store()
        flow_state = {"transition_count": 3}
        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.role_policy_helpers.block_planner_noop_issue"
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_not_called()
        assert flow_state["transition_count"] == 1  # 0 + 1 = 1
        store.add_event.assert_called_once()
        event_args = store.add_event.call_args
        assert event_args[0][1] == "state_transitioned"

    # --- Single-step transition limit tests ---

    def test_single_step_pair_two_times_passes(self) -> None:
        """Test that a transition pair occurring 2 times does NOT block."""
        store = _make_mock_store()
        store.count_specific_pair = Mock(return_value=2)  # Below limit
        store.record_transition = Mock()
        flow_state: dict[str, int] = {}
        mock_conn = _make_mock_conn()

        with (
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
            patch("vibe3.clients.GitHubClient") as mock_gh,
            patch("sqlite3.connect", return_value=mock_conn),
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
                flow_state=flow_state,
            )

        mock_block.assert_not_called()
        store.record_transition.assert_called_once()
        call_kwargs = store.record_transition.call_args[1]
        assert call_kwargs["from_state"] == "state/plan"
        assert call_kwargs["to_state"] == "state/ready"
        assert call_kwargs["actor"] == "agent:plan"
        assert call_kwargs["branch"] == "task/issue-42"
