"""Mixin for unified check execution."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from vibe3.services.check_service import CheckResult, FixResult, InitResult


@dataclass
class ExecuteCheckResult:
    """Result of execute_check."""

    mode: Literal["default", "init", "all", "fix"]
    success: bool
    summary: str
    details: dict = field(default_factory=dict)


class CheckExecuteMixin:
    """Mixin providing unified check execution with mode-based routing."""

    def init_remote_index(self) -> "InitResult":
        """Initialize remote index. Must be implemented by mixed-in class."""
        raise NotImplementedError

    def verify_all_flows(self) -> list["CheckResult"]:
        """Verify all flows. Must be implemented by mixed-in class."""
        raise NotImplementedError

    def verify_current_flow(self) -> "CheckResult":
        """Verify current flow. Must be implemented by mixed-in class."""
        raise NotImplementedError

    def auto_fix(self, issues: list[str]) -> "FixResult":
        """Auto-fix issues. Must be implemented by mixed-in class."""
        raise NotImplementedError

    def execute_check(
        self,
        mode: Literal["default", "init", "all", "fix"] = "default",
        branch: str | None = None,
    ) -> ExecuteCheckResult:
        """Unified check execution with mode-based routing.

        Args:
            mode: Check mode (default, init, all, fix)
            branch: Branch name for single-branch check. If None, uses current branch.

        Returns:
            ExecuteCheckResult with mode, success, summary, and details
        """
        if mode == "init":
            return self._handle_init_mode()
        elif mode == "all":
            return self._handle_all_mode()
        elif mode == "fix":
            return self._handle_fix_mode(branch)
        else:
            return self._handle_default_mode(branch)

    def _handle_init_mode(self) -> ExecuteCheckResult:
        """Handle --init mode: scan merged PRs to back-fill task_issue_number."""
        result = self.init_remote_index()
        return ExecuteCheckResult(
            mode="init",
            success=True,
            summary=(
                f"Done  total={result.total_flows}  "
                f"updated={result.updated}  skipped={result.skipped}"
            ),
            details=(
                {"unresolvable": result.unresolvable} if result.unresolvable else {}
            ),
        )

    def _handle_all_mode(self) -> ExecuteCheckResult:
        """Handle --all mode: check every flow."""
        results = self.verify_all_flows()
        invalid = [r for r in results if not r.is_valid]
        return ExecuteCheckResult(
            mode="all",
            success=len(invalid) == 0,
            summary=(
                f"All {len(results)} flows passed"
                if not invalid
                else f"{len(invalid)}/{len(results)} flows have issues"
            ),
            details={"invalid": invalid},
        )

    def _handle_fix_mode(self, branch: str | None) -> ExecuteCheckResult:
        """Handle --fix mode: auto-fix current branch."""
        result_single = self.verify_current_flow()
        if result_single.is_valid:
            return ExecuteCheckResult(
                mode="fix", success=True, summary="All checks passed"
            )

        fix_result = self.auto_fix(result_single.issues)
        return ExecuteCheckResult(
            mode="fix",
            success=fix_result.success,
            summary=(
                "All issues fixed"
                if fix_result.success
                else f"Error: {fix_result.error}"
            ),
            details={"issues": result_single.issues},
        )

    def _handle_default_mode(self, branch: str | None) -> ExecuteCheckResult:
        """Handle default mode: check current branch."""
        result_single = self.verify_current_flow()
        return ExecuteCheckResult(
            mode="default",
            success=result_single.is_valid,
            summary=(
                "All checks passed"
                if result_single.is_valid
                else f"Issues found for branch '{result_single.branch}'"
            ),
            details={"issues": result_single.issues},
        )
