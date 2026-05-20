"""Tests for GlobalDispatchCoordinator queue operations."""

from __future__ import annotations

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.global_dispatch_coordinator import QueueEntry


class TestQueueOperations:
    @pytest.mark.asyncio
    async def test_dispatch_all_when_capacity_available(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        issues = [make_issue(1), make_issue(2)]
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            issues,
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="claimed"),
                QueueEntry(issue_number=2, collected_state="claimed"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "issue_num,role,collected_state,issue_state,labels,assignees",
        [
            (
                467,
                "handoff-manager",
                "handoff",
                IssueState.HANDOFF,
                ["supervisor", "state/handoff"],
                ["manager-bot"],
            ),
            (468, "manager", "ready", IssueState.READY, ["state/ready"], []),
            (
                469,
                "handoff-manager",
                "handoff",
                IssueState.HANDOFF,
                ["state/handoff"],
                [],
            ),
        ],
    )
    async def test_invalid_issues_removed_from_frozen_queue(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        make_issue_info,
        issue_num,
        role,
        collected_state,
        issue_state,
        labels,
        assignees,
    ) -> None:
        """Issues violating queue criteria are removed (supervisor, no assignee)."""
        issue = make_issue(issue_num)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            role, [issue], capacity=capacity, mock_health_check=True
        )
        coordinator._frozen_queue = [
            QueueEntry(
                issue_number=issue_num,
                collected_state=collected_state,
                waiting_state=None,
            )
        ]
        coordinator._load_issue = lambda n: make_issue_info(
            n, issue_state, labels=labels, assignees=assignees
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = lambda r, i, t: emit_calls.append((r, i))

        await coordinator.coordinate()

        assert len(emit_calls) == 0
        assert coordinator._frozen_queue == []

    @pytest.mark.asyncio
    async def test_skip_when_capacity_full(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        issues = [make_issue(1), make_issue(2), make_issue(3)]
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            issues,
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="claimed"),
                QueueEntry(issue_number=2, collected_state="claimed"),
                QueueEntry(issue_number=3, collected_state="claimed"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
                3: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_frozen_queue_prevents_duplicate_dispatch_without_state_change(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        issues = [make_issue(1), make_issue(2)]
        capacity = make_capacity(remaining=3)

        coordinator = make_coordinator(
            "planner",
            issues,
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="claimed"),
                QueueEntry(issue_number=2, collected_state="claimed"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()
        await coordinator.coordinate()

        assert len(emit_calls) == 2

    @pytest.mark.asyncio
    async def test_emit_failure_handled_gracefully(
        self, make_issue, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        issue1 = make_issue(1)
        issue2 = make_issue(2)
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "planner",
            [issue1, issue2],
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
        )

        async def mock_collect() -> list[QueueEntry]:
            return [
                QueueEntry(issue_number=1, collected_state="claimed"),
                QueueEntry(issue_number=2, collected_state="claimed"),
            ]

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(
            coordinator,
            {
                1: IssueState.CLAIMED,
                2: IssueState.CLAIMED,
            },
        )

        emit_calls = []
        call_count = [0]

        def emit_with_failure(role, issue, tick_id=0):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("emit failed")
            emit_calls.append((role, issue))

        coordinator._emit_dispatch_intent = emit_with_failure

        # With dead try-except removed, publish() failures propagate.
        # Dispatch handler now catches its own errors and writes blocked_reason.
        with pytest.raises(RuntimeError, match="emit failed"):
            await coordinator.coordinate()

        assert call_count[0] == 1

    @pytest.mark.asyncio
    async def test_collect_failure_does_not_affect_other_roles(
        self,
        make_issue,
        make_capacity,
        make_coordinator,
        install_issue_loader,
        make_issue_info,
    ) -> None:
        """Test that polling failure for one state doesn't prevent others."""
        issue_planner = make_issue(10)
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner",
            [issue_planner],
            capacity=capacity,
            with_branches=True,
            mock_health_check=True,
        )

        async def mock_poll(state: IssueState) -> list:
            if state == IssueState.READY:
                raise RuntimeError("API error")
            elif state == IssueState.CLAIMED:
                return [make_issue_info(10, IssueState.CLAIMED)]
            return []

        coordinator._poll_issues_by_state = mock_poll

        install_issue_loader(coordinator, {10: IssueState.CLAIMED})

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 1

    @pytest.mark.asyncio
    async def test_empty_queue_does_nothing(
        self, make_capacity, make_coordinator, install_issue_loader
    ) -> None:
        capacity = make_capacity(remaining=1)

        coordinator = make_coordinator(
            "planner", [], capacity=capacity, with_branches=True, mock_health_check=True
        )

        async def mock_collect() -> list[QueueEntry]:
            return []

        coordinator._collect_frozen_queue = mock_collect

        install_issue_loader(coordinator, {})

        emit_calls = []
        coordinator._emit_dispatch_intent = (
            lambda role, issue, tick_id: emit_calls.append((role, issue))
        )

        await coordinator.coordinate()

        assert len(emit_calls) == 0

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case,expected_count,expected_numbers",
        [
            ("normal", 2, {100, 101}),
            ("supervisor_only", 0, set()),
        ],
    )
    async def test_blocked_issues_collection_filtering(
        self,
        make_capacity,
        make_coordinator,
        test_case,
        expected_count,
        expected_numbers,
    ) -> None:
        """BLOCKED issues bypass qualify gate; supervisor-labeled issues excluded."""
        capacity = make_capacity(remaining=2)

        coordinator = make_coordinator(
            "manager",
            [],
            capacity=capacity,
            mock_health_check=True,
        )

        # Create raw payloads based on test case
        if test_case == "normal":
            raw_payloads = [
                {
                    "number": 100,
                    "title": "Issue 100",
                    "labels": [{"name": "state/blocked"}],
                    "assignees": [{"login": "manager-bot"}],
                    "html_url": "https://github.com/owner/repo/issues/100",
                },
                {
                    "number": 101,
                    "title": "Issue 101",
                    "labels": [{"name": "state/blocked"}],
                    "assignees": [{"login": "manager-bot"}],
                    "html_url": "https://github.com/owner/repo/issues/101",
                },
                # Supervisor-labeled issue should be filtered out
                {
                    "number": 102,
                    "title": "Issue 102",
                    "labels": [{"name": "supervisor"}, {"name": "state/blocked"}],
                    "assignees": [{"login": "manager-bot"}],
                    "html_url": "https://github.com/owner/repo/issues/102",
                },
            ]
        else:  # supervisor_only
            raw_payloads = [
                {
                    "number": 102,
                    "title": "Issue 102",
                    "labels": [{"name": "supervisor"}, {"name": "state/blocked"}],
                    "assignees": [{"login": "manager-bot"}],
                    "html_url": "https://github.com/owner/repo/issues/102",
                }
            ]

        # Mock GitHub API to return raw payloads for BLOCKED state
        def mock_list_issues(**kwargs):
            if kwargs.get("label") == "state/blocked":
                return raw_payloads
            return []

        coordinator._github.list_issues = mock_list_issues

        # Directly test _poll_issues_by_state for BLOCKED state
        blocked_issues = await coordinator._poll_issues_by_state(IssueState.BLOCKED)

        # Verify filtering behavior
        assert len(blocked_issues) == expected_count
        assert {issue.number for issue in blocked_issues} == expected_numbers

        # Verify all returned issues have BLOCKED state
        for issue in blocked_issues:
            assert issue.state == IssueState.BLOCKED
