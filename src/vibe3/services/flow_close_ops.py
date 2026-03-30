"""Implementation of flow close operations.

Includes: close, branch cleanup, PR merge guard, close target resolution,
restore branch helpers, and label sync for lifecycle events.
"""

from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.models.flow import CloseTargetDecision
from vibe3.models.orchestration import IssueState
from vibe3.models.pr import PRState
from vibe3.services.base_resolution_usecase import MAIN_BRANCH_REF
from vibe3.services.label_service import LabelService
from vibe3.services.signature_service import SignatureService

# ---------------------------------------------------------------------------
# Restore branch helpers (from flow_restore_branch.py)
# ---------------------------------------------------------------------------

_BASELINE_WORKTREE_BRANCHES: dict[str, str] = {
    "main": "main",
    "develop": "develop",
    "bugfix": "bugfix",
}


def resolve_baseline_branch_for_worktree_root(worktree_root: str | None) -> str | None:
    """Resolve baseline restore branch for a worktree root path."""
    if not worktree_root:
        return None
    worktree_name = Path(worktree_root).name.lower()
    return _BASELINE_WORKTREE_BRANCHES.get(worktree_name)


def is_baseline_restore_branch(branch: str) -> bool:
    """Return whether branch is one of baseline restore branches."""
    return branch in _BASELINE_WORKTREE_BRANCHES


# ---------------------------------------------------------------------------
# PR merge guard (from flow_pr_guard.py)
# ---------------------------------------------------------------------------


def ensure_flow_pr_merged(
    gh_client: Any,
    flow_data: dict[str, Any],
    branch: str,
) -> None:
    """Ensure the flow has a merged PR before allowing flow close."""
    pr_number = flow_data.get("pr_number")
    try:
        pr = gh_client.get_pr(pr_number) if pr_number else None
        if pr is None:
            pr = gh_client.get_pr(branch=branch)
    except Exception as error:
        raise UserError(
            "无法检查当前 flow 的 PR merge 状态。\n"
            "请先确认 PR 已 merged；\n"
            "若要放弃当前 flow，请执行 `vibe3 flow aborted`。\n"
            f"原始错误: {error}"
        ) from error

    if not pr:
        raise UserError(
            "当前 flow 未找到可关闭的 PR。\n"
            "请先执行 `vibe3 pr create` 并完成 merge；"
            "若要放弃当前 flow，请执行 `vibe3 flow aborted`。"
        )

    merged = pr.state == PRState.MERGED or pr.merged_at is not None
    if not merged:
        raise UserError(
            f"PR #{pr.number} 尚未 merged，不能关闭 flow。\n"
            "请先完成 merge；若要放弃当前 flow，请执行 `vibe3 flow aborted`。"
        )


# ---------------------------------------------------------------------------
# Close target resolution (from flow_close_target.py)
# ---------------------------------------------------------------------------


def resolve_close_target(store: Any, branch: str) -> CloseTargetDecision:
    """Resolve target branch for flow close with explicit rules."""
    dependency_store = store
    if not hasattr(dependency_store, "get_flow_dependents"):
        dependency_store = SQLiteClient()

    try:
        dependents = dependency_store.get_flow_dependents(branch)
    except Exception as e:
        logger.warning(f"Failed to query flow dependents: {e}")
        dependents = []

    if len(dependents) == 1:
        return CloseTargetDecision(
            target_branch=dependents[0],
            should_pull=False,
            reason="Single active dependent flow exists",
        )

    if len(dependents) > 1:
        logger.warning(
            f"Multiple active flows depend on '{branch}': {', '.join(dependents)}\n"
            f"Use 'vibe3 flow switch <branch>' to switch to specific branch"
        )

    return CloseTargetDecision(
        target_branch="main",
        should_pull=True,
        reason="No single active dependent - returning to safe branch",
    )


# ---------------------------------------------------------------------------
# Label sync for lifecycle events (from flow_label_sync.py)
# ---------------------------------------------------------------------------


def _is_terminal_flow_status(status: str | None) -> bool:
    """Return whether a flow status is terminal for task closing decisions."""
    return status in {"done", "aborted", "stale"}


def _issue_has_other_open_task_flows(
    store: Any, branch: str, issue_number: int
) -> bool:
    """Check if issue is still bound as task by other non-terminal flows."""
    linked_flows = store.get_flows_by_issue(issue_number, role="task")
    flows = linked_flows if isinstance(linked_flows, list) else []
    for flow in flows:
        other_branch = flow.get("branch")
        if not other_branch or other_branch == branch:
            continue
        flow_status = flow.get("flow_status")
        if not _is_terminal_flow_status(flow_status):
            return True
    return False


def sync_flow_done_task_labels(store: Any, branch: str) -> None:
    """Sync all task-role issues in a flow to state/done."""
    issue_links_raw = store.get_issue_links(branch)
    issue_links = issue_links_raw if isinstance(issue_links_raw, list) else []
    label_service = LabelService()
    for link in issue_links:
        if link.get("issue_role") != "task":
            continue
        issue_number = link.get("issue_number")
        if issue_number is None:
            continue
        if _issue_has_other_open_task_flows(store, branch, int(issue_number)):
            continue
        label_service.confirm_issue_state(
            int(issue_number),
            IssueState.DONE,
            actor="flow:done",
            force=True,
        )


def sync_flow_blocked_task_label(store: Any, branch: str) -> None:
    """Sync task-role issues in a flow to state/blocked when flow is blocked."""
    issue_links_raw = store.get_issue_links(branch)
    issue_links = issue_links_raw if isinstance(issue_links_raw, list) else []
    label_service = LabelService()
    for link in issue_links:
        if link.get("issue_role") != "task":
            continue
        issue_number = link.get("issue_number")
        if issue_number is None:
            continue
        label_service.confirm_issue_state(
            int(issue_number),
            IssueState.BLOCKED,
            actor="flow:blocked",
            force=True,
        )


# ---------------------------------------------------------------------------
# Branch cleanup and close implementation
# ---------------------------------------------------------------------------


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
