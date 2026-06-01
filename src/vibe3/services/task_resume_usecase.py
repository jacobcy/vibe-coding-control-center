"""Unified task resume usecase.

Provides a single entry point for resuming tasks regardless of
whether they are in failed or blocked state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, cast

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService
from vibe3.services.status_query_service import StatusQueryService
from vibe3.services.task_resume_candidates import TaskResumeCandidates
from vibe3.services.task_resume_operations import TaskResumeOperations

if TYPE_CHECKING:
    from vibe3.models.flow import FlowStatusResponse


# Type alias for progress callback: (issue_number, branch, step, status) -> None
ProgressCallback = Callable[[int, str | None, str, str], None]


def _format_resume_failure_reason(exc: Exception) -> str:
    """Return a concise, human-readable failure reason for resume output."""
    detail = str(exc).strip()
    if detail:
        return detail
    return exc.__class__.__name__


class TaskResumeUsecase:
    """Unified usecase for resuming failed or blocked tasks."""

    def __init__(
        self,
        status_service: StatusQueryService | None = None,
        label_service: LabelService | None = None,
        flow_service: FlowService | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
        issue_flow_service: IssueFlowService | None = None,
    ) -> None:
        self.status_service = status_service or StatusQueryService()
        self.label_service = label_service or LabelService()
        self.flow_service = flow_service or FlowService()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()
        self.issue_flow_service = issue_flow_service or IssueFlowService()

        # Initialize delegate modules
        self.candidates = TaskResumeCandidates(
            status_service=self.status_service,
            label_service=self.label_service,
            flow_service=self.flow_service,
            issue_flow_service=self.issue_flow_service,
        )
        self.operations = TaskResumeOperations(
            git_client=self.git_client,
            github_client=self.github_client,
            flow_service=self.flow_service,
            label_service=self.label_service,
            issue_flow_service=self.issue_flow_service,
        )

    def resume_issues(
        self,
        issue_numbers: list[int] | None = None,
        reason: str = "",
        dry_run: bool = False,
        flows: list[FlowStatusResponse] | None = None,
        stale_flows: list[FlowStatusResponse] | None = None,
        repo: str | None = None,
        label_state: str = "",
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        """Resume blocked issues.

        Args:
            issue_numbers: Optional list of specific issue numbers to resume
            reason: Resume reason to include in comments
            dry_run: If True, only report candidates without mutating
            flows: Active flow status responses
            stale_flows: Stale flow status responses
            repo: Repository (owner/repo format, optional)
            label_state: State to restore. Empty string means infer automatically.
                Task resume preserves worktree/branch; destructive rebuild belongs
                to FlowRebuildUsecase.
            progress_callback: Optional callback for progress updates.
                Signature: (issue_number: int, branch: str | None, step: str,
                    status: str) -> None

        Returns:
            Dict with:
                - resumed: List of successfully resumed issues
                - skipped: List of skipped issues with reasons
                - requested: List of requested issue numbers (if provided)
                - candidates: List of resumable candidates (dry-run only)
        """
        candidates = self.status_service.fetch_resume_candidates(
            flows=flows or [], stale_flows=stale_flows or []
        )

        if issue_numbers is not None:
            candidates = self.candidates.merge_explicit_issue_candidates(
                issue_numbers=issue_numbers,
                candidates=candidates,
                flows=flows or [],
                stale_flows=stale_flows or [],
            )

        # Filter by requested issue numbers if provided
        if issue_numbers is not None:
            candidates = [c for c in candidates if c.get("number") in issue_numbers]

        result: dict[str, Any] = {
            "resumed": [],
            "skipped": [],
            "requested": issue_numbers if issue_numbers is not None else [],
        }

        # Add skipped for requested issues not in candidates
        if issue_numbers is not None:
            candidate_numbers = {c.get("number") for c in candidates}
            for issue_num in issue_numbers:
                if issue_num not in candidate_numbers:
                    result["skipped"].append(
                        {
                            "number": issue_num,
                            "reason": "当前状态或现场不支持恢复，跳过恢复",
                        }
                    )

        # Dry-run: return candidates without mutation
        if dry_run:
            result["candidates"] = candidates
            return result

        # Apply resume operations
        for candidate in candidates:
            issue_number = candidate.get("number")
            resume_kind = candidate.get("resume_kind")
            flow = cast("FlowStatusResponse | None", candidate.get("flow"))
            branch = getattr(flow, "branch", None) if flow else None

            if not isinstance(issue_number, int) or not isinstance(resume_kind, str):
                continue

            logger.bind(
                domain="resume",
                action="candidate",
                issue_number=issue_number,
                resume_kind=resume_kind,
                branch=branch,
            ).info("Processing resume candidate")

            if not self.candidates.verify_issue_state_for_resume(
                issue_number, resume_kind, repo
            ):
                result["skipped"].append(
                    {
                        "number": issue_number,
                        "reason": "状态验证失败，跳过恢复",
                    }
                )
                continue

            try:
                self.operations.reset_issue_to_ready(
                    issue_number=issue_number,
                    resume_kind=resume_kind,
                    flow=flow,
                    repo=repo,
                    reason=reason,
                    label_state=label_state,
                    progress_callback=progress_callback,
                )

                result["resumed"].append(
                    {"number": issue_number, "resume_kind": resume_kind}
                )

            except Exception as exc:
                failure_reason = _format_resume_failure_reason(exc)
                logger.bind(
                    domain="resume",
                    action="candidate_failed",
                    issue_number=issue_number,
                    resume_kind=resume_kind,
                    branch=branch,
                ).warning(f"Resume candidate failed: {failure_reason}")
                result["skipped"].append(
                    {
                        "number": issue_number,
                        "reason": f"恢复操作失败: {failure_reason}",
                    }
                )

        return result
