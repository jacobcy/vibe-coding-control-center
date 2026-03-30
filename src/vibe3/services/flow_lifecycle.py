"""Flow lifecycle operations - close, block, abort."""

from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.exceptions import UserError
from vibe3.models.flow import CloseTargetDecision, CreateDecision
from vibe3.services.flow_close_ops import (
    close_flow_impl,
    resolve_close_target,
    sync_flow_blocked_task_label,
)
from vibe3.services.flow_create_decision import decide_create_from_current_worktree
from vibe3.services.signature_service import SignatureService


class FlowLifecycleMixin:
    """Mixin providing flow lifecycle operations."""

    store: Any
    git_client: Any

    def can_create_from_current_worktree(
        self: Any,
        current_branch: str,
    ) -> CreateDecision:
        """Determine if a new flow can be created in the current worktree."""
        return decide_create_from_current_worktree(self.store, current_branch)

    def resolve_close_target(
        self: Any,
        branch: str,
    ) -> CloseTargetDecision:
        """Resolve target branch for flow close with explicit rules."""
        return resolve_close_target(self.store, branch)

    def close_flow(
        self: Any,
        branch: str,
        check_pr: bool = True,
        actor: str | None = None,
        delete_worktree: bool = False,
    ) -> bool:
        """Close flow and delete branch."""
        return close_flow_impl(
            self.store,
            branch,
            check_pr=check_pr,
            actor=actor,
            delete_worktree=delete_worktree,
            resolve_close_target_fn=lambda b: self.resolve_close_target(b),
        )

    def block_flow(
        self: Any,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
        actor: str | None = None,
    ) -> None:
        """Mark flow as blocked."""
        logger.bind(
            domain="flow",
            action="block",
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
        ).info("Blocking flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise UserError(
                f"当前分支 '{branch}' 没有 flow\n"
                f"先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支"
            )

        effective_actor = SignatureService.resolve_actor(
            explicit_actor=actor,
            flow_actor=flow_data.get("latest_actor"),
        )

        if blocked_by_issue:
            from vibe3.services.task_service import TaskService

            TaskService().link_issue(
                branch,
                blocked_by_issue,
                role="dependency",
                actor=effective_actor,
            )

        blocked_by = reason or (
            f"Blocked by issue #{blocked_by_issue}" if blocked_by_issue else None
        )

        self.store.update_flow_state(
            branch,
            flow_status="blocked",
            blocked_by=blocked_by,
            latest_actor=effective_actor,
        )

        self.store.add_event(
            branch,
            "flow_blocked",
            effective_actor,
            f"Flow blocked{': ' + reason if reason else ''}",
        )
        sync_flow_blocked_task_label(self.store, branch)

    def abort_flow(
        self: Any,
        branch: str,
        actor: str | None = None,
    ) -> None:
        """Abort flow and delete branch."""
        flow_data = self.store.get_flow_state(branch) or {}
        effective_actor = SignatureService.resolve_actor(
            explicit_actor=actor,
            flow_actor=flow_data.get("latest_actor"),
        )
        _abort_flow_impl(self.store, branch, actor=effective_actor)


def _abort_flow_impl(store: Any, branch: str, actor: str = "workflow") -> None:
    """Abort flow and delete branch."""
    git = GitClient()

    logger.bind(domain="flow", action="abort", branch=branch).info("Aborting flow")

    flow_data = store.get_flow_state(branch)
    if not flow_data:
        raise RuntimeError(f"Flow not found for branch {branch}")

    if git.branch_exists(branch):
        git.delete_branch(branch, force=True)

    try:
        git.delete_remote_branch(branch)
    except Exception:
        logger.bind(domain="flow", action="abort", branch=branch).warning(
            "Failed to delete remote branch, continuing"
        )

    store.update_flow_state(branch, flow_status="aborted", latest_actor=actor)
    store.add_event(
        branch,
        "flow_aborted",
        actor,
        f"Flow aborted, branch '{branch}' deleted",
    )
