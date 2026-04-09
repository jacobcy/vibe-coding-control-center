"""Event handlers for manager events.

Handlers for manager execution and flow dispatching.
"""

from typing import Callable

from loguru import logger

from vibe3.agents.execution_lifecycle import ExecutionLifecycleService
from vibe3.agents.execution_role_policy import ExecutionRolePolicyService
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.domain.events.flow_lifecycle import IssueStateChanged
from vibe3.domain.events.manager import (
    DomainEvent,
    ManagerExecutionCompleted,
    ManagerExecutionStarted,
    ManagerFlowDispatched,
    ManagerFlowQueued,
)
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.flow_service import FlowService


def handle_issue_state_changed_for_manager(event: IssueStateChanged) -> None:
    """Handle IssueStateChanged event for manager chain.

    当 issue 进入 state/claimed 时触发 manager execution.
    通过 ExecutionRolePolicyService 统一解析 backend、prompt、session 配置。
    通过 ExecutionLifecycleService 统一记录 started/completed/failed。

    Args:
        event: IssueStateChanged event
    """
    # Only handle state/claimed
    if event.to_state != "claimed":
        return

    logger.bind(
        domain="manager_handler",
        issue_number=event.issue_number,
        from_state=event.from_state,
        to_state=event.to_state,
    ).info("Manager handler triggered for claimed issue")

    # Resolve execution policy via ExecutionRolePolicyService
    config = OrchestraConfig.from_settings()
    policy = ExecutionRolePolicyService(config)

    backend = policy.resolve_backend("manager")
    prompt_contract = policy.resolve_prompt_contract("manager")
    session_strategy = policy.resolve_session_strategy("manager")

    logger.bind(
        domain="manager_handler",
        issue_number=event.issue_number,
        backend=backend,
        prompt_template=prompt_contract.template,
        session_mode=session_strategy.mode,
    ).debug("Resolved execution policy for manager role")

    # Setup ExecutionLifecycleService for unified lifecycle recording
    store = SQLiteClient()
    lifecycle = ExecutionLifecycleService(store)

    # Build target branch name (will be used for lifecycle tracking)
    # Format: task/issue-{number} (manager convention)
    target = f"task/issue-{event.issue_number}"

    # Record execution started
    lifecycle.record_started(
        role="manager",
        target=target,
        actor="orchestra:manager",
        refs={"issue_number": str(event.issue_number)},
    )

    logger.bind(
        domain="manager_handler",
        issue_number=event.issue_number,
        target=target,
    ).debug("Recorded manager execution started")

    # Fetch full issue details from GitHub API
    github_client = GitHubClient()
    issue_data = github_client.view_issue(event.issue_number)

    if issue_data is None or isinstance(issue_data, str):
        logger.bind(
            domain="manager_handler",
            issue_number=event.issue_number,
            error="issue_not_found",
        ).error("Failed to fetch issue details from GitHub")

        # Record failed lifecycle event
        lifecycle.record_failed(
            role="manager",
            target=target,
            actor="orchestra:manager",
            error="Failed to fetch issue details from GitHub",
            refs={"issue_number": str(event.issue_number)},
        )
        return

    # Build IssueInfo from GitHub API response
    issue_info = IssueInfo.from_github_payload(issue_data)

    if issue_info is None:
        logger.bind(
            domain="manager_handler",
            issue_number=event.issue_number,
            error="invalid_issue_data",
        ).error("Failed to parse issue data from GitHub response")

        lifecycle.record_failed(
            role="manager",
            target=target,
            actor="orchestra:manager",
            error="Failed to parse issue data",
            refs={"issue_number": str(event.issue_number)},
        )
        return

    # Ensure state is CLAIMED (override parsed state with event state)
    issue_info.state = IssueState.CLAIMED

    # Delegate to ManagerExecutor with resolved policy
    manager_executor = ManagerExecutor(config)

    logger.bind(
        domain="manager_handler",
        issue_number=event.issue_number,
        backend=backend,
    ).debug("Delegating to ManagerExecutor")

    # Execute manager dispatch and record lifecycle outcome
    try:
        dispatch_result = manager_executor.dispatch_manager(issue_info)

        if dispatch_result:
            lifecycle.record_completed(
                role="manager",
                target=target,
                actor="orchestra:manager",
                detail=f"Manager dispatched issue #{event.issue_number}",
                refs={"issue_number": str(event.issue_number)},
            )

            logger.bind(
                domain="manager_handler",
                issue_number=event.issue_number,
                backend=backend,
                prompt_template=prompt_contract.template,
                session_mode=session_strategy.mode,
                target=target,
            ).success("Manager execution completed via domain event")
        else:
            lifecycle.record_failed(
                role="manager",
                target=target,
                actor="orchestra:manager",
                error="ManagerExecutor.dispatch_manager returned False",
                refs={"issue_number": str(event.issue_number)},
            )

            logger.bind(
                domain="manager_handler",
                issue_number=event.issue_number,
            ).warning("Manager dispatch returned False")

    except Exception as exc:
        lifecycle.record_failed(
            role="manager",
            target=target,
            actor="orchestra:manager",
            error=str(exc),
            refs={"issue_number": str(event.issue_number)},
        )

        logger.bind(
            domain="manager_handler",
            issue_number=event.issue_number,
        ).exception(f"Manager dispatch failed: {exc}")


