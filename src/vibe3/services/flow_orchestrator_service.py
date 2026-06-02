"""Flow orchestrator service - 编排逻辑下沉到Service层."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.protocols import GitHubClientProtocol
from vibe3.environment.worktree import WorktreeManager
from vibe3.models.pr import PRState
from vibe3.services.flow_cleanup_service import FlowCleanupService
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import block_manager_noop_issue
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.orchestra_status_service import OrchestraStatusService
from vibe3.services.pr_service import PRService
from vibe3.services.signature_service import SignatureService
from vibe3.services.task_service import TaskService

if TYPE_CHECKING:
    from vibe3.config.orchestra_config import OrchestraConfig
    from vibe3.models.orchestration import IssueInfo
    from vibe3.services.orchestra_status_service import OrchestraSnapshot


class FlowOrchestratorService:
    """Flow编排服务，提供快照和编排能力.

    职责：
    - 获取运行时快照
    - 编排Flow状态（但不直接执行）
    - 提供查询接口
    - 创建Flow for Issue（替代FlowManager的层违规调用）

    这个类替代Execution层对Service层的反向依赖.

    Implements FlowReader protocol for use with OrchestraStatusService.
    """

    def __init__(
        self,
        config: OrchestraConfig,
        *,
        store: SQLiteClient | None = None,
        git: GitClient | None = None,
        github: GitHubClient | None = None,
    ) -> None:
        """Initialize with config and optional clients."""
        self.config = config
        self.store = SQLiteClient() if store is None else store
        self.git = GitClient() if git is None else git
        self.github = GitHubClient() if github is None else github
        self.flow_service = FlowService(store=self.store, git_client=self.git)
        self.issue_flow_service = IssueFlowService(store=self.store)
        self.task_service = TaskService(store=self.store)

    def snapshot(self) -> OrchestraSnapshot | None:
        """Get current orchestra snapshot."""
        return OrchestraStatusService.fetch_live_snapshot(self.config)

    # FlowReader protocol implementation

    def get_flow_for_issue(self, issue_number: int) -> dict[str, Any] | None:
        """Return the active flow record for the given issue, or None.

        Delegates to IssueFlowService.find_active_flow for deterministic selection:
        1. Active canonical flow (task/issue-N)
        2. Active non-canonical flow
        3. First available flow (fallback)
        """
        return self.issue_flow_service.find_active_flow(issue_number)

    def get_pr_for_issue(self, issue_number: int) -> int | None:
        """Return the PR number associated with the issue's flow, or None.

        First checks the stored flow record, then falls back to standard
        branch→PR query path if the store hasn't been updated yet.
        """
        flow = self.get_flow_for_issue(issue_number)
        if flow and flow.get("pr_number"):
            return int(flow["pr_number"])

        # Fallback: standard branch→PR query path
        # Use flow's actual branch if exists and non-empty, otherwise canonical branch
        if flow and flow.get("branch"):
            branch = str(flow["branch"])
        else:
            branch = self.issue_flow_service.canonical_branch_name(issue_number)

        try:
            pr = PRService(
                github_client=cast(GitHubClientProtocol, self.github),
                git_client=self.git,
                store=self.store,
            ).get_branch_pr_status(branch)
            if pr:
                return pr.number
        except (subprocess.CalledProcessError, FileNotFoundError):
            # GitHub CLI not available or query failed
            pass

        return None

    def get_active_flow_count(self) -> int:
        """Return the number of currently active flows."""
        return self.store.get_active_flow_count()

    # Flow creation logic

    def bootstrap_issue_flow(
        self,
        issue: IssueInfo,
        *,
        branch: str,
        slug: str | None = None,
        source: str = "dispatch",
        actor: str | None = None,
        initiated_by: str | None = None,
        ensure_worktree: bool = False,
        reactivate_existing: bool = False,
        related_issue_numbers: tuple[int, ...] = (),
        dependency_issue_numbers: tuple[int, ...] = (),
    ) -> dict[str, Any]:
        """Create or reactivate a standardized flow scene for an issue.

        This is the shared bootstrap interface for both:
        - orchestra automatic flow creation
        - human-collaboration skill bootstrap planning

        It centralizes branch preparation, flow creation/reactivation, issue binding,
        optional worktree resolution, and compatible related/dependency linkage.
        """
        slug = slug or f"issue-{issue.number}"
        initiator = initiated_by or SignatureService.resolve_initiator(branch)

        try:
            if not self.git.branch_exists(branch):
                # Ensure scene_base_ref remote is up-to-date before creating branch
                remote = self.config.scene_base_ref.split("/")[0]
                self.git.fetch(remote)
                self.git.create_branch_ref(
                    branch,
                    start_ref=self.config.scene_base_ref,
                )
                # For non-worktree mode, checkout the newly created branch
                if not ensure_worktree:
                    self.git.switch_branch(branch)

            existing_state = self.store.get_flow_state(branch)
            if reactivate_existing and existing_state:
                flow_state = self.flow_service.reactivate_flow(
                    branch,
                    flow_slug=slug,
                    initiator=initiator,
                )
            else:
                flow_state = self.flow_service.create_flow(
                    slug=slug,
                    branch=branch,
                    actor=actor,
                    initiated_by=initiator,
                    source=source,
                )

            self.task_service.link_issue(branch, issue.number, "task", actor=actor)
            for related_issue in related_issue_numbers:
                self.task_service.link_issue(
                    branch, related_issue, "related", actor=actor
                )
            for dependency_issue in dependency_issue_numbers:
                self.flow_service.block_flow(
                    branch,
                    blocked_by_issue=dependency_issue,
                    actor=actor,
                )

            result = self.store.get_flow_state(branch) or flow_state.model_dump()
            if ensure_worktree:
                worktree_manager = WorktreeManager(
                    self.config,
                    repo_path=Path(self.git.get_git_common_dir()).parent,
                )
                worktree_ctx = worktree_manager.resolve_bootstrap_worktree_context(
                    branch=branch,
                    issue_number=issue.number,
                    use_worktree=True,
                )
                result["worktree_path"] = str(worktree_ctx.path)
                # Persist worktree_path to store -- the in-memory result
                # is only returned to the caller, so DB must be updated
                # explicitly for consistency checks to pass later.
                self.store.update_flow_state(
                    branch, worktree_path=str(worktree_ctx.path)
                )
            return result
        except Exception as exc:
            # CRITICAL: Complete cleanup on bootstrap failure
            # When ensure_worktree=True, worktree creation happens
            # AFTER flow_state is written, so failure must clean up
            # both branch AND flow record
            try:
                logger.bind(
                    domain="flow",
                    branch=branch,
                    issue=issue.number,
                ).warning(f"Bootstrap failed, performing complete cleanup: {exc}")

                # Use FlowCleanupService for comprehensive cleanup
                cleanup = FlowCleanupService(
                    git_client=self.git,
                    store=self.store,
                )
                cleanup.cleanup_flow_scene(
                    branch,
                    include_remote=False,
                    terminate_sessions=False,
                    keep_flow_record=False,  # Delete flow record
                    force_delete=True,  # Hard delete for bootstrap failure
                )
            except Exception as cleanup_exc:
                logger.bind(
                    domain="flow",
                    branch=branch,
                ).error(f"Failed cleanup after bootstrap failure: {cleanup_exc}")
            raise

    def rebuild_stale_issue_flow(
        self,
        issue: IssueInfo,
        *,
        branch: str,
        slug: str | None = None,
        source: str = "dispatch",
        ensure_worktree: bool = False,
    ) -> dict[str, Any] | None:
        """Rebuild a stale flow using FlowRebuildUsecase.

        Returns None if the issue already has a merged PR (no rebuild needed).
        """
        from vibe3.services.flow_rebuild_usecase import FlowRebuildUsecase

        # Use branch→PR lookup for consistency (not issue→PR)
        # Query all PR states (including merged) to detect merged PRs
        try:
            pr = PRService(
                github_client=cast(GitHubClientProtocol, self.github),
                git_client=self.git,
                store=self.store,
            ).get_branch_pr_status(branch)
            if pr and (pr.state == PRState.MERGED or pr.merged_at):
                block_manager_noop_issue(
                    issue_number=issue.number,
                    repo=self.config.repo,
                    reason=(
                        f"尝试重建 flow 但 PR #{pr.number} 已 merge。"
                        "Flow 应标记为 done 而非 aborted。需要人工确认 flow 状态。"
                    ),
                    actor="orchestra:flow_dispatch",
                )
                return None
        except (subprocess.CalledProcessError, FileNotFoundError):
            # GitHub CLI not available or query failed, continue with rebuild
            pass

        return FlowRebuildUsecase(
            store=self.store,
            git_client=self.git,
            orchestrator=self,
        ).rebuild_issue_flow(
            issue=issue,
            branch=branch,
            slug=slug,
            source=source,
            reason="stale flow rebuild",
            include_remote=False,
            ensure_worktree=ensure_worktree,
        )

    def create_flow_for_issue(self, issue: IssueInfo) -> dict[str, Any] | None:
        """Create flow for issue, handling existing flows and branch creation.

        This method provides a service-layer entry point for flow creation,
        avoiding the need for services to import from execution layer.

        Args:
            issue: Issue info containing number, title, state, labels

        Returns:
            Created or existing flow dict, or None if capacity limit reached
        """
        log = logger.bind(
            domain="orchestra",
            action="create_flow",
            issue=issue.number,
        )

        slug = f"issue-{issue.number}"
        branch = self.issue_flow_service.canonical_branch_name(issue.number)

        # Check for existing flows via issue link
        existing_flows = self.store.get_flows_by_issue(issue.number, role="task")

        # Also check canonical branch directly (handles corrupted/missing issue links)
        canonical_flow = self.store.get_flow_state(branch)

        # Reuse existing flow if applicable
        for existing in existing_flows:
            flow_status = str(existing.get("flow_status") or "")
            if flow_status in ("active", "done"):
                log.info(f"Flow already exists for issue #{issue.number}")
                return existing

        # Check canonical flow (from issue link or direct branch check)
        existing_canonical = next(
            (
                flow
                for flow in existing_flows
                if str(flow.get("branch") or "").strip() == branch
            ),
            canonical_flow,  # Fallback to direct branch check
        )

        if existing_canonical:
            flow_status = str(existing_canonical.get("flow_status") or "")
            # Reactivate or rebuild stale/aborted flows
            if flow_status in ("stale", "aborted"):
                try:
                    result = self.bootstrap_issue_flow(
                        issue,
                        branch=branch,
                        slug=slug,
                        source="dispatch",
                        reactivate_existing=True,
                    )
                    log.info(f"Reactivated canonical flow for issue #{issue.number}")
                    return result
                except Exception as exc:
                    log.error(f"Failed to reactivate flow: {exc}")
                    # Fall through to create new flow

            log.info(f"Using existing canonical flow for issue #{issue.number}")
            return existing_canonical

        try:
            result = self.bootstrap_issue_flow(
                issue,
                branch=branch,
                slug=slug,
                source="dispatch",
            )
            log.success(f"Created flow for issue #{issue.number}")
            return result
        except Exception as exc:
            # Handle concurrent creation
            existing = self.store.get_flow_state(branch) or {}
            if existing:
                log.warning(
                    f"Flow created concurrently for #{issue.number}, using existing"
                )
                return existing
            log.error(f"Failed to create flow for #{issue.number}: {exc}")
            raise RuntimeError(
                f"Failed to create flow for issue #{issue.number}: {exc}"
            ) from exc
