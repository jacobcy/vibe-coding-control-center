"""Simple queue-based dispatch coordinator with tick-level queue freezing.

Each tick:
1. Check if current queue is empty
2. If empty, collect new queue (freeze for this tick)
3. If not empty, continue processing current queue
4. Dispatch by fixed role order until capacity full or queue exhausted
5. End this tick

Queue freezing ensures no duplicate dispatch within a tick.
No tmux session checking - simpler and more reliable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.execution.capacity_service import CapacityService
from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.logging import append_orchestra_event

if TYPE_CHECKING:
    from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService


@dataclass
class CandidateIssue:
    """Issue candidate for dispatch."""

    issue: IssueInfo
    service: StateLabelDispatchService

    @property
    def role(self) -> str:
        """Use registry_role for capacity tracking."""
        return str(self.service.role_def.registry_role)


class GlobalDispatchCoordinator:
    """Simple queue-based coordinator with tick-level queue freezing.

    Queue Model:
    - Each tick starts with an empty queue
    - Collect all ready issues once (queue frozen for this tick)
    - Dispatch by role order until capacity full
    - Next tick sees queue empty, collects new queue
    - No tmux session checking - queue freezing prevents duplicates

    Usage:
        coordinator = GlobalDispatchCoordinator(capacity_service, dispatch_services)
        await coordinator.coordinate()
    """

    def __init__(
        self,
        capacity: CapacityService,
        dispatch_services: list[StateLabelDispatchService],
    ) -> None:
        self._capacity = capacity
        self._dispatch_services = dispatch_services
        # Per-tick frozen queue
        self._frozen_queue: list[CandidateIssue] | None = None

    async def coordinate(self) -> None:
        """Main dispatch entry: frozen queue model.

        Queue remains frozen until fully exhausted.
        Only collect new queue when previous queue is empty.
        """
        # Step 1: Check if we need to collect a new queue
        if self._frozen_queue is None or len(self._frozen_queue) == 0:
            self._frozen_queue = await self._collect_frozen_queue()
            if not self._frozen_queue:
                append_orchestra_event(
                    "dispatcher",
                    "GlobalDispatchCoordinator: no candidates",
                )
                return

        # Step 2: Get current capacity (simple tmux count)
        import subprocess

        try:
            result = subprocess.run(
                ["tmux", "list-sessions"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            # Count vibe3- sessions, subtract 1 (orchestra dispatcher session)
            vibe3_count = len(
                [line for line in result.stdout.splitlines() if "vibe3-" in line]
            )
            live_worker_count = max(0, vibe3_count - 1)  # Exclude orchestra session
            max_capacity = self._capacity.config.max_concurrent_flows
            available_slots = max(0, max_capacity - live_worker_count)
        except Exception:
            # Fallback to capacity service if tmux fails
            status = self._capacity.get_capacity_status("manager")
            available_slots = status["remaining"]

        if available_slots <= 0:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: capacity full",
            )
            return

        # Step 3: Dispatch by fixed role order from frozen queue
        role_order = ["reviewer", "executor", "planner", "manager"]

        dispatched_count = 0
        dispatched_candidates: list[CandidateIssue] = []
        for role in role_order:
            # Filter frozen queue for this role
            role_candidates = [c for c in self._frozen_queue if c.role == role]

            for candidate in role_candidates:
                # Check capacity limit
                if dispatched_count >= available_slots:
                    append_orchestra_event(
                        "dispatcher",
                        f"GlobalDispatchCoordinator: dispatched={dispatched_count} "
                        f"skipped remaining (capacity full)",
                    )
                    # Remove dispatched candidates and return
                    self._frozen_queue = [
                        c for c in self._frozen_queue if c not in dispatched_candidates
                    ]
                    return

                # Dispatch
                try:
                    candidate.service._emit_dispatch_intent(candidate.issue)
                    dispatched_count += 1
                    dispatched_candidates.append(candidate)

                    green = "\033[32m"
                    reset = "\033[0m"
                    append_orchestra_event(
                        "dispatcher",
                        f"GlobalDispatchCoordinator: {green}dispatched{reset} "
                        f"#{candidate.issue.number} ({role})",
                    )

                    logger.bind(
                        domain="global_dispatch",
                        role=role,
                        issue=candidate.issue.number,
                    ).info(f"Dispatched #{candidate.issue.number} ({role})")
                except Exception as exc:
                    logger.bind(
                        domain="global_dispatch",
                        role=role,
                        issue=candidate.issue.number,
                    ).error(f"Dispatch failed for #{candidate.issue.number}: {exc}")

        # Step 4: Remove dispatched items from frozen queue (not clear entire queue)
        # Queue remains frozen until fully exhausted
        if dispatched_count > 0:
            # Remove dispatched candidates from frozen queue
            # Keep remaining candidates for next tick
            self._frozen_queue = [
                c for c in self._frozen_queue if c not in dispatched_candidates
            ]

            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatched="
                f"{dispatched_count}{reset}",
            )

    async def _collect_frozen_queue(self) -> list[CandidateIssue]:
        """Collect all ready issues for frozen queue."""
        candidates: list[CandidateIssue] = []
        role_order = ["reviewer", "executor", "planner", "manager"]

        for role in role_order:
            service = self._find_service_for_role(role)
            if not service:
                continue

            # Scan candidates for this role (with error handling)
            try:
                issues = await service.collect_ready_issues()
                for issue in issues:
                    candidates.append(CandidateIssue(issue=issue, service=service))
            except Exception as exc:
                logger.bind(
                    domain="global_dispatch",
                    role=role,
                ).error(f"collect_ready_issues failed for {role}: {exc}")

        return candidates

    def _find_service_for_role(self, role: str) -> StateLabelDispatchService | None:
        """Find dispatch service for a role."""
        for service in self._dispatch_services:
            if service.role_def.registry_role == role:
                return service
        return None
