"""Simple queue-based dispatch coordinator.

Each tick:
1. Calculate available capacity based on live tmux sessions
2. Scan candidates by fixed role order (reviewer → executor → planner → manager)
3. Dispatch all eligible tasks (no live session conflict, within capacity)
4. End this tick

Removed complexity:
- No frontier/stage gate
- No in-flight/launching state machine
- No global sorting
- No "scan again after dispatch"
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
    """Simple queue-based coordinator.

    Fixed role order dispatch without complex state machines.

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

    async def coordinate(self) -> None:
        """Main dispatch entry: scan once, batch dispatch by role order."""
        # Step 1: Get current capacity
        status = self._capacity.get_capacity_status("manager")
        available_slots = status["remaining"]

        if available_slots <= 0:
            append_orchestra_event(
                "dispatcher",
                "GlobalDispatchCoordinator: capacity full",
            )
            return

        # Step 2: Scan candidates by fixed role order
        # Priority: reviewer → executor → planner → manager
        role_order = ["reviewer", "executor", "planner", "manager"]

        dispatched_count = 0
        for role in role_order:
            # Find service for this role
            service = self._find_service_for_role(role)
            if not service:
                continue

            # Scan candidates for this role (with error handling)
            try:
                candidates = await service.collect_ready_issues()
            except Exception as exc:
                logger.bind(
                    domain="global_dispatch",
                    role=role,
                ).error(f"collect_ready_issues failed for {role}: {exc}")
                continue

            for issue in candidates:
                # Check capacity limit
                if dispatched_count >= available_slots:
                    append_orchestra_event(
                        "dispatcher",
                        f"GlobalDispatchCoordinator: dispatched={dispatched_count} "
                        f"skipped remaining (capacity full)",
                    )
                    return

                # Check if branch already has live session (prevent duplicate dispatch)
                branch = f"task/issue-{issue.number}"
                live_sessions = (
                    self._capacity._registry.get_truly_live_sessions_for_target(
                        role=role,
                        branch=branch,
                        target_id=str(issue.number),
                    )
                )
                if live_sessions:
                    logger.bind(
                        domain="global_dispatch",
                        role=role,
                        issue=issue.number,
                    ).debug(f"Skip #{issue.number} ({role}): live session exists")
                    continue

                # Dispatch
                try:
                    service._emit_dispatch_intent(issue)
                    dispatched_count += 1

                    green = "\033[32m"
                    reset = "\033[0m"
                    append_orchestra_event(
                        "dispatcher",
                        f"GlobalDispatchCoordinator: {green}dispatched{reset} "
                        f"#{issue.number} ({role})",
                    )

                    logger.bind(
                        domain="global_dispatch",
                        role=role,
                        issue=issue.number,
                    ).info(f"Dispatched #{issue.number} ({role})")
                except Exception as exc:
                    logger.bind(
                        domain="global_dispatch",
                        role=role,
                        issue=issue.number,
                    ).error(f"Dispatch failed for #{issue.number}: {exc}")

        # End of tick
        if dispatched_count > 0:
            green = "\033[32m"
            reset = "\033[0m"
            append_orchestra_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: {green}dispatched="
                f"{dispatched_count}{reset}",
            )

    def _find_service_for_role(self, role: str) -> StateLabelDispatchService | None:
        """Find dispatch service for a role."""
        for service in self._dispatch_services:
            if service.role_def.registry_role == role:
                return service
        return None
