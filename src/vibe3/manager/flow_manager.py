"""Flow management utilities for orchestra manager."""

from loguru import logger

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService
from vibe3.services.session_registry import SessionRegistryService
from vibe3.services.task_service import TaskService


class FlowManager:
    """Manages issue-to-flow mapping and command execution.

    Uses FlowService and TaskService for all state mutations so that
    orchestra-created flows participate in the standard flow lifecycle
    (events recorded, vibe3 flow show works, etc.).

    Git branch creation is handled directly via GitClient because
    FlowService.create_flow_with_branch() has an uncommitted-changes
    guard that is inappropriate for a background server context.
    """

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

    def get_flow_for_issue(self, issue_number: int) -> dict | None:
        """Get flow linked to an issue with deterministic selection.

        Priority order:
        1. Active canonical flow (task/issue-N)
        2. Active non-canonical flow
        3. First available flow (fallback)

        This ensures deterministic selection when multiple flows exist
        for the same issue.
        """
        return self.issue_flow_service.find_active_flow(issue_number)

    def _is_reusable_auto_flow(
        self, flow: dict[str, object], issue_number: int
    ) -> bool:
        branch = str(flow.get("branch") or "").strip()
        canonical_branch = self.issue_flow_service.canonical_branch_name(issue_number)
        if branch != canonical_branch:
            return False
        return str(flow.get("flow_status") or "active") not in {
            "done",
            "aborted",
            "stale",
        }

    def _reactivate_canonical_flow(
        self, issue: IssueInfo, branch: str, slug: str
    ) -> dict:
        from vibe3.services.signature_service import SignatureService

        initiator = SignatureService.resolve_initiator(branch)
        flow_state = self.flow_service.reactivate_flow(
            branch,
            flow_slug=slug,
            initiator=initiator,
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
    ) -> dict:
        """Hard-reset stale canonical flow by removing scene residue first.

        This repair step must stay metadata-only. Worktrees are created only when
        manager dispatch actually begins, not while rebuilding a stale ready scene.
        """

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
        """Get count of active auto-managed flows across the system."""
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

    def get_active_manager_session_count(self) -> int:
        """Count live manager sessions for task flows via runtime_session registry.

        This method queries the runtime_session table directly to count
        manager sessions in 'running' or 'starting' status.

        Returns:
            Number of live manager sessions.
        """

        registry = SessionRegistryService(
            store=self.store,
            backend=CodeagentBackend(),
        )
        return registry.count_live_worker_sessions(role="manager")

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

    def create_flow_for_issue(self, issue: IssueInfo) -> dict:
        """Create (or reuse) a flow for an issue.

        Uses FlowService.create_flow() so lifecycle events are recorded
        and the flow is visible via `vibe3 flow show`.

        Args:
            issue: Issue to create flow for

        Returns:
            Flow state dict

        Raises:
            RuntimeError: If flow creation fails or capacity is reached
        """
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
                return self._rebuild_stale_canonical_flow(issue, branch, slug)
            log.info(f"Reactivating canonical flow for issue #{issue.number}")
            return self._reactivate_canonical_flow(issue, branch, slug)

        # Capacity Check: Before creating a NEW flow, verify global capacity
        # Prefer registry count for consistency with dispatch path
        if self._registry is not None:
            active_count = self._registry.count_live_worker_sessions(role="manager")
        else:
            active_count = self.get_active_manager_session_count()
        if active_count >= self.config.max_concurrent_flows:
            limit = self.config.max_concurrent_flows
            raise RuntimeError(
                f"Manager capacity reached ({active_count}/{limit}). "
                "Deferred flow creation."
            )

        # Ensure branch exists (create_branch_ref: no checkout, no worktree mutation)
        branch_created = False
        if not self.git.branch_exists(branch):
            try:
                self.git.create_branch_ref(
                    branch,
                    start_ref=self.config.scene_base_ref,
                )
                branch_created = True
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to create branch '{branch}': {exc}"
                ) from exc

        # Register flow via FlowService (lifecycle events, proper recording)
        # Use orchestra tag only if it's a managed issue-specific branch
        from vibe3.services.signature_service import SignatureService

        initiator = SignatureService.resolve_initiator(branch)
        try:
            flow_state = self.flow_service.create_flow(
                slug=slug,
                branch=branch,
                actor=None,
                initiated_by=initiator,
            )
        except Exception as exc:
            # Guard against race condition: re-check if flow was created concurrently
            existing = self.store.get_flow_state(branch) or {}
            if existing:
                log.warning(
                    f"Flow created concurrently for #{issue.number}, using existing"
                )
                return existing
            # Clean up orphan branch if we created it and flow registration failed
            if branch_created:
                try:
                    self.git.delete_branch(branch, skip_if_worktree=True)
                    log.info(
                        f"Cleaned up orphan branch '{branch}' "
                        "after flow creation failure"
                    )
                except Exception as cleanup_exc:
                    log.warning(
                        f"Failed to clean up branch '{branch}' "
                        f"after flow creation failure: {cleanup_exc}"
                    )
            raise RuntimeError(
                f"Failed to create flow for issue #{issue.number}: {exc}"
            ) from exc

        # Bind issue via TaskService
        try:
            self.task_service.link_issue(branch, issue.number, "task", actor=None)
        except Exception as exc:
            log.warning(f"Failed to link issue #{issue.number} to flow: {exc}")

        log.info(f"Created flow '{slug}' on branch '{branch}'")
        return flow_state.model_dump()

    def get_pr_for_issue(self, issue_number: int) -> int | None:
        """Get PR number for an issue.

        Priority:
        1. PR stored in flow state
        2. GitHub API lookup via GitHubClient
        """
        flow = self.get_flow_for_issue(issue_number)
        if flow and flow.get("pr_number"):
            return int(flow["pr_number"])

        return self.github.get_pr_for_issue(issue_number, repo=self.config.repo)
