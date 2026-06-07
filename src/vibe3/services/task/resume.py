"""Task resume operations.

`task resume` only clears blocked state and restores the issue label. Destructive
scene rebuild belongs to FlowRebuildUsecase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, cast

from loguru import logger

from vibe3.clients import BackendProtocol, GitClient, GitHubClient
from vibe3.exceptions import UserError
from vibe3.models import IssueState
from vibe3.services.flow_service import FlowService
from vibe3.services.issue.flow import IssueFlowService
from vibe3.services.label_service import LabelService
from vibe3.services.status_query_service import StatusQueryService

if TYPE_CHECKING:
    from vibe3.models import FlowStatusResponse


ProgressCallback = Callable[[int, str | None, str, str], None]


class TaskResumeOperations:
    """Non-destructive blocked issue resume operations."""

    def __init__(
        self,
        git_client: GitClient,
        github_client: GitHubClient,
        flow_service: FlowService,
        label_service: LabelService,
        issue_flow_service: IssueFlowService,
        backend: BackendProtocol | None = None,
    ) -> None:
        self.git_client = git_client
        self.github_client = github_client
        self.flow_service = flow_service
        self.label_service = label_service
        self.issue_flow_service = issue_flow_service
        self._backend = backend

    def reset_issue_to_ready(
        self,
        *,
        issue_number: int,
        resume_kind: str,
        flow: FlowStatusResponse | None,
        repo: str | None,
        reason: str,
        label_state: str | None = "",
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Clear blocked state without deleting worktree, branch, or flow record."""
        branch = getattr(flow, "branch", None) if flow else None
        if label_state is None:
            raise UserError(
                "Task resume no longer supports destructive label_state=None. "
                "Use FlowRebuildUsecase for flow/worktree rebuild."
            )

        if isinstance(branch, str):
            flow_status = self.flow_service.get_flow_status(branch)
            if flow_status and flow_status.flow_status == "done":
                raise UserError(
                    f"Flow '{branch}' is done - cannot reset. "
                    "Use 'vibe check --clean-branch' to clean physical resources, "
                    "or close the linked issue manually if still open."
                )
            self._guard_no_live_sessions(branch)

        def emit_progress(step: str, status: str = "running") -> None:
            if progress_callback:
                progress_callback(issue_number, branch, step, status)

        emit_progress("checking consistency and recovering")

        # Delegate to unified recovery service (manual path: auto=False)
        from vibe3.services.flow_recovery_service import FlowRecoveryService

        recovery = FlowRecoveryService(
            store=self.flow_service.store,
            git_client=self.git_client,
            github_client=self.github_client,
        )
        recovery.recover(
            branch=branch or "",
            issue_number=issue_number,
            reason=f"Resumed from {resume_kind}: {reason}",
            auto=False,
        )
        emit_progress("recovery complete", status="done")

    def _guard_no_live_sessions(self, branch: str) -> None:
        if self._backend is None:
            # Skip session check if backend not provided (e.g., manual CLI use)
            return

        from vibe3.environment import SessionRegistryService

        registry = SessionRegistryService(
            store=self.flow_service.store,
            backend=self._backend,
        )
        live_sessions = registry.get_truly_live_sessions_for_branch(branch)
        if live_sessions:
            raise UserError(
                f"Flow '{branch}' still has a live runtime session; "
                "wait for the active automation run to finish before resume."
            )

    def _resolve_target_state(
        self,
        branch: str | None,
        label_state: str,
    ) -> IssueState:
        if not label_state:
            from vibe3.models import FlowState
            from vibe3.services.flow_resume_resolver import infer_resume_label

            fs_dict = (
                self.flow_service.store.get_flow_state(branch)
                if isinstance(branch, str)
                else None
            )
            return (
                infer_resume_label(FlowState.model_validate(fs_dict))
                if fs_dict
                else IssueState.READY
            )

        valid_states = {
            "ready": IssueState.READY,
            "claimed": IssueState.CLAIMED,
            "in-progress": IssueState.IN_PROGRESS,
            "handoff": IssueState.HANDOFF,
            "review": IssueState.REVIEW,
            "merge-ready": IssueState.MERGE_READY,
        }
        return valid_states.get(label_state, IssueState.CLAIMED)


