"""Task resume candidate construction logic.

This module provides candidate discovery and construction functions
for task resume operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.models import IssueState

if TYPE_CHECKING:
    from vibe3.models.flow import FlowStatusResponse
    from vibe3.services.flow_service import FlowService
    from vibe3.services.issue_flow_service import IssueFlowService
    from vibe3.services.shared.labels import LabelService
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
