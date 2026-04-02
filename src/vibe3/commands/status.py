"""Status command - unified dashboard for flows and orchestra."""

import json
from typing import Annotated

import typer

from vibe3.commands.common import trace_scope
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.status_service import OrchestraStatusService
from vibe3.services.flow_service import FlowService
from vibe3.ui.console import console

AllOption = Annotated[
    bool, typer.Option("--all", help="显示所有状态的 flow（含 done/aborted/stale）")
]
JsonOption = Annotated[bool, typer.Option("--json", help="JSON 格式输出")]
TraceOption = Annotated[bool, typer.Option("--trace", help="启用调用链路追踪")]


def status(
    all_flows: AllOption = False,
    json_output: JsonOption = False,
    trace: TraceOption = False,
) -> None:
    """Show dashboard of all issues and their flow status from Orchestra perspective."""
    with trace_scope(trace, "status", domain="status"):
        # 1. Orchestra State (Issues & Managers)
        config = OrchestraConfig.from_settings()
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)

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

        if orch_snapshot.server_running:
            console.print("Server: [green]running[/]")
        else:
            console.print("Server: [dim]stopped[/]")

        if orch_snapshot.queued_issues:
            console.print(
                f"Queue: [yellow]{len(orch_snapshot.queued_issues)} issues waiting[/]"
            )
        console.print()

        # 2. Issue Tracking (The Core View)
        # Combine Orchestra issues with Flow information
        service = FlowService()
        flows = service.list_flows(status=None if all_flows else "active")

        # Map task issue numbers to flows for easy lookup
        issue_to_flow = {f.task_issue_number: f for f in flows if f.task_issue_number}
        queued_set = set(orch_snapshot.queued_issues)

        console.print("[bold cyan]Issue Progress:[/]")

        # Active Issues from Orchestra
        if orch_snapshot.active_issues:
            for issue in orch_snapshot.active_issues:
                flow = issue_to_flow.get(issue.number)
                is_queued = issue.number in queued_set

                if is_queued:
                    status_str = "QUEUED"
                    status_color = "yellow"
                    flow_info = "  [dim]flow:[/] [yellow](waiting)[/]"
                elif flow:
                    status_str = "RUNNING"
                    status_color = "green"
                    flow_info = f"  [dim]flow:[/] [cyan]{flow.branch}[/]"
                else:
                    state_val = (
                        issue.state.value
                        if issue.state and hasattr(issue.state, "value")
                        else (issue.state or "unknown")
                    )
                    status_str = state_val.upper()
                    status_color = "dim"
                    flow_info = "  [dim]flow:[/] [dim](none)[/]"

                console.print(
                    f"  #{issue.number:4}  [{status_color}]{status_str:10}[/]  "
                    f"{issue.title[:40]}..."
                )
                console.print(f"             {flow_info}")
        else:
            console.print("  [dim]No active issues tracked by orchestra.[/]")

        console.print()

        # 4. Worktree context (from Flow Status logic)
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
            console.print("\n[bold cyan]Active Worktrees & Flows:[/]")
            for flow in flows:
                wt = worktree_map.get(flow.branch, "(no worktree)")
                task = (
                    f"#{flow.task_issue_number}"
                    if flow.task_issue_number
                    else "(no task)"
                )
                console.print(
                    f"  [cyan]{flow.branch:30}[/] [dim]wt:[/] {wt:15} "
                    f"[dim]task:[/] {task}"
                )
