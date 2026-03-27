"""Flow lifecycle operations - close, block, abort."""

from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import UserError
from vibe3.models.flow import CloseTargetDecision, CreateDecision
from vibe3.services.base_resolution_usecase import MAIN_BRANCH_REF
from vibe3.services.flow_abort_ops import abort_flow_impl
from vibe3.services.flow_close_target import resolve_close_target
from vibe3.services.flow_create_decision import decide_create_from_current_worktree
from vibe3.services.flow_label_sync import (
    sync_flow_blocked_task_label,
    sync_flow_done_task_labels,
)
from vibe3.services.flow_pr_guard import ensure_flow_pr_merged


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
    ) -> None:
        """Close flow and delete branch."""
        git = GitClient()

        logger.bind(
            domain="flow",
            action="close",
            branch=branch,
            check_pr=check_pr,
        ).info("Closing flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise UserError(
                f"当前分支 '{branch}' 没有 flow\n"
                f"先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支"
            )
        if check_pr:
            ensure_flow_pr_merged(GitHubClient(), flow_data, branch)

        try:
            close_target = self.resolve_close_target(branch)
            target_branch = close_target.target_branch
            should_pull = close_target.should_pull
        except Exception as e:
            logger.warning(f"Failed to resolve close target: {e}")
            target_branch, should_pull = "main", True

        if target_branch == "main" and git.is_branch_occupied_by_worktree(
            target_branch
        ):
            target_branch = git.get_safe_main_branch_name()
            should_pull = False
            logger.bind(
                domain="flow",
                action="close",
                branch=branch,
                target=target_branch,
            ).info("Main branch is occupied; switching to safe branch")

        switched_before_delete = False
        if git.get_current_branch() == branch:
            try:
                if git.branch_exists(target_branch):
                    git.switch_branch(target_branch)
                else:
                    git.create_branch(target_branch, start_ref=MAIN_BRANCH_REF)
            except Exception as e:
                raise RuntimeError(
                    f"Cannot switch away from closing branch '{branch}' "
                    f"to '{target_branch}': {e}"
                ) from e

            switched_before_delete = True
            logger.bind(
                domain="flow",
                action="close",
                branch=branch,
                target=target_branch,
            ).info("Switched away from closing branch")

        if git.is_branch_occupied_by_worktree(branch):
            logger.bind(
                domain="flow",
                action="close",
                branch=branch,
            ).warning(
                f"Branch '{branch}' is checked out in another worktree. "
                "Skipping local branch deletion."
            )
        elif git.branch_exists(branch):
            git.delete_branch(branch, force=True)

        try:
            git.delete_remote_branch(branch)
        except Exception:
            logger.bind(
                domain="flow",
                action="close",
                branch=branch,
            ).warning("Failed to delete remote branch, continuing")

        self.store.update_flow_state(branch, flow_status="done")

        self.store.add_event(
            branch,
            "flow_closed",
            "system",
            f"Flow closed, branch '{branch}' deleted",
        )
        sync_flow_done_task_labels(self.store, branch)

        switched_to_target = switched_before_delete
        try:
            if not switched_before_delete:
                if git.branch_exists(target_branch):
                    git.switch_branch(target_branch)
                else:
                    git.create_branch(target_branch, start_ref=MAIN_BRANCH_REF)
                switched_to_target = True
                logger.bind(
                    domain="flow",
                    action="close",
                    branch=branch,
                    target=target_branch,
                ).info("Switched after flow close")

            if should_pull and switched_to_target:
                try:
                    git._run(["pull"])
                    logger.info(
                        f"Switched to {target_branch} and pulled latest changes"
                    )
                except Exception as e:
                    logger.warning(f"Failed to pull: {e}")

        except Exception as e:
            logger.warning(f"Failed to switch after close: {e}")

    def block_flow(
        self: Any,
        branch: str,
        reason: str | None = None,
        blocked_by_issue: int | None = None,
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

        if blocked_by_issue:
            from vibe3.services.task_service import TaskService

            TaskService().link_issue(branch, blocked_by_issue, role="dependency")

        blocked_by = reason or (
            f"Blocked by issue #{blocked_by_issue}" if blocked_by_issue else None
        )

        self.store.update_flow_state(
            branch,
            flow_status="blocked",
            blocked_by=blocked_by,
        )

        self.store.add_event(
            branch,
            "flow_blocked",
            "system",
            f"Flow blocked{': ' + reason if reason else ''}",
        )
        sync_flow_blocked_task_label(flow_data)

    def abort_flow(
        self: Any,
        branch: str,
    ) -> None:
        """Abort flow and delete branch."""
        abort_flow_impl(self.store, branch)
