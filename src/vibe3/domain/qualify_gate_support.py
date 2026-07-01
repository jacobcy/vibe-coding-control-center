"""Helper functions for qualify gate logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibe3.models import PRResponse
from vibe3.services.flow import FlowCleanupService, FlowStatusService

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
    from vibe3.models import IssueInfo


def _append_orchestra_event(
    channel: str, message: str, *, color: str | None = None
) -> None:
    from vibe3.observability import append_orchestra_event

    append_orchestra_event(channel, message, color=color)


def terminalize_closed_issue(
    *,
    issue: "IssueInfo",
    branch: str,
    store: "SQLiteClient",
    github: "GitHubClient",
    flow_manager: "FlowManagerProtocol",
    flow_status_service_cls: type[Any] = FlowStatusService,
    flow_cleanup_service_cls: type[Any] = FlowCleanupService,
) -> None:
    if not branch:
        return

    _append_orchestra_event(
        "dispatcher",
        f"qualify_gate skip (#{issue.number}): issue closed on GitHub — "
        "terminalizing local flow",
    )

    flow_state = store.get_flow_state(branch)
    current_status = flow_state.get("flow_status") if flow_state else None
    # Issue #3189: review/failed are PR-backed terminal states — preserve them
    # like aborted (route through eligibility heuristic instead of overwriting).
    if current_status not in ("done", "aborted", "review", "failed"):
        flow_status_service_cls(
            store=store,
            git_client=flow_manager.git,
            github_client=github,
        ).mark_flow_aborted(branch, f"Issue #{issue.number} closed on GitHub")
    elif current_status in ("aborted", "review", "failed") and flow_state:
        # Heuristic: all phases done + PR merged → transition to done
        flow_status_service = flow_status_service_cls(
            store=store,
            git_client=flow_manager.git,
            github_client=github,
        )
        eligible, pr_number = flow_status_service.evaluate_aborted_to_done_eligibility(
            flow_state, branch
        )
        if eligible:
            flow_status_service.transition_aborted_to_done(
                branch,
                f"Issue #{issue.number} closed, all phases complete, PR merged",
                pr_number=pr_number,
            )

    flow_cleanup_service_cls(store=store).cleanup_flow_scene(
        branch,
        include_remote=False,
        terminate_sessions=True,
        keep_flow_record=True,
    )


def transition_to_review(
    *,
    branch: str,
    pr: "PRResponse",
    store: "SQLiteClient",
    flow_manager: "FlowManagerProtocol",
    github: "GitHubClient",
    flow_status_service_cls: type[Any] = FlowStatusService,
) -> None:
    flow_status_service_cls(
        store=store,
        git_client=flow_manager.git,
        github_client=github,
    ).mark_flow_status(
        branch,
        "review",
        f"PR #{pr.number} is open with running worker",
        "flow_auto_review",
        "auto_review_flow",
    )
    _append_orchestra_event(
        "qualify_gate",
        "Auto-transitioned flow "
        f"{branch} to review: PR #{pr.number} open with running worker",
    )
