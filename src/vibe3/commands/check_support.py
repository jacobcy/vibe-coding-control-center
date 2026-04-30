"""Shared command-layer helpers for check mode routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from vibe3.services.check_remote import InitResult
from vibe3.services.check_service import CheckResult, CheckService


@dataclass
class ExecuteCheckResult:
    """Result of command-level check execution."""

    mode: Literal["default", "init", "all", "fix", "fix_all", "clean_branch"]
    success: bool
    summary: str
    details: dict = field(default_factory=dict)


def _run_with_progress(
    service: CheckService,
    status: str | list[str],
) -> list[CheckResult]:
    """Run verify_all_flows with Rich Progress display.

    Args:
        service: CheckService instance.
        status: Status filter for verify_all_flows.

    Returns:
        List of CheckResult objects.
    """
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task_id = progress.add_task("Checking flows", total=None)

        def on_progress(current: int, total: int, branch: str) -> None:
            if total > 0:
                progress.update(
                    task_id,
                    total=total,
                    advance=1,
                    description=f"Checking {branch}",
                )

        results = service.verify_all_flows(status=status, on_progress=on_progress)

    return results


def execute_check_mode(
    service: CheckService,
    mode: Literal[
        "default", "init", "all", "fix", "fix_all", "clean_branch"
    ] = "default",
    *,
    branch: str | None = None,
    verbose: bool = False,
    show_progress: bool = True,
) -> ExecuteCheckResult:
    """Run command-oriented check modes
    using CheckService primitives.

    Args:
        service: CheckService instance.
        mode: Check mode to execute.
        branch: Branch to check (for single-branch modes).
        verbose: Enable verbose output.
        show_progress: Show progress bar for 'all' and 'fix_all' modes.
    """
    if mode == "init":
        init_result: InitResult = service.init_remote_index()
        summary = (
            f"Done  total={init_result.total_flows}  "
            f"updated={init_result.updated}  skipped={init_result.skipped}"
        )
        return ExecuteCheckResult(
            mode="init",
            success=True,
            summary=summary,
            details=(
                {"unresolvable": init_result.unresolvable}
                if init_result.unresolvable
                else {}
            ),
        )

    if mode == "clean_branch":
        # Use dedicated cleanup service for --clean-branch
        from vibe3.services.check_cleanup_service import CheckCleanupService

        cleanup_service = CheckCleanupService(
            store=service.store,
            git_client=service.git_client,
        )
        result = cleanup_service.clean_residual_branches()
        return ExecuteCheckResult(
            mode="clean_branch",
            success=True,
            summary=str(result["summary"]),
            details=result,
        )

    if mode == "all":
        if show_progress:
            results = _run_with_progress(service, status="active")
        else:
            results = service.verify_all_flows(status="active")

        invalid = [r for r in results if not r.is_valid]
        return ExecuteCheckResult(
            mode="all",
            success=len(invalid) == 0,
            summary=(
                f"All {len(results)} active flows passed"
                if not invalid
                else f"{len(invalid)}/{len(results)} active flows have issues"
            ),
            details={"invalid": invalid},
        )

    if mode == "fix_all":
        if show_progress:
            results = _run_with_progress(service, status=["active", "stale"])
        else:
            results = service.verify_all_flows(status=["active", "stale"])

        invalid_fix: list[CheckResult] = [r for r in results if not r.is_valid]
        if not invalid_fix:
            return ExecuteCheckResult(
                mode="fix_all",
                success=True,
                summary=f"All {len(results)} active flows passed",
            )

        if not verbose:
            typer.echo(f"Checking {len(invalid_fix)} flows with issues...")

        fixed_count = 0
        failed: list[str] = []
        for idx, check_result in enumerate(invalid_fix, 1):
            if verbose:
                typer.echo(f"  [{idx}/{len(invalid_fix)}] {check_result.branch}")
            fix_result = service.auto_fix(
                check_result.issues, branch=check_result.branch
            )
            if fix_result.success:
                fixed_count += 1
            else:
                error_msg = fix_result.error or "unknown error"
                failed.append(f"{check_result.branch}: {error_msg}")

        total = len(invalid_fix)
        if failed:
            return ExecuteCheckResult(
                mode="fix_all",
                success=False,
                summary=(
                    f"Fixed {fixed_count}/{total}, {len(failed)} had unfixable issues"
                ),
                details={"fixed": fixed_count, "failed": failed},
            )
        return ExecuteCheckResult(
            mode="fix_all",
            success=True,
            summary=(
                f"All {fixed_count} fixable issues resolved across {len(results)} flows"
            ),
            details={"fixed": fixed_count},
        )

    if mode == "fix":
        verify_result: CheckResult = service.verify_current_flow()
        if verify_result.is_valid:
            return ExecuteCheckResult(
                mode="fix", success=True, summary="All checks passed"
            )

        fix_result = service.auto_fix(verify_result.issues, branch=branch)
        return ExecuteCheckResult(
            mode="fix",
            success=fix_result.success,
            summary=(
                "All issues fixed"
                if fix_result.success
                else f"Error: {fix_result.error}"
            ),
            details={"issues": verify_result.issues},
        )

    # mode == "default"
    default_result: CheckResult = service.verify_current_flow()
    return ExecuteCheckResult(
        mode="default",
        success=default_result.is_valid,
        summary=(
            "All checks passed"
            if default_result.is_valid
            else f"Issues found for branch '{default_result.branch}'"
        ),
        details={"issues": default_result.issues},
    )
