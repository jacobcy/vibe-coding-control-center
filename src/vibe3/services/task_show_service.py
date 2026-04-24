"""Read-side task summary query service for `task show`."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import GitError
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.pr import PRResponse
from vibe3.services.artifact_parser import ArtifactParser
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
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
        flow_service: FlowService,
        github_client: GitHubClient,
    ) -> None:
        self.store = store
        self.flow_service = flow_service
        self.github_client = github_client

    def fetch_issue_with_comments(
        self, issue_number: int
    ) -> dict[str, object] | str | None:
        """Fetch issue data including comments from GitHub."""
        return self.github_client.view_issue(issue_number)

    def resolve_branch(self, branch: str | None = None) -> str:
        """Resolve explicit or current branch for task commands."""
        if branch:
            return resolve_issue_branch_input(branch, self.flow_service) or branch
        try:
            return self.flow_service.get_current_branch()
        except GitError as exc:
            raise RuntimeError(f"unable to resolve current branch ({exc})") from exc

    @staticmethod
    def _summarize_text(text: str, *, limit: int = 50) -> str:
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
            git_client=self.flow_service.git_client,
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

    def show_task(self, branch: str | None = None) -> TaskShowResult:
        """Load task detail from local state plus quick remote summary."""
        target_branch = self.resolve_branch(branch)
        local_task = self.flow_service.get_flow_status(target_branch)

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
                comments_raw = issue.get("comments")
                comments: list[dict[str, Any]] = (
                    comments_raw  # type: ignore[assignment]
                    if isinstance(comments_raw, list)
                    else []
                )
                latest_comment = self._build_comment_summary(
                    comments[-1] if comments else None
                )
                latest_human_instruction = self._build_comment_summary(
                    next(
                        (
                            comment
                            for comment in reversed(comments)
                            if is_human_comment(comment)
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
