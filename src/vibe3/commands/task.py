#!/usr/bin/env python3
"""Task command handlers."""

import json
from contextlib import contextmanager
from typing import Annotated, Any, Iterator

import typer

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.task_resume_usecase import TaskResumeUsecase
from vibe3.services.task_service import TaskService
from vibe3.ui.task_ui import (
    render_task_show_with_milestone,
)

app = typer.Typer(
    help="Manage execution tasks", no_args_is_help=True, rich_markup_mode="rich"
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _build_github_client() -> GitHubClient:
    """Construct a milestone service."""
    return GitHubClient()


def _build_resume_usecase() -> TaskResumeUsecase:
    """Construct a unified resume usecase."""
    return TaskResumeUsecase()


def _is_human_comment(comment: dict[str, Any]) -> bool:
    author = comment.get("author") or {}
    login = str(author.get("login") or "").strip().lower()
    if not login:
        return True
    if login == "linear" or login.endswith("[bot]"):
        return False
    return True


def _render_comments(issue: dict[str, Any], json_output: bool) -> None | dict[str, Any]:
    comments = issue.get("comments") or []
    latest_comment = comments[-1] if comments else None
    latest_human = next(
        (comment for comment in reversed(comments) if _is_human_comment(comment)),
        None,
    )

    if json_output:
        return {
            "issue": issue.get("number"),
            "title": issue.get("title"),
            "body": issue.get("body"),
            "state": issue.get("state"),
            "labels": [label.get("name") for label in issue.get("labels", [])],
            "latest_comment": latest_comment,
            "latest_human_comment": latest_human,
        }

    # Render issue body first
    typer.echo("\nIssue Body:")
    body = str(issue.get("body") or "").strip()
    if body:
        # Indent body lines for better readability
        for line in body.split("\n"):
            typer.echo(f"  {line}")
    else:
        typer.echo("  (no description)")

    # Render latest comment
    typer.echo("\nLatest Comment:")
    if latest_comment:
        author = (latest_comment.get("author") or {}).get("login") or "unknown"
        typer.echo(f"  author  {author}")
        comment_body = str(latest_comment.get("body") or "").strip()
        for line in comment_body.split("\n"):
            typer.echo(f"  {line}")
    else:
        typer.echo("  (no comments)")

    # Render latest human instruction
    typer.echo("\nLatest Human Instruction:")
    if latest_human:
        author = (latest_human.get("author") or {}).get("login") or "unknown"
        typer.echo(f"  author  {author}")
        human_body = str(latest_human.get("body") or "").strip()
        for line in human_body.split("\n"):
            typer.echo(f"  {line}")
    else:
        typer.echo("  (no human comments)")

    return None


@app.command()
def show(
    branch: Annotated[str | None, typer.Argument(help="Branch name")] = None,
    trace: Annotated[bool, typer.Option("--trace")] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    comments: Annotated[
        bool, typer.Option("--comments", help="Include latest issue comments context")
    ] = False,
) -> None:
    """Show task details."""
    task_svc = TaskService()
    milestone_svc = _build_github_client()

    try:
        target_branch = task_svc.resolve_branch(branch)
    except RuntimeError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if trace:
        setup_logging(verbose=2)

    ctx = (
        trace_context(command="task show", domain="task", branch=target_branch)
        if trace
        else _noop()
    )
    with ctx:
        task_result = task_svc.show_task(target_branch)

        # Fetch milestone context if task has an issue number
        milestone_ctx = None
        issue_number = None
        if task_result.local_task and task_result.local_task.task_issue_number:
            issue_number = task_result.local_task.task_issue_number

        if issue_number:
            milestone_ctx = milestone_svc.get_milestone_context(issue_number)

        # Delegate rendering to UI layer
        render_task_show_with_milestone(task_result, milestone_ctx, json_output)

        if comments and issue_number:
            task_svc = TaskService()
            issue = task_svc.fetch_issue_with_comments(issue_number)
            if issue == "network_error":
                typer.echo("\nIssue comments unavailable: network/auth error")
            elif issue is None:
                typer.echo(
                    f"\nIssue comments unavailable: issue #{issue_number} not found"
                )
            else:
                assert isinstance(issue, dict)
                comments_data = _render_comments(issue, json_output)
                if json_output and comments_data and task_result.local_task:
                    # Merge comments into a single JSON with task data
                    combined = task_result.local_task.model_dump()
                    combined["comments"] = comments_data
                    typer.echo(json.dumps(combined, indent=2, default=str))
                elif not json_output:
                    pass  # _render_comments already printed text
                elif task_result.local_task:
                    pass  # task JSON already printed; comments_data is just info


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
    from vibe3.commands import status as status_command

    status_command.status(
        all_flows=all_flows,
        check=check,
        json_output=json_output,
        trace=trace,
    )


@app.command()
def resume(
    issue_numbers: Annotated[
        list[int] | None,
        typer.Argument(help="Issue numbers to resume"),
    ] = None,
    failed: Annotated[
        bool, typer.Option("--failed", help="Resume all failed issues")
    ] = False,
    blocked: Annotated[
        bool, typer.Option("--blocked", help="Resume all blocked issues")
    ] = False,
    all_tasks: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Reset all auto-created task/issue-* scenes and resume from ready",
        ),
    ] = False,
    label: Annotated[
        bool,
        typer.Option(
            "--label",
            help="Clear blocked_reason/failed_reason and restore to handoff "
            "state (no worktree deletion)",
        ),
    ] = False,
    label_ready: Annotated[
        bool,
        typer.Option(
            "--label-ready",
            help="Clear blocked_reason/failed_reason and restore to ready "
            "state (no worktree deletion)",
        ),
    ] = False,
    reason: Annotated[str, typer.Option("--reason", help="Reason for resume")] = "",
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Execute the resume (default dry-run)")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Resume failed or blocked issues to ready.

    Use --failed to resume all failed issues, --blocked to resume all
    blocked issues, or --all to reset every auto-created task/issue-*
    scene back to ready. Or specify issue numbers directly.

    **Label-only mode (no worktree deletion)**:
    Use --label to clear blocked_reason/failed_reason and restore to
    handoff state WITHOUT deleting worktree/branch.
    Use --label-ready to restore to ready state WITHOUT deletion.
    Without these flags, the original behavior deletes worktree/branch.

    Examples:
        vibe3 task resume 303 --label -y         # Restore to handoff, keep worktree
        vibe3 task resume 303 --label-ready -y   # Restore to ready, keep worktree
        vibe3 task resume 303 -y                 # Delete worktree/branch (original)

    By default, runs in dry-run mode. Use --yes to execute the resume.
    """
    if trace:
        setup_logging(verbose=2)

    # Validate arguments
    selected_modes = [failed, blocked, all_tasks]
    has_flag = any(selected_modes)
    if not has_flag and not issue_numbers:
        typer.echo(
            "Error: Must specify --failed, --blocked, --all, or provide issue numbers",
            err=True,
        )
        raise typer.Exit(1)

    if sum(1 for flag in selected_modes if flag) > 1:
        typer.echo(
            "Error: Cannot specify more than one of --failed, --blocked, and --all",
            err=True,
        )
        raise typer.Exit(1)

    if has_flag and issue_numbers:
        typer.echo(
            "Error: Cannot combine issue numbers with --failed, --blocked, or --all",
            err=True,
        )
        raise typer.Exit(1)

    # Resolve label state from bool flags
    if label and label_ready:
        typer.echo(
            "Error: Cannot specify both --label and --label-ready",
            err=True,
        )
        raise typer.Exit(1)
    effective_label: str | None = None
    if label_ready:
        effective_label = "ready"
    elif label:
        effective_label = "handoff"

    target_issues: list[int] | None
    candidate_mode = "resumable"
    if has_flag:
        target_issues = None
        if all_tasks:
            candidate_mode = "all_task"
    else:
        assert issue_numbers is not None
        target_issues = list(issue_numbers)

    usecase = _build_resume_usecase()
    flow_service = FlowService()

    # Fetch all flows for candidate building
    resume_flows = (
        flow_service.list_flows(status=None)
        if candidate_mode == "all_task"
        else flow_service.list_flows(status="active")
    )
    stale_flows = []
    if candidate_mode != "all_task":
        stale_flows = flow_service.list_flows(status="stale")

    # Handle --failed/--blocked filtering by state label
    if has_flag and candidate_mode == "resumable":
        # Fetch all orchestrated issues (not just stale)
        all_issues = usecase.status_service.fetch_orchestrated_issues(
            flows=resume_flows,
            queued_set=set(),
            stale_flows=stale_flows,
        )

        # Filter by state label
        target_state = IssueState.FAILED if failed else IssueState.BLOCKED

        # Extract issue numbers matching target state
        issue_numbers = [
            num
            for issue in all_issues
            if issue.get("state") == target_state
            and isinstance((num := issue.get("number")), int)
        ]

        if not issue_numbers:
            state_name = "failed" if failed else "blocked"
            typer.echo(f"No {state_name} issues found.")
            return

        result = usecase.resume_issues(
            issue_numbers=issue_numbers,
            reason=reason,
            dry_run=not yes,
            flows=resume_flows,
            stale_flows=stale_flows,
            candidate_mode=candidate_mode,
            label_state=effective_label,
        )
    else:
        # Original logic for --all or explicit issue numbers
        result = usecase.resume_issues(
            issue_numbers=target_issues,
            reason=reason,
            dry_run=not yes,
            flows=resume_flows,
            stale_flows=stale_flows,
            candidate_mode=candidate_mode,
            label_state=effective_label,
        )

    if not yes and has_flag and not result.get("candidates"):
        if all_tasks:
            typer.echo("No auto-created task scenes found.")
        elif failed:
            typer.echo("No failed issues found.")
        else:
            typer.echo("No blocked issues found.")
        return

    if json_output:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        # Human-readable output
        if not yes:
            if has_flag:
                candidate_count = len(result.get("candidates", []))
                if all_tasks:
                    typer.echo(f"Found {candidate_count} auto-created task scene(s)")
                elif failed:
                    typer.echo(f"Found {candidate_count} failed issue(s)")
                else:
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
