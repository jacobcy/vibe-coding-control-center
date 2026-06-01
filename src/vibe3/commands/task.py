#!/usr/bin/env python3
"""Task command handlers."""

import json
from contextlib import contextmanager
from typing import Annotated, Iterator

import typer

from vibe3.commands.command_options import FormatOption
from vibe3.commands.common import enable_method_trace
from vibe3.exceptions import SystemError, UserError
from vibe3.models.orchestration import IssueState
from vibe3.observability.logger import setup_logging
from vibe3.services.flow_service import FlowService
from vibe3.services.task_resume_usecase import TaskResumeUsecase
from vibe3.services.task_service import TaskService
from vibe3.ui.console import console
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
    from typing import cast

    from vibe3.commands.status_render import (
        render_blocked_items,
        render_completed_flows,
        render_epic_items,
        render_issue_progress,
        render_missing_state_items,
        render_pr_ref_items,
        render_remote_items,
        render_rfc_items,
        render_supervisor_issues,
    )
    from vibe3.config.orchestra_settings import load_orchestra_config
    from vibe3.models.orchestration import IssueState
    from vibe3.services.flow_service import FlowService
    from vibe3.services.orchestra_helpers import get_manager_usernames
    from vibe3.services.orchestra_status_service import OrchestraStatusService
    from vibe3.services.status_query_service import (
        StatusQueryService,
        is_auto_task_branch,
    )
    from vibe3.services.task_status_classifier import (
        TaskStatusBucket,
        classify_task_status,
    )

    if trace:
        setup_logging(verbose=2)
        enable_method_trace()

    if check:
        from vibe3.commands.common import run_full_check_shortcut

        run_full_check_shortcut()

    # Get orchestra snapshot and config
    config = load_orchestra_config()
    orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    if orch_snapshot is None:
        import time

        time.sleep(0.5)
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)

    if not orch_snapshot:
        from dataclasses import replace

        from vibe3.services.flow_orchestrator_service import (
            FlowOrchestratorService,
        )

        orch_service = OrchestraStatusService(
            config, orchestrator=FlowOrchestratorService(config)
        )
        local_snap = orch_service.snapshot()
        orch_snapshot = replace(local_snap, server_running=False)

    # JSON output
    if json_output:
        service = FlowService()
        flows = service.list_flows(status=None if all_flows else "active")

        queued_set = set(orch_snapshot.queued_issues)
        query_service = StatusQueryService(repo=config.repo)
        orchestrated_issues = query_service.fetch_orchestrated_issues(
            flows,
            queued_set,
            stale_flows=[],
            manager_usernames=get_manager_usernames(config),
            supervisor_label=config.supervisor_handoff.issue_label,
        )

        from dataclasses import asdict

        output_data = {
            "orchestra": asdict(orch_snapshot),
            "flows": [f.model_dump() for f in flows],
            "orchestrated_issues": orchestrated_issues,
        }
        typer.echo(json.dumps(output_data, indent=2, default=str))
        return

    # Table output - task progress only
    def _include_issue_in_task_progress(item: dict[str, object]) -> bool:
        """Only auto-task flows should participate in task-oriented Issue Progress."""
        from vibe3.models.flow import FlowStatusResponse

        flow = cast(FlowStatusResponse | None, item.get("flow"))
        state = cast(IssueState, item["state"])

        if flow is None:
            is_remote = cast(bool, item.get("remote", False))
            if is_remote:
                return True
            return state in {
                IssueState.READY,
                IssueState.HANDOFF,
                IssueState.BLOCKED,
                IssueState.DONE,
                IssueState.CLAIMED,
                IssueState.IN_PROGRESS,
                IssueState.REVIEW,
            }
        return is_auto_task_branch(flow.branch)

    service = FlowService()
    flows = service.list_flows(status=None if all_flows else "active")
    if not all_flows:
        flows.extend(service.list_flows(status="done"))
        flows.extend(service.list_flows(status="blocked"))

    stale_flows = service.list_flows(status="stale") if not all_flows else []

    queued_set = set(orch_snapshot.queued_issues)
    query_service = StatusQueryService(repo=config.repo)
    orchestrated_issues = query_service.fetch_orchestrated_issues(
        flows,
        queued_set,
        stale_flows=stale_flows,
        manager_usernames=get_manager_usernames(config),
        supervisor_label=config.supervisor_handoff.issue_label,
    )

    supervisor_label = config.supervisor_handoff.issue_label

    # Filtering decision tree
    supervisor_items = [
        item
        for item in orchestrated_issues
        if supervisor_label in cast(list[str], item.get("labels", []))
    ]
    supervisor_numbers = {cast(int, item["number"]) for item in supervisor_items}

    roadmap_rfc_items = [
        item
        for item in orchestrated_issues
        if "roadmap/rfc" in cast(list[str], item.get("labels", []))
        and supervisor_label not in cast(list[str], item.get("labels", []))
    ]
    roadmap_rfc_numbers = {cast(int, item["number"]) for item in roadmap_rfc_items}
    roadmap_epic_items = [
        item
        for item in orchestrated_issues
        if "roadmap/epic" in cast(list[str], item.get("labels", []))
        and supervisor_label not in cast(list[str], item.get("labels", []))
    ]
    roadmap_epic_numbers = {cast(int, item["number"]) for item in roadmap_epic_items}

    manager_usernames = get_manager_usernames(config)

    waiting_for_pool_items = [
        item
        for item in orchestrated_issues
        if item.get("state") is None
        and item.get("assignee") is not None
        and item.get("assignee") in manager_usernames
        and supervisor_label not in cast(list[str], item.get("labels", []))
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
        and "orchestra-governed" not in cast(list[str], item.get("labels", []))
    ]
    governed_anomaly_items = [
        item
        for item in orchestrated_issues
        if item.get("state") is None
        and item.get("assignee") is not None
        and item.get("assignee") in manager_usernames
        and supervisor_label not in cast(list[str], item.get("labels", []))
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
        and "orchestra-governed" in cast(list[str], item.get("labels", []))
    ]
    missing_state_numbers = {
        cast(int, item["number"])
        for item in waiting_for_pool_items + governed_anomaly_items
    }

    task_progress_items = [
        item
        for item in orchestrated_issues
        if _include_issue_in_task_progress(item)
        and cast(int, item["number"]) not in supervisor_numbers
        and cast(int, item["number"]) not in roadmap_rfc_numbers
        and cast(int, item["number"]) not in roadmap_epic_numbers
        and cast(int, item["number"]) not in missing_state_numbers
    ]

    remote_items = [
        item
        for item in task_progress_items
        if cast(bool, item.get("remote"))
        and cast(IssueState, item["state"]) != IssueState.BLOCKED
    ]
    non_remote_items = [
        item for item in task_progress_items if not cast(bool, item.get("remote"))
    ]

    bucketed_items: dict[TaskStatusBucket, list[dict[str, object]]] = {
        TaskStatusBucket.ASSIGNEE_INTAKE: [],
        TaskStatusBucket.READY_QUEUE: [],
        TaskStatusBucket.READY_ANOMALY: [],
        TaskStatusBucket.ACTIVE_ANOMALY: [],
        TaskStatusBucket.OTHER: [],
    }
    for item in non_remote_items:
        state = cast(IssueState | None, item["state"])
        if state == IssueState.DONE:
            continue

        bucket = classify_task_status(
            state,
            cast(str | None, item.get("assignee")),
            get_manager_usernames(config),
        )
        bucketed_items[bucket].append(item)

    render_issue_progress(bucketed_items, config)
    console.print()

    render_remote_items(remote_items)
    console.print()

    render_supervisor_issues(supervisor_items)
    console.print()

    pr_ref_items = [
        item
        for item in task_progress_items
        if item.get("flow") and getattr(item["flow"], "pr_ref", None)
    ]
    render_pr_ref_items(pr_ref_items)

    blocked_items = [
        item
        for item in orchestrated_issues
        if cast(IssueState, item["state"]) == IssueState.BLOCKED
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
        and cast(int, item["number"]) not in supervisor_numbers
    ]

    render_missing_state_items(waiting_for_pool_items, governed_anomaly_items)
    render_rfc_items(roadmap_rfc_items)
    render_epic_items(roadmap_epic_items, orchestrated_issues)
    render_blocked_items(blocked_items)

    if all_flows:
        completed_flows = [
            flow
            for flow in flows
            if getattr(flow, "flow_status", "active") in {"done", "aborted", "merged"}
        ]
        render_completed_flows(completed_flows)


