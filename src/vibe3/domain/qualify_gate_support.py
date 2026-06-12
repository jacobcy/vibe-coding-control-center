"""Helper functions for qualify gate logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Literal, cast

from vibe3.clients import GitClient
from vibe3.models import FlowStatusResponse, IssueState, PRResponse
from vibe3.services import (
    BlockedStateService,
    FlowCleanupService,
    FlowService,
    FlowStatusService,
    IssueFlowService,
    LabelService,
    TaskResumeOperations,
    infer_resume_label,
)

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.config import OrchestraConfig
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
    from vibe3.models import CoordinationTruth, IssueInfo


def _append_orchestra_event(channel: str, message: str) -> None:
    from vibe3.observability import append_orchestra_event

    append_orchestra_event(channel, message)


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
        "qualify_gate skip (#{issue.number}): issue closed on GitHub — "
        "terminalizing local flow",
    )

    flow_state = store.get_flow_state(branch)
    current_status = flow_state.get("flow_status") if flow_state else None
    if current_status not in ("done", "aborted"):
        flow_status_service_cls(
            store=store,
            git_client=flow_manager.git,
            github_client=github,
        ).mark_flow_aborted(branch, f"Issue #{issue.number} closed on GitHub")

    flow_cleanup_service_cls(store=store).cleanup_flow_scene(
        branch,
        include_remote=False,
        terminate_sessions=True,
        keep_flow_record=True,
    )


def resume_dep_resolved(
    *,
    branch: str,
    issue_number: int,
    dep_issue_numbers: list[int],
    store: "SQLiteClient",
    github: "GitHubClient",
    config: "OrchestraConfig",
    blocked_state_service_cls: type[Any] = BlockedStateService,
    label_service_cls: type[Any] = LabelService,
    flow_state_model: type[Any] | None = None,
    infer_resume_label_fn: Callable[[Any], IssueState] = infer_resume_label,
) -> IssueState:
    from vibe3.models import FlowState

    flow_state = store.get_flow_state(branch)
    if flow_state:
        try:
            target_state = infer_resume_label_fn(
                (flow_state_model or FlowState).model_validate(flow_state)
            )
        except Exception:
            target_state = IssueState.READY
    else:
        target_state = IssueState.READY

    service = blocked_state_service_cls(
        github_client=github,
        label_service=label_service_cls(repo=config.repo),
        store=store,
    )
    result = service.unblock(
        branch=branch,
        target_state=target_state,
        issue_number=issue_number,
        actor="orchestra:qualify",
        detail=f"Dependencies #{', #'.join(map(str, dep_issue_numbers))} closed",
    )
    if not result.label_cleared:
        raise RuntimeError(
            f"Failed to clear state/blocked label on issue #{issue_number}. "
            f"Manual fix: gh issue edit {issue_number} --remove-label state/blocked"
        )

    _append_orchestra_event(
        "dispatcher",
        "qualify_gate dep_resolved #"
        f"{issue_number}: dependencies #{', #'.join(map(str, dep_issue_numbers))} "
        f"closed, cleared blocked state to {target_state.to_label()}",
    )
    return target_state


def align_blocked_state(
    *,
    issue_number: int,
    branch: str,
    truth: "CoordinationTruth",
    labels: list[str],
    flow_state: dict[str, object] | None,
    blocked_label: str,
    store: "SQLiteClient",
    github: "GitHubClient",
    config: "OrchestraConfig",
    blocked_state_service_cls: type[Any] = BlockedStateService,
    label_service_cls: type[Any] = LabelService,
) -> None:
    label_blocked = blocked_label in labels

    if not flow_state or flow_state.get("flow_status") != "blocked":
        blocked_state_service_cls(
            github_client=github,
            store=store,
            label_service=label_service_cls(repo=config.repo),
        ).write_cache(
            branch=branch,
            reason=truth.blocked_reason,
            blocked_by_issue=truth.blocked_by_issue,
            actor="system:qualify_gate",
        )
        _append_orchestra_event(
            "dispatcher",
            "qualify_gate align_blocked #"
            f"{issue_number}: local cache synced to blocked from body truth",
        )

    if blocked_label not in labels:
        try:
            label_service_cls(repo=config.repo).confirm_issue_state(
                issue_number,
                IssueState.BLOCKED,
                actor="orchestra:qualify_gate",
                force=True,
            )
            label_blocked = True
        except Exception:
            pass

    _append_orchestra_event(
        "dispatcher",
        format_blocked_skip_event(
            issue_number=issue_number,
            truth=truth,
            flow_state=flow_state,
            label_blocked=label_blocked,
        ),
    )


def has_stale_blocked_state(
    *,
    labels: list[str],
    flow_state: dict[str, object] | None,
    blocked_label: str,
) -> bool:
    if not flow_state:
        return False
    label_blocked = blocked_label in labels
    local_blocked = bool(
        flow_state.get("blocked_by_issue")
        or flow_state.get("blocked_reason")
        or flow_state.get("flow_status") == "blocked"
    )
    return label_blocked or local_blocked


def source_value(source: object | None) -> str:
    return str(value) if (value := getattr(source, "value", None)) else "none"


def format_blocked_skip_event(
    *,
    issue_number: int,
    truth: "CoordinationTruth",
    flow_state: dict[str, object] | None,
    label_blocked: bool,
) -> str:
    blocked_by = f"#{truth.blocked_by_issue}" if truth.blocked_by_issue else "none"
    local_flow_status = (
        str(flow_state.get("flow_status") or "none") if flow_state else "none"
    )
    return (
        f"qualify_gate skip #{issue_number}: blocked per body truth "
        f"(projection_state={truth.projection_state or 'none'}, "
        f"projection_source={source_value(truth.projection_state_source)}, "
        f"blocked_reason={truth.blocked_reason or 'none'}, "
        f"blocked_reason_source={source_value(truth.blocked_reason_source)}, "
        f"blocked_by_issue={blocked_by}, "
        f"blocked_by_issue_source={source_value(truth.blocked_by_issue_source)}, "
        f"local_flow_status={local_flow_status}, "
        f"label_blocked={label_blocked})"
    )


def auto_resume_blocked(
    *,
    issue_number: int,
    branch: str,
    labels: list[str],
    flow_state: dict[str, object] | None,
    store: "SQLiteClient",
    github: "GitHubClient",
    config: "OrchestraConfig",
    task_resume_operations_cls: type[Any] = TaskResumeOperations,
    flow_service_cls: type[Any] = FlowService,
    label_service_cls: type[Any] = LabelService,
    issue_flow_service_cls: type[Any] = IssueFlowService,
    infer_resume_label_fn: Callable[[Any], IssueState] = infer_resume_label,
) -> IssueState:
    from vibe3.models import FlowState

    if flow_state:
        fs_obj = FlowState.model_validate(flow_state)
        target_label = infer_resume_label_fn(fs_obj)
    else:
        target_label = IssueState.READY

    flow_status_value = (
        flow_state.get("flow_status", "blocked") if flow_state else "blocked"
    )
    flow = FlowStatusResponse(
        branch=branch,
        flow_slug=str(flow_state.get("flow_slug") or branch) if flow_state else branch,
        flow_status=cast(
            Literal["active", "blocked", "done", "stale", "aborted"],
            flow_status_value,
        ),
        latest_actor="orchestra:qualify",
        task_issue_number=issue_number,
    )
    operations = task_resume_operations_cls(
        git_client=GitClient(),
        github_client=github,
        flow_service=flow_service_cls(store=store),
        label_service=label_service_cls(repo=config.repo),
        issue_flow_service=issue_flow_service_cls(store=store),
    )
    operations.reset_issue_to_ready(
        issue_number=issue_number,
        resume_kind="blocked",
        flow=flow,
        repo=config.repo,
        reason="qualify gate auto-resume",
        label_state="",
    )

    _append_orchestra_event(
        "dispatcher",
        f"qualify_gate auto_resume #{issue_number}: unblocked to {target_label.value}",
    )
    return target_label


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