class TaskResumeCandidates:
    """Candidate construction for task resume operations."""

    def __init__(
        self,
        status_service: StatusQueryService,
        label_service: LabelService,
        flow_service: FlowService,
        issue_flow_service: IssueFlowService,
    ) -> None:
        self.status_service = status_service
        self.label_service = label_service
        self.flow_service = flow_service
        self.issue_flow_service = issue_flow_service

    def merge_explicit_issue_candidates(
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
            direct_candidate = self.build_explicit_issue_candidate(
                issue_number=issue_number,
                flows=flows,
                stale_flows=stale_flows,
            )
            if direct_candidate is None:
                continue
            candidates.append(direct_candidate)
            existing_numbers.add(issue_number)

        return candidates

    def build_explicit_issue_candidate(
        self,
        *,
        issue_number: int,
        flows: list[FlowStatusResponse],
        stale_flows: list[FlowStatusResponse],
    ) -> dict[str, Any] | None:
        """为显式指定的 issue 直接构造恢复候选。

        Task resume 只处理 blocked 状态。
        对于其他状态，用户应使用 vibe3 flow rebuild。
        """
        current_state = self.label_service.get_state(issue_number)

        # Issue 不存在或已完成，不允许 resume
        if current_state is None or current_state == IssueState.DONE:
            return None

        # 只处理 blocked 状态
        if current_state != IssueState.BLOCKED:
            logger.bind(
                domain="task",
                action="resume_candidate_skip",
                issue_number=issue_number,
                current_state=current_state,
            ).warning(
                f"Issue #{issue_number} is not blocked (state={current_state}), "
                "task resume only handles blocked issues. "
                "Use 'vibe3 flow rebuild' for explicit rebuild."
            )
            return None

        # 查找关联的 flow（可能不存在）
        flow = self.find_resume_flow(issue_number, flows, stale_flows)

        # blocked 状态统一使用 resume_kind="blocked"
        return {
            "number": issue_number,
            "title": "",
            "state": current_state,
            "resume_kind": "blocked",
            "flow": flow,
        }

    def find_resume_flow_by_status(
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
            preferred = self.select_resume_flow(preferred, flow)

        for flow in self.flow_service.list_flows(status=None):
            if (
                flow.task_issue_number != issue_number
                or flow.flow_status not in statuses
            ):
                continue
            preferred = self.select_resume_flow(preferred, flow)

        return preferred

    def find_resume_flow(
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
            preferred = self.select_resume_flow(preferred, flow)

        if preferred is not None:
            return preferred

        for flow in self.flow_service.list_flows(status=None):
            if flow.task_issue_number != issue_number:
                continue
            preferred = self.select_resume_flow(preferred, flow)

        return preferred

    def select_resume_flow(
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

    def verify_issue_state_for_resume(
        self, issue_number: int, resume_kind: str, repo: str | None
    ) -> bool:
        """Verify issue is still in expected state for resume.

        Args:
            issue_number: GitHub issue number
            resume_kind: Expected resume kind ("blocked" or "aborted")
            repo: Repository (owner/repo format, optional)

        Returns:
            True if issue can be resumed, False otherwise
        """
        # ✅ Use authoritative truth: check if issue has merged PR
        from vibe3.services.pr_status_checker import has_merged_pr_for_issue

        if has_merged_pr_for_issue(issue_number, repo):
            # Issue has merged PR, cannot be resumed
            logger.bind(
                domain="resume",
                issue_number=issue_number,
                resume_kind=resume_kind,
            ).info("Issue has merged PR, cannot be resumed")
            return False

        current_state = self.label_service.get_state(issue_number)

        if current_state is None:
            return False

        if resume_kind == "blocked":
            return current_state.value == "blocked"
        elif resume_kind == "aborted":
            # Aborted flows can be resumed from READY or HANDOFF states
            # The flow_status=aborted check is done in fetch_resume_candidates
            # Here we verify the issue is in a valid state for resumption
            return current_state.value in ("ready", "handoff")

        return False


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
