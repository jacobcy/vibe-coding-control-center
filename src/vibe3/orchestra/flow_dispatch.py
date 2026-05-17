"""Flow dispatch support for role execution.

This module owns issue->flow orchestration for execution-facing roles.
It was moved out of manager/ so manager can keep shrinking toward a role shell.
"""

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService
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
            reactivate_existing=True,
        )

        try:
            self.task_service.link_issue(branch, issue.number, "task", actor=None)
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to relink issue #{issue.number} to flow: {exc}"
            )

        return flow_state.model_dump()

    def _rebuild_stale_canonical_flow(
        self, issue: IssueInfo, branch: str, slug: str
    ) -> dict | None:
        # Guard: Check if PR was already merged - should not rebuild
        # Use branch→PR lookup instead of issue→PR for consistency
        prs = self.github.list_prs_for_branch(branch)
        if prs:
            pr = prs[0]  # Take most recent PR
            if pr and (pr.state == PRState.MERGED or pr.merged_at):
                # Block issue instead of throwing exception
                # This is a tolerable issue that requires human intervention
                logger.bind(
                    domain="flow_dispatch",
                    issue=issue.number,
                    pr=pr.number,
                    state=pr.state.value,
                ).warning(
                    f"Cannot rebuild flow #{issue.number}: "
                    f"PR #{pr.number} already merged. "
                    "Blocking issue for human intervention."
                )

                block_manager_noop_issue(
                    issue_number=issue.number,
                    repo=self.config.repo,
                    reason=(
                        f"尝试重建 flow 但 PR #{pr.number} 已 merge。"
                        f"Flow 应标记为 done 而非 aborted。需要人工确认 flow 状态。"
                    ),
                    actor="orchestra:flow_dispatch",
                )

                # Return None to signal dispatch should stop (issue now blocked)
                # This allows server to continue running
                return None

        worktree_path = self.git.find_worktree_path_for_branch(branch)
        if worktree_path is not None:
            self.git.remove_worktree(worktree_path, force=True)

        if self.git.branch_exists(branch):
            self.git.delete_branch(
                branch,
                force=True,
                skip_if_worktree=True,
            )

        if not self.git.branch_exists(branch):
            self.git.create_branch_ref(
                branch,
                start_ref=self.config.scene_base_ref,
            )

        return self._reactivate_canonical_flow(issue, branch, slug)
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
                )
            log.info(f"Reactivating canonical flow for issue #{issue.number}")
            return self._reactivate_canonical_flow(issue, branch, slug)

        if self._registry is None:
            raise RuntimeError("SessionRegistryService is required for capacity check")
        active_count = self._registry.count_live_worker_sessions(role="manager")
        if active_count >= self.config.max_concurrent_flows:
            limit = self.config.max_concurrent_flows
            raise RuntimeError(
                f"Manager capacity reached ({active_count}/{limit}). "
                f"Deferred flow creation."
            )

        try:
            result = self._bootstrap_service.bootstrap_issue_flow(
                issue,
                branch=branch,
                slug=slug,
                source="dispatch",
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
        flow = self.get_flow_for_issue(issue_number)
        if flow and flow.get("pr_number"):
            return int(flow["pr_number"])
        return self.github.get_pr_for_issue(issue_number, repo=self.config.repo)
