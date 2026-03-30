"""Implementation of flow close operations."""

from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import UserError
from vibe3.services.base_resolution_usecase import MAIN_BRANCH_REF
from vibe3.services.flow_label_sync import sync_flow_done_task_labels
from vibe3.services.flow_pr_guard import ensure_flow_pr_merged
from vibe3.services.flow_restore_branch import (
    is_baseline_restore_branch,
    resolve_baseline_branch_for_worktree_root,
)
from vibe3.services.signature_service import SignatureService


def delete_branch_with_cleanup(
    git: GitClient,
    branch: str,
    delete_worktree: bool = False,
) -> bool:
    """Handle worktree occupation and delete branch."""
    _log = logger.bind(domain="flow", action="close", branch=branch)
    branch_deleted = False

    occupied_wts = git.get_worktrees_for_branch(branch)
    if occupied_wts:
        if delete_worktree:
            for wt_path in occupied_wts:
                _log.bind(worktree=wt_path).info("Deleting occupied worktree")
                git._run(["worktree", "remove", wt_path, "--force"])
        else:
            _log.warning(
                f"Branch '{branch}' is checked out in another "
                "worktree. Skipping local branch deletion."
            )

    if not git.is_branch_occupied_by_worktree(branch) and git.branch_exists(branch):
        git.delete_branch(branch, force=True, skip_if_worktree=True)
        _log.info("Local branch deleted")
        branch_deleted = True

    try:
        git.delete_remote_branch(branch)
        _log.info("Remote branch deleted")
    except Exception:
        _log.warning("Failed to delete remote branch, continuing")

    return branch_deleted


def close_flow_impl(
    store: Any,
    branch: str,
    check_pr: bool = True,
    actor: str | None = None,
    delete_worktree: bool = False,
    resolve_close_target_fn: Any = None,
) -> bool:
    """Close flow and delete branch implementation.

    Args:
        store: SQLiteClient or similar
        branch: Branch to close
        check_pr: Whether to verify PR is merged
        actor: Actor performing the action
        delete_worktree: Whether to delete worktree if branch is occupied
        resolve_close_target_fn: Callable to resolve close target branch

    Returns:
        True if branch was actually deleted, False otherwise
    """
    git = GitClient()
    _log = logger.bind(domain="flow", action="close", branch=branch)
    _log.info("Closing flow", check_pr=check_pr)

    flow_data = store.get_flow_state(branch)
    if not flow_data:
        raise UserError(
            f"当前分支 '{branch}' 没有 flow\n"
            f"先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支"
        )
    if check_pr:
        ensure_flow_pr_merged(GitHubClient(), flow_data, branch)
    effective_actor = SignatureService.resolve_actor(
        explicit_actor=actor,
        flow_actor=flow_data.get("latest_actor"),
    )

    try:
        if resolve_close_target_fn:
            close_target = resolve_close_target_fn(branch)
        else:
            from vibe3.services.flow_close_target import resolve_close_target

            close_target = resolve_close_target(store, branch)
        target_branch = close_target.target_branch
        should_pull = close_target.should_pull
    except Exception as e:
        logger.warning(f"Failed to resolve close target: {e}")
        target_branch, should_pull = "main", True

    worktree_root = ""
    try:
        worktree_root = git.get_worktree_root()
    except Exception as e:
        _log.warning(f"Failed to resolve worktree root: {e}")

    baseline_branch = resolve_baseline_branch_for_worktree_root(worktree_root)
    if target_branch == "main":
        if baseline_branch:
            target_branch = baseline_branch
            should_pull = True
            _log.bind(worktree_root=worktree_root).info(
                "Using baseline restore branch for current worktree"
            )
        else:
            target_branch = git.get_safe_main_branch_name()
            should_pull = False
            _log.bind(worktree_root=worktree_root).info(
                "Non-baseline worktree; using safe restore branch"
            )

    if is_baseline_restore_branch(target_branch) and git.is_branch_occupied_by_worktree(
        target_branch
    ):
        target_branch = git.get_safe_main_branch_name()
        should_pull = False
        _log.info("Main branch is occupied; switching to safe branch")

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
        _log.bind(target=target_branch).info("Switched away from closing branch")

    branch_deleted: bool = delete_branch_with_cleanup(
        git, branch, delete_worktree=delete_worktree
    )

    store.update_flow_state(
        branch,
        flow_status="done",
        latest_actor=effective_actor,
    )

    event_message = "Flow closed"
    if branch_deleted:
        event_message += f", branch '{branch}' deleted"
    else:
        event_message += f", branch '{branch}' preserved (occupied by other worktree)"

    store.add_event(
        branch,
        "flow_closed",
        effective_actor,
        event_message,
    )
    sync_flow_done_task_labels(store, branch)

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
                git._run(["pull", "origin", target_branch])
                logger.info(
                    f"Switched to {target_branch} and synced origin/{target_branch}"
                )
            except Exception as e:
                logger.warning(f"Failed to pull: {e}")

    except Exception as e:
        logger.warning(f"Failed to switch after close: {e}")

    return branch_deleted
