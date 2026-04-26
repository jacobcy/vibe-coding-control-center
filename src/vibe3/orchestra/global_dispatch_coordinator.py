"""Frozen-queue dispatch coordinator.

Queue rule:
1. Only collect a new queue when the frozen queue is empty
2. Keep queued issues resident across ticks
3. After dispatch, an issue waits for its state label to change
4. Once state changes, move that issue to the front of the queue
5. Only capacity uses tmux session counting
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.logging import append_orchestra_event

if TYPE_CHECKING:
    from vibe3.models.orchestra_config import OrchestraConfig
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
        config: "OrchestraConfig | None" = None,
    ) -> None:
        self._capacity = capacity
        self._dispatch_services = dispatch_services
        self._frozen_queue: list[QueueEntry] | None = None
        self._github = (
            dispatch_services[0]._github if dispatch_services else None  # noqa: SLF001
        )
        self._repo = dispatch_services[0].config.repo if dispatch_services else None
        self._config = (
            config
            if config is not None
            else (dispatch_services[0].config if dispatch_services else None)
        )

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

    async def _backfill_manager_assigned_issues(self) -> list[IssueInfo]:
        """Backfill issues already assigned to manager usernames but not yet labeled.

        This reconciles the frozen queue with GitHub's current assignee state when
        the service restarts after being offline. Issues assigned to manager
        usernames are candidate for manager dispatch even if they don't have
        the state/ready label yet.

        Returns:
            List of filtered candidate issues ready for dispatch
        """
        if self._github is None or self._config is None:
            return []

        # Handle case where config doesn't have manager_usernames attribute
        # For example: old mocks/tests that predate this feature
        manager_usernames = getattr(self._config, "manager_usernames", [])
        if not manager_usernames:
            return []

        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: backfill starting for "
            f"{len(manager_usernames)} manager username(s)",
        )

        # Get executor for blocking GitHub API calls - max_workers must be > 0
        max_workers = max(1, len(manager_usernames))
        executor = ThreadPoolExecutor(max_workers=max_workers)

        async def query_user(username: str) -> list[dict[str, object]]:
            return await asyncio.get_event_loop().run_in_executor(
                executor,
                lambda: self._github.list_issues(  # type: ignore[union-attr]
                    limit=50,
                    state="open",
                    assignee=username,
                    repo=self._repo,
                ),
            )

        # Query all manager usernames in parallel
        tasks = [query_user(username) for username in manager_usernames]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect all issues, deduplicate by issue number
        seen_issue_numbers: set[int] = set()
        all_issues: list[IssueInfo] = []

        total_found = 0
        for result in results:
            if isinstance(result, Exception):
                logger.bind(domain="global_dispatch").error(
                    f"Backfill query failed: {result}"
                )
                continue

            if not isinstance(result, list):
                continue

            # Type narrowing: result must be list[dict[str, object]] here
            result_list: list[dict[str, object]] = result
            total_found += len(result_list)
            for item in result_list:
                raw_number = item.get("number", 0)
                if isinstance(raw_number, (int, str)):
                    issue_number = int(raw_number)
                else:
                    issue_number = 0
                if issue_number == 0 or issue_number in seen_issue_numbers:
                    continue

                # Parse issue from GitHub payload
                issue = IssueInfo.from_github_payload(item)
                if issue is None:
                    continue

                seen_issue_numbers.add(issue_number)
                all_issues.append(issue)

        # Apply filtering: already has flow, unresolved dependencies, blocked/failed
        if not self._dispatch_services:
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: backfill found {len(all_issues)} "
                f"unique issues among {total_found} total, but no dispatch services "
                f"available for filtering",
            )
            return []

        # Get the manager service for dependency checking - we need the store
        manager_service = next(
            (
                s
                for s in self._dispatch_services
                if s.role_def.trigger_state == IssueState.READY
            ),
            None,
        )

        filtered: list[IssueInfo] = []
        filtered_out = {
            "has_flow": 0,
            "blocked": 0,
            "failed": 0,
            "dependency_unsatisfied": 0,
        }

        for issue in all_issues:
            # Check for blocked/failed labels
            if IssueState.BLOCKED.to_label() in issue.labels:
                filtered_out["blocked"] += 1
                continue
            if IssueState.FAILED.to_label() in issue.labels:
                filtered_out["failed"] += 1
                continue

            # Check if issue already has a flow - skip if yes
            has_flow = False
            if manager_service is not None:
                # Check flows using manager service's store
                flows = manager_service._store.get_flows_by_issue(
                    issue.number, role="task"
                )
                if flows and any(str(flow.get("branch", "")).strip() for flow in flows):
                    has_flow = True

            if has_flow:
                filtered_out["has_flow"] += 1
                continue

            # Check dependencies if we have manager service
            if manager_service is not None:
                dependencies = manager_service._get_issue_dependencies(issue.number)
                if dependencies:
                    unresolved = [
                        d
                        for d in dependencies
                        if not manager_service._is_dependency_satisfied(d)
                    ]
                    if unresolved:
                        filtered_out["dependency_unsatisfied"] += 1
                        # Mark as blocked if there are unresolved dependencies
                        if len(unresolved) > 0 and hasattr(
                            manager_service, "_mark_issue_waiting"
                        ):
                            manager_service._mark_issue_waiting(
                                issue.number, unresolved
                            )
                        continue

            filtered.append(issue)

        append_orchestra_event(
            "dispatcher",
            f"GlobalDispatchCoordinator: backfill complete - found {len(all_issues)} "
            f"unique issues, {len(filtered)} passed filters. Filtered out: "
            f"has_flow={filtered_out['has_flow']}, blocked={filtered_out['blocked']}, "
            f"failed={filtered_out['failed']}, "
            f"dependency_unsatisfied={filtered_out['dependency_unsatisfied']}",
        )

        executor.shutdown(wait=False, cancel_futures=True)
        return filtered

    async def _collect_frozen_queue(self) -> list[QueueEntry]:
        """Collect a new frozen queue only when the current one is empty.

        Backfill is run first to pick up any issues already assigned to managers
        that were assigned while the service was offline. Then label-based
        collection runs, with deduplication across both sources.
        """
        queue: list[QueueEntry] = []
        seen_issue_numbers: set[int] = set()

        # Step 1: Backfill manager-assigned issues (runs first to ensure prioritization)
        try:
            backfill_issues = await self._backfill_manager_assigned_issues()
            for issue in backfill_issues:
                if issue.number in seen_issue_numbers:
                    continue
                seen_issue_numbers.add(issue.number)
                queue.append(QueueEntry(issue_number=issue.number))
        except Exception as exc:
            logger.bind(domain="global_dispatch").error(f"Backfill failed: {exc}")

        # Step 2: Collect from state-label based services
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
            if entry.waiting_state is None:
                retained.append(entry)
                continue

            issue = self._load_issue(entry.issue_number)
            if issue is None or issue.state is None:
                retained.append(entry)
                continue

            current_state = issue.state.value
            if current_state == entry.waiting_state:
                retained.append(entry)
                continue

            # Blocked/failed states require human intervention - remove from queue
            if current_state in ("blocked", "failed"):
                removed.append(entry)
                append_orchestra_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: removed #{entry.issue_number} "
                    f"from queue (state changed to {current_state}, "
                    f"requires human intervention)",
                )
                continue

            # Progress detected (state changed to non-terminal) - promote to front
            entry.waiting_state = None
            promoted.append(entry)
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: requeued #{entry.issue_number} "
                f"to front after state change to {current_state}",
            )

        # Update frozen queue: promoted + retained (removed entries discarded)
        if promoted or retained:
            self._frozen_queue = promoted + retained

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
