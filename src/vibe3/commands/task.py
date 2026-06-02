#!/usr/bin/env python3
"""Task command handlers."""

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated, Iterator

import typer

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient

from vibe3.commands.command_options import FormatOption
from vibe3.commands.common import enable_method_trace
from vibe3.exceptions import SystemError, UserError
from vibe3.models.orchestration import IssueState
from vibe3.observability.logger import setup_logging
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.pr_branch_resolver import resolve_command_branch
from vibe3.services.task_resume_usecase import TaskResumeUsecase
from vibe3.services.task_service import TaskService
from vibe3.ui.task_ui import (
    render_task_comments,
    render_task_show,
)

app = typer.Typer(
    help="""Manage execution tasks.

Tasks represent work items linked to flows.
Use task commands to check status and resume blocked work.

Examples:
  vibe3 task show                # Show current task details
  vibe3 task show 123            # Show task for issue #123
  vibe3 task status              # Show global task dashboard
  vibe3 task resume --blocked    # Resume all blocked issues (dry-run)
  vibe3 task resume 456 --yes    # Resume issue #456 (execute)
  vibe3 task resume --branch task/issue-123 --yes  # Resume via branch name
  vibe3 task resume --pr 456 --yes                 # Resume via PR number

For more details: vibe3 task <command> --help
""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _build_resume_usecase() -> TaskResumeUsecase:
    """Construct a unified resume usecase."""
    return TaskResumeUsecase()


def _parse_issue_number_from_branch(
    branch: str, store: "SQLiteClient", flow_service: FlowService
) -> int:
    """Extract task issue number from branch.

    Tries DB links first, then pattern matching.
    """
    # Try DB links first (most reliable — handles non-canonical branches)
    links = store.get_issue_links(branch)
    for link in links:
        if link.get("issue_role") == "task":
            issue_num = link["issue_number"]
            if isinstance(issue_num, int):
                return issue_num

    # Fall back to pattern matching (task/issue-N, dev/issue-N)
    issue_svc = IssueFlowService(store=store)
    num = issue_svc.parse_issue_number_any(branch)
    if num is not None:
        return num

    raise UserError(f"无法从分支 '{branch}' 解析 issue 编号")


@app.command()
def show(
    issue: Annotated[
        str | None,
        typer.Argument(help="Issue number (auto-resolves to task branch if exists)"),
    ] = None,
    branch_opt: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    pr_opt: Annotated[
        int | None,
        typer.Option("--pr", help="PR number to resolve branch from"),
    ] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    output_format: FormatOption = "table",
    full: Annotated[
        bool, typer.Option("--full", help="Show complete summary without truncation")
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Show a quick current-task summary for humans and agents.

    This command is the fast scene entry before reading handoff details or
    entering manager/plan/executor/reviewer prompts.
    """
    # Handle deprecated --json flag
    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"

    task_svc = TaskService()

    try:
        # Pass branch_opt and issue separately for conflict detection
        # allow_no_flow=True allows showing remote issue info without local flow
        target_branch = task_svc.resolve_branch(
            branch_opt, pr_number=pr_opt, position_arg=issue, allow_no_flow=True
        )
    except (UserError, SystemError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if trace:
        setup_logging(verbose=2)

    if trace:
        enable_method_trace()

    # Pass target_branch directly to show_task (re-resolution is handled inside)
    task_result = task_svc.show_task(target_branch)

    issue_number = None
    if task_result.local_task and task_result.local_task.task_issue_number:
        issue_number = task_result.local_task.task_issue_number
    elif target_branch.isdigit():
        # Branch resolved to numeric issue (no flow exists)
        issue_number = int(target_branch)

    render_task_show(task_result, output_format, full=full)

    # Always show recent comments (if issue exists and not json/yaml output)
    if issue_number and output_format == "table":
        issue_data = task_svc.fetch_issue_with_comments(issue_number)
        if issue_data == "network_error":
            typer.echo("\nIssue comments unavailable: network/auth error")
        elif issue_data is None:
            typer.echo(f"\nIssue comments unavailable: issue #{issue_number} not found")
        else:
            assert isinstance(issue_data, dict)
            render_task_comments(issue_data)


@app.command()
def status(
    all_flows: Annotated[
        bool,
        typer.Option("--all", help="显示所有状态的 flow（含 done/aborted/stale）"),
    ] = False,
    check: Annotated[
        bool, typer.Option("--check", help="显示前先运行完整 vibe3 check")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Show task-oriented global status dashboard."""
    from vibe3.commands.status import _full_status_dashboard

    _full_status_dashboard(
        all_flows=all_flows,
        check=check,
        output_format="table" if not json_output else "json",
        trace=trace,
        min_ms=None,
        json_output=json_output,
    )


@app.command()
def resume(
    issue_numbers: Annotated[
        list[int] | None,
        typer.Argument(help="Issue numbers to resume"),
    ] = None,
    blocked: Annotated[
        bool, typer.Option("--blocked", help="Resume all blocked issues")
    ] = False,
    branch_opt: Annotated[
        str | None,
        typer.Option("--branch", help="Branch name or issue number"),
    ] = None,
    pr_opt: Annotated[
        int | None,
        typer.Option("--pr", help="PR number to resolve branch from"),
    ] = None,
    label: Annotated[
        str | None,
        typer.Option(
            "--label",
            metavar="[STATE]",
            help="Restore blocked issue to inferred or specified state "
            "WITHOUT deleting worktree/branch. "
            "STATE can be: auto, ready, claimed, in-progress, handoff, "
            "review, merge-ready. "
            "Omitting --label is equivalent to --label auto.",
        ),
    ] = None,
    reason: Annotated[str, typer.Option("--reason", help="Reason for resume")] = "",
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Execute the resume (default dry-run)")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Resume blocked issues without deleting worktree/branch.

    `vibe3 task resume` is equivalent to `vibe3 task resume --label auto`.
    Destructive scene rebuild is handled by `vibe3 flow rebuild`.

    By default, runs in dry-run mode. Use --yes to execute the resume.

    Examples:
        vibe3 task resume --blocked          # Resume all blocked issues
        vibe3 task resume 456 --yes          # Resume issue #456
        vibe3 task resume --branch task/issue-123 --yes  # Resume via branch
        vibe3 task resume --pr 456 --yes     # Resume via PR number
    """
    if trace:
        setup_logging(verbose=2)

    # Register EDA event handlers
    from vibe3.domain.handlers import register_event_handlers

    register_event_handlers()

    # Validate arguments
    # Check for conflicts between --blocked, --branch/--pr, and positional issue_numbers
    if blocked and (branch_opt is not None or pr_opt is not None):
        typer.echo("Error: Cannot combine --blocked with --branch or --pr", err=True)
        raise typer.Exit(1)

    if (branch_opt is not None or pr_opt is not None) and issue_numbers:
        typer.echo(
            "Error: Cannot combine --branch/--pr with positional issue numbers",
            err=True,
        )
        raise typer.Exit(1)

    if blocked and issue_numbers:
        typer.echo("Error: Cannot combine issue numbers with --blocked", err=True)
        raise typer.Exit(1)

    if not blocked and not issue_numbers and not branch_opt and not pr_opt:
        typer.echo(
            "Error: Must specify --blocked, --branch, --pr, or provide issue numbers",
            err=True,
        )
        raise typer.Exit(1)

    # Resolve label state from parameter.
    # Public contract: task resume == task resume --label auto.
    valid_states = {
        "ready",
        "claimed",
        "in-progress",
        "handoff",
        "review",
        "merge-ready",
    }
    effective_label = ""
    if label is not None:
        if label == "auto":
            effective_label = ""
        elif label in valid_states:
            effective_label = label
        else:
            typer.echo(
                f"Error: Invalid state '{label}'. "
                f"Must be one of: auto, {', '.join(sorted(valid_states))}.",
                err=True,
            )
            raise typer.Exit(1)

    # Resolve branch if --branch or --pr is provided
    flow_service = FlowService()
    resolved_issue_numbers: list[int] | None = None

    if branch_opt is not None or pr_opt is not None:
        # Build position_arg from issue_numbers if provided
        position_arg = str(issue_numbers[0]) if issue_numbers else None

        try:
            target_branch = resolve_command_branch(
                branch_opt=branch_opt,
                pr_opt=pr_opt,
                position_arg=position_arg,
                flow_service=flow_service,
            )
        except (UserError, SystemError) as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error

        # Parse issue number from resolved branch
        try:
            issue_num = _parse_issue_number_from_branch(
                target_branch, flow_service.store, flow_service
            )
            resolved_issue_numbers = [issue_num]
        except UserError as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error

    target_issues: list[int] | None
    if blocked:
        target_issues = None
    elif resolved_issue_numbers is not None:
        target_issues = resolved_issue_numbers
    else:
        assert issue_numbers is not None
        target_issues = list(issue_numbers)

    usecase = _build_resume_usecase()

    # Fetch all flows for candidate building
    resume_flows = flow_service.list_flows(status="active")
    stale_flows = flow_service.list_flows(status="stale")

    # Handle --blocked filtering by state label
    if blocked:
        # Fetch all orchestrated issues (not just stale)
        all_issues = usecase.status_service.fetch_orchestrated_issues(
            flows=resume_flows,
            queued_set=set(),
            stale_flows=stale_flows,
        )

        # Filter by state label (FAILED unified to BLOCKED)
        target_state = IssueState.BLOCKED

        # Extract issue numbers matching target state
        issue_numbers = [
            num
            for issue in all_issues
            if issue.get("state") == target_state
            and isinstance((num := issue.get("number")), int)
        ]

        if not issue_numbers:
            typer.echo("No blocked issues found.")
            return

    # Progress callback for verbose output
    def progress_callback(
        issue_number: int, branch: str | None, step: str, status: str
    ) -> None:
        prefix = f"  #{issue_number}"
        if branch:
            prefix += f" [{branch}]"
        if status == "done":
            typer.echo(f"{prefix} ✓ {step}")
        elif status == "failed":
            typer.echo(f"{prefix} ✗ {step}", err=True)
        else:
            typer.echo(f"{prefix} → {step}")

    # Execute resume
    if blocked:
        result = usecase.resume_issues(
            issue_numbers=issue_numbers,
            reason=reason,
            dry_run=not yes,
            flows=resume_flows,
            stale_flows=stale_flows,
            label_state=effective_label,
            progress_callback=progress_callback if yes else None,
        )
    else:
        # Explicit issue numbers
        result = usecase.resume_issues(
            issue_numbers=target_issues,
            reason=reason,
            dry_run=not yes,
            flows=resume_flows,
            stale_flows=stale_flows,
            label_state=effective_label,
            progress_callback=progress_callback if yes else None,
        )

    if not yes and blocked and not result.get("candidates"):
        typer.echo("No blocked issues found.")
        return

    if json_output:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        # Human-readable output
        if not yes:
            if blocked:
                candidate_count = len(result.get("candidates", []))
                typer.echo(f"Found {candidate_count} blocked issue(s)")
                typer.echo("\n[dry-run mode] Would resume the following issues:")
            if "candidates" in result:
                for candidate in result["candidates"]:
                    num = candidate.get("number")
                    title = candidate.get("title", "")
                    resume_kind = candidate.get("resume_kind", "unknown")
                    # Show resume kind for each candidate
                    kind_label = f" ({resume_kind})"
                    if resume_kind == "blocked":
                        flow = candidate.get("flow")
                        if flow and hasattr(flow, "flow_status"):
                            kind_label += f", {flow.flow_status}"
                    typer.echo(f"  #{num}: {title}{kind_label}")
        else:
            typer.echo("\nResume completed:")

        # Show statistics
        resumed = result.get("resumed", [])
        skipped = result.get("skipped", [])
        requested = result.get("requested", [])

        typer.echo(
            f"\n  Requested: "
            f"{len(requested) if isinstance(requested, list) else requested}"
        )
        typer.echo(f"  Resumed: {len(resumed)}")
        if resumed:
            resumed_numbers = [
                r["number"] if isinstance(r, dict) else r for r in resumed
            ]
            typer.echo(f"    Issues: {', '.join(f'#{n}' for n in resumed_numbers)}")

        if skipped:
            typer.echo(f"  Skipped: {len(skipped)}")
            for item in skipped:
                num = (
                    item.get("number")
                    if isinstance(item, dict)
                    else item.get("issue_number")
                )
                reason_text = item.get("reason", "")
                typer.echo(f"    #{num}: {reason_text}")

        if yes and not result.get("resumed"):
            typer.echo(
                "\nTip: No issues were resumed. "
                "Check if issues are in failed or blocked state."
            )
        elif yes:
            typer.echo(
                "\nTip: If all failed issues are resumed, "
                "the failed gate will automatically unblock."
            )
