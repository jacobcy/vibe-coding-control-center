"""Tests for GlobalDispatchCoordinator state transitions and priority handling."""

from __future__ import annotations

import re

import pytest

from vibe3.models.orchestration import IssueState


class TestStateTransitions:
    """Tests for stateless coordinator state transitions."""

    @pytest.mark.asyncio
    async def test_capacity_limit_stops_dispatch(
        self,
        make_issue_info,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that capacity limit stops dispatch after limit reached."""
        from unittest.mock import MagicMock, patch

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

        # Create issues with different states (sorted by priority)
        review_issue = make_issue_info(304, IssueState.REVIEW)
        claimed_issue = make_issue_info(303, IssueState.CLAIMED)
        ready_issue = make_issue_info(372, IssueState.READY)

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                mock_flow_context.return_value = ("task/issue-304", None)

                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                # Mock _scan_dispatchable_states to return issues in priority order
                async def mock_scan():
                    return [review_issue, claimed_issue, ready_issue]

                coordinator._scan_dispatchable_states = mock_scan
                coordinator._health_check_before_dispatch = lambda issue: True

                emit_calls = []
                coordinator._emit_dispatch_intent = (
                    lambda role, issue, tick_id: emit_calls.append((role, issue))
                )

                await coordinator.coordinate()

                assert len(emit_calls) == 2
                dispatched_numbers = [call[1].number for call in emit_calls]
                assert 304 in dispatched_numbers
                assert 303 in dispatched_numbers
                assert 372 not in dispatched_numbers

    @pytest.mark.asyncio
    async def test_terminal_state_removes_issue_from_queue(
        self,
        make_issue_info,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that DONE issues are filtered out."""
        from unittest.mock import MagicMock, patch

        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 1}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 1
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        ready_issue = make_issue_info(1, IssueState.READY)

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

                # First scan returns READY issue
                async def mock_scan_ready():
                    return [ready_issue]

                coordinator._scan_dispatchable_states = mock_scan_ready
                coordinator._health_check_before_dispatch = lambda issue: True

                emit_calls = []
                coordinator._emit_dispatch_intent = (
                    lambda role, issue, tick_id: emit_calls.append((role, issue))
                )

                await coordinator.coordinate()
                assert len(emit_calls) == 1

                # Second scan returns DONE issue (should be filtered)
                done_issue = make_issue_info(1, IssueState.DONE)

                async def mock_scan_done():
                    return [done_issue]

                coordinator._scan_dispatchable_states = mock_scan_done

                await coordinator.coordinate()
                await coordinator.coordinate()

                # Should still have only 1 dispatch (DONE filtered out)
                assert len(emit_calls) == 1

    @pytest.mark.asyncio
    async def test_falsely_blocked_issue_dispatches_after_qualify(
        self,
        make_issue_info,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Falsely-blocked issue is dispatched after qualify_blocked_issue (#1125)."""
        from unittest.mock import MagicMock, patch

        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 1}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 1
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        blocked_issue = make_issue_info(100, IssueState.BLOCKED)

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                mock_flow_context.return_value = ("task/issue-100", None)

                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                async def mock_scan():
                    return [blocked_issue]

                coordinator._scan_dispatchable_states = mock_scan

                # Mock qualify_blocked_issue to return READY (unblocked)
                def mock_qualify(issue) -> IssueState | None:
                    assert issue.number == 100
                    return IssueState.READY

                coordinator._qualify_gate.qualify_blocked_issue = mock_qualify
                coordinator._health_check_before_dispatch = lambda issue: True

                emit_calls = []
                coordinator._emit_dispatch_intent = (
                    lambda role, issue, tick_id=0: emit_calls.append((role, issue))
                )

                await coordinator.coordinate()

                # Falsely-blocked issue should be dispatched to manager role
                assert len(emit_calls) == 1
                assert emit_calls[0][1].number == 100
                assert emit_calls[0][0].registry_role == "manager"


class TestLoggingBehavior:
    """Tests for logging output."""

    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_instead_of_dispatch_success(
        self,
        make_issue_info,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Coordinator logs 'dispatch-intent' not 'dispatched'."""
        from unittest.mock import MagicMock, patch

        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 1}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 1
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        claimed_issue = make_issue_info(303, IssueState.CLAIMED)

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                mock_flow_context.return_value = ("task/issue-303", None)

                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                async def mock_scan():
                    return [claimed_issue]

                coordinator._scan_dispatchable_states = mock_scan
                coordinator._health_check_before_dispatch = lambda issue: True

                events: list[str] = []

                def capture_event(
                    _category: str, message: str, level: str = "INFO"
                ) -> None:
                    _ = level
                    events.append(message)

                monkeypatch.setattr(
                    "vibe3.orchestra.global_dispatch_coordinator.append_orchestra_event",
                    capture_event,
                )

                await coordinator.coordinate()

                normalized_events = [
                    re.sub(r"\x1b\[[0-9;]*m", "", message) for message in events
                ]

                assert any(
                    "dispatch-intent #303 (planner)" in message
                    for message in normalized_events
                )
                assert not any(
                    "dispatched #303 (planner)" in message
                    for message in normalized_events
                )

    @pytest.mark.asyncio
    async def test_logs_dispatch_intent_before_emit_side_effect(
        self,
        make_issue_info,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Coordinator logs dispatch-intent before calling emit."""
        from unittest.mock import MagicMock, patch

        from vibe3.orchestra.global_dispatch_coordinator import (
            GlobalDispatchCoordinator,
        )

        mock_github = MagicMock()
        mock_store = MagicMock()
        mock_flow_manager = MagicMock()
        mock_capacity = MagicMock()
        mock_config = MagicMock()

        mock_capacity.get_capacity_status.return_value = {"remaining": 1}
        mock_config.repo = "test/repo"
        mock_config.max_concurrent_flows = 1
        mock_config.get_manager_usernames.return_value = ["manager-bot"]
        mock_supervisor_handoff = MagicMock()
        mock_supervisor_handoff.issue_label = "supervisor"
        mock_config.supervisor_handoff = mock_supervisor_handoff

        claimed_issue = make_issue_info(467, IssueState.CLAIMED)

        with patch(
            "vibe3.orchestra.global_dispatch_coordinator.get_flow_context"
        ) as mock_flow_context:
            with patch("vibe3.orchestra.global_dispatch_coordinator.publish"):
                mock_flow_context.return_value = ("task/issue-467", None)

                coordinator = GlobalDispatchCoordinator(
                    config=mock_config,
                    capacity=mock_capacity,
                    github=mock_github,
                    store=mock_store,
                    flow_manager=mock_flow_manager,
                )

                async def mock_scan():
                    return [claimed_issue]

                coordinator._scan_dispatchable_states = mock_scan
                coordinator._health_check_before_dispatch = lambda issue: True

                events: list[str] = []

                def capture_event(
                    _category: str, message: str, level: str = "INFO"
                ) -> None:
                    _ = level
                    events.append(message)

                monkeypatch.setattr(
                    "vibe3.orchestra.global_dispatch_coordinator.append_orchestra_event",
                    capture_event,
                )

                def emit_side_effect(role, issue, tick_id=0) -> None:
                    capture_event(
                        "dispatcher",
                        "planner launch failed for #467: Failed to resolve worktree",
                    )

                coordinator._emit_dispatch_intent = emit_side_effect

                await coordinator.coordinate()

                normalized_events = [
                    re.sub(r"\x1b\[[0-9;]*m", "", message) for message in events
                ]

                assert normalized_events[0] == (
                    "GlobalDispatchCoordinator: dispatch-intent #467 (planner)"
                )
                assert normalized_events[1] == (
                    "planner launch failed for #467: Failed to resolve worktree"
                )
