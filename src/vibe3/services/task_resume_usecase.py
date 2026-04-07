"""Unified task resume usecase.

Provides a single entry point for resuming tasks regardless of
whether they are in failed or blocked state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
        candidate_mode: str = "resumable",
    ) -> dict[str, Any]:
        """Resume failed or blocked issues.

        Args:
            issue_numbers: Optional list of specific issue numbers to resume
            reason: Resume reason to include in comments
            dry_run: If True, only report candidates without mutating
            flows: Active flow status responses
            stale_flows: Stale flow status responses
            repo: Repository (owner/repo format, optional)

        Returns:
            Dict with:
                - resumed: List of successfully resumed issues
                - skipped: List of skipped issues with reasons
                - requested: List of requested issue numbers (if provided)
                - candidates: List of resumable candidates (dry-run only)
        """
        if candidate_mode == "all_task":
            candidates = self.candidates.build_all_task_candidates(flows or [])
        else:
            candidates = self.status_service.fetch_resume_candidates(
                flows=flows or [], stale_flows=stale_flows or []
            )

        if issue_numbers is not None and candidate_mode != "all_task":
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
        if candidate_mode == "all_task" and issue_numbers is None:
            result["requested"] = [
                num
                for candidate in candidates
                if isinstance((num := candidate.get("number")), int)
            ]

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
            worktree_path: str | None = None

            if not isinstance(issue_number, int) or not isinstance(resume_kind, str):
                continue

            logger.bind(
                domain="resume",
                action="candidate",
                issue_number=issue_number,
                resume_kind=resume_kind,
                branch=branch,
            ).info("Processing resume candidate")

            if resume_kind == "all":
                if isinstance(branch, str):
                    resolved_path = self.git_client.find_worktree_path_for_branch(
                        branch
                    )
                    worktree_path = (
                        str(resolved_path) if resolved_path is not None else None
                    )
                skip_reason = self.candidates.maybe_skip_all_task_candidate(
                    issue_number=issue_number,
                    flow=flow,
                    candidate_state=candidate.get("state"),
                    worktree_path=worktree_path,
                )
                if skip_reason is not None:
                    result["skipped"].append(
                        {"number": issue_number, "reason": skip_reason}
                    )
                    continue

            # Defensive check: verify current state matches resume_kind
            if not self.candidates.verify_issue_state_for_resume(
                issue_number, resume_kind, repo
            ):
                result["skipped"].append(
                    {
                        "number": issue_number,
                        "reason": f"不再处于 {resume_kind} 状态，跳过恢复",
                    }
                )
                continue

            try:
                if resume_kind in {"failed", "blocked", "all"}:
                    self.operations.reset_issue_to_ready(
                        issue_number=issue_number,
                        resume_kind=resume_kind,
                        flow=flow,
                        repo=repo,
                        reason=reason,
                        worktree_path=worktree_path,
                    )

                    if resume_kind == "all":
                        self._comment_all_resume_success(
                            issue_number=issue_number,
                            repo=repo,
                            reason=reason,
                        )

                elif resume_kind == "aborted":
                    flow = cast("FlowStatusResponse | None", candidate.get("flow"))
                    if flow and isinstance(flow.branch, str):
                        self.operations.reactivate_aborted_flow(flow.branch)

                result["resumed"].append(
                    {"number": issue_number, "resume_kind": resume_kind}
                )

            except Exception:
                # Skip on error, could log here
                result["skipped"].append(
                    {"number": issue_number, "reason": "恢复操作失败"}
                )

        return result

    def _comment_all_resume_success(
        self,
        *,
        issue_number: int,
        repo: str | None,
        reason: str,
    ) -> None:
        """Record all-mode reset success without affecting command outcome."""
        try:
            comment_body = (
                "[resume] 已重置 task scene，回到 state/ready。\n\n"
                "后续会按标准 dispatcher/manager 路径重新创建 worktree 并执行。"
            )
            normalized_reason = reason.strip()
            if normalized_reason:
                comment_body += f"\n\n原因:{normalized_reason}"

            issue_payload = self.github_client.view_issue(issue_number, repo=repo)
            if isinstance(issue_payload, dict) and self._latest_comment_matches(
                issue_payload, comment_body
            ):
                return

            self.github_client.add_comment(
                issue_number,
                comment_body,
                repo=repo,
            )
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="comment_all_resume_success",
                issue_number=issue_number,
            ).warning(f"Failed to add all-mode resume comment: {exc}")

    def _latest_comment_matches(
        self,
        issue_payload: dict[str, object],
        comment_body: str,
    ) -> bool:
        """Return True when the latest issue comment is the same comment."""
        comments = issue_payload.get("comments")
        if not isinstance(comments, list):
            return False
        normalized_comment = comment_body.strip()
        for comment in reversed(comments):
            if not isinstance(comment, dict):
                continue
            body = comment.get("body")
            return isinstance(body, str) and body.strip() == normalized_comment
        return False
