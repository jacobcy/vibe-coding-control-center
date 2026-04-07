"""Unified task resume usecase.

Provides a single entry point for resuming tasks regardless of
whether they are in failed or blocked state.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.manager.session_naming import get_manager_session_name
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import (
    resume_blocked_issue_to_ready,
    resume_failed_issue_to_ready,
)
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService
from vibe3.services.status_query_service import StatusQueryService

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
            candidates = self._build_all_task_candidates(flows or [])
        else:
            candidates = self.status_service.fetch_resume_candidates(
                flows=flows or [], stale_flows=stale_flows or []
            )

        if issue_numbers is not None and candidate_mode != "all_task":
            candidates = self._merge_explicit_issue_candidates(
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
                skip_reason = self._maybe_skip_all_task_candidate(
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
            if not self._verify_issue_state_for_resume(issue_number, resume_kind, repo):
                result["skipped"].append(
                    {
                        "number": issue_number,
                        "reason": f"不再处于 {resume_kind} 状态，跳过恢复",
                    }
                )
                continue

            try:
                if resume_kind in {"failed", "blocked", "all"}:
                    self._reset_issue_to_ready(
                        issue_number=issue_number,
                        resume_kind=resume_kind,
                        flow=flow,
                        repo=repo,
                        reason=reason,
                        worktree_path=worktree_path,
                    )

                elif resume_kind == "aborted":
                    flow = cast("FlowStatusResponse | None", candidate.get("flow"))
                    if flow and isinstance(flow.branch, str):
                        self._reactivate_aborted_flow(flow.branch)

                result["resumed"].append(
                    {"number": issue_number, "resume_kind": resume_kind}
                )

            except Exception:
                # Skip on error, could log here
                result["skipped"].append(
                    {"number": issue_number, "reason": "恢复操作失败"}
                )

        return result

    def _merge_explicit_issue_candidates(
        self,
        *,
        issue_numbers: list[int],
        candidates: list[dict[str, Any]],
        flows: list[FlowStatusResponse],
        stale_flows: list[FlowStatusResponse],
    ) -> list[dict[str, Any]]:
        """补充显式点名恢复的 issue，避免被治理候选集误过滤。"""
        existing_numbers = {
            number
            for candidate in candidates
            if isinstance((number := candidate.get("number")), int)
        }

        for issue_number in issue_numbers:
            if issue_number in existing_numbers:
                continue
            direct_candidate = self._build_explicit_issue_candidate(
                issue_number=issue_number,
                flows=flows,
                stale_flows=stale_flows,
            )
            if direct_candidate is None:
                continue
            candidates.append(direct_candidate)
            existing_numbers.add(issue_number)

        return candidates

    def _build_explicit_issue_candidate(
        self,
        *,
        issue_number: int,
        flows: list[FlowStatusResponse],
        stale_flows: list[FlowStatusResponse],
    ) -> dict[str, Any] | None:
        """为显式指定的 issue 直接构造恢复候选。"""
        current_state = self.label_service.get_state(issue_number)
        if current_state in {IssueState.READY, IssueState.HANDOFF}:
            aborted_flow = self._find_resume_flow_by_status(
                issue_number,
                statuses={"aborted"},
                flows=flows,
                stale_flows=stale_flows,
            )
            if aborted_flow is not None:
                return {
                    "number": issue_number,
                    "title": "",
                    "state": current_state,
                    "resume_kind": "aborted",
                    "flow": aborted_flow,
                }

        flow = self._find_resume_flow(issue_number, flows, stale_flows)
        if (
            flow is not None
            and flow.flow_status == "aborted"
            and current_state in {IssueState.READY, IssueState.HANDOFF}
        ):
            return {
                "number": issue_number,
                "title": "",
                "state": current_state,
                "resume_kind": "aborted",
                "flow": flow,
            }

        if current_state == IssueState.FAILED:
            resume_kind = "failed"
        elif current_state == IssueState.BLOCKED:
            resume_kind = "blocked"
        else:
            return None

        return {
            "number": issue_number,
            "title": "",
            "state": current_state,
            "resume_kind": resume_kind,
            "flow": flow,
        }

    def _find_resume_flow_by_status(
        self,
        issue_number: int,
        *,
        statuses: set[str],
        flows: list[FlowStatusResponse],
        stale_flows: list[FlowStatusResponse],
    ) -> FlowStatusResponse | None:
        """按 flow_status 查找 issue 对应的恢复现场。"""
        preferred: FlowStatusResponse | None = None
        for flow in [*flows, *stale_flows]:
            if (
                flow.task_issue_number != issue_number
                or flow.flow_status not in statuses
            ):
                continue
            preferred = self._select_resume_flow(preferred, flow)

        for flow in self.flow_service.list_flows(status=None):
            if (
                flow.task_issue_number != issue_number
                or flow.flow_status not in statuses
            ):
                continue
            preferred = self._select_resume_flow(preferred, flow)

        return preferred

    def _find_resume_flow(
        self,
        issue_number: int,
        flows: list[FlowStatusResponse],
        stale_flows: list[FlowStatusResponse],
    ) -> FlowStatusResponse | None:
        """从已加载 flow 列表中为恢复操作关联现场。"""
        preferred: FlowStatusResponse | None = None
        for flow in [*flows, *stale_flows]:
            if flow.task_issue_number != issue_number:
                continue
            preferred = self._select_resume_flow(preferred, flow)

        if preferred is not None:
            return preferred

        for flow in self.flow_service.list_flows(status=None):
            if flow.task_issue_number != issue_number:
                continue
            preferred = self._select_resume_flow(preferred, flow)

        return preferred

    def _select_resume_flow(
        self,
        current: FlowStatusResponse | None,
        candidate: FlowStatusResponse,
    ) -> FlowStatusResponse:
        """为显式恢复选择最合适的 flow 现场。"""
        if current is None:
            return candidate

        current_is_task = self.issue_flow_service.is_task_branch(current.branch)
        candidate_is_task = self.issue_flow_service.is_task_branch(candidate.branch)
        if candidate_is_task != current_is_task:
            return candidate if candidate_is_task else current

        status_rank = {
            "active": 0,
            "stale": 1,
            "aborted": 2,
            "blocked": 3,
            "done": 4,
            "merged": 4,
        }
        current_rank = status_rank.get(current.flow_status, 5)
        candidate_rank = status_rank.get(candidate.flow_status, 5)
        if candidate_rank < current_rank:
            return candidate

        return current

    def _maybe_skip_all_task_candidate(
        self,
        *,
        issue_number: int,
        flow: FlowStatusResponse | None,
        candidate_state: object,
        worktree_path: str | None,
    ) -> str | None:
        """Skip noop all-task candidates that no longer have a task scene to reset."""
        branch = getattr(flow, "branch", None) if flow else None
        if not isinstance(branch, str):
            return None

        has_runtime_sessions = bool(
            flow
            and any(
                getattr(flow, field, None)
                for field in (
                    "manager_session_id",
                    "planner_session_id",
                    "executor_session_id",
                    "reviewer_session_id",
                )
            )
        )

        if (
            candidate_state == IssueState.READY
            and worktree_path is None
            and not has_runtime_sessions
        ):
            logger.bind(
                domain="resume",
                action="skip_noop_all_task",
                issue_number=issue_number,
                branch=branch,
                worktree_path=None,
                state="ready",
            ).info("Skipping ready candidate without task scene")
            return "已是 state/ready 且无 task scene，跳过恢复"
        return None

    def _verify_issue_state_for_resume(
        self, issue_number: int, resume_kind: str, repo: str | None
    ) -> bool:
        """Verify issue is still in expected state for resume.

        Args:
            issue_number: GitHub issue number
            resume_kind: Expected resume kind ("failed", "blocked", or "aborted")
            repo: Repository (owner/repo format, optional)

        Returns:
            True if issue state matches resume_kind, False otherwise
        """
        current_state = self.label_service.get_state(issue_number)

        if resume_kind == "all":
            return current_state is None or current_state != IssueState.DONE

        if current_state is None:
            return False

        if resume_kind == "failed":
            return current_state.value == "failed"
        elif resume_kind == "blocked":
            return current_state.value == "blocked"
        elif resume_kind == "aborted":
            # Aborted flows can be resumed from READY or HANDOFF states
            # The flow_status=aborted check is done in fetch_resume_candidates
            # Here we verify the issue is in a valid state for resumption
            return current_state.value in ("ready", "handoff")

        return False

    def _cleanup_stale_flow(self, branch: str) -> None:
        """Clean up stale flow metadata after blocked resume.

        Args:
            branch: Branch name for the flow to clean up
        """
        try:
            logger.bind(
                domain="resume",
                action="cleanup_stale_flow",
                branch=branch,
            ).info("Cleaning up stale flow")

            # Reactivate the stale flow (change status from "stale" to "active")
            self.flow_service.reactivate_flow(branch)
        except Exception as exc:
            # Log but don't fail the resume operation
            logger.bind(
                domain="resume",
                action="cleanup_stale_flow",
                branch=branch,
            ).warning(f"Failed to clean up stale flow: {exc}")

    def _build_all_task_candidates(
        self, flows: list[FlowStatusResponse]
    ) -> list[dict[str, Any]]:
        """Build reset candidates for every auto-created task flow."""
        issue_details: dict[int, dict[str, Any]] = {}
        try:
            orchestrated_issues = self.status_service.fetch_orchestrated_issues(
                flows=flows,
                queued_set=set(),
                stale_flows=[],
            )
            for issue in orchestrated_issues:
                issue_number = issue.get("number")
                if isinstance(issue_number, int):
                    issue_details[issue_number] = issue
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="build_all_task_candidates",
            ).warning(f"Failed to enrich all-task candidates from GitHub: {exc}")

        candidates: list[dict[str, Any]] = []
        for flow in flows:
            branch = getattr(flow, "branch", None)
            if not isinstance(branch, str):
                continue
            if not self.issue_flow_service.is_task_branch(branch):
                continue
            issue_number = getattr(flow, "task_issue_number", None)
            if not isinstance(issue_number, int):
                continue
            issue = issue_details.get(issue_number, {})
            candidate = {
                "number": issue_number,
                "title": str(issue.get("title") or ""),
                "state": issue.get("state")
                or self.label_service.get_state(issue_number),
                "flow": flow,
            }
            candidate["resume_kind"] = "all"
            candidates.append(candidate)
        return candidates

    def _reset_issue_to_ready(
        self,
        *,
        issue_number: int,
        resume_kind: str,
        flow: FlowStatusResponse | None,
        repo: str | None,
        reason: str,
        worktree_path: str | None = None,
    ) -> None:
        """Reset an issue to ready after clearing stale task scene state."""
        branch = getattr(flow, "branch", None) if flow else None
        previous_state = self.label_service.get_state(issue_number)

        if resume_kind == "failed":
            resume_failed_issue_to_ready(
                issue_number=issue_number,
                repo=repo,
                reason=reason,
            )
        elif resume_kind == "blocked":
            resume_blocked_issue_to_ready(
                issue_number=issue_number,
                repo=repo,
                reason=reason,
            )
        else:
            self.label_service.confirm_issue_state(
                issue_number,
                IssueState.READY,
                actor="human:resume",
                force=True,
            )

        if isinstance(branch, str):
            try:
                self._reset_task_scene(branch, worktree_path=worktree_path)
            except Exception as exc:
                self._restore_issue_state(
                    issue_number=issue_number,
                    previous_state=previous_state,
                    repo=repo,
                    failure_reason=str(exc),
                )
                raise

        if resume_kind == "all":
            self._comment_all_resume_success(
                issue_number=issue_number,
                repo=repo,
                reason=reason,
            )

    def _reset_task_scene(self, branch: str, worktree_path: str | None = None) -> None:
        """Delete stale task worktree and clear flow runtime state."""
        if not self.issue_flow_service.is_task_branch(branch):
            return

        self._terminate_task_sessions(branch)

        resolved_path = worktree_path
        if resolved_path is None:
            found_path = self.git_client.find_worktree_path_for_branch(branch)
            resolved_path = str(found_path) if found_path is not None else None
        logger.bind(
            domain="resume",
            action="reset_task_scene",
            branch=branch,
            worktree_path=resolved_path,
        ).info("Resetting task scene")
        if resolved_path is not None:
            self.git_client.remove_worktree(resolved_path, force=True)
        self.flow_service.reactivate_flow(branch)

    def _terminate_task_sessions(self, branch: str) -> None:
        """Kill lingering tmux sessions for a task issue before resume."""
        issue_number = self.issue_flow_service.parse_issue_number(branch)
        if issue_number is None:
            return

        prefixes = (
            get_manager_session_name(issue_number),
            f"vibe3-plan-issue-{issue_number}",
            f"vibe3-run-issue-{issue_number}",
            f"vibe3-review-issue-{issue_number}",
        )

        try:
            result = subprocess.run(
                ["tmux", "ls"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError:
            return
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="terminate_task_sessions",
                branch=branch,
            ).warning(f"Failed to inspect tmux sessions: {exc}")
            return

        if result.returncode != 0:
            return

        active_sessions: list[str] = []
        for line in result.stdout.splitlines():
            session_name = line.split(":", 1)[0].strip()
            if any(
                session_name == prefix or session_name.startswith(f"{prefix}-")
                for prefix in prefixes
            ):
                active_sessions.append(session_name)

        for session_name in active_sessions:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

    def _restore_issue_state(
        self,
        *,
        issue_number: int,
        previous_state: IssueState | None,
        repo: str | None,
        failure_reason: str,
    ) -> None:
        """Best-effort rollback when scene reset fails after issue transition."""
        if previous_state is None or previous_state == IssueState.READY:
            return
        try:
            self.label_service.confirm_issue_state(
                issue_number,
                previous_state,
                actor="human:resume",
                force=True,
            )
            self.github_client.add_comment(
                issue_number,
                "[resume] task scene 重置失败，已恢复为 "
                f"state/{previous_state.value}。\n\n"
                f"原因:{failure_reason}",
                repo=repo,
            )
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="rollback_issue_state",
                issue_number=issue_number,
                previous_state=previous_state.value,
            ).warning("Failed to rollback issue state after resume error: " f"{exc}")

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

    def _reactivate_aborted_flow(self, branch: str) -> None:
        """Reactivate an aborted flow.

        Args:
            branch: Branch name for the aborted flow
        """
        try:
            logger.bind(
                domain="resume",
                action="reactivate_aborted",
                branch=branch,
            ).info("Reactivating aborted flow")

            # Reactivate the aborted flow (change status from "aborted" to "active")
            self.flow_service.reactivate_flow(branch)
        except Exception as exc:
            logger.bind(
                domain="resume",
                action="reactivate_aborted",
                branch=branch,
            ).warning(f"Failed to reactivate aborted flow: {exc}")
            raise
