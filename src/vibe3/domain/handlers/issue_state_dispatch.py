"""Manager dispatch-intent handler."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import get_store
from vibe3.config import load_orchestra_config
from vibe3.domain.events.flow_lifecycle import ManagerDispatchIntent
from vibe3.domain.handler_registry import register_handler
from vibe3.exceptions import CapacityDeferredError
from vibe3.models import IssueInfo, IssueState
from vibe3.services import (
    block_manager_noop_issue,
    record_dispatch_failure_if_unexpected,
)

if TYPE_CHECKING:
    from vibe3.agents import CodeagentBackend
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.config import OrchestraConfig
    from vibe3.environment import SessionRegistryService
    from vibe3.execution import CapacityService, ExecutionCoordinator


@dataclass
class DispatchContext:
    """Pre-configured services for manager dispatch."""

    config: "OrchestraConfig"
    backend: "CodeagentBackend"
    capacity: "CapacityService"
    github_client: "GitHubClient"
    registry: "SessionRegistryService"
    coordinator: "ExecutionCoordinator"


def build_dispatch_context(
    config: "OrchestraConfig",
    store: "SQLiteClient",
) -> DispatchContext:
    """Construct all dispatch services from base dependencies."""
    from vibe3.agents import CodeagentBackend
    from vibe3.environment import SessionRegistryService
    from vibe3.execution import CapacityService, ExecutionCoordinator

    backend = CodeagentBackend()
    return DispatchContext(
        config=config,
        backend=backend,
        capacity=CapacityService(config, store, backend),
        github_client=_lazy_github_client(),
        registry=SessionRegistryService(store=store, backend=backend),
        coordinator=ExecutionCoordinator(config, store, backend=backend),
    )


def _lazy_github_client() -> "GitHubClient":
    from vibe3.clients import GitHubClient

    return GitHubClient()


@register_handler("ManagerDispatchIntent")
def handle_manager_dispatch_intent(
    event: ManagerDispatchIntent,
    /,
    dispatch_context: DispatchContext | None = None,
) -> None:
    """Dispatch manager from an authoritative dispatch-intent event."""
    if event.actor == "human:resume":
        logger.bind(
            domain="issue_state_dispatch_handler",
            issue_number=event.issue_number,
            trigger_state=event.trigger_state,
            actor=event.actor,
        ).info("Skipping auto-dispatch for human resume event")
        return

    if event.trigger_state not in {
        IssueState.READY.value,
        IssueState.HANDOFF.value,
    }:
        return

    logger.bind(
        domain="issue_state_dispatch_handler",
        role="manager",
        issue_number=event.issue_number,
        trigger_state=event.trigger_state,
        branch=event.branch,
    ).info("Manager dispatch intent received, scheduling async dispatch")

    async def _do_dispatch(ctx: DispatchContext) -> None:
        from vibe3.roles import build_manager_request

        def _block_for_noop(reason: str) -> None:
            logger.bind(
                domain="issue_state_dispatch_handler",
                role="manager",
                issue_number=event.issue_number,
            ).error(reason)
            block_manager_noop_issue(
                issue_number=event.issue_number,
                repo=None,
                reason=reason,
                actor="agent:manager",
            )

        loop = asyncio.get_running_loop()

        # Early capacity check BEFORE expensive work (GitHub fetch, coordinator setup)
        # to avoid wasteful network/DB operations when system is at capacity
        if not ctx.capacity.can_dispatch("manager"):
            return  # CapacityService.can_dispatch already logs INFO

        target_state = (
            IssueState.READY
            if event.trigger_state == IssueState.READY.value
            else IssueState.HANDOFF
        )

        if event.issue_title is not None:
            issue_info: IssueInfo | None = IssueInfo(
                number=event.issue_number,
                title=event.issue_title,
                state=target_state,
            )
        else:
            from vibe3.clients import GITHUB_DEFAULT_VIEW_FIELDS

            issue_data = await loop.run_in_executor(
                None,
                lambda: ctx.github_client.view_issue(
                    event.issue_number, fields=list(GITHUB_DEFAULT_VIEW_FIELDS)  # type: ignore[call-overload]
                ),
            )

            if issue_data is None or isinstance(issue_data, str):
                _block_for_noop(
                    "Failed to fetch issue details from GitHub for manager dispatch"
                )
                return

            issue_info = IssueInfo.from_github_payload(issue_data)
            if issue_info is None:
                _block_for_noop(
                    "Failed to parse issue data from GitHub"
                    " response for manager dispatch"
                )
                return

            issue_info.state = target_state

        if issue_info is None:
            _block_for_noop("Issue info is None, cannot dispatch manager role")
            return

        # Phase 2: diff-based simple test task routing
        if _should_reroute_to_supervisor(issue_info, ctx.github_client, ctx.config):
            _reroute_to_supervisor(issue_info, ctx.github_client, ctx.config)
            return

        try:
            request = await loop.run_in_executor(
                None,
                lambda: build_manager_request(
                    ctx.config,
                    issue_info,
                    registry=ctx.registry,
                    tick_id=event.tick_id,
                ),
            )

        except CapacityDeferredError as exc:
            # Capacity defer is normal — just log and return (don't block)
            logger.bind(
                domain="issue_state_dispatch_handler",
                role="manager",
                issue_number=event.issue_number,
            ).info(f"Manager dispatch deferred: {exc.message}")
            return

        if request is None:
            _block_for_noop("Failed to prepare role execution request")
            return

        try:
            result = await loop.run_in_executor(
                None, lambda: ctx.coordinator.dispatch_execution(request)
            )
            record_dispatch_failure_if_unexpected(
                result=result,
                role="manager",
                issue_number=event.issue_number,
                branch=event.branch,
                tick_id=event.tick_id,
                dispatch_source="automatic",
            )

            if result.launched:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                ).success("Role execution launched via ExecutionCoordinator")
            elif result.skipped:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                ).info(f"Role dispatch skipped: {result.reason}")
            else:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                ).warning(f"Role dispatch failed: {result.reason}")

        except Exception as exc:
            record_dispatch_failure_if_unexpected(
                role="manager",
                issue_number=event.issue_number,
                branch=event.branch,
                exception=exc,
                tick_id=event.tick_id,
                dispatch_source="automatic",
            )
            logger.bind(
                domain="issue_state_dispatch_handler",
                role="manager",
                issue_number=event.issue_number,
            ).exception(f"Role dispatch failed: {exc}")

    try:
        loop = asyncio.get_running_loop()
        if dispatch_context is None:
            config = load_orchestra_config()
            with get_store() as store:
                dispatch_context = build_dispatch_context(config, store)
                loop.create_task(
                    _do_dispatch(dispatch_context),
                    name=f"manager-dispatch-{event.issue_number}-{event.trigger_state}",
                )
        else:
            loop.create_task(
                _do_dispatch(dispatch_context),
                name=f"manager-dispatch-{event.issue_number}-{event.trigger_state}",
            )
    except RuntimeError:
        # No event loop running, run synchronously
        if dispatch_context is None:
            config = load_orchestra_config()
            with get_store() as store:
                dispatch_context = build_dispatch_context(config, store)
        asyncio.run(_do_dispatch(dispatch_context))


def _should_reroute_to_supervisor(
    issue: IssueInfo,
    github: "GitHubClient",
    config: "OrchestraConfig",
) -> bool:
    """Check if issue has a simple test diff that can be rerouted.

    Includes flow state check to ensure safe reroute:
    - Only reroute when flow is in safe states (ready/claimed/blocked)
    - Never reroute when in_progress or handoff with progress

    Args:
        issue: Issue information
        github: GitHub client for PR and flow state queries
        config: Orchestra config for repo info

    Returns:
        True if issue should be rerouted to supervisor, False otherwise
    """
    from vibe3.services.label_service import LabelService
    from vibe3.services.simple_test_task_assessor import (
        MAX_FILES,
        MAX_LINES,
        is_simple_test_from_diff,
    )

    # Check issue state label first - only reroute in safe states
    label_service = LabelService(repo=config.repo)
    issue_state = label_service.get_state(issue.number)

    # Safe states: ready, claimed, or blocked (未开始执行的状态)
    # Unsafe states: in_progress, handoff (已开始工作的状态)
    safe_states = {IssueState.READY, IssueState.CLAIMED, IssueState.BLOCKED, None}
    if issue_state not in safe_states:
        state_val = issue_state.value if issue_state else "None"
        logger.bind(
            domain="issue_state_dispatch_handler",
            issue_number=issue.number,
            issue_state=issue_state.value if issue_state else None,
        ).warning(f"Skipping reroute: issue in unsafe state '{state_val}'")
        return False

    # Find linked PRs for this issue's branch
    branch = f"issue-{issue.number}"
    prs = github.list_prs_for_branch(branch, repo=config.repo)
    if not prs:
        return False

    pr = prs[0]
    files = github.get_pr_files(pr.number)
    diff = github.get_pr_diff(pr.number)

    if not files or not diff:
        return False

    # Count additions/deletions from diff
    additions = sum(1 for line in diff.split("\n") if line.startswith("+"))
    deletions = sum(1 for line in diff.split("\n") if line.startswith("-"))

    is_simple = is_simple_test_from_diff(files, additions, deletions)
    if is_simple:
        total_lines = additions + deletions
        logger.bind(
            domain="issue_state_dispatch_handler",
            issue_number=issue.number,
            pr_number=pr.number,
            files=len(files),
            lines=total_lines,
        ).info(
            f"Simple test task detected: {len(files)} files, "
            f"{total_lines} lines (threshold: ≤{MAX_FILES} files, ≤{MAX_LINES} lines)"
        )

    return is_simple


def _reroute_to_supervisor(
    issue: IssueInfo,
    github: "GitHubClient",
    config: "OrchestraConfig",
) -> None:
    """Close current issue and create new one for supervisor/apply.

    Args:
        issue: Issue information
        github: GitHub client for issue operations
        config: Orchestra config for repo info
    """
    from vibe3.services.simple_test_task_assessor import MAX_FILES, MAX_LINES

    # Close original with explanation
    github.close_issue(
        issue.number,
        comment=(
            "Closed: rerouted to supervisor/apply fast track "
            "(simple test-only change detected)."
        ),
    )

    # Create new issue with supervisor labels
    new_number = github.create_issue(
        title=f"[fast-track] {issue.title}",
        body=(
            f"Rerouted from #{issue.number} (simple test task auto-detection).\n\n"
            f"Original issue: #{issue.number}\n"
            f"Reason: test-only changes within complexity threshold "
            f"(≤{MAX_FILES} files, ≤{MAX_LINES} lines)."
        ),
        labels=["supervisor", "state/handoff"],
    )

    if new_number:
        logger.bind(
            domain="issue_state_dispatch_handler",
            original=issue.number,
            new=new_number,
        ).info(f"Rerouted #{issue.number} → #{new_number} (supervisor/apply)")
