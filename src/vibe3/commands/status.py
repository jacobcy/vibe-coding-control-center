"""Status command - unified dashboard for flows and orchestra."""

import json
from typing import Annotated, cast

import typer

from vibe3.clients.github_client import GitHubClient
from vibe3.commands.common import trace_scope
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.status_service import OrchestraStatusService
from vibe3.server.registry import _validate_pid_file
from vibe3.services.flow_service import FlowService
from vibe3.ui.console import console

AllOption = Annotated[
    bool, typer.Option("--all", help="显示所有状态的 flow（含 done/aborted/stale）")
]
JsonOption = Annotated[bool, typer.Option("--json", help="JSON 格式输出")]
TraceOption = Annotated[bool, typer.Option("--trace", help="启用调用链路追踪")]


def _state_from_labels(raw_labels: object) -> IssueState | None:
    if not isinstance(raw_labels, list):
        return None
    for item in raw_labels:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        parsed = IssueState.from_label(name)
        if parsed is not None:
            return parsed
    return None


def _is_auto_task_branch(branch: str) -> bool:
    return branch.startswith("task/issue-")


def _is_canonical_task_branch(branch: str, task_issue_number: int | None) -> bool:
    return task_issue_number is not None and branch == f"task/issue-{task_issue_number}"


def _issue_priority(state: IssueState) -> tuple[int, str]:
    """Sort orchestration issues by operational urgency."""
    if state in {
        IssueState.IN_PROGRESS,
        IssueState.REVIEW,
        IssueState.HANDOFF,
        IssueState.CLAIMED,
    }:
        return (0, state.value)
    if state == IssueState.READY:
        return (1, state.value)
    if state == IssueState.BLOCKED:
        return (2, state.value)
    if state == IssueState.FAILED:
        return (3, state.value)
    return (4, state.value)


def _resolve_server_label(
    config: OrchestraConfig, snapshot_found: bool, server_running: bool
) -> str:
    if snapshot_found and server_running:
        return "[green]running[/]"
    pid, is_valid = _validate_pid_file(config.pid_file)
    if is_valid and pid is not None:
        return "[yellow]unreachable[/]"
    return "[dim]stopped[/]"


