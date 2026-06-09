"""Shared command-layer helpers for check mode routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from vibe3.services import CheckResult, CheckService, InitResult


@dataclass
class ExecuteCheckResult:
    """Result of command-level check execution."""

    mode: Literal["default", "init", "all", "fix", "fix_all", "clean_branch", "branch"]
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
        "default", "init", "all", "fix", "fix_all", "clean_branch", "branch"
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


@dataclass
class RemoteAuditResult:
    """Result of remote label audit."""

    total_issues: int
    issues_found: int
    total_removed: int
    total_added: int
    results: list[Any] = field(default_factory=list)


def execute_remote_check(*, dry_run: bool = False) -> RemoteAuditResult:
    """Execute remote label consistency audit by wiring existing capabilities.

    Uses audit functions from shared/labels.py (Rules 1-4) and
    GhIssueLabelPort for label mutations.
    """
    from vibe3.clients import GhIssueLabelPort, GitHubClient, SQLiteClient
    from vibe3.config import get_manager_usernames, load_orchestra_config
    from vibe3.services import (
        audit_multiple_state_labels,
        audit_orphan_execution_state,
        audit_orphan_orchestra_governed,
        audit_roadmap_state_conflict,
        has_manager_assignee,
        normalize_assignees,
        normalize_labels,
    )

    config = load_orchestra_config()
    manager_usernames = get_manager_usernames(config)

    github = GitHubClient()
    store = SQLiteClient()
    label_port = GhIssueLabelPort(repo=config.repo)

    # Fetch all open issues
    all_issues = github.list_issues(
        limit=5000, state="open", fields=["number", "title", "labels", "assignees"]
    )

    # Build set of branches with local flow records
    flow_branches = {f["branch"] for f in store.get_all_flows() if f.get("branch")}

    results: list[dict[str, object]] = []

    for issue in all_issues:
        number = issue.get("number")
        if not isinstance(number, int):
            continue

        labels = normalize_labels(issue.get("labels", []))
        assignees = normalize_assignees(issue.get("assignees", []))
        is_manager = has_manager_assignee(assignees, manager_usernames)

        removed: list[str] = []
        added: list[str] = []
        rules: list[str] = []

        # Rule 1: roadmap + state conflict
        r1 = audit_roadmap_state_conflict(labels)
        if r1:
            removed.extend(r1)
            rules.append("规则 1 (roadmap 标签冲突)")
            # Rule 1 fires → skip Rules 2/3 (roadmap issues get all state removed)

        if not r1:
            # Rule 2: multiple state labels
            r2 = audit_multiple_state_labels(labels)
            if r2:
                removed.extend(r2)
                rules.append("规则 2 (多个 state 标签)")

            # Rule 3: orphan execution state (manager-assigned only)
            if is_manager:
                r3_rm, r3_add = audit_orphan_execution_state(
                    labels,
                    has_local_flow=f"task/issue-{number}" in flow_branches,
                )
                if r3_rm:
                    removed.extend(r3_rm)
                    added.extend(r3_add)
                    rules.append("规则 3 (孤儿执行态标签)")

        # Rule 4: orphan orchestra-governed (manager-assigned only)
        if is_manager:
            r4 = audit_orphan_orchestra_governed(labels)
            if r4:
                removed.extend(r4)
                rules.append("规则 4 (孤儿 orchestra-governed)")

        if removed or added:
            # Deduplicate
            removed = list(dict.fromkeys(removed))
            added = list(dict.fromkeys(added))

            results.append(
                {
                    "number": number,
                    "removed": removed,
                    "added": added,
                    "rules": ", ".join(rules),
                }
            )

            if not dry_run:
                for lb in removed:
                    label_port.remove_issue_label(number, lb)
                for lb in added:
                    label_port.add_issue_label(number, lb)

    total_removed = 0
    total_added = 0
    for r in results:
        total_removed += len(r["removed"])  # type: ignore[arg-type]
        total_added += len(r["added"])  # type: ignore[arg-type]

    return RemoteAuditResult(
        total_issues=len(all_issues),
        issues_found=len(results),
        total_removed=total_removed,
        total_added=total_added,
        results=results,
    )
