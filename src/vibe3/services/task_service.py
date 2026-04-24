"""Task service implementation."""

import re
from dataclasses import asdict, dataclass
from pathlib import Path
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
from vibe3.services.artifact_parser import ArtifactParser
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.services.label_service import LabelService
from vibe3.services.signature_service import SignatureService
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input
from vibe3.utils.path_helpers import resolve_ref_path


def is_human_comment(comment: dict[str, Any]) -> bool:
    """Return True if the comment author is a human (not a bot or linear)."""
    author = comment.get("author") or {}
    login = str(author.get("login") or "").strip().lower()
    if not login:
        return True
    return login != "linear" and not login.endswith("[bot]")


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
    issue_title: str | None = None
    issue_state: str | None = None
    latest_ref: "TaskRefSummary | None" = None
    latest_human_instruction: "TaskCommentSummary | None" = None
    latest_comment: "TaskCommentSummary | None" = None
    pr_summary: "TaskPRSummary | None" = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize task show result for JSON output."""
        payload: dict[str, Any] = {
            "branch": self.branch,
            "local_task": (
                self.local_task.model_dump() if self.local_task is not None else None
            ),
            "related_issue_numbers": self.related_issue_numbers or [],
            "dependency_issue_numbers": self.dependency_issue_numbers or [],
            "issue_title": self.issue_title,
            "issue_state": self.issue_state,
            "latest_ref": asdict(self.latest_ref) if self.latest_ref else None,
            "latest_human_instruction": (
                asdict(self.latest_human_instruction)
                if self.latest_human_instruction
                else None
            ),
            "latest_comment": (
                asdict(self.latest_comment) if self.latest_comment else None
            ),
            "pr_summary": asdict(self.pr_summary) if self.pr_summary else None,
        }
        return payload


@dataclass
class TaskRefSummary:
    """Focused summary of the latest authoritative ref."""

    kind: str
    ref: str
    summary: str


@dataclass
class TaskCommentSummary:
    """Focused summary of the latest issue instruction/comment."""

    author: str
    body: str
    created_at: str | None = None


@dataclass
class TaskPRSummary:
    """PR/CI snapshot for quick task inspection."""

    number: int
    title: str
    state: str
    draft: bool
    url: str
    checks: str | None = None


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

        if role == "task":
            # task_issue_number is no longer stored in flow_state.
            # We only update latest_actor to track activity.
            self.store.update_flow_state(
                normalized_branch,
                latest_actor=effective_actor,
            )

        self.store.add_event(
            normalized_branch,
            "issue_linked",
            effective_actor,
            f"Issue #{issue_number} linked as {role}",
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

    @staticmethod
    def _is_human_comment(comment: dict[str, Any]) -> bool:
        return is_human_comment(comment)

    @staticmethod
    def _summarize_text(text: str, *, limit: int = 50) -> str:
        """Collapse markdown-ish content into a single short preview line."""
        parts: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped in {"---", "```"}:
                continue
            stripped = re.sub(r"^#{1,6}\s*", "", stripped)
            stripped = re.sub(r"^[-*+]\s*", "", stripped)
            stripped = re.sub(r"^\d+\.\s*", "", stripped)
            if stripped:
                parts.append(stripped)

        collapsed = re.sub(r"\s+", " ", " ".join(parts)).strip()
        if not collapsed:
            return ""
        if len(collapsed) <= limit:
            return collapsed
        return collapsed[:limit].rstrip() + "..."

    def _build_comment_summary(
        self, comment: dict[str, Any] | None
    ) -> TaskCommentSummary | None:
        if not comment:
            return None

        author = str((comment.get("author") or {}).get("login") or "unknown").strip()
        body = self._summarize_text(str(comment.get("body") or "").strip())
        if not body:
            return None

        return TaskCommentSummary(
            author=author or "unknown",
            body=body,
            created_at=str(comment.get("createdAt") or "") or None,
        )

    def _resolve_ref_abspath(
        self, ref_value: str | None, worktree_root: str | None
    ) -> Path | None:
        if not ref_value:
            return None

        absolute_path = resolve_ref_path(ref_value, worktree_root, absolute=True)
        if not absolute_path:
            return None

        path = Path(absolute_path)
        if not path.exists() or not path.is_file():
            return None
        return path

    def _build_ref_summary(
        self, kind: str, ref_value: str | None, worktree_root: str | None
    ) -> TaskRefSummary | None:
        if not ref_value:
            return None

        ref_path = self._resolve_ref_abspath(ref_value, worktree_root)
        if ref_path is None:
            return None

        try:
            raw_content = ref_path.read_text(encoding="utf-8")
        except OSError:
            return None

        content = ArtifactParser.sanitize_handoff_content(raw_content)
        summary = self._summarize_text(content)
        if not summary:
            return None

        return TaskRefSummary(kind=kind, ref=ref_value, summary=summary)

    def _select_latest_ref(
        self, branch: str, flow: FlowStatusResponse
    ) -> TaskRefSummary | None:
        worktree_root = flow.worktree_root
        current_refs = {
            "plan": flow.plan_ref,
            "report": flow.report_ref,
            "audit": flow.audit_ref,
        }

        handoff_service = HandoffService(
            store=self.store,
            git_client=self._flow_service.git_client,
        )
        events = sorted(
            handoff_service.get_handoff_events(branch),
            key=lambda event: event.created_at,
            reverse=True,
        )
        event_to_kind = {
            "handoff_plan": "plan",
            "handoff_report": "report",
            "handoff_run": "report",
            "handoff_audit": "audit",
        }
        for event in events:
            kind = event_to_kind.get(event.event_type)
            if not kind:
                continue
            refs = event.refs if isinstance(event.refs, dict) else {}
            event_ref = str(refs.get("ref") or "")
            if not event_ref or current_refs.get(kind) != event_ref:
                continue
            summary = self._build_ref_summary(kind, event_ref, worktree_root)
            if summary is not None:
                return summary

        fallback_candidates: list[tuple[float, TaskRefSummary]] = []
        for kind, ref_value in current_refs.items():
            summary = self._build_ref_summary(kind, ref_value, worktree_root)
            if summary is None:
                continue
            ref_path = self._resolve_ref_abspath(ref_value, worktree_root)
            if ref_path is None:
                continue
            fallback_candidates.append((ref_path.stat().st_mtime, summary))

        if not fallback_candidates:
            return None
        fallback_candidates.sort(key=lambda item: item[0], reverse=True)
        return fallback_candidates[0][1]

    @staticmethod
    def _normalize_pr_checks(pr: PRResponse) -> str | None:
        checks = pr.ci_status
        if checks:
            lowered = str(checks).strip().lower()
            if lowered == "success":
                return "pass"
            if lowered in {"failure", "failed", "error"}:
                return "fail"
            if lowered in {"pending", "expected", "queued", "in_progress"}:
                return "pending"
            return lowered
        if pr.ci_passed:
            return "pass"
        if pr.state.value.upper() == "OPEN":
            return "pending"
        return None

    def _build_pr_summary(self, branch: str) -> TaskPRSummary | None:
        pr = self.github_client.get_pr(branch=branch)
        if pr is None:
            return None
        return TaskPRSummary(
            number=pr.number,
            title=pr.title,
            state=pr.state.value.lower(),
            draft=pr.draft,
            url=pr.url,
            checks=self._normalize_pr_checks(pr),
        )

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

        issue_title: str | None = None
        issue_state: str | None = None
        latest_human_instruction: TaskCommentSummary | None = None
        latest_comment: TaskCommentSummary | None = None
        if local_task and local_task.task_issue_number:
            issue = self.fetch_issue_with_comments(local_task.task_issue_number)
            if isinstance(issue, dict):
                issue_title = str(issue.get("title") or "").strip() or None
                issue_state = str(issue.get("state") or "").strip() or None
                comments_raw = issue.get("comments") or []
                comments: list[dict[str, Any]] = (
                    comments_raw if isinstance(comments_raw, list) else []
                )
                latest_comment = self._build_comment_summary(
                    comments[-1] if comments else None
                )
                latest_human_instruction = self._build_comment_summary(
                    next(
                        (
                            comment
                            for comment in reversed(comments)
                            if self._is_human_comment(comment)
                        ),
                        None,
                    )
                )

        return TaskShowResult(
            branch=target_branch,
            local_task=local_task,
            related_issue_numbers=related_issue_numbers,
            dependency_issue_numbers=dependency_issue_numbers,
            issue_title=issue_title,
            issue_state=issue_state,
            latest_ref=(
                self._select_latest_ref(target_branch, local_task)
                if local_task
                else None
            ),
            latest_human_instruction=latest_human_instruction,
            latest_comment=latest_comment,
            pr_summary=self._build_pr_summary(target_branch),
        )
