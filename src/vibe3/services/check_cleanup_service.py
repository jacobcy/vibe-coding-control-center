"""Check cleanup service - handles --clean-branch logic for terminal flows.

This service is separated from check_service.py to keep responsibilities clear:
- check_service.py: Consistency verification and auto-fix
- check_cleanup_service.py: Terminal flow cleanup
- expired_resource_cleanup_service.py: Expired resource cleanup
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.services.flow_cleanup_service import FlowCleanupService


class CheckCleanupService:
    """Service for cleaning up terminal flow resources.

    Handles the --clean-branch functionality:
    - done: Clean physical resources, keep flow record as audit history
    - aborted: Clean everything including flow record (allows issue to restart)
    """

    # Terminal flow statuses that indicate completed flows.
    # "merged" was a historical status now migrated to "done" by
    # FlowState.migrate_flow_status in models/flow.py.
    TERMINAL_FLOW_STATUSES = ("done", "aborted")

    def __init__(
        self,
        store: "SQLiteClient",
        git_client: "GitClient",
        github_client: "GitHubClient | None" = None,
    ) -> None:
        self.store = store
        self.git_client = git_client
        self._github_client = github_client

    def clean_residual_branches(self, *, force: bool = False) -> dict[str, Any]:
        """Check and clean residual branches for terminal flows.

        NEW: Also cleans expired resources:
        - Agent worktrees (> 7 days)
        - Remote non-protected branches (> 7 days)
        - Local inactive branches (> 7 days)

        Args:
            force: If True, force delete unmerged branches (git branch -D)

        Returns:
            Dict with summary and details of cleaned branches.
        """
        from vibe3.config.settings import VibeConfig
        from vibe3.services.expired_resource_cleanup_service import (
            ExpiredResourceCleanupService,
        )

        # Existing: terminal flow cleanup
        results: dict[str, Any] = self._clean_terminal_flows()
        summary_parts = [str(results.get("summary", ""))]

        # NEW: expired resource cleanup
        config = VibeConfig.get_defaults()
        cleanup_config = config.check_cleanup

        expired_service = ExpiredResourceCleanupService(
            store=self.store,
            git_client=self.git_client,
            github_client=self._github_client,
        )

        if cleanup_config.enable_agent_worktree_cleanup:
            results["agent_worktrees"] = expired_service.clean_expired_agent_worktrees(
                max_age_days=cleanup_config.agent_worktree_max_age_days
            )
            cleaned = results["agent_worktrees"].get("cleaned") or []
            summary_parts.append(f"agent_worktrees cleaned {len(cleaned)}")

        if cleanup_config.enable_remote_branch_cleanup:
            results["remote_branches"] = expired_service.clean_expired_remote_branches(
                max_age_days=cleanup_config.remote_branch_max_age_days
            )
            cleaned = results["remote_branches"].get("cleaned") or []
            summary_parts.append(f"remote_branches cleaned {len(cleaned)}")

        if cleanup_config.enable_local_branch_cleanup:
            results["local_branches"] = expired_service.clean_expired_local_branches(
                max_age_days=cleanup_config.local_branch_max_age_days, force=force
            )
            cleaned = results["local_branches"].get("cleaned") or []
            summary_parts.append(f"local_branches cleaned {len(cleaned)}")

        results["summary"] = "; ".join([p for p in summary_parts if p])
        return results

    def _clean_terminal_flows(self) -> dict[str, object]:
        """Clean terminal flows (done/aborted).

        Different handling based on flow status:
        - done: Clean physical resources, keep flow record as audit history
        - aborted: Clean everything including flow record (allows issue to restart)

        Returns:
            Dict with summary and details of cleaned flows.
        """
        from vibe3.services.flow_cleanup_service import FlowCleanupService

        logger.bind(domain="check", action="clean_residual").info(
            "Checking for residual branches"
        )

        # Get all terminal flows (done/aborted)
        all_flows = self.store.get_all_flows()
        terminal_flows = [
            f for f in all_flows if f.get("flow_status") in self.TERMINAL_FLOW_STATUSES
        ]

        # PRE-FILTER: Get branches with live sessions (batch query)
        branches_with_live = self._get_branches_with_live_sessions()

        if branches_with_live:
            logger.bind(domain="check").info(
                f"Skipped {len(branches_with_live)} branches with live sessions: "
                f"{', '.join(sorted(branches_with_live))}"
            )

        cleanup_service = FlowCleanupService(
            git_client=self.git_client,
            store=self.store,
        )

        cleaned: list[str] = []
        kept_records: list[str] = []
        removed_invalid: list[str] = []
        failed: list[str] = []
        skipped_live: list[str] = []

        for flow in terminal_flows:
            branch = flow["branch"]
            flow_status = flow.get("flow_status", "")

            # Remove invalid branch records (e.g., HEAD)
            if self._is_invalid_branch_name(branch):
                if self._remove_invalid_flow_record(branch):
                    removed_invalid.append(branch)
                continue

            # SKIP: Branch has live sessions
            if branch in branches_with_live:
                skipped_live.append(branch)
                continue

            # Process valid terminal flow
            self._process_terminal_flow(
                branch=branch,
                flow_status=flow_status,
                cleanup_service=cleanup_service,
                cleaned=cleaned,
                kept_records=kept_records,
                failed=failed,
            )

        summary = f"Cleaned {len(cleaned)} aborted flows"
        if kept_records:
            summary += f", preserved {len(kept_records)} done records"
        if removed_invalid:
            summary += f", removed {len(removed_invalid)} invalid records"
        if skipped_live:
            summary += f", skipped {len(skipped_live)} branches with live sessions"
        if failed:
            summary += f", failed {len(failed)}"

        # Clean orphan detached HEAD worktrees
        detached_results = self._cleanup_detached_worktrees()
        detached_cleaned = detached_results.get("cleaned", [])
        detached_failed = detached_results.get("failed", [])

        if detached_cleaned:
            summary += f", cleaned {len(detached_cleaned)} detached worktrees"
        if detached_failed:
            summary += f", failed {len(detached_failed)} detached worktrees"

        return {
            "summary": summary,
            "cleaned": cleaned,
            "kept_records": kept_records,
            "removed_invalid": removed_invalid,
            "failed": failed + detached_failed,
            "skipped_live": skipped_live,
            "total_flows_checked": len(terminal_flows),
        }

    def _get_branches_with_live_sessions(self) -> set[str]:
        """Batch query all live sessions and return branches with active sessions.

        This is a pre-filter optimization: instead of checking live sessions
        per branch during cleanup (N queries), we query once upfront and
        filter out branches with live sessions before cleanup attempts.

        Returns:
            Set of branch names that have truly live sessions.

        Raises:
            SystemError: If query fails, preventing accidental cleanup.
        """
        try:
            from vibe3.agents import CodeagentBackend
            from vibe3.environment.session_registry import SessionRegistryService

            backend = CodeagentBackend()
            registry = SessionRegistryService(store=self.store, backend=backend)

            # Reuse existing method: batch query + liveness verification
            return registry.get_all_branches_with_live_sessions()

        except Exception as exc:
            logger.bind(domain="check").error(
                f"Failed to query live sessions: {exc}. "
                "Cannot proceed with cleanup - manual verification required."
            )
            raise SystemError(
                f"Live session query failed: {exc}. "
                "Cleanup aborted to prevent accidental deletion of active sessions. "
                "Please verify manually or retry."
            ) from exc

    def _is_invalid_branch_name(self, branch: str) -> bool:
        """Check if branch name is invalid (e.g., HEAD, HEAD~1)."""
        return branch == "HEAD" or branch.startswith("HEAD")

    def _remove_invalid_flow_record(self, branch: str) -> bool:
        """Remove invalid flow record from database.

        Returns:
            True if successfully removed, False otherwise.
        """
        try:
            self.store.delete_flow(branch)
            logger.bind(domain="check", branch=branch).info(
                "Removed invalid flow record"
            )
            return True
        except Exception as exc:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to remove invalid flow record: {exc}"
            )
            return False

    def _process_terminal_flow(
        self,
        branch: str,
        flow_status: str,
        cleanup_service: "FlowCleanupService",
        cleaned: list[str],
        kept_records: list[str],
        failed: list[str],
    ) -> None:
        """Process a single terminal flow with appropriate cleanup.

        SAFETY CHECK: Two-layer protection against live session deletion.
        - Layer 1 (pre-filter): Batch query upfront for performance optimization
        - Layer 2 (defensive): Per-branch verification in cleanup_flow_scene()
          (LiveSessionsDetectedError catches race conditions)
        If sessions are still running, cleanup aborted by LiveSessionsDetectedError.

        Args:
            branch: Branch name
            flow_status: Flow status (done/aborted)
            cleanup_service: Cleanup service instance
            cleaned: List to append successfully cleaned aborted flows
            kept_records: List to append done flows with preserved records
            failed: List to append failure messages
        """
        # done: keep record as audit history (issue is closed, PR was merged)
        # aborted: delete record (issue may still be open, allow restart)
        keep_flow_record = flow_status == "done"

        try:
            results = cleanup_service.cleanup_flow_scene(
                branch,
                include_remote=True,
                terminate_sessions=True,
                keep_flow_record=keep_flow_record,
            )

            if keep_flow_record:
                # done: success if physical resources cleaned
                if results.get("worktree", False) or results.get("local_branch", False):
                    kept_records.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        "Cleaned done flow resources, kept record"
                    )
            else:
                # aborted: success if flow record deleted
                if results.get("flow_record", False):
                    cleaned.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        "Cleaned aborted flow completely"
                    )

                    # Resume blocked issue to READY (passive cleanup)
                    self._resume_blocked_issue(branch)
                else:
                    failed.append(f"{branch}: flow record deletion failed")
        except Exception as exc:
            failed.append(f"{branch}: {exc}")
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to clean terminal flow resources: {exc}"
            )

    def _resume_blocked_issue(self, branch: str) -> None:
        """Resume blocked issue when flow is aborted (passive cleanup).

        This closes the cleanup loop for vibe check --clean-branch:
        when a flow is detected as aborted and cleaned up, the corresponding
        issue should return to READY state, allowing it to be dispatched again.

        Skips already-closed issues to avoid reopening completed work.

        Args:
            branch: Branch name (expected to be task/issue-N pattern)
        """
        try:
            from vibe3.models.orchestration import IssueState
            from vibe3.services.blocked_state_service import BlockedStateService

            issue_number = self._parse_issue_number(branch)
            if issue_number is None:
                logger.bind(domain="check", branch=branch).debug(
                    "Not a task branch, skipping issue label cleanup"
                )
                return

            from vibe3.clients.github_client import GitHubClient

            gh = self._github_client or GitHubClient()
            gh_issue = gh.view_issue(issue_number)
            if (
                isinstance(gh_issue, dict)
                and str(gh_issue.get("state", "")).upper() == "CLOSED"
            ):
                logger.bind(domain="check", branch=branch).info(
                    f"Issue #{issue_number} already closed, skip resume"
                )
                return

            # Resume issue using unified BlockedStateService
            service = BlockedStateService(
                store=self.store,
                github_client=gh,
            )
            service.unblock(
                branch=branch,
                target_state=IssueState.READY,
                issue_number=issue_number,
                detail="Flow aborted and cleaned up by vibe check --clean-branch",
            )

            # Add informative comment
            comment_body = """旧 flow 已清理（flow record 已删除）。

