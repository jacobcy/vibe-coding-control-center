"""Flow lifecycle operations - close, block, abort."""

from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.flow import CloseTargetDecision, CreateDecision
from vibe3.services.flow_abort_ops import abort_flow_impl
from vibe3.services.flow_close_target import resolve_close_target


class FlowLifecycleMixin:
    """Mixin providing flow lifecycle operations."""

    store: Any
    git_client: Any

    def can_create_from_current_worktree(
        self: Any,
        current_branch: str,
    ) -> CreateDecision:
        """Determine if a new flow can be created in the current worktree.

        Rules:
        - active: reject - current flow is in progress
        - blocked: allow from current branch - user wants to create downstream flow
        - done/aborted/stale/no-flow: require fresh worktree check

        Args:
            current_branch: Current git branch name

        Returns:
            CreateDecision with allowed status and guidance
        """
        flow_data = self.store.get_flow_state(current_branch)

        if not flow_data:
            return CreateDecision(
                allowed=True,
                reason="No active flow in current worktree",
                start_ref="origin/main",
                requires_new_worktree=False,
            )

        status = flow_data.get("flow_status", "active")

        if status == "active":
            return CreateDecision(
                allowed=False,
                reason=(
                    "Current flow is active - cannot create new flow in same worktree"
                ),
                requires_new_worktree=True,
                guidance=(
                    "Use 'vibe3 wtnew <name>' to create a new worktree for new features"
                ),
            )

        if status == "blocked":
            return CreateDecision(
                allowed=True,
                reason=(
                    "Current flow is blocked - "
                    "can create downstream flow from current branch"
                ),
                start_ref=current_branch,
                allow_base_current=True,
                requires_new_worktree=False,
            )

        if status in ("done", "aborted", "stale"):
            return CreateDecision(
                allowed=True,
                reason=f"Current flow is {status} - safe to start new target",
                start_ref="origin/main",
                requires_new_worktree=False,
            )

        return CreateDecision(
            allowed=True,
            reason="Unknown status - allowing with caution",
            start_ref="origin/main",
            requires_new_worktree=False,
        )

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
        """Close flow and delete branch.

        Args:
            branch: Branch name
            check_pr: Whether to check PR merge status

        Raises:
            RuntimeError: If PR not merged and check_pr is True
        """
        git = GitClient()

        logger.bind(
            domain="flow",
            action="close",
            branch=branch,
            check_pr=check_pr,
        ).info("Closing flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

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
                    git.create_branch(target_branch, start_ref="origin/main")
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

        task_issue_number = flow_data.get("task_issue_number")
        if task_issue_number is not None:
            if not GitHubClient().close_issue(task_issue_number):
                raise RuntimeError(
                    f"Failed to close bound task issue #{task_issue_number}"
                )

        self.store.update_flow_state(branch, flow_status="done")

        self.store.add_event(
            branch,
            "flow_closed",
            "system",
            f"Flow closed, branch '{branch}' deleted",
        )
        if task_issue_number is not None:
            self.store.add_event(
                branch,
                "task_issue_closed",
                "system",
                f"Task issue #{task_issue_number} closed",
            )

        switched_to_target = switched_before_delete
        try:
            if not switched_before_delete:
                if git.branch_exists(target_branch):
                    git.switch_branch(target_branch)
                else:
                    git.create_branch(target_branch, start_ref="origin/main")
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
        """Mark flow as blocked.

        Args:
            branch: Branch name
            reason: Optional blocking reason
            blocked_by_issue: Optional issue number that blocks this flow
        """
        logger.bind(
            domain="flow",
            action="block",
            branch=branch,
            reason=reason,
            blocked_by_issue=blocked_by_issue,
        ).info("Blocking flow")

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            raise RuntimeError(f"Flow not found for branch {branch}")

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

    def abort_flow(
        self: Any,
        branch: str,
    ) -> None:
        """Abort flow and delete branch.

        Args:
            branch: Branch name
        """
        abort_flow_impl(self.store, branch)
