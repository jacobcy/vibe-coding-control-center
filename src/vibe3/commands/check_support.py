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

from vibe3.clients import GhIssueLabelPort
from vibe3.config import OrchestraConfig, get_manager_usernames
from vibe3.services import CheckResult, CheckService, InitResult
from vibe3.services.shared import (
    collect_label_anomalies,
    has_manager_assignee,
    normalize_assignees,
    normalize_labels,
)


@dataclass
class ExecuteCheckResult:
    """Result of command-level check execution."""

    mode: Literal[
        "default", "init", "all", "fix", "fix_all", "clean_branch", "branch", "remote"
    ]
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

    return list(results)


def execute_check_mode(
    service: CheckService,
    mode: Literal[
        "default", "init", "all", "fix", "fix_all", "clean_branch", "branch", "remote"
    ] = "default",
    *,
    branch: str | None = None,
    verbose: bool = False,
    show_progress: bool = True,
    force: bool = False,
) -> ExecuteCheckResult:
    """Run command-oriented check modes
    using CheckService primitives.

    Args:
        service: CheckService instance.
        mode: Check mode to execute.
        branch: Branch to check (for single-branch modes).
        verbose: Enable verbose output.
        show_progress: Show progress bar for 'all' and 'fix_all' modes.
        force: Force delete for clean_branch mode.
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
        from vibe3.services import CheckCleanupService

        cleanup_service = CheckCleanupService(
            store=service.store,
            git_client=service.git_client,
        )
        result = cleanup_service.clean_residual_branches(force=force)
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

        # Collect warnings from all flows (regardless of validity)
        all_warnings: list[tuple[str, str]] = []  # (branch, warning_message)
        for r in results:
            for warning in r.warnings:
                all_warnings.append((r.branch, warning))

        # Display warnings separately
        if all_warnings:
            typer.echo(f"\nWarnings ({len(all_warnings)}):")
            for branch, warning in all_warnings:
                typer.echo(f"  [{branch}] {warning}")

        if not invalid_fix:
            return ExecuteCheckResult(
                mode="fix_all",
                success=True,
                summary=f"All {len(results)} active flows passed",
            )

        if not verbose:
            typer.echo(f"\nChecking {len(invalid_fix)} flows with issues...")

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

    if mode == "branch":
        if not branch:
            typer.echo("Error: --branch requires a branch name.", err=True)
            raise typer.Exit(code=1)

        branch_result: CheckResult = service.verify_branch(branch)

        if branch_result.is_valid:
            return ExecuteCheckResult(
                mode="branch",
                success=True,
                summary=f"Branch '{branch}' passed all checks",
            )

        # Try auto-fix if issues found
        fix_result = service.auto_fix(branch_result.issues, branch=branch)
        if fix_result.success:
            return ExecuteCheckResult(
                mode="branch",
                success=True,
                summary=f"Branch '{branch}' issues fixed",
                details={"fixed": fix_result.applied},
            )

        return ExecuteCheckResult(
            mode="branch",
            success=False,
            summary=f"Branch '{branch}' has unfixable issues",
            details={"issues": branch_result.issues},
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


def _audit_single_issue(
    issue: dict,
    *,
    local_issue_numbers: set[int],
    manager_usernames: tuple[str, ...],
) -> list[dict]:
    """Audit one GitHub issue for label anomalies.

    Returns list of anomaly dicts with keys:
        issue_number, rule, removed, added.
    """
    issue_number = issue.get("number")
    if not issue_number:
        return []

    raw_labels = issue.get("labels", [])
    labels = normalize_labels(raw_labels)

    raw_assignees = issue.get("assignees", [])
    assignees = normalize_assignees(raw_assignees)

    has_local_flow = issue_number in local_issue_numbers
    is_manager_issue = has_manager_assignee(assignees, manager_usernames)

    anomalies = collect_label_anomalies(
        labels,
        issue_number=issue_number,
        has_local_flow=has_local_flow,
        is_manager_issue=is_manager_issue,
    )

    return [
        {
            "issue_number": a.issue_number,
            "rule": a.rule,
            "removed": a.removed,
            "added": a.added,
        }
        for a in anomalies
    ]


def execute_remote_check(
    *,
    dry_run: bool = True,
    show_progress: bool = True,
) -> ExecuteCheckResult:
    """Audit remote issue labels for anomalies and optionally fix them.

    Args:
        dry_run: Only report, don't modify labels.
        show_progress: Show progress bar while checking issues.

    Returns:
        ExecuteCheckResult with mode="remote" and grouped anomaly details.
    """
    service = CheckService()
    store = service.store
    gh_client = service.github_client
    label_port = GhIssueLabelPort()

    config = OrchestraConfig()
    manager_usernames = get_manager_usernames(config)

    # Fetch all open issues
    issues = gh_client.list_issues(
        state="open",
        fields=["labels", "assignees", "number"],
    )

    # Build set of locally-tracked issue numbers
    all_flows = store.get_all_flows()
    local_issue_numbers: set[int] = set()
    for flow in all_flows:
        branch = flow.get("branch", "")
        if branch:
            issue_num = store.get_task_issue_number(branch)
            if issue_num is not None:
                local_issue_numbers.add(issue_num)

    all_anomalies: list[dict] = []
    errors: list[str] = []

    if show_progress:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task_id = progress.add_task("Checking remote issues", total=len(issues))
            for issue in issues:
                progress.update(
                    task_id,
                    advance=1,
                    description=f"Checking issue #{issue.get('number', '?')}",
                )
                anomalies = _audit_single_issue(
                    issue,
                    local_issue_numbers=local_issue_numbers,
                    manager_usernames=manager_usernames,
                )
                all_anomalies.extend(anomalies)
    else:
        for issue in issues:
            anomalies = _audit_single_issue(
                issue,
                local_issue_numbers=local_issue_numbers,
                manager_usernames=manager_usernames,
            )
            all_anomalies.extend(anomalies)

    # Apply fixes if not dry-run
    if not dry_run:
        for anomaly in all_anomalies:
            inum = anomaly["issue_number"]
            for label in anomaly["removed"]:
                try:
                    label_port.remove_issue_label(inum, label)
                except Exception as e:
                    errors.append(f"#{inum}: failed to remove {label}: {e}")
            for label in anomaly["added"]:
                try:
                    label_port.add_issue_label(inum, label)
                except Exception as e:
                    errors.append(f"#{inum}: failed to add {label}: {e}")

    checked_count = len(issues)
    anomaly_count = len(all_anomalies)
    total_removed = sum(len(a["removed"]) for a in all_anomalies)
    total_added = sum(len(a["added"]) for a in all_anomalies)

    if anomaly_count == 0:
        summary = f"Checked {checked_count} issues, no anomalies found"
    else:
        summary = f"Checked {checked_count} issues, found {anomaly_count} anomalies"

    return ExecuteCheckResult(
        mode="remote",
        success=anomaly_count == 0,
        summary=summary,
        details={
            "checked_count": checked_count,
            "anomalies": all_anomalies,
            "removed_count": total_removed,
            "added_count": total_added,
            "errors": errors,
            "dry_run": dry_run,
        },
    )