**建议方案：**

1. **关闭此 issue** - 如果需求已不再需要
2. **创建 follow-up issue** - 如果需要继续开发，建议创建新 issue 重新规划
3. **重新开始** - 当前 issue 已恢复到 READY 状态，可以被重新派发

**注意：** 不建议在旧 flow 的基础上继续开发，因为之前的代码上下文已丢失。"""

            gh.add_comment(issue_number, comment_body)

            logger.bind(domain="check", branch=branch).info(
                f"Resumed issue #{issue_number} to READY"
            )
        except Exception as exc:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to resume blocked issue: {exc}"
            )

    def _get_issue_state(self, issue_number: int) -> str | None:
        """Get current issue state for event record.

        Args:
            issue_number: GitHub issue number

        Returns:
            Current state value (e.g., "blocked", "ready") or None if unknown
        """
        try:
            from vibe3.services.label_service import LabelService

            state = LabelService().get_state(issue_number)
            return state.value if state else None
        except Exception as exc:
            logger.bind(
                domain="check",
                issue_number=issue_number,
            ).debug(f"Failed to get issue state: {exc}")
            return None

    def _parse_issue_number(self, branch: str) -> int | None:
        """Extract issue number from task/issue-N branch."""
        import re

        match = re.fullmatch(r"^task/issue-(\d+)$", branch)
        return int(match.group(1)) if match else None

    def _cleanup_detached_worktrees(self) -> dict[str, list[str]]:
        """Clean up orphaned detached HEAD worktrees from invalid flow records.

        This method only removes worktrees that correspond to flow records with
        invalid branch names (e.g., "HEAD", "HEAD~1"). It does NOT remove
        arbitrary detached worktrees created by users for other purposes.

        Safety:
        - Protected by user confirmation in check command
        - Skips worktree containing current working directory
        - Only removes flow-managed worktrees

        Returns:
            Dict with 'cleaned', 'skipped_self', and 'failed' lists.
        """
        import os

        logger.bind(domain="check", action="cleanup_detached").info(
            "Scanning for orphaned detached HEAD worktrees"
        )

        try:
            # Get all worktrees using git client (consistent error handling)
            result = self.git_client._run(["worktree", "list", "--porcelain"])

            # Parse worktrees
            worktrees: list[tuple[str, str, bool]] = []  # (path, head_sha, detached)
            wt_path = ""
            wt_head = ""
            is_detached = False

            def flush() -> None:
                nonlocal wt_path, wt_head, is_detached
                if wt_path:
                    worktrees.append((wt_path, wt_head, is_detached))
                wt_path = ""
                wt_head = ""
                is_detached = False

            for line in result.splitlines():
                line = line.strip()
                if line.startswith("worktree "):
                    flush()
                    wt_path = line.split(" ", 1)[1]
                elif line.startswith("HEAD "):
                    wt_head = line.split(" ", 1)[1]
                elif line == "detached":
                    is_detached = True
                elif not line:
                    flush()

            flush()

            # Filter detached worktrees
            detached_worktrees = [
                (path, head_sha) for path, head_sha, detached in worktrees if detached
            ]

            if not detached_worktrees:
                return {"cleaned": [], "skipped_self": [], "failed": []}

            logger.bind(domain="check").info(
                f"Found {len(detached_worktrees)} detached HEAD worktrees"
            )

            # SAFETY: Get current worktree root (not just CWD)
            # This protects even if user runs from a subdirectory
            current_wt_root = self.git_client.get_worktree_root()
            current_cwd = os.getcwd()

            # Get all invalid branch flows (HEAD, HEAD~N)
            all_flows = self.store.get_all_flows()
            invalid_branches = {
                f["branch"]
                for f in all_flows
                if self._is_invalid_branch_name(f.get("branch", ""))
            }

            # Remove detached worktrees (only if flow-managed)
            cleaned: list[str] = []
            skipped_self: list[str] = []
            failed: list[str] = []

            for wt_path, head_sha in detached_worktrees:
                # SAFETY CHECK 1: Never delete current worktree
                wt_abs = os.path.abspath(wt_path)
                if wt_abs == current_wt_root or current_cwd.startswith(wt_abs + os.sep):
                    skipped_self.append(wt_path)
                    logger.bind(
                        domain="check",
                        worktree=wt_path,
                    ).warning(
                        "Skipping detached worktree:"
                        " it is the current working directory"
                    )
                    continue

                # SAFETY CHECK 2: Only remove if flow-managed
                # Check if this worktree path exists in any flow record
                # (including those with invalid branch names)
                is_flow_managed = any(wt_path in str(f) for f in all_flows)

                if not is_flow_managed and not invalid_branches:
                    logger.bind(
                        domain="check",
                        worktree=wt_path,
                    ).debug("Skipping detached worktree:" " not managed by flow")
                    continue

                try:
                    self.git_client._run(["worktree", "remove", "--force", wt_path])
                    cleaned.append(wt_path)
                    logger.bind(
                        domain="check",
                        worktree=wt_path,
                        head_sha=head_sha[:7],
                    ).info("Removed orphaned detached HEAD worktree")
                except Exception as exc:
                    error_msg = f"{wt_path}: {exc}"
                    failed.append(error_msg)
                    logger.bind(domain="check", worktree=wt_path).warning(
                        f"Failed to remove detached worktree: {exc}"
                    )

            return {"cleaned": cleaned, "skipped_self": skipped_self, "failed": failed}

        except Exception as exc:
            logger.bind(domain="check").error(f"Failed to scan worktrees: {exc}")
            return {"cleaned": [], "skipped_self": [], "failed": []}
