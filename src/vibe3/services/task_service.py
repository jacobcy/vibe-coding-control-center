"""Task service implementation."""

from typing import Any, Literal

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
from vibe3.services.task_show_service import (
    TaskCommentSummary,
    TaskPRSummary,
    TaskRefSummary,
    TaskShowResult,
    TaskShowService,
    is_human_comment,
)

__all__ = [
    "TaskService",
    "TaskShowService",
    "TaskShowResult",
    "TaskRefSummary",
    "TaskCommentSummary",
    "TaskPRSummary",
    "is_human_comment",
]


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
        self._show_service = TaskShowService(
            store=self.store,
            flow_service=self._flow_service,
            github_client=self.github_client,
        )
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
        # Normalize branch name to prevent case/space variants
        normalized_branch = branch.strip()

        logger.bind(
            domain="task",
            action="link_issue",
            branch=normalized_branch,
            issue_number=issue_number,
            role=role,
        ).info("Linking issue to flow")

        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            normalized_branch,
            explicit_actor=actor,
        )

        # CRITICAL: For task role, query existing task flows BEFORE adding new link
        # to prevent data inconsistency if reclassification fails
        superseded_flows: list[dict[str, Any]] = []
        if role == "task":
            task_flows = self.store.get_flows_by_issue(issue_number, role="task")
            if isinstance(task_flows, list):
                superseded_flows = [
                    flow
                    for flow in task_flows
                    if str(flow.get("branch") or "").strip() != normalized_branch
                ]

        # Now add the new link
        self.store.add_issue_link(normalized_branch, issue_number, role)

        # Fetch existing events for idempotent checks
        existing_events = self.store.get_events(normalized_branch)

        if role == "task":
            # Write spec_ref for task role (issue number as spec)
            self.store.update_flow_state(
                normalized_branch,
                latest_actor=effective_actor,
                spec_ref=f"#{issue_number}",
            )
            # Add spec_bound event (idempotent)
            already_bound = any(
                e.get("event_type") == "spec_bound"
                and str((e.get("refs") or {}).get("issue_number") or "")
                == str(issue_number)
                for e in existing_events
            )
            if not already_bound:
                self.store.add_event(
                    normalized_branch,
                    "spec_bound",
                    effective_actor,
                    f"Spec bound: #{issue_number}",
                    refs={"issue_number": issue_number},
                )

        # Add issue_linked event (idempotent)
        already_linked = any(
            e.get("event_type") == "issue_linked"
            and str((e.get("refs") or {}).get("issue_number") or "")
            == str(issue_number)
            for e in existing_events
        )
        if not already_linked:
            self.store.add_event(
                normalized_branch,
                "issue_linked",
                effective_actor,
                f"Issue #{issue_number} linked as {role}",
                refs={"issue_number": issue_number, "role": role},
            )

        # Demote superseded flows AFTER successful link
        if role == "task" and superseded_flows:
            self._demote_superseded_flows(
                superseded_flows=superseded_flows,
                current_branch=normalized_branch,
                issue_number=issue_number,
                actor=effective_actor,
            )

        return IssueLink(
            branch=normalized_branch,
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

    def _demote_superseded_flows(
        self,
        *,
        superseded_flows: list[dict[str, Any]],
        current_branch: str,
        issue_number: int,
        actor: str,
    ) -> None:
        """Demote superseded task flows to related role."""
        if not superseded_flows:
            return

        logger.bind(
            domain="task",
            action="demote_superseded_flows",
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
        label_added = False
        try:
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
                return  # Cannot proceed without supervisor label
            label_added = True

            LabelService(issue_port=self._get_issue_label_port()).set_state(
                issue_number,
                IssueState.HANDOFF,
            )
        except Exception as exc:
            logger.bind(
                domain="task",
                action="notify_superseded_canonical_flow",
                issue_number=issue_number,
                error=str(exc),
            ).exception("Failed to set handoff state for superseded task issue")

            # Rollback supervisor label if state transition failed after label was added
            if label_added:
                try:
                    self._get_issue_label_port().remove_issue_label(
                        issue_number,
                        supervisor_label,
                    )
                except Exception as rollback_exc:
                    logger.bind(
                        domain="task",
                        action="notify_superseded_canonical_flow_rollback",
                        issue_number=issue_number,
                        label=supervisor_label,
                    ).warning(f"Failed to rollback supervisor label: {rollback_exc}")

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
        except GitError as exc:
            logger.bind(
                domain="task",
                action="get_branch_pr",
                branch=branch,
                error=str(exc),
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
        return self._show_service.fetch_issue_with_comments(issue_number)

    def resolve_branch(self, branch: str | None = None) -> str:
        """Resolve explicit or current branch for task commands."""
        return self._show_service.resolve_branch(branch)

    def show_task(self, branch: str | None = None) -> TaskShowResult:
        """Load task detail from local state."""
        return self._show_service.show_task(branch)

    def search_issues(
        self,
        query: str,
        limit: int = 30,
        state: str = "open",
        label: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search GitHub issues for potential duplicates.

        Args:
            query: Search query string
            limit: Maximum number of results
            state: Issue state filter (open, closed, all)
            label: Optional label filter

        Returns:
            List of issue dicts with number, title, state, labels
        """
        return self.github_client.search_issues(
            query=query,
            limit=limit,
            state=state,
            label=label,
        )
