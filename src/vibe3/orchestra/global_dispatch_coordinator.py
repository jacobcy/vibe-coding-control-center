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
from vibe3.orchestra.queue_persistence import QueuePersistence
from vibe3.utils.label_utils import should_skip_from_queue

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService


MAX_RETRY_COUNT = 3


@dataclass
class QueueEntry:
    """Frozen queue entry tracked only by issue identity and wait state."""

    issue_number: int
    collected_state: str | None = None
    waiting_state: str | None = None
    retry_count: int = 0


class GlobalDispatchCoordinator:
    """Frozen queue with state-change requeue semantics."""

    def __init__(
        self,
        capacity: CapacityService,
        dispatch_services: list[StateLabelDispatchService],
        registry: "SessionRegistryService | None" = None,
        store: "SQLiteClient | None" = None,
    ) -> None:
        self._capacity = capacity
        self._dispatch_services = dispatch_services
        self._registry = registry
        self._persistence = QueuePersistence(store)
        self._github = (
            dispatch_services[0]._github if dispatch_services else None  # noqa: SLF001
        )
        self._repo = dispatch_services[0].config.repo if dispatch_services else None
        # Union manager_usernames from all services
        self._manager_usernames = tuple(
            username
            for service in dispatch_services
            for username in service.config.manager_usernames
        )
        # Get supervisor_label from first service (should be same for all)
        self._supervisor_label = (
            dispatch_services[0].config.supervisor_handoff.issue_label
            if dispatch_services
            else "supervisor"
        )

        # Load persisted queue on initialization
        self._frozen_queue: list[QueueEntry] | None = (
            self._persistence.load_persisted_queue()
        )

    def _get_available_capacity(self) -> int:
        """Check current capacity and return available slots."""
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
            return max(0, max_capacity - live_worker_count)
        except Exception:
            status = self._capacity.get_capacity_status("manager")
            return status["remaining"]

    def _dispatch_ready_issues(self, available_slots: int) -> int:
        """Dispatch ready issues from the queue.

        Returns the number of issues dispatched.
        """
        if self._frozen_queue is None:
            return 0

        dispatched_count = 0
        index = 0
        while index < len(self._frozen_queue):
            if dispatched_count >= available_slots:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: dispatched={dispatched_count} "
                    f"skipped remaining (capacity full)",
                )
                return dispatched_count

            entry = self._frozen_queue[index]
            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None:
                self._frozen_queue.pop(index)
                self._persistence.remove_persisted_entry(entry.issue_number)
                continue

            if should_skip_from_queue(
                issue,
                supervisor_label=self._supervisor_label,
                manager_usernames=self._manager_usernames,
                require_manager_assignee=True,
            ):
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{issue.number} "
                    "from queue (supervisor or assignee check failed)",
                )
                self._frozen_queue.pop(index)
                self._persistence.remove_persisted_entry(entry.issue_number)
                continue

            if issue.state == IssueState.DONE:
                self._frozen_queue.pop(index)
                self._persistence.remove_persisted_entry(entry.issue_number)
                continue

            # Update collected_state to current state for tracking
            # No longer "avoid" state changes - assignee check is sufficient
            entry.collected_state = issue.state.value

            if entry.waiting_state is not None:
                index += 1
                continue

            # Per-issue active session gate:
            # Prevent dispatch if ANY worker role session is still live for this issue.
            if self._registry is not None:
                active = self._registry.get_live_sessions_for_issue(
                    issue_number=entry.issue_number,
                    roles=["manager", "planner", "executor", "reviewer"],
                )
                if active:
                    append_orchestra_event(
                        "dispatcher",
                        f"GlobalDispatchCoordinator: skipped #{entry.issue_number} "
                        f"(active session: role={active[0].get('role')})",
                    )
                    index += 1
                    continue

            # For BLOCKED issues: run qualify gate at intent time (lazy evaluation)
            if issue.state == IssueState.BLOCKED:
                blocked_service = self._find_service_for_state(IssueState.BLOCKED)
                if blocked_service is None:
                    self._frozen_queue.pop(index)
                    continue
                target_state = blocked_service.qualify_blocked_issue(issue)
                if target_state is None:
                    # Still blocked — remove from frozen queue, re-collected next tick
                    self._frozen_queue.pop(index)
                    continue
                service = self._find_service_for_state(target_state)
                if service is None:
                    self._frozen_queue.pop(index)
                    continue
                entry.collected_state = target_state.value
            else:
                service = self._find_service_for_state(issue.state)
                if service is None:
                    self._frozen_queue.pop(index)
                    continue

            try:
                green = "\033[32m"
                reset = "\033[0m"
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: {green}dispatch-intent{reset} "
                    f"#{issue.number} ({service.role_def.registry_role})",
                )
                service._emit_dispatch_intent(issue)
                # For BLOCKED issues, waiting_state must track the TARGET state
                # (qualify gate already changed GitHub labels to target_state).
                # Using issue.state.value ("blocked") cause _promote_progressed_entries
                # to detect a false state change and re-dispatch on the next tick.
                entry.waiting_state = entry.collected_state
                dispatched_count += 1

                # Persist updated waiting_state
                self._persistence.update_persisted_entry(entry)

                logger.bind(
                    domain="global_dispatch",
                    role=service.role_def.registry_role,
                    issue=issue.number,
                ).info(
                    f"Emitted dispatch intent for #{issue.number} "
                    f"({service.role_def.registry_role})"
                )
            except Exception as exc:
                logger.bind(
                    domain="global_dispatch",
                    role=service.role_def.registry_role,
                    issue=issue.number,
                ).error(f"Dispatch failed for #{issue.number}: {exc}")
            index += 1

        return dispatched_count

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
            # Persist newly collected queue entries
            self._persistence.persist_queue_entries(self._frozen_queue)

        self._promote_progressed_entries()

        # Check and remove entries exceeding retry threshold
        removed_entries = self._persistence.check_retry_threshold(
            self._frozen_queue or []
        )
        if removed_entries and self._frozen_queue:
            removed_numbers = {e.issue_number for e in removed_entries}
            self._frozen_queue = [
                e for e in self._frozen_queue if e.issue_number not in removed_numbers
            ]

        # Check if queue was emptied by _promote_progressed_entries
        # (e.g., all issues became blocked/done)
        if not self._frozen_queue:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: queue emptied by state changes",
            )
            return

        available_slots = self._get_available_capacity()

        if available_slots <= 0:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: capacity full",
            )
            return

        dispatched_count = self._dispatch_ready_issues(available_slots)

        if dispatched_count > 0:
            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatch-intent="
                f"{dispatched_count}{reset}",
            )

    async def _collect_frozen_queue(self) -> list[QueueEntry]:
        """Collect a new frozen queue only when the current one is empty."""
        queue: list[QueueEntry] = []
        seen_issue_numbers: set[int] = set()
        append_orchestra_event(
            "dispatcher",
            "GlobalDispatchCoordinator: starting queue collection",
        )
        for state in (
            IssueState.REVIEW,
            IssueState.MERGE_READY,
            IssueState.IN_PROGRESS,
            IssueState.CLAIMED,
            IssueState.HANDOFF,
            IssueState.BLOCKED,  # Qualify gate runs at intent time
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
                    queue.append(
                        QueueEntry(
                            issue_number=issue.number,
                            collected_state=state.value,
                        )
                    )
            except Exception as exc:
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: collect_ready_issues failed for "
                    f"{state.value}: {exc}",
                )
                logger.bind(
                    domain="global_dispatch",
                    state=state.value,
                ).error(f"collect_ready_issues failed for {state.value}: {exc}")
        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: queue collection complete, "
            f"total={len(queue)} issues",
        )
        return queue

    def _promote_progressed_entries(self) -> None:
        """Move progressed issues to the front; remove blocked/failed from queue.

        Blocked and failed states require human intervention and should not be
        automatically retried by the dispatcher. Remove them from the frozen queue
        to avoid wasting dispatch slots.
        """
        if not self._frozen_queue:
            return

        promoted: list[QueueEntry] = []
        retained: list[QueueEntry] = []
        removed: list[QueueEntry] = []
        for entry in self._frozen_queue:
            should_remove, reason = self._should_remove_entry(entry)

            if should_remove:
                if reason != "issue_not_found":
                    append_orchestra_event(
                        "dispatcher",
                        f"GlobalDispatchCoordinator: removed #{entry.issue_number} "
                        f"from queue ({reason}, requires human intervention)",
                    )
                removed.append(entry)
                continue

            if entry.waiting_state is None:
                retained.append(entry)
                continue

            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None:
                continue

            current_state = issue.state.value
            if current_state == entry.waiting_state:
                # Issue returned to same state - increment retry count
                entry.retry_count += 1
                self._persistence.update_persisted_entry(entry)

                # State unchanged. Check whether the agent session that would
                # advance it is still alive.  If no session exists the label can
                # never change ─ promote the entry for re-dispatch so the queue
                # can eventually drain and re-collect.
                if self._registry is not None:
                    active = self._registry.get_live_sessions_for_issue(
                        issue_number=entry.issue_number,
                        roles=["manager", "planner", "executor", "reviewer"],
                    )
                    if not active:
                        entry.waiting_state = None
                        promoted.append(entry)
                        append_orchestra_event(
                            "dispatcher",
                            f"GlobalDispatchCoordinator: requeued "
                            f"#{entry.issue_number} "
                            f"(no active session, state={current_state})",
                        )
                        continue
                retained.append(entry)
                continue

            # Progress detected (state changed to non-terminal) - promote to front
            entry.waiting_state = None
            entry.collected_state = current_state  # Sync with current state
            entry.retry_count = 0  # Reset retry count on successful state transition
            promoted.append(entry)
            self._persistence.update_persisted_entry(entry)
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: requeued #{entry.issue_number} "
                f"to front after state change to {current_state}",
            )

        # Update frozen queue: promoted + retained (removed entries discarded)
        if promoted or retained:
            self._frozen_queue = promoted + retained
        else:
            # All entries removed (e.g., all issues became blocked)
            # Clear frozen queue to trigger fresh collection on next tick
            self._frozen_queue = None

        # Remove deleted entries from persistence
        for entry in removed:
            self._persistence.remove_persisted_entry(entry.issue_number)

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

    def _should_remove_entry(self, entry: QueueEntry) -> tuple[bool, str]:
        """Check if entry should be removed from queue.

        Returns (should_remove, reason) tuple.
        """
        if entry.waiting_state is None:
            return False, ""

        issue = self._load_issue(entry.issue_number)
        if issue is None or issue.state is None:
            return True, "issue_not_found"

        if should_skip_from_queue(
            issue,
            supervisor_label=self._supervisor_label,
            manager_usernames=self._manager_usernames,
            require_manager_assignee=True,
        ):
            return True, "supervisor_or_assignee_check_failed"

        current_state = issue.state.value
        if current_state == "blocked":
            return True, f"state_changed_to_{current_state}"

        return False, ""