@app.command()
def resume(
    issue_numbers: Annotated[
        list[int] | None,
        typer.Argument(help="Issue numbers to resume"),
    ] = None,
    remote: Annotated[
        bool,
        typer.Option(
            "--remote",
            help="保留远程分支不删除（默认删除远程分支）",
        ),
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
        str | None,
        typer.Option(
            "--label",
            metavar="[STATE]",
            help="Clear blocked_reason and restore to specified state "
            "WITHOUT deleting worktree/branch. "
            "STATE can be: auto, ready, claimed, in-progress, handoff, "
            "review, merge-ready. "
            "Use 'auto' to infer state from flow refs "
            "(prefers review/merge-ready if pr_ref/audit_ref present, "
            "else defaults to CLAIMED). "
            "Without --label, the original behavior deletes worktree/branch.",
        ),
    ] = None,
    reason: Annotated[str, typer.Option("--reason", help="Reason for resume")] = "",
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Execute the resume (default dry-run)")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    trace: Annotated[bool, typer.Option("--trace")] = False,
) -> None:
    """Resume blocked issues to ready.

    Use --remote to keep remote branch (do not delete origin).
    Use --label [STATE] to only update labels without deleting worktree.
    --remote and --label are mutually exclusive.

    By default, runs in dry-run mode. Use --yes to execute the resume.
    """
    if trace:
        setup_logging(verbose=2)

    # Register EDA event handlers
    from vibe3.domain.handlers import register_event_handlers

    register_event_handlers()

    # Validate arguments
    if remote and label is not None:
        typer.echo(
            "Error: Cannot specify both --remote and --label",
            err=True,
        )
        raise typer.Exit(1)

    selected_modes = [blocked, all_tasks]
    has_flag = any(selected_modes)
    if not has_flag and not issue_numbers:
        typer.echo(
            "Error: Must specify --blocked, --all, or provide issue numbers",
            err=True,
        )
        raise typer.Exit(1)

    if sum(1 for flag in selected_modes if flag) > 1:
        typer.echo(
            "Error: Cannot specify more than one of --blocked and --all",
            err=True,
        )
        raise typer.Exit(1)

    if has_flag and issue_numbers:
        typer.echo(
            "Error: Cannot combine issue numbers with --blocked or --all",
            err=True,
        )
        raise typer.Exit(1)

    # Resolve label state from parameter
    valid_states = {
        "ready",
        "claimed",
        "in-progress",
        "handoff",
        "review",
        "merge-ready",
    }
    effective_label: str | None = None
    if label is not None:
        # --label flag is present
        if label == "auto":
            # --label auto -> trigger inference in service
            effective_label = ""
        elif label in valid_states:
            # --label <state> provided
            effective_label = label
        else:
            typer.echo(
                f"Error: Invalid state '{label}'. "
                f"Must be one of: auto, {', '.join(sorted(valid_states))}.",
                err=True,
            )
            raise typer.Exit(1)
    # else: label is None → don't specify --label → delete worktree

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

    # Handle --blocked filtering by state label
    if has_flag and candidate_mode == "resumable":
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
    if has_flag and candidate_mode == "resumable":
        result = usecase.resume_issues(
            issue_numbers=issue_numbers,
            reason=reason,
            dry_run=not yes,
            flows=resume_flows,
            stale_flows=stale_flows,
            candidate_mode=candidate_mode,
            label_state=effective_label,
            remote=remote,
            progress_callback=progress_callback if yes else None,
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
            remote=remote,
            progress_callback=progress_callback if yes else None,
        )

    if not yes and has_flag and not result.get("candidates"):
        if all_tasks:
            typer.echo("No auto-created task scenes found.")
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
