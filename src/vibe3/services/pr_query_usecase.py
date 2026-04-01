"""Usecase helpers for PR query command orchestration."""

from dataclasses import dataclass
from typing import Any, Callable

from vibe3.analysis.inspect_output_adapter import pr_analysis_summary
from vibe3.models.pr import PRResponse
from vibe3.services.flow_service import FlowService
from vibe3.services.pr_service import PRService


@dataclass(frozen=True)
class PrQueryTarget:
    """Resolved PR query target from explicit args or current flow."""

    pr_number: int | None
    branch: str | None
    current_branch: str | None
    from_flow: bool = False


class PrQueryUsecase:
    """Coordinate command-facing PR show logic."""

    def __init__(
        self,
        pr_service: PRService,
        flow_service: FlowService,
        inspect_runner: Callable[[list[str]], dict[str, object]] | None = None,
    ) -> None:
        self.pr_service = pr_service
        self.flow_service = flow_service
        self.inspect_runner = inspect_runner

    def resolve_target(
        self,
        pr_number: int | None,
        branch: str | None,
    ) -> PrQueryTarget:
        """Resolve explicit target or infer PR number from current flow."""
        if pr_number or branch:
            return PrQueryTarget(
                pr_number=pr_number,
                branch=branch,
                current_branch=None,
                from_flow=False,
            )

        current_branch = self.flow_service.get_current_branch()
        flow_data = self.pr_service.store.get_flow_state(current_branch)
        resolved_pr = flow_data.get("pr_number") if flow_data else None
        return PrQueryTarget(
            pr_number=resolved_pr,
            branch=None,
            current_branch=current_branch,
            from_flow=resolved_pr is not None,
        )

    def fetch_pr(
        self,
        pr_number: int | None,
        branch: str | None,
        current_branch: str | None = None,
    ) -> PRResponse:
        """Load PR or raise a command-facing lookup error."""
        pr = self.pr_service.get_pr(pr_number, branch)
        if not pr and pr_number is not None and current_branch:
            # Remote-first fallback: cached pr_number may drift; retry by branch truth.
            pr = self.pr_service.get_pr(branch=current_branch)
        if not pr:
            raise LookupError("PR not found")
        return pr

    def build_missing_pr_message(
        self,
        pr_number: int | None,
        branch: str | None,
        current_branch: str | None,
    ) -> str:
        """Build a command-facing not-found message."""
        if not pr_number and not branch:
            branch_name = current_branch or self.flow_service.get_current_branch()
            flow_status = self.flow_service.get_flow_status(branch_name)
            bind_hint = ""
            if not flow_status or flow_status.task_issue_number is None:
                bind_hint = (
                    "\n提示：当前 flow 还没有 task，建议先执行\n"
                    "  vibe3 flow bind <issue> --role task"
                )
            return (
                f"No PR found for current branch '{branch_name}'\n\n"
                "To create a PR, run:\n"
                f'  vibe3 pr create -t "Your PR title"{bind_hint}'
            )

        target = f"PR #{pr_number}" if pr_number else f"branch '{branch}'"
        return f"{target} not found"

    def load_analysis_summary(self, pr_number: int) -> dict[str, Any]:
        """Load inspect summary used by command outputs."""
        if self.inspect_runner is None:
            raise RuntimeError("inspect_runner is required for analysis loading")
        analysis = self.inspect_runner(["pr", str(pr_number)])
        return pr_analysis_summary(analysis)

    @staticmethod
    def build_output_payload(
        pr: PRResponse,
        analysis_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Merge PR data with optional analysis summary for structured output."""
        payload = pr.model_dump()
        if analysis_summary:
            payload["analysis"] = {
                key: value for key, value in analysis_summary.items() if key != "raw"
            }
        return payload
