"""Auto-scene recovery for damaged task/issue-* worktrees."""

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.contracts import ExecutionLaunchResult, ExecutionRequest
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.logging import append_orchestra_event

if TYPE_CHECKING:
    from vibe3.environment.session_registry import SessionRegistryService


def _read_worktree_head(worktree_path: Path) -> str | None:
    """Return the active branch name, or HEAD for detached worktrees."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


class AutoSceneRecoveryService:
    """Best-effort recovery for damaged auto task scenes."""

    def __init__(self, store: SQLiteClient) -> None:
        self.store = store

    def maybe_reset_damaged_scene(
        self,
        request: ExecutionRequest,
        error_msg: str,
        resolve_repo_path: Callable[[ExecutionRequest], Path],
        registry: "SessionRegistryService",
    ) -> ExecutionLaunchResult | None:
        """Recover damaged task/issue-* scenes when no live session owns the branch."""
        branch = request.target_branch
        if (
            request.worktree_requirement != WorktreeRequirement.PERMANENT
            or not branch.startswith("task/issue-")
        ):
            return None

        live_sessions = registry.get_truly_live_sessions_for_branch(branch)
        if live_sessions:
            return None

        repo_path = resolve_repo_path(request)
        target_path = repo_path / ".worktrees" / branch

        from vibe3.environment.worktree_support import (
            find_worktree_by_path,
            find_worktree_for_branch,
        )

        path_exists = target_path.exists()
        path_registered = find_worktree_by_path(repo_path, target_path)
        branch_worktree = find_worktree_for_branch(repo_path, branch)
        actual_head = (
            _read_worktree_head(target_path)
            if path_exists and path_registered
            else None
        )

        damage_signals: list[str] = []
        if "already exists" in error_msg and path_exists:
            damage_signals.append("canonical worktree path already exists")
        if path_registered and branch_worktree is None:
            damage_signals.append("registered worktree is not bound to target branch")
        if actual_head == "HEAD":
            damage_signals.append("registered worktree has detached HEAD")
        elif actual_head and actual_head != branch:
            damage_signals.append(f"registered worktree points at {actual_head}")

        if not damage_signals:
            return None

        return self._execute_recovery(
            request=request,
            branch=branch,
            damage_signals=damage_signals,
            error_msg=error_msg,
        )

    def _execute_recovery(
        self,
        request: ExecutionRequest,
        branch: str,
        damage_signals: list[str],
        error_msg: str,
    ) -> ExecutionLaunchResult | None:
        from vibe3.exceptions.error_codes import E_EXEC_AUTO_SCENE_RESET
        from vibe3.services import (
            FlowCleanupService,
            LiveSessionsDetectedError,
            record_error,
        )

        detail = "; ".join(damage_signals)
        recovery_actor = "orchestra:auto-recover"
        recovery_reason = (
            f"Damaged auto scene detected for {branch}: {detail}. "
            f"Original launch error: {error_msg}"
        )

        record_error(
            error_code=E_EXEC_AUTO_SCENE_RESET,
            error_message=recovery_reason,
            tick_id=request.tick_id,
            issue_number=request.target_id,
            branch=branch,
            store=self.store,
        )

        append_orchestra_event(
            "dispatcher",
            f"{request.role} auto-reset triggered for #{request.target_id}: {detail}",
            level="ERROR",
        )
        self.store.add_event(
            branch,
            "auto_scene_reset_triggered",
            recovery_actor,
            detail=recovery_reason,
            refs={
                "role": request.role,
                "damage_signals": detail,
                "original_error": error_msg,
            },
        )

        try:
            cleanup_results = FlowCleanupService(store=self.store).cleanup_flow_scene(
                branch,
                include_remote=True,
                terminate_sessions=True,
                keep_flow_record=False,
            )
        except LiveSessionsDetectedError:
            append_orchestra_event(
                "dispatcher",
                (
                    f"{request.role} auto-reset aborted for #{request.target_id}: "
                    f"live session detected during cleanup (race condition)"
                ),
                level="WARNING",
            )
            self.store.add_event(
                branch,
                "auto_scene_reset_aborted",
                recovery_actor,
                detail=(
                    "Auto-scene reset was aborted because a live runtime session was "
                    "detected during the cleanup phase. This indicates a race "
                    "condition where a session started between damage detection "
                    "and cleanup."
                ),
                refs={
                    "role": request.role,
                    "damage_signals": detail,
                },
            )
            logger.bind(
                domain="auto_scene_recovery",
                branch=branch,
            ).warning("Auto-scene reset aborted due to live session race condition")
            return None
        critical_failures = [
            step
            for step in ("worktree", "local_branch", "flow_record")
            if not cleanup_results.get(step, False)
        ]
        if critical_failures:
            failed_steps = ", ".join(critical_failures)
            append_orchestra_event(
                "dispatcher",
                (
                    f"{request.role} auto-reset incomplete for #{request.target_id}: "
                    f"{failed_steps}"
                ),
                level="ERROR",
            )
            self.store.add_event(
                branch,
                "auto_scene_reset_incomplete",
                recovery_actor,
                detail=(
                    "Automatic auto-scene reset did not finish critical cleanup "
                    f"steps: {failed_steps}"
                ),
                refs={k: str(v) for k, v in cleanup_results.items()},
            )
            logger.bind(
                domain="auto_scene_recovery",
                branch=branch,
                failed_steps=failed_steps,
            ).error("Auto-scene reset incomplete")
            return ExecutionLaunchResult(
                launched=False,
                reason=f"Auto-reset incomplete: {failed_steps}",
                reason_code="auto_scene_reset_incomplete",
            )

        # Use BlockedStateService to unblock and restore to READY
        # This ensures all three sources (body, DB, labels) are cleared
        from vibe3.services import BlockedStateService

        service = BlockedStateService(store=self.store)
        service.unblock(
            branch=branch,
            target_state=IssueState.READY,
            issue_number=request.target_id,
            actor=recovery_actor,
            detail="Auto scene reset completed - issue returned to READY",
        )
        self.store.add_event(
            branch,
            "auto_scene_reset_completed",
            recovery_actor,
            detail=(
                f"Auto scene reset completed for issue #{request.target_id}; "
                "issue returned to READY for clean re-dispatch"
            ),
            refs={k: str(v) for k, v in cleanup_results.items()},
        )
        append_orchestra_event(
            "dispatcher",
            (
                f"{request.role} auto-reset completed for #{request.target_id}; "
                "issue returned to ready"
            ),
            level="WARNING",
        )
        return ExecutionLaunchResult(
            launched=False,
            skipped=True,
            reason=(
                f"Auto-reset damaged scene for {branch}; "
                "issue returned to READY for retry"
            ),
            reason_code="auto_scene_reset",
        )
