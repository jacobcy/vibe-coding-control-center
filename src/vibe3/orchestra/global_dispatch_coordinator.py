"""Frozen-queue dispatch coordinator.

Queue rule:
1. Only collect a new queue when the frozen queue is empty
2. Keep queued issues resident across ticks
3. After dispatch, an issue waits for its state label to change
4. Once state changes, move that issue to the front of the queue
5. Only capacity uses tmux session counting
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.logging import append_orchestra_event

if TYPE_CHECKING:
    from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService


@dataclass
class QueueEntry:
    """Frozen queue entry tracked only by issue identity and wait state."""

    issue_number: int
    waiting_state: str | None = None


class GlobalDispatchCoordinator:
    """Frozen queue with state-change requeue semantics."""

    def __init__(
        self,
        capacity: CapacityService,
        dispatch_services: list[StateLabelDispatchService],
    ) -> None:
        self._capacity = capacity
        self._dispatch_services = dispatch_services
        self._frozen_queue: list[QueueEntry] | None = None
        self._github = (
            dispatch_services[0]._github if dispatch_services else None  # noqa: SLF001
        )
        self._repo = dispatch_services[0].config.repo if dispatch_services else None

    async def coordinate(self) -> None:
        """Run one heartbeat tick against the frozen queue."""
        if self._frozen_queue is None or len(self._frozen_queue) == 0:
            self._frozen_queue = await self._collect_frozen_queue()
            if not self._frozen_queue:
                append_orchestra_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: no candidates",
                )
                return

        self._promote_progressed_entries()

        import subprocess

        try:
            result = subprocess.run(
                ["tmux", "list-sessions"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            vibe3_count = len(
                [line for line in result.stdout.splitlines() if "vibe3-" in line]
            )
            live_worker_count = max(0, vibe3_count - 1)
            max_capacity = self._capacity.config.max_concurrent_flows
            available_slots = max(0, max_capacity - live_worker_count)
        except Exception:
            status = self._capacity.get_capacity_status("manager")
            available_slots = status["remaining"]

        if available_slots <= 0:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: capacity full",
            )
            return

        dispatched_count = 0
        index = 0
        while index < len(self._frozen_queue):
            if dispatched_count >= available_slots:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: dispatched={dispatched_count} "
                    f"skipped remaining (capacity full)",
                )
                return

            entry = self._frozen_queue[index]
            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None:
                self._frozen_queue.pop(index)
                continue

            if issue.state in {
                IssueState.BLOCKED,
                IssueState.FAILED,
                IssueState.MERGE_READY,
                IssueState.DONE,
            }:
                self._frozen_queue.pop(index)
                continue

            if entry.waiting_state is not None:
                index += 1
                continue

            service = self._find_service_for_state(issue.state)
            if service is None:
                self._frozen_queue.pop(index)
                continue

            try:
                service._emit_dispatch_intent(issue)
                entry.waiting_state = issue.state.value
                dispatched_count += 1

                green = "\033[32m"
                reset = "\033[0m"
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: {green}dispatched{reset} "
                    f"#{issue.number} ({service.role_def.registry_role})",
                )
                logger.bind(
                    domain="global_dispatch",
                    role=service.role_def.registry_role,
                    issue=issue.number,
                ).info(
                    f"Dispatched #{issue.number} " f"({service.role_def.registry_role})"
                )
            except Exception as exc:
                logger.bind(
                    domain="global_dispatch",
                    role=service.role_def.registry_role,
                    issue=issue.number,
                ).error(f"Dispatch failed for #{issue.number}: {exc}")
            index += 1

        if dispatched_count > 0:
            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatched="
                f"{dispatched_count}{reset}",
            )

    async def _collect_frozen_queue(self) -> list[QueueEntry]:
        """Collect a new frozen queue only when the current one is empty."""
        queue: list[QueueEntry] = []
        seen_issue_numbers: set[int] = set()
        for state in (
            IssueState.REVIEW,
            IssueState.IN_PROGRESS,
            IssueState.CLAIMED,
            IssueState.HANDOFF,
            IssueState.READY,
        ):
            service = self._find_service_for_state(state)
            if service is None:
                continue
            try:
                issues = await service.collect_ready_issues()
                for issue in issues:
                    if issue.number in seen_issue_numbers:
                        continue
                    seen_issue_numbers.add(issue.number)
                    queue.append(QueueEntry(issue_number=issue.number))
            except Exception as exc:
                logger.bind(
                    domain="global_dispatch",
                    state=state.value,
                ).error(f"collect_ready_issues failed for {state.value}: {exc}")
        return queue

    def _promote_progressed_entries(self) -> None:
        """Move completed-progress issues to the front of the frozen queue."""
        if not self._frozen_queue:
            return

        promoted: list[QueueEntry] = []
        retained: list[QueueEntry] = []
        for entry in self._frozen_queue:
            if entry.waiting_state is None:
                retained.append(entry)
                continue

            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None:
                continue

            current_state = issue.state.value
            if current_state == entry.waiting_state:
                retained.append(entry)
                continue

            entry.waiting_state = None
            promoted.append(entry)
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: requeued #{entry.issue_number} "
                f"to front after state change to {current_state}",
            )

        if promoted:
            self._frozen_queue = promoted + retained
        else:
            self._frozen_queue = retained

    def _load_issue(self, issue_number: int) -> IssueInfo | None:
        """Load the current issue snapshot for an already-frozen issue."""
        if self._github is None:
            return None
        try:
            payload = self._github.view_issue(issue_number, repo=self._repo)
        except Exception as exc:
            logger.bind(domain="global_dispatch", issue=issue_number).error(
                f"view_issue failed for #{issue_number}: {exc}"
            )
            return None
        if not isinstance(payload, dict):
            return None
        return IssueInfo.from_github_payload(payload)

    def _find_service_for_state(
        self,
        state: IssueState,
    ) -> StateLabelDispatchService | None:
        """Find the dispatch service responsible for a state label."""
        for service in self._dispatch_services:
            if service.role_def.trigger_state == state:
                return service
        return None