def status(
    all_flows: AllOption = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="显示前先运行 flow 一致性校验"),
    ] = False,
    json_output: JsonOption = False,
    trace: TraceOption = False,
) -> None:
    """Show dashboard of all issues and their flow status from Orchestra perspective."""
    with trace_scope(trace, "status", domain="status"):
        if check:
            from vibe3.services.check_service import CheckService

            try:
                CheckService().verify_all_flows()
            except Exception:
                pass  # check failure should not block status display

        # 1. Orchestra State (Issues & Managers)
        config = OrchestraConfig.from_settings()
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
        snapshot_found = orch_snapshot is not None

        if not orch_snapshot:
            # Fallback if server is not running
            from dataclasses import replace

            orch_service = OrchestraStatusService(config)
            local_snap = orch_service.snapshot()
            orch_snapshot = replace(local_snap, server_running=False)

        if json_output:
            service = FlowService()
            flows = service.list_flows(status=None if all_flows else "active")

            json_data = {
                "orchestra": (
                    orch_snapshot.model_dump()
                    if hasattr(orch_snapshot, "model_dump")
                    else str(orch_snapshot)
                ),
                "flows": [f.model_dump() for f in flows],
            }
            typer.echo(json.dumps(json_data, indent=2, default=str))
            return

        # Header
        from datetime import datetime

        ts_str = datetime.fromtimestamp(orch_snapshot.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        console.print(f"[bold]Orchestra Status[/] [dim]({ts_str})[/]")
        console.print(
            "Server: "
            + _resolve_server_label(
                config, snapshot_found, orch_snapshot.server_running
            )
        )

        if orch_snapshot.queued_issues:
            console.print(
                f"Queue: [yellow]{len(orch_snapshot.queued_issues)} issues waiting[/]"
            )
        console.print()

        # 2. Issue Tracking (state truth + local scene)
        service = FlowService()
        flows = service.list_flows(status=None if all_flows else "active")

        issue_to_flow = {f.task_issue_number: f for f in flows if f.task_issue_number}
        queued_set = set(orch_snapshot.queued_issues)
        github = GitHubClient()

        orchestrated_issues: list[dict[str, object]] = []
        try:
            raw_issues = github.list_issues(limit=100, state="open", assignee=None)
        except Exception:
            raw_issues = []

        for item in raw_issues:
            number = item.get("number")
            if not isinstance(number, int):
                continue
            state = _state_from_labels(item.get("labels"))
            if state is None:
                continue
            if state == IssueState.DONE:
                continue
            flow = issue_to_flow.get(number)
            orchestrated_issues.append(
                {
                    "number": number,
                    "title": str(item.get("title") or ""),
                    "state": state,
                    "flow": flow,
                    "queued": number in queued_set,
                }
            )

        orchestrated_issues.sort(
            key=lambda item: (
                *_issue_priority(cast(IssueState, item["state"])),
                cast(int, item["number"]),
            )
        )

        console.print("[bold cyan]Issue Progress:[/]")

        if orchestrated_issues:
            active_items = [
                item
                for item in orchestrated_issues
                if cast(IssueState, item["state"])
                in {
                    IssueState.CLAIMED,
                    IssueState.HANDOFF,
                    IssueState.IN_PROGRESS,
                    IssueState.REVIEW,
                }
            ]
            ready_items = [
                item
                for item in orchestrated_issues
                if cast(IssueState, item["state"]) == IssueState.READY
            ]

            console.print("  [bold]Active:[/]")
            if active_items:
                for item in active_items:
                    number = cast(int, item["number"])
                    title = cast(str, item["title"])
                    state = cast(IssueState, item["state"])
                    flow = item["flow"]
                    is_queued = cast(bool, item["queued"])

                    status_str = "QUEUED" if is_queued else state.value.upper()
                    status_color = "yellow" if is_queued else "green"
                    flow_info = (
                        f"  [dim]flow:[/] [cyan]{flow.branch}[/]"
                        if flow
                        else "  [dim]flow:[/] [dim](none)[/]"
                    )
                    console.print(
                        f"  #{number:4}  [{status_color}]{status_str:10}[/]  {title[:48]}..."
                    )
                    console.print(f"             {flow_info}")
            else:
                console.print("  [dim](none)[/]")

            console.print("\n  [bold]Ready Queue:[/]")
            if ready_items:
                for item in ready_items:
                    number = cast(int, item["number"])
                    title = cast(str, item["title"])
                    flow = item["flow"]
                    flow_info = (
                        f"  [dim]flow:[/] [cyan]{flow.branch}[/]"
                        if flow
                        else "  [dim]flow:[/] [dim](none)[/]"
                    )
                    console.print(
                        f"  #{number:4}  [cyan]READY     [/]  {title[:48]}..."
                    )
                    console.print(f"             {flow_info}")
            else:
                console.print("  [dim](none)[/]")
        else:
            console.print("  [dim]No orchestration-tracked issues.[/]")

        console.print()

        blocked_items = [
            item
            for item in orchestrated_issues
            if cast(IssueState, item["state"]) == IssueState.BLOCKED
        ]
        console.print("[bold cyan]Blocked Issues:[/]")
        if blocked_items:
            for item in blocked_items:
                number = cast(int, item["number"])
                title = cast(str, item["title"])
                flow = item["flow"]
                flow_info = (
                    f"[cyan]{flow.branch}[/]" if flow else "[dim](no flow scene)[/]"
                )
                console.print(f"  #{number:4}  {title[:56]}...  [dim]{flow_info}[/]")
        else:
            console.print("  [dim](none)[/]")

        # 3. Local scene context (tracked flows + worktrees)
        worktree_map: dict[str, str] = {}
        try:
            from vibe3.clients.git_client import GitClient

            git = GitClient()
            worktree_output = git._run(["worktree", "list", "--porcelain"])
            current_worktree = ""
            for line in worktree_output.splitlines():
                line = line.strip()
                if line.startswith("worktree "):
                    current_worktree = line.split(" ", 1)[1]
                elif line.startswith("branch ") and current_worktree:
                    branch_ref = line.split(" ", 1)[1]
                    branch = branch_ref.removeprefix("refs/heads/")
                    worktree_map[branch] = current_worktree.split("/")[-1]
        except Exception:
            pass

        if flows:
            auto_flows = [
                flow
                for flow in flows
                if _is_auto_task_branch(flow.branch) and flow.branch in worktree_map
            ]
            manual_flows = [
                flow for flow in flows if not _is_auto_task_branch(flow.branch)
            ]

            console.print("\n[bold cyan]Auto Task Scenes:[/]")
            if auto_flows:
                for flow in auto_flows:
                    wt = worktree_map.get(flow.branch, "(no worktree)")
                    if _is_canonical_task_branch(flow.branch, flow.task_issue_number):
                        console.print(f"  [cyan]{flow.branch:30}[/] [dim]wt:[/] {wt}")
                    else:
                        task = (
                            f"#{flow.task_issue_number}"
                            if flow.task_issue_number
                            else "(no task)"
                        )
                        console.print(
                            f"  [cyan]{flow.branch:30}[/] [dim]wt:[/] {wt:15} [dim]task:[/] {task}"
                        )

            else:
                console.print("  [dim](none)[/]")

            console.print("\n[bold cyan]Manual Scenes:[/]")
            if manual_flows:
                for flow in manual_flows:
                    wt = worktree_map.get(flow.branch, "(no worktree)")
                    task = (
                        f"#{flow.task_issue_number}"
                        if flow.task_issue_number
                        else "(no task)"
                    )
                    console.print(
                        f"  [cyan]{flow.branch:30}[/] [dim]wt:[/] {wt:15} [dim]task:[/] {task}"
                    )
            else:
                console.print("  [dim](none)[/]")
