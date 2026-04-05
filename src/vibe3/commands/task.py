#!/usr/bin/env python3
"""Task command handlers."""

import json
from contextlib import contextmanager
from typing import Annotated, Any, Iterator

import typer

from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.flow_service import FlowService
from vibe3.services.milestone_service import MilestoneService
from vibe3.services.status_query_service import StatusQueryService
from vibe3.services.task_failed_resume_usecase import TaskFailedResumeUsecase
from vibe3.services.task_service import TaskService
from vibe3.services.task_usecase import TaskUsecase
from vibe3.ui.task_ui import (
    render_task_show_with_milestone,
)

app = typer.Typer(
    help="Manage execution tasks", no_args_is_help=True, rich_markup_mode="rich"
)


@contextmanager
def _noop() -> Iterator[None]:
    yield


def _build_task_usecase() -> TaskUsecase:
    """Construct a task usecase with command-local service wiring."""
    return TaskUsecase(
        flow_service=FlowService(),
        task_service=TaskService(),
    )


def _build_milestone_service() -> MilestoneService:
    """Construct a milestone service."""
    return MilestoneService()


def _build_resume_usecase() -> TaskFailedResumeUsecase:
    """Construct a resume usecase with required services."""
    status_service = StatusQueryService()
    return TaskFailedResumeUsecase(
        status_service=status_service,
        failure_service=None,  # Not used directly
    )


def _is_human_comment(comment: dict[str, Any]) -> bool:
    author = comment.get("author") or {}
    login = str(author.get("login") or "").strip().lower()
    if not login:
        return True
    if login == "linear" or login.endswith("[bot]"):
        return False
    return True


def _render_comments(issue: dict[str, Any], json_output: bool) -> None | dict:
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
            "state": issue.get("state"),
            "labels": [label.get("name") for label in issue.get("labels", [])],
            "latest_comment": latest_comment,
            "latest_human_comment": latest_human,
        }

    typer.echo("\nLatest Comment:")
    if latest_comment:
        author = (latest_comment.get("author") or {}).get("login") or "unknown"
        typer.echo(f"  author  {author}")
        typer.echo(f"  body    {str(latest_comment.get('body') or '').strip()}")
    else:
        typer.echo("  (no comments)")

    typer.echo("\nLatest Human Instruction:")
    if latest_human:
        author = (latest_human.get("author") or {}).get("login") or "unknown"
        typer.echo(f"  author  {author}")
        typer.echo(f"  body    {str(latest_human.get('body') or '').strip()}")
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
    usecase = _build_task_usecase()
    milestone_svc = _build_milestone_service()

    try:
        target_branch = usecase.resolve_branch(branch)
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
        task_result = usecase.show_task(target_branch)

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
        bool, typer.Option("--check", help="显示前先运行 flow 一致性校验")
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
    all_issues: Annotated[
        bool, typer.Option("--all", help="Resume all open failed issues")
    ] = False,
    reason: Annotated[str, typer.Option("--reason", help="Reason for resume")] = "",
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Execute the resume (default dry-run)")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Resume failed issues to ready or handoff.

    By default, runs in dry-run mode. Use --yes to execute the resume.
    """
    if trace:
        setup_logging(verbose=2)

    # Validate arguments
    if not all_issues and not issue_numbers:
        typer.echo(
            "Error: Must specify either --all or provide issue numbers",
            err=True,
        )
        raise typer.Exit(1)

    if not reason:
        typer.echo(
            "Error: --reason is required",
            err=True,
        )
        raise typer.Exit(1)

    # Build issue list
    target_issues: list[int]
    if all_issues:
        # Fetch all failed candidates
        usecase = _build_resume_usecase()
        candidates = usecase.status_service.fetch_failed_resume_candidates(flows=[])
        if not candidates:
            typer.echo("No open failed issues found.")
            return

        target_issues = []
        for c in candidates:
            num = c.get("number")
            if isinstance(num, int):
                target_issues.append(num)
        typer.echo(f"Found {len(target_issues)} failed issue(s)")
    else:
        assert issue_numbers is not None
        target_issues = list(issue_numbers)

    # Execute resume
    usecase = _build_resume_usecase()
    result = usecase.resume_failed_issues(
        issue_numbers=target_issues,
        reason=reason,
        dry_run=not yes,
    )

    if json_output:
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        # Human-readable output
        if not yes:
            typer.echo("\n[dry-run mode] Would resume the following issues:")
            if "candidates" in result:
                for candidate in result["candidates"]:
                    num = candidate.get("number")
                    title = candidate.get("title", "")
                    typer.echo(f"  #{num}: {title}")
        else:
            typer.echo("\nResume completed:")

        # Show statistics
        resumed = result.get("resumed", [])
        skipped = result.get("skipped", [])
        requested = result.get("requested", 0)

        typer.echo(f"\n  Requested: {requested}")
        typer.echo(f"  Resumed: {len(resumed)}")
        if resumed:
            typer.echo(f"    Issues: {', '.join(f'#{n}' for n in resumed)}")

        if skipped:
            typer.echo(f"  Skipped: {len(skipped)}")
            for item in skipped:
                num = item.get("issue_number")
                reason_text = item.get("reason", "")
                typer.echo(f"    #{num}: {reason_text}")

        if yes and not result.get("resumed"):
            typer.echo(
                "\nTip: No issues were resumed. Check if issues are in failed state."
            )
        elif yes:
            typer.echo(
                "\nTip: If all failed issues are resumed, "
                "the failed gate will automatically unblock."
            )
