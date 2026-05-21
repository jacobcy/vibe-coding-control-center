"""Tests for GlobalDispatchCoordinator stateless dispatch operations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueInfo, IssueState


class TestStatelessDispatch:
    """Tests for the stateless scan-dispatch coordinate() behavior."""

    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(self) -> None:
        """When capacity available, dispatch all ready issues."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        # Setup mocks
        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 2}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 2
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        # Create ready issues
        issue1 = IssueInfo(
            number=1,
            title="Issue 1",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            assignees=["manager-bot"],
        )
        issue2 = IssueInfo(
            number=2,
            title="Issue 2",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            assignees=["manager-bot"],
        )

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.load_issue"
        ) as mock_load_issue:
            with patch(
                "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
            ) as mock_flow_context:
                with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                    mock_load_issue.side_effect = lambda n, *args: {
                        1: issue1,
                        2: issue2,
                    }.get(n)
                    mock_flow_context.return_value = ("task/issue-1", None)

                    coordinator = GlobalDispatchCoordinator(
                        config=mock_config,
                        capacity=mock_capacity,
                        github=mock_github,
                        store=mock_store,
                        flow_manager=mock_flow_manager,
                    )

                    # Mock _scan_dispatchable_states to return ready issues
                    async def mock_scan():
                        return [issue1, issue2]

                    coordinator._scan_dispatchable_states = mock_scan
                    coordinator._health_check_before_dispatch = lambda issue: True

                    emit_calls = []
                    coordinator._emit_dispatch_intent = (
                        lambda role, issue, tick_id: emit_calls.append((role, issue))
                    )

                    await coordinator.coordinate()

                    assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(self) -> None:
        """When capacity full, dispatch nothing."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 0}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 1
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                mock_flow_context.return_value = ("task/issue-1", None)

                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                issue1 = IssueInfo(
                    number=1,
                    title="Issue 1",
                    state=IssueState.CLAIMED,
                    labels=["state/claimed"],
                    assignees=["manager-bot"],
                )

                async def mock_scan():
                    return [issue1]

                coordinator._scan_dispatchable_states = mock_scan

                emit_calls = []
                coordinator._emit_dispatch_intent = (
                    lambda role, issue, tick_id: emit_calls.append((role, issue))
                )

                await coordinator.coordinate()

                assert len(emit_calls) == 0

    @pytest.mark.asyncio
    async def test_filter_active_issues(self) -> None:
        """Active issues (in tmux/registry) are filtered out."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()
        mock_registry = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 2}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 2
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        # Issue 1 is active (has live session)
        issue1 = IssueInfo(
            number=1,
            title="Issue 1",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            assignees=["manager-bot"],
        )
        # Issue 2 is not active
        issue2 = IssueInfo(
            number=2,
            title="Issue 2",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            assignees=["manager-bot"],
        )

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                mock_flow_context.return_value = ("task/issue-2", None)

                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                    registry=mock_registry,
                )

                # Mock registry to indicate issue 1 is active.
                # Schema matches real runtime_session rows:
                # target_type='issue', target_id='<numeric>'.
                mock_store.list_live_runtime_sessions.return_value = [
                    {"target_type": "issue", "target_id": "1", "role": "executor"}
                ]

                async def mock_scan():
                    return [issue1, issue2]

                coordinator._scan_dispatchable_states = mock_scan
                coordinator._health_check_before_dispatch = lambda issue: True

                emit_calls = []
                coordinator._emit_dispatch_intent = (
                    lambda role, issue, tick_id: emit_calls.append((role, issue))
                )

                await coordinator.coordinate()

                # Only issue 2 should be dispatched
                assert len(emit_calls) == 1
                assert emit_calls[0][1].number == 2

    @pytest.mark.asyncio
    async def test_filter_done_issues(self) -> None:
        """Issues in DONE state are filtered out."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 2}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 2
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        # Issue in DONE state
        done_issue = IssueInfo(
            number=1,
            title="Done Issue",
            state=IssueState.DONE,
            labels=["state/done"],
            assignees=["manager-bot"],
        )
        # Issue ready to dispatch
        ready_issue = IssueInfo(
            number=2,
            title="Ready Issue",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            assignees=["manager-bot"],
        )

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                mock_flow_context.return_value = ("task/issue-2", None)

                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                async def mock_scan():
                    return [done_issue, ready_issue]

                coordinator._scan_dispatchable_states = mock_scan
                coordinator._health_check_before_dispatch = lambda issue: True

                emit_calls = []
                coordinator._emit_dispatch_intent = (
                    lambda role, issue, tick_id: emit_calls.append((role, issue))
                )

                await coordinator.coordinate()

                # Only ready issue should be dispatched
                assert len(emit_calls) == 1
                assert emit_calls[0][1].number == 2

    @pytest.mark.asyncio
    async def test_health_check_failure_skips_dispatch(self) -> None:
        """Issues failing health check are skipped."""
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 2}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 2
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        issue1 = IssueInfo(
            number=1,
            title="Issue 1",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            assignees=["manager-bot"],
        )
        issue2 = IssueInfo(
            number=2,
            title="Issue 2",
            state=IssueState.CLAIMED,
            labels=["state/claimed"],
            assignees=["manager-bot"],
        )

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                mock_flow_context.return_value = ("task/issue-1", None)

                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                async def mock_scan():
                    return [issue1, issue2]

                coordinator._scan_dispatchable_states = mock_scan

                # Issue 1 fails health check, issue 2 passes
                def health_check(issue):
                    return issue.number != 1

                coordinator._health_check_before_dispatch = health_check

                emit_calls = []
                coordinator._emit_dispatch_intent = (
                    lambda role, issue, tick_id: emit_calls.append((role, issue))
                )

                await coordinator.coordinate()

                # Only issue 2 should be dispatched
                assert len(emit_calls) == 1
                assert emit_calls[0][1].number == 2


class TestActiveIssueParsing:
    """Regression tests for _get_active_issue_numbers schema parsing.

    Real runtime_session rows store target_type='issue' and target_id as a
    numeric string (e.g. '42'). An earlier draft expected target_id to look
    like 'issue-<n>', which silently matched nothing in production and caused
    already-running issues to be re-dispatched every tick.
    """

    def _make_coordinator(self, sessions):
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_store = MagicMock()
        mock_store.list_live_runtime_sessions.return_value = sessions
        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 2
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff
        return GlobalDispatchCoordinator(
            config=mock_config,
            capacity=MagicMock(),
            github=MagicMock(),
            store=mock_store,
            flow_manager=MagicMock(),
            registry=MagicMock(),
        )

    def test_recognizes_real_schema(self) -> None:
        """target_type='issue' + numeric target_id is recognized."""
        coordinator = self._make_coordinator(
            [
                {"target_type": "issue", "target_id": "42", "role": "executor"},
                {"target_type": "issue", "target_id": "303", "role": "manager"},
            ]
        )
        assert coordinator._get_active_issue_numbers() == {42, 303}

    def test_ignores_non_issue_target_types(self) -> None:
        """Rows with target_type != 'issue' are ignored (e.g. raw branches)."""
        coordinator = self._make_coordinator(
            [
                {"target_type": "branch", "target_id": "main", "role": "executor"},
                {"target_type": "issue", "target_id": "7", "role": "executor"},
            ]
        )
        assert coordinator._get_active_issue_numbers() == {7}

    def test_ignores_malformed_target_id(self) -> None:
        """Non-numeric / empty target_id is skipped without raising."""
        coordinator = self._make_coordinator(
            [
                {"target_type": "issue", "target_id": "issue-1", "role": "executor"},
                {"target_type": "issue", "target_id": "", "role": "executor"},
                {"target_type": "issue", "target_id": None, "role": "executor"},
                {"target_type": "issue", "target_id": "99", "role": "executor"},
            ]
        )
        assert coordinator._get_active_issue_numbers() == {99}


class TestScanDispatchableStates:
    """Unit tests for _scan_dispatchable_states().

    The stateless coordinator polls GitHub once per dispatchable state per
    tick and folds the results into a single candidate list. These tests
    exercise the parts that are normally stubbed by TestStatelessDispatch:
    label parsing, duplicate suppression, qualify_gate routing, and
    skip-filter integration.
    """

    @staticmethod
    def _make_payload(
        number: int, state_label: str, assignees: tuple[str, ...] = ("manager-bot",)
    ) -> dict:
        return {
            "number": number,
            "title": f"Issue {number}",
            "labels": [{"name": state_label}],
            "assignees": [{"login": login} for login in assignees],
        }

    def _make_coordinator(self, *, list_issues_side_effect, qualify_target=None):
        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_github.list_issues.side_effect = list_issues_side_effect

        mock_config = MagicMock()
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 2
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        coordinator = GlobalDispatchCoordinator(
            config=mock_config,
            capacity=MagicMock(),
            github=mock_github,
            store=MagicMock(),
            flow_manager=MagicMock(),
            registry=MagicMock(),
        )

        # Stub flow_context to return a synthetic branch (avoids touching git)
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context",
            return_value=("task/issue-x", None),
        ):
            # Stub qualify_gate: by default echo the scanned state (passes through)
            coordinator._qualify_gate = MagicMock()
            if qualify_target == "ECHO":
                coordinator._qualify_gate.run_qualify_gate.side_effect = (
                    lambda issue, branch, flow_state, labels, state: state
                )
            else:
                coordinator._qualify_gate.run_qualify_gate.return_value = qualify_target
            return coordinator

    @pytest.mark.asyncio
    async def test_skips_issues_without_state_label(self) -> None:
        """Issues missing any state/* label are dropped (defensive filter)."""
        from vibe3.models.orchestration import IssueState

        def list_issues(**kwargs):
            if kwargs.get("label") == IssueState.READY.to_label():
                return [
                    # valid: has state/ready
                    self._make_payload(1, "state/ready"),
                    # invalid: no state/* label at all
                    {
                        "number": 2,
                        "title": "Issue 2",
                        "labels": [{"name": "type/bug"}],
                        "assignees": [{"login": "manager-bot"}],
                    },
                ]
            return []

        coordinator = self._make_coordinator(
            list_issues_side_effect=list_issues, qualify_target="ECHO"
        )
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context",
            return_value=("task/issue-x", None),
        ):
            candidates = await coordinator._scan_dispatchable_states()

        assert {c.number for c in candidates} == {1}

    @pytest.mark.asyncio
    async def test_suppresses_duplicate_issues_across_states(self) -> None:
        """An issue carrying multiple state/* labels is only emitted once."""
        from vibe3.models.orchestration import IssueState

        # Issue 7 appears under both REVIEW and CLAIMED queries; the first
        # state encountered (REVIEW per coordinator's iteration order) wins.
        def list_issues(**kwargs):
            label = kwargs.get("label")
            if label == IssueState.REVIEW.to_label():
                return [self._make_payload(7, "state/review")]
            if label == IssueState.CLAIMED.to_label():
                return [self._make_payload(7, "state/claimed")]
            return []

        coordinator = self._make_coordinator(
            list_issues_side_effect=list_issues, qualify_target="ECHO"
        )
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context",
            return_value=("task/issue-7", None),
        ):
            candidates = await coordinator._scan_dispatchable_states()

        assert len(candidates) == 1
        assert candidates[0].number == 7

    @pytest.mark.asyncio
    async def test_blocked_issues_bypass_qualify_gate_at_scan_time(self) -> None:
        """BLOCKED issues skip qualify_gate during scan (deferred to dispatch)."""
        from vibe3.models.orchestration import IssueState

        def list_issues(**kwargs):
            if kwargs.get("label") == IssueState.BLOCKED.to_label():
                return [self._make_payload(11, "state/blocked")]
            return []

        coordinator = self._make_coordinator(
            list_issues_side_effect=list_issues,
            qualify_target=None,  # would filter if called
        )
        candidates = await coordinator._scan_dispatchable_states()

        assert {c.number for c in candidates} == {11}
        coordinator._qualify_gate.run_qualify_gate.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_blocked_issues_filtered_when_qualify_gate_disagrees(
        self,
    ) -> None:
        """Non-BLOCKED issues are dropped if qualify_gate retargets or rejects."""
        from vibe3.models.orchestration import IssueState

        def list_issues(**kwargs):
            if kwargs.get("label") == IssueState.READY.to_label():
                return [
                    self._make_payload(20, "state/ready"),
                    self._make_payload(21, "state/ready"),
                ]
            return []

        coordinator = self._make_coordinator(
            list_issues_side_effect=list_issues,
            qualify_target=None,  # reject everything
        )
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context",
            return_value=("task/issue-x", None),
        ):
            candidates = await coordinator._scan_dispatchable_states()

        assert candidates == []

    @pytest.mark.asyncio
    async def test_assignee_missing_filters_candidate(self) -> None:
        """Issues without the required manager assignee are filtered."""
        from vibe3.models.orchestration import IssueState

        def list_issues(**kwargs):
            if kwargs.get("label") == IssueState.READY.to_label():
                return [
                    # has manager-bot assignee → kept
                    self._make_payload(30, "state/ready"),
                    # no manager assignee → dropped by should_skip_from_queue
                    self._make_payload(31, "state/ready", assignees=("random-user",)),
                ]
            return []

        coordinator = self._make_coordinator(
            list_issues_side_effect=list_issues, qualify_target="ECHO"
        )
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context",
            return_value=("task/issue-x", None),
        ):
            candidates = await coordinator._scan_dispatchable_states()

        assert {c.number for c in candidates} == {30}

    @pytest.mark.asyncio
    async def test_per_state_exception_does_not_abort_scan(self) -> None:
        """If one state query fails, other states still contribute candidates."""
        from vibe3.models.orchestration import IssueState

        def list_issues(**kwargs):
            label = kwargs.get("label")
            if label == IssueState.REVIEW.to_label():
                raise RuntimeError("simulated GitHub API failure")
            if label == IssueState.READY.to_label():
                return [self._make_payload(42, "state/ready")]
            return []

        coordinator = self._make_coordinator(
            list_issues_side_effect=list_issues, qualify_target="ECHO"
        )
        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context",
            return_value=("task/issue-x", None),
        ):
            candidates = await coordinator._scan_dispatchable_states()

        # READY survives even though REVIEW raised
        assert {c.number for c in candidates} == {42}
