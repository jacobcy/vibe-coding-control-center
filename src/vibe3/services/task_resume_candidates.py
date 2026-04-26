"""Task resume candidate construction logic.

This module provides candidate discovery and construction functions
for task resume operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.models.orchestration import IssueState

if TYPE_CHECKING:
    from vibe3.models.flow import FlowStatusResponse
    from vibe3.services.flow_service import FlowService
    from vibe3.services.issue_flow_service import IssueFlowService
    from vibe3.services.label_service import LabelService
    from vibe3.services.status_query_service import StatusQueryService


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

        对于显式指定的 issue（通过 vibe3 task resume <issue_number>），
        允许任何非 DONE 状态进行完整重建，用于清理脏数据场景。
        """
        current_state = self.label_service.get_state(issue_number)

        # Issue 不存在或已完成，不允许 resume
        if current_state is None or current_state == IssueState.DONE:
            return None

        # 查找关联的 flow（可能不存在）
        flow = self.find_resume_flow(issue_number, flows, stale_flows)

        # 对于 aborted flow 且状态为 ready/handoff，使用 aborted 恢复
        if current_state in {IssueState.READY, IssueState.HANDOFF}:
            aborted_flow = self.find_resume_flow_by_status(
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

            if flow is not None and flow.flow_status == "aborted":
                return {
                    "number": issue_number,
                    "title": "",
                    "state": current_state,
                    "resume_kind": "aborted",
                    "flow": flow,
                }

        # 根据状态确定 resume_kind
        if current_state == IssueState.FAILED:
            resume_kind = "failed"
        elif current_state == IssueState.BLOCKED:
            resume_kind = "blocked"
        else:
            # 对于其他状态（ready/handoff/review/merge-ready 等），
            # 使用 "all" 类型，允许完整重建
            resume_kind = "all"

        return {
            "number": issue_number,
            "title": "",
            "state": current_state,
            "resume_kind": resume_kind,
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

    def maybe_skip_all_task_candidate(
        self,
        *,
        issue_number: int,
        flow: FlowStatusResponse | None,
        candidate_state: object,
        worktree_path: str | None,
        has_live_sessions: bool | None = None,
        label_state: str | None = None,  # 新增：区分 --label 和完整重建
    ) -> str | None:
        """Skip noop all-task candidates that no longer have a task scene to reset.

        Args:
            issue_number: GitHub issue number
            flow: Flow status response
            candidate_state: Current issue state
            worktree_path: Worktree path (if exists)
            has_live_sessions: Whether branch has live runtime sessions (from registry).
                Registry is the single source of truth for session status.
            label_state: Optional label state (--label mode). None means full rebuild.

        Returns:
            Skip reason string if candidate should be skipped, None otherwise.
        """
        branch = getattr(flow, "branch", None) if flow else None

        # Registry is the source of truth for live sessions
        has_runtime_sessions = bool(has_live_sessions)

        # --label 模式：保留现场，只清理 reason
        # 如果没有现场可清理 reason，则跳过
        if label_state is not None:
            if (
                candidate_state == IssueState.READY
                and worktree_path is None
                and not has_runtime_sessions
            ):
                logger.bind(
                    domain="resume",
                    action="skip_noop_label_resume",
                    issue_number=issue_number,
                    branch=branch,
                    worktree_path=None,
                    state="ready",
                ).info("Skipping --label resume without task scene")
                return "已是 state/ready 且无 task scene，无法清理 reason，跳过恢复"

        # 完整重建模式（无 --label）：
        # 即使没有 worktree/flow，也可以继续（将状态设为 ready，等待重新 dispatch）
        # 只有当有活跃 session 时才跳过（需要用户手动处理）
        if has_runtime_sessions:
            logger.bind(
                domain="resume",
                action="skip_live_session",
                issue_number=issue_number,
                branch=branch,
                worktree_path=worktree_path,
            ).info("Skipping resume due to live runtime sessions")
            return "存在活跃 runtime session，需要先手动终止，跳过恢复"

        return None

    def verify_issue_state_for_resume(
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

    def build_all_task_candidates(
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

            # Filter out completed/aborted/merged flows
            flow_status = getattr(flow, "flow_status", None)
            if flow_status in {"done", "aborted", "merged"}:
                logger.bind(
                    domain="resume",
                    action="skip_completed_flow",
                    issue_number=issue_number,
                    flow_status=flow_status,
                ).debug(f"Skipping {flow_status} flow for issue #{issue_number}")
                continue

            # Filter out flows with PR (factually complete)
            pr_ref = getattr(flow, "pr_ref", None)
            if isinstance(pr_ref, str) and pr_ref:
                logger.bind(
                    domain="resume",
                    action="skip_pr_flow",
                    issue_number=issue_number,
                    pr_ref=pr_ref,
                ).debug(f"Skipping flow with PR {pr_ref} for issue #{issue_number}")
                continue

            # Validate issue exists and get current state
            current_state = self.label_service.get_state(issue_number)
            if current_state is None:
                # Issue doesn't exist or labels missing, skip
                logger.bind(
                    domain="resume",
                    action="skip_nonexistent_issue",
                    issue_number=issue_number,
                ).debug(f"Skipping issue #{issue_number} without valid state labels")
                continue

            issue = issue_details.get(issue_number, {})
            candidate = {
                "number": issue_number,
                "title": str(issue.get("title") or ""),
                "state": current_state,  # Use validated state
                "flow": flow,
            }
            candidate["resume_kind"] = "all"
            candidates.append(candidate)
        return candidates
