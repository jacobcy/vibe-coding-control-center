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

                # Mock registry to indicate issue 1 is active
                mock_store.list_live_runtime_sessions.return_value = [
                    {"target_id": "issue-1", "role": "executor"}
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
