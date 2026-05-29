"""Flow dispatch support for role execution.

This module owns issue->flow orchestration for execution-facing roles.
Migrated from orchestra/flow_dispatch.py to establish domain-first architecture.
"""

import subprocess
from typing import cast

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.protocols import GitHubClientProtocol
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService
from vibe3.services.pr_service import PRService
from vibe3.services.task_service import TaskService


class FlowManager:
    """Manage issue-to-flow mapping and flow scene creation for execution."""

    def __init__(
        self,
        config: OrchestraConfig,
        *,
        store: SQLiteClient | None = None,
        git: GitClient | None = None,
        github: GitHubClient | None = None,
        registry: SessionRegistryService | None = None,
    ) -> None:
        self.config = config
        self.store = SQLiteClient() if store is None else store
        self.git = GitClient() if git is None else git
        self.flow_service = FlowService(store=self.store, git_client=self.git)
        self.task_service = TaskService(store=self.store)
        self.github = GitHubClient() if github is None else github
        self.label_service = LabelService(repo=config.repo)
        self.issue_flow_service = IssueFlowService(store=self.store)
        self._registry = registry
        self._bootstrap_service = FlowOrchestratorService(
            config,
            store=self.store,
            git=self.git,
            github=self.github,
        )

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Find the latest flow for an issue, regardless of active status.

        This supports using the GitHub Issue as the source of truth (SSOT).
        If an issue has a label that triggers dispatch, we need the branch
        context even if the flow was previously marked as aborted or done.
        """
        return self.issue_flow_service.find_active_flow(issue_number)

    def _is_reusable_auto_flow(
        self, flow: dict[str, object], issue_number: int
    ) -> bool:
        branch = str(flow.get("branch") or "").strip()
        canonical_branch = self.issue_flow_service.canonical_branch_name(issue_number)
        if branch != canonical_branch:
            return False

        # Guard against orphaned flow records: reject if git branch missing
        if not self.git.branch_exists(branch):
            logger.bind(
                domain="flow_dispatch",
                branch=branch,
                issue_number=issue_number,
            ).warning(f"Flow branch '{branch}' missing in git — rejecting as stale")
            return False

        return str(flow.get("flow_status") or "active") not in {
            "done",
            "aborted",
            "stale",
        }

    def _reactivate_canonical_flow(
        self, issue: IssueInfo, branch: str, slug: str
    ) -> dict:
        return self._bootstrap_service.bootstrap_issue_flow(
            issue,
            branch=branch,
            slug=slug,
            source="dispatch",
            ensure_worktree=True,  # Orchestra task flows must use worktree
        )

    def get_active_flow_count(self) -> int:
        active = 0
        for flow in self.store.get_all_flows():
            if flow.get("flow_status") != "active":
                continue
            branch = str(flow.get("branch") or "").strip()
            if not self.issue_flow_service.is_task_branch(branch):
                continue
            issue_number = self._resolve_task_issue_number(branch, flow)
            if issue_number is None:
                continue
            state = self.label_service.get_state(issue_number)
            if state in {
                IssueState.CLAIMED,
                IssueState.HANDOFF,
                IssueState.IN_PROGRESS,
                IssueState.REVIEW,
            }:
                active += 1
        return active

    def _resolve_task_issue_number(
        self, branch: str, flow: dict[str, object]
    ) -> int | None:
        task_issue = flow.get("task_issue_number")
        if isinstance(task_issue, int):
            return task_issue
        issue_links = self.store.get_issue_links(branch)
        for link in issue_links:
            if (
                link.get("issue_role") == "task"
                and link.get("issue_number") is not None
            ):
                return int(link["issue_number"])
        return self.issue_flow_service.parse_issue_number(branch)

    def create_flow_for_issue(self, issue: IssueInfo) -> dict | None:
        log = logger.bind(
            domain="orchestra",
            action="create_flow",
            issue=issue.number,
        )

        slug = f"issue-{issue.number}"
        branch = f"task/{slug}"
        existing_flows = self.store.get_flows_by_issue(issue.number, role="task")
        for existing in existing_flows:
            if self._is_reusable_auto_flow(existing, issue.number):
                log.info(f"Flow already exists for issue #{issue.number}")
                return existing

        existing_canonical = next(
            (
                flow
                for flow in existing_flows
                if str(flow.get("branch") or "").strip() == branch
            ),
            None,
        )
        if existing_canonical:
            if str(existing_canonical.get("flow_status") or "") == "stale":
                log.info(f"Rebuilding stale canonical flow for issue #{issue.number}")
                return self._bootstrap_service.rebuild_stale_issue_flow(
                    issue,
                    branch=branch,
                    slug=slug,
                    ensure_worktree=True,  # Orchestra task flows must use worktree
                )
            # Guard: branch missing for aborted flow → rebuild to avoid dispatch failure
            if not self.git.branch_exists(branch):
                log.warning(
                    f"Branch '{branch}' missing for aborted flow "
                    f"#{issue.number}, rebuilding"
                )
                return self._bootstrap_service.rebuild_stale_issue_flow(
                    issue,
                    branch=branch,
                    slug=slug,
                    ensure_worktree=True,  # Orchestra task flows must use worktree
                )
            log.info(f"Reactivating canonical flow for issue #{issue.number}")
            return self._reactivate_canonical_flow(issue, branch, slug)

        if self._registry is None:
            raise RuntimeError("SessionRegistryService is required for capacity check")
        active_count = self._registry.count_live_worker_sessions(role="manager")
        if active_count >= self.config.max_concurrent_flows:
            limit = self.config.max_concurrent_flows
            from vibe3.exceptions import CapacityDeferredError

            raise CapacityDeferredError(
                f"Manager capacity reached ({active_count}/{limit}). "
                f"Deferred flow creation."
            )

        try:
            result = self._bootstrap_service.bootstrap_issue_flow(
                issue,
                branch=branch,
                slug=slug,
                source="dispatch",
                ensure_worktree=True,  # Orchestra task flows must use worktree
            )
        except Exception as exc:
            existing = self.store.get_flow_state(branch) or {}
            if existing:
                log.warning(
                    f"Flow created concurrently for #{issue.number}, using existing"
                )
                return existing
            raise RuntimeError(
                f"Failed to create flow for issue #{issue.number}: {exc}"
            ) from exc

        log.info(f"Created flow '{slug}' on branch '{branch}'")
        return result

    def get_pr_for_issue(self, issue_number: int) -> int | None:
        """Return the PR number associated with the issue's flow, or None.

        Implements FlowReader protocol using standard branch→PR query path.
        """
        # Priority 1: from stored flow record (fast path)
        flow = self.get_flow_for_issue(issue_number)
        if flow and flow.get("pr_number"):
            return int(flow["pr_number"])

        # Fallback: branch→PR standard path
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