def handle_manager_execution_started(event: ManagerExecutionStarted) -> None:
    """Handle ManagerExecutionStarted event.

    Logs manager execution start and updates flow state.
    """
    logger.bind(
        domain="events",
        event="manager_execution_started",
        issue=event.issue_number,
        branch=event.branch,
    ).info("Manager execution started")

    # Record event in flow history
    flow_service = FlowService()
    flow_service.store.add_event(
        event.branch,
        "manager_started",
        event.actor,
        detail=f"Manager started processing issue #{event.issue_number}",
        refs={"issue": str(event.issue_number)},
    )


def handle_manager_execution_completed(event: ManagerExecutionCompleted) -> None:
    """Handle ManagerExecutionCompleted event.

    Logs manager execution completion and updates flow state.
    """
    logger.bind(
        domain="events",
        event="manager_execution_completed",
        issue=event.issue_number,
        branch=event.branch,
    ).success("Manager execution completed")

    # Record event in flow history
    flow_service = FlowService()
    flow_service.store.add_event(
        event.branch,
        "manager_completed",
        event.actor,
        detail=f"Manager completed processing issue #{event.issue_number}",
        refs={"issue": str(event.issue_number)},
    )


def handle_manager_flow_dispatched(event: ManagerFlowDispatched) -> None:
    """Handle ManagerFlowDispatched event.

    Logs flow dispatch and adds comment to issue.
    """
    logger.bind(
        domain="events",
        event="manager_flow_dispatched",
        issue=event.issue_number,
        branch=event.branch,
        tmux=event.tmux_session,
    ).info("Manager flow dispatched")

    # Add comment to issue
    GitHubClient().add_comment(
        event.issue_number,
        f"🚀 Manager dispatched flow to tmux session: `{event.tmux_session}`\n\n"
        f"Branch: `{event.branch}`",
    )


def handle_manager_flow_queued(event: ManagerFlowQueued) -> None:
    """Handle ManagerFlowQueued event.

    Logs flow queue and adds comment to issue.
    """
    logger.bind(
        domain="events",
        event="manager_flow_queued",
        issue=event.issue_number,
        reason=event.reason,
        active_flows=event.active_flows,
        capacity=event.max_capacity,
    ).warning("Manager flow queued due to capacity")

    # Add comment to issue
    GitHubClient().add_comment(
        event.issue_number,
        f"⏳ Flow queued due to capacity limit\n\n"
        f"**Reason**: {event.reason}\n"
        f"**Active flows**: {event.active_flows}/{event.max_capacity}\n\n"
        f"Flow will be dispatched when capacity becomes available.",
    )


def register_manager_handlers() -> None:
    """Register all manager event handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    # Subscribe to IssueStateChanged for manager trigger
    subscribe(
        "IssueStateChanged",
        cast(Callable[[DomainEvent], None], handle_issue_state_changed_for_manager),
    )

    subscribe(
        "ManagerExecutionStarted",
        cast(Callable[[DomainEvent], None], handle_manager_execution_started),
    )
    subscribe(
        "ManagerExecutionCompleted",
        cast(Callable[[DomainEvent], None], handle_manager_execution_completed),
    )
    subscribe(
        "ManagerFlowDispatched",
        cast(Callable[[DomainEvent], None], handle_manager_flow_dispatched),
    )
    subscribe(
        "ManagerFlowQueued",
        cast(Callable[[DomainEvent], None], handle_manager_flow_queued),
    )

    logger.bind(domain="events").info("Manager event handlers registered")
