"""Task service implementation."""

from dataclasses import dataclass
from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_labels import GhIssueLabelPort, IssueLabelPort
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.exceptions import GitError
from vibe3.models.flow import FlowStatusResponse, IssueLink
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.models.pr import PRResponse
from vibe3.services.flow_service import FlowService
from vibe3.services.label_service import LabelService
from vibe3.services.signature_service import SignatureService
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input


@dataclass
class TaskListRow:
    """UI-friendly task list row."""

    branch: str
    flow_slug: str
    flow_status: str
    task_issue_number: int | None


@dataclass
class TaskShowResult:
    """Task show query result with local context."""

    branch: str
    local_task: FlowStatusResponse | None = None
    related_issue_numbers: list[int] | None = None
    dependency_issue_numbers: list[int] | None = None


class TaskService:
    """Service for managing task state."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        github_client: GitHubClient | None = None,
        issue_label_port: IssueLabelPort | None = None,
        orchestra_config: OrchestraConfig | None = None,
    ) -> None:
        self.store = SQLiteClient() if store is None else store
        self._flow_service = FlowService(store=self.store)
        self.github_client = GitHubClient() if github_client is None else github_client
        self._issue_label_port = issue_label_port
        self._orchestra_config = orchestra_config

    # ------------------------------------------------------------------
    # Core task operations
    # ------------------------------------------------------------------

    def link_issue(
        self,
        branch: str,
        issue_number: int,
        role: Literal["task", "related", "dependency"] = "related",
        actor: str | None = None,
    ) -> IssueLink:
        """Link an issue to a flow."""
        logger.bind(
            domain="task",
            action="link_issue",
            branch=branch,
            issue_number=issue_number,
            role=role,
        ).info("Linking issue to flow")

        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )

        self.store.add_issue_link(branch, issue_number, role)

        if role == "task":
            # task_issue_number is no longer stored in flow_state.
            # We only update latest_actor to track activity.
            self.store.update_flow_state(
                branch,
                latest_actor=effective_actor,
            )

        self.store.add_event(
            branch,
            "issue_linked",
            effective_actor,
            f"Issue #{issue_number} linked as {role}",
        )

        if role == "task":
            self._enforce_single_task_flow(
                current_branch=branch,
                issue_number=issue_number,
                actor=effective_actor,
            )

        return IssueLink(
            branch=branch,
            issue_number=issue_number,
            issue_role=role,
        )

    def reclassify_issue(
        self,
        branch: str,
        issue_number: int,
        *,
        old_role: Literal["task", "related", "dependency"],
        new_role: Literal["task", "related", "dependency"],
        actor: str | None = None,
    ) -> IssueLink:
        """Reclassify an existing issue link without deleting flow history."""
        logger.bind(
            domain="task",
            action="reclassify_issue",
            branch=branch,
            issue_number=issue_number,
            old_role=old_role,
            new_role=new_role,
        ).info("Reclassifying issue link")

        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )

        updated = self.store.update_issue_link_role(
            branch,
            issue_number,
            old_role,
            new_role,
        )
        if not updated:
            raise ValueError(
                f"Issue #{issue_number} not linked as {old_role} on flow {branch}"
            )

        self.store.update_flow_state(
            branch,
            latest_actor=effective_actor,
        )
        self.store.add_event(
            branch,
            "issue_reclassified",
            effective_actor,
            f"Issue #{issue_number} reclassified: {old_role} -> {new_role}",
        )

        return IssueLink(
            branch=branch,
            issue_number=issue_number,
            issue_role=new_role,
        )

    def _enforce_single_task_flow(
        self,
        *,
        current_branch: str,
        issue_number: int,
        actor: str,
    ) -> None:
        task_flows = self.store.get_flows_by_issue(issue_number, role="task")
        if not isinstance(task_flows, list):
            return
        superseded_flows = [
            flow
            for flow in task_flows
            if str(flow.get("branch") or "").strip() != current_branch
        ]
        if not superseded_flows:
            return

        logger.bind(
            domain="task",
            action="enforce_single_task_flow",
            issue_number=issue_number,
            current_branch=current_branch,
            superseded_count=len(superseded_flows),
        ).info("Demoting superseded task flows")

        for flow in superseded_flows:
            old_branch = str(flow.get("branch") or "").strip()
            if not old_branch:
                continue
            self.reclassify_issue(
                old_branch,
                issue_number,
                old_role="task",
                new_role="related",
                actor=actor,
            )
            self._notify_superseded_canonical_flow(
                old_branch=old_branch,
                new_branch=current_branch,
                issue_number=issue_number,
                actor=actor,
            )

    def _notify_superseded_canonical_flow(
        self,
        *,
        old_branch: str,
        new_branch: str,
        issue_number: int,
        actor: str,
    ) -> None:
        canonical_branch = f"task/issue-{issue_number}"
        if old_branch != canonical_branch:
            return

        pr = self._get_branch_pr(old_branch)
        if pr is None:
            return

        config = self._get_orchestra_config()
        issue_payload = self.github_client.view_issue(issue_number, repo=config.repo)
        if not isinstance(issue_payload, dict):
            logger.bind(
                domain="task",
                action="notify_superseded_canonical_flow",
                issue_number=issue_number,
                old_branch=old_branch,
            ).warning("Unable to load issue payload for superseded task flow")
            return

        if str(issue_payload.get("state") or "").strip().lower() != "open":
            return

        assignees = [
            str(assignee.get("login") or "").strip()
            for assignee in issue_payload.get("assignees", [])
            if isinstance(assignee, dict) and str(assignee.get("login") or "").strip()
        ]
        if assignees and not self.github_client.remove_assignees(
            issue_number,
            assignees,
            repo=config.repo,
        ):
            logger.bind(
                domain="task",
                action="notify_superseded_canonical_flow",
                issue_number=issue_number,
                assignees=assignees,
            ).warning("Failed to remove issue assignees for superseded task flow")

        supervisor_label = config.supervisor_handoff.issue_label
        if not self._get_issue_label_port().add_issue_label(
            issue_number,
            supervisor_label,
        ):
            logger.bind(
                domain="task",
                action="notify_superseded_canonical_flow",
                issue_number=issue_number,
                label=supervisor_label,
            ).warning("Failed to add supervisor label for superseded task flow")

        try:
            LabelService(issue_port=self._get_issue_label_port()).set_state(
                issue_number,
                IssueState.HANDOFF,
            )
        except Exception as exc:
            logger.bind(
                domain="task",
                action="notify_superseded_canonical_flow",
                issue_number=issue_number,
                state_label=config.supervisor_handoff.handoff_state_label,
            ).warning(f"Failed to move superseded task issue to handoff: {exc}")

        pr_state = pr.state.value.lower()
        comment = (
            f"[{actor}] 检测到 issue #{issue_number} 之前的 task flow "
            f"`{old_branch}` 已被新 flow `{new_branch}` 取代。\n\n"
            f"该旧 flow 关联 PR #{pr.number}（state: {pr_state}）。"
            f"当前 issue 可能已在该 PR 完成，请确认是否应关闭。"
        )
        if not self.github_client.add_comment(issue_number, comment, repo=config.repo):
            logger.bind(
                domain="task",
                action="notify_superseded_canonical_flow",
                issue_number=issue_number,
                pr_number=pr.number,
            ).warning("Failed to post superseded-task reminder comment")

    def _get_branch_pr(self, branch: str) -> PRResponse | None:
        try:
            prs = self.github_client.list_prs_for_branch(branch, state="all")
        except Exception as exc:
            logger.bind(
                domain="task",
                action="get_branch_pr",
                branch=branch,
            ).warning(f"Failed to query PRs for superseded task flow: {exc}")
            return None
        return prs[0] if prs else None

    def _get_orchestra_config(self) -> OrchestraConfig:
        if self._orchestra_config is None:
            self._orchestra_config = load_orchestra_config()
        return self._orchestra_config

    def _get_issue_label_port(self) -> IssueLabelPort:
        if self._issue_label_port is None:
            config = self._get_orchestra_config()
            self._issue_label_port = GhIssueLabelPort(repo=config.repo)
        return self._issue_label_port

    def get_task(self, branch: str) -> FlowStatusResponse | None:
        """Get task (flow) details."""
        logger.bind(domain="task", action="get", branch=branch).debug("Getting task")
        return self._flow_service.get_flow_status(branch)

    def fetch_issue_with_comments(
        self, issue_number: int
    ) -> dict[str, object] | str | None:
        """Fetch issue data including comments from GitHub.

        Args:
            issue_number: GitHub issue number

        Returns:
            Issue dict, "network_error" string, or None if not found
        """
        return self.github_client.view_issue(issue_number)

    # ------------------------------------------------------------------
    # Task query operations (merged from task_usecase.py)
    # ------------------------------------------------------------------

    def list_task_rows(self) -> list[TaskListRow]:
        """List local tasks as UI-oriented rows."""
        task_flows = [
            flow for flow in self._flow_service.list_flows() if flow.task_issue_number
        ]
        rows: list[TaskListRow] = []
        for task_flow in task_flows:
            rows.append(
                TaskListRow(
                    branch=task_flow.branch,
                    flow_slug=task_flow.flow_slug,
                    flow_status=task_flow.flow_status,
                    task_issue_number=task_flow.task_issue_number,
                )
            )
        return rows

    def resolve_branch(self, branch: str | None = None) -> str:
        """Resolve explicit or current branch for task commands."""
        if branch:
            return resolve_issue_branch_input(branch, self._flow_service) or branch
        try:
            return self._flow_service.get_current_branch()
        except GitError as exc:
            raise RuntimeError(f"unable to resolve current branch ({exc})") from exc

    def show_task(self, branch: str | None = None) -> TaskShowResult:
        """Load task detail from local state."""
        target_branch = self.resolve_branch(branch)
        local_task = self.get_task(target_branch)

        issue_links = self.store.get_issue_links(target_branch)
        related_issue_numbers = [
            link["issue_number"]
            for link in issue_links
            if link["issue_role"] == "related"
        ]
        dependency_issue_numbers = [
            link["issue_number"]
            for link in issue_links
            if link["issue_role"] == "dependency"
        ]
        return TaskShowResult(
            branch=target_branch,
            local_task=local_task,
            related_issue_numbers=related_issue_numbers,
            dependency_issue_numbers=dependency_issue_numbers,
        )
