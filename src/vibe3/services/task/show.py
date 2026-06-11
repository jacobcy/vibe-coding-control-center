"""Read-side task summary query service for `task show`."""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from vibe3.clients import GitClient, GitHubClient, GitHubClientProtocol, SQLiteClient
from vibe3.models import FlowStatusResponse, PRResponse
from vibe3.services.pr.service import PRService
from vibe3.services.shared.artifacts import ArtifactParser
from vibe3.services.shared.comment import is_human_comment
from vibe3.services.shared.paths import resolve_ref_path

if TYPE_CHECKING:
    from vibe3.services.protocols import FlowQueryProtocol


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


@dataclass
class TaskShowResult:
    """Task show query result with local context."""

    branch: str
    local_task: FlowStatusResponse | None = None
    task_issue_numbers: list[int] = field(default_factory=list)
    related_issue_numbers: list[int] | None = None
    dependency_issue_numbers: list[int] | None = None
    issue_title: str | None = None
    issue_state: str | None = None
    latest_ref: TaskRefSummary | None = None
    latest_human_instruction: TaskCommentSummary | None = None
    latest_comment: TaskCommentSummary | None = None
    pr_summary: TaskPRSummary | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize task show result for JSON output."""
        return {
            "branch": self.branch,
            "local_task": (
                self.local_task.model_dump() if self.local_task is not None else None
            ),
            "task_issue_numbers": self.task_issue_numbers,
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


class TaskShowService:
    """Read/query side for task scene summary."""

    def __init__(
        self,
        store: SQLiteClient,
        flow_service: "FlowQueryProtocol",
        github_client: GitHubClient,
        git_client: GitClient | None = None,
    ) -> None:
        self.store = store
        self._flow_service = flow_service
        self.github_client = github_client
        self._git_client = git_client

    def fetch_issue_with_comments(
        self, issue_number: int
    ) -> dict[str, object] | str | None:
        """Fetch issue data including comments from GitHub."""
        return self.github_client.view_issue(
            issue_number,
            fields=[
                "number",
                "title",
                "body",
                "state",
                "updatedAt",
                "labels",
                "comments",
                "milestone",
                "assignees",
            ],
        )

    def resolve_branch(
        self,
        branch: str | None = None,
        *,
        pr_number: int | None = None,
        position_arg: str | None = None,
        allow_no_flow: bool = False,
    ) -> str:
        """Resolve explicit or current branch for task commands.

        Args:
            branch: Branch name or issue number (--branch option)
            pr_number: PR number to resolve branch from
            position_arg: Positional argument (issue number or branch)
            allow_no_flow: If True, return raw numeric string instead of raising
                UserError when no flows exist for an issue number.
        """
        from vibe3.services.pr.resolver import resolve_command_branch

        return resolve_command_branch(
            branch_opt=branch,
            pr_opt=pr_number,
            position_arg=position_arg,
            flow_service=self._flow_service,
            github_client=self.github_client,
            git_client=self._git_client,
            allow_no_flow=allow_no_flow,
        )

    @staticmethod
    def _summarize_text(text: str, *, limit: int = 1200) -> str:
        result: list[str] = []
        prev_blank = False
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped in {"---", "```"}:
                if result and not prev_blank:
                    result.append("")
                    prev_blank = True
                continue
            stripped = re.sub(r"^#{1,6}\s*", "", stripped)
            stripped = re.sub(r"^[-*+]\s*", "", stripped)
            stripped = re.sub(r"^\d+\.\s*", "", stripped)
            if stripped:
                result.append(stripped)
                prev_blank = False
        while result and result[-1] == "":
            result.pop()
        collapsed = "\n".join(result)
        if not collapsed:
            return ""
        if len(collapsed) <= limit:
            return collapsed
        return collapsed[:limit].rstrip() + "..."

    def _build_comment_summary(
        self, comment: dict[str, Any] | None, *, full_body: bool = False
    ) -> TaskCommentSummary | None:
        """Build comment summary.

        Args:
            comment: Comment dict from GitHub API
            full_body: If True, return full body without truncation.
                       If False (default), summarize to 1200 chars.
        """
        if not comment:
            return None

        author = str((comment.get("author") or {}).get("login") or "unknown").strip()
        body = str(comment.get("body") or "").strip()
        if not body:
            return None
        if not full_body:
            body = self._summarize_text(body)
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
        """Select the latest ref from previous round based on state transitions.

        Uses state machine logic: reviewer_status==done → audit_ref,
        executor_status==done → report_ref, planner_status==done → plan_ref.
        Falls back to most recent ref by mtime if no status is done.
        """
        worktree_root = flow.worktree_root

        # Check state transitions in reverse order: reviewer → executor → planner
        status_to_ref = {
            "reviewer_status": ("audit_ref", "audit"),
            "executor_status": ("report_ref", "report"),
            "planner_status": ("plan_ref", "plan"),
        }

        for status_field, (ref_field, kind) in status_to_ref.items():
            status_value = getattr(flow, status_field, None)
            if status_value == "done":
                ref_value = getattr(flow, ref_field, None)
                if ref_value:
                    summary = self._build_ref_summary(kind, ref_value, worktree_root)
                    if summary:
                        return summary

        # Fallback: most recent ref by modification time
        current_refs = {
            "plan": flow.plan_ref,
            "report": flow.report_ref,
            "audit": flow.audit_ref,
        }

        fallback_candidates: list[tuple[float, TaskRefSummary]] = []
        for kind, ref_value in current_refs.items():
            if not ref_value:
                continue
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
        try:
            pr = PRService(
                github_client=cast(GitHubClientProtocol, self.github_client),
                store=self.store,
            ).get_branch_pr_status(branch)
            if not pr:
                return None
        except (subprocess.CalledProcessError, FileNotFoundError):
            # GitHub CLI not available or query failed
            return None

        return TaskPRSummary(
            number=pr.number,
            title=pr.title,
            state=pr.state.value.lower(),
            draft=pr.draft,
            url=pr.url,
            checks=self._normalize_pr_checks(pr),
        )

    def show_task(self, branch: str | None = None) -> TaskShowResult:
        """Load task detail from local state plus quick remote summary."""
        # Skip re-resolution if branch is already provided (resolved by command layer)
        if branch is None:
            target_branch = self.resolve_branch()
        else:
            target_branch = branch
        local_task = self._flow_service.get_flow_status(target_branch)

        # Resolve task issue numbers from DB links
        from vibe3.services.issue import IssueFlowService

        issue_flow_service = IssueFlowService(store=self.store)
        task_issue_number = issue_flow_service.resolve_task_issue_number(target_branch)
        task_issue_numbers = [task_issue_number] if task_issue_number else []

        # Resolve related and dependency issue numbers from DB links
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

        # Determine issue number: from flow or from branch if numeric
        issue_number: int | None = None
        if local_task and local_task.task_issue_number:
            issue_number = local_task.task_issue_number
        elif target_branch.isdigit():
            # Branch is an issue number but no flow exists
            issue_number = int(target_branch)
        elif not local_task:
            # Try to resolve from branch name pattern (e.g., task/issue-123)
            issue_number = issue_flow_service.resolve_task_issue_number(target_branch)

        if issue_number:
            issue = self.fetch_issue_with_comments(issue_number)
            if isinstance(issue, dict):
                issue_title = str(issue.get("title") or "").strip() or None
                issue_state = str(issue.get("state") or "").strip() or None
                comments_raw = issue.get("comments")
                comments: list[dict[str, Any]] = (
                    cast(list[dict[str, Any]], comments_raw)
                    if isinstance(comments_raw, list)
                    else []
                )
                latest_comment = self._build_comment_summary(
                    comments[-1] if comments else None, full_body=True
                )
                latest_human_instruction = self._build_comment_summary(
                    next(
                        (
                            comment
                            for comment in reversed(comments)
                            if is_human_comment(comment)
                        ),
                        None,
                    ),
                    full_body=True,
                )

        return TaskShowResult(
            branch=target_branch,
            local_task=local_task,
            task_issue_numbers=task_issue_numbers,
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
