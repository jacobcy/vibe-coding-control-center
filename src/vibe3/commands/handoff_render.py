"""Handoff rendering utilities for CLI display.

Pure functions for rendering agent chains, handoff events, and updates log.
"""

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.flow import FlowState
from vibe3.ui.console import console
from vibe3.ui.flow_ui_primitives import resolve_ref_path

# Preview limit for update messages
UPDATE_LOG_MESSAGE_PREVIEW_LIMIT = 80


def _render_agent_chain(
    state: FlowState,
    store: SQLiteClient,
    live_sessions: list[dict] | None = None,
    worktree_root: str | None = None,
) -> None:
    """Render agent chain with issue URL fallback for spec_ref."""
    console.print("[bold]Agent Chain[/]")

    # Check if this is an issue-based flow
    from vibe3.clients.github_client import GitHubClient
    from vibe3.config.settings import VibeConfig
    from vibe3.services.issue_flow_service import IssueFlowService

    issue_service = IssueFlowService(store=store)
    issue_number = issue_service.parse_issue_number_any(state.branch)

    for label, actor_label in [
        ("spec_ref", "planner_actor"),
        ("plan_ref", "planner_actor"),
        ("report_ref", "executor_actor"),
        ("audit_ref", "reviewer_actor"),
    ]:
        val = getattr(state, label, None)
        actor = getattr(state, actor_label, None) or ""
        actor_str = f"  [dim]{actor}[/]" if actor else ""

        # Special handling for spec_ref: show issue URL if None but issue flow
        if label == "spec_ref" and not val and issue_number is not None:
            # Try to get issue URL from cache or GitHub API
            cache = store.get_flow_context_cache(state.branch)
            issue_url = None
            effective_issue_number = issue_number

            # Try cache first for issue number
            if cache and cache.get("task_issue_number"):
                effective_issue_number = cache["task_issue_number"]

            # Build GitHub issue URL
            config = VibeConfig.get_defaults()
            repo = config.orchestra.repo if config.orchestra.repo else None

            if not repo:
                # Fallback: try to get repo from gh CLI (current repo)
                try:
                    import subprocess

                    result = subprocess.run(
                        ["gh", "repo", "view", "--json", "nameWithOwner"],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    import json

                    data = json.loads(result.stdout)
                    repo = data.get("nameWithOwner")
                except Exception:
                    pass

            if repo:
                # repo format: "owner/repo"
                issue_url = f"https://github.com/{repo}/issues/{effective_issue_number}"
            else:
                # Last fallback: try to get from GitHub API
                try:
                    gh = GitHubClient()
                    issue_data = gh.view_issue(effective_issue_number)
                    if isinstance(issue_data, dict):
                        issue_url = issue_data.get("html_url")
                except Exception:
                    pass

            if issue_url:
                console.print(f"  [dim]{label}[/]{actor_str}")
                console.print(
                    f"    [link={issue_url}]{issue_url}[/]",
                    no_wrap=True,
                    overflow="ellipsis",
                )
            else:
                # Fallback: show issue number with pending status
                console.print(f"  [dim]{label}[/]{actor_str}")
                console.print(
                    f"    [dim]#{effective_issue_number} (issue flow, pending spec)[/]"
                )
        elif label == "spec_ref" and not val and issue_number is None:
            # Non-issue flow with no spec_ref
            console.print(f"  [dim]{label}[/]  [dim](pending)[/]")
        else:
            # Normal ref display (plan_ref, report_ref, audit_ref)
            display_val = resolve_ref_path(val, worktree_root)
            if display_val:
                label_line = f"  [dim]{label}[/]{actor_str}"
                console.print(label_line)
                console.print(f"    {display_val}", no_wrap=True, overflow="ellipsis")
            else:
                console.print(f"  [dim]{label}[/]  [dim](pending)[/]")

    # Render live sessions if provided
    if live_sessions:
        console.print()
        console.print("[bold]Live Sessions[/]")
        for session in live_sessions:
            role = session.get("role", "unknown")
            tmux = session.get("tmux_session", "")
            status = session.get("status", "unknown")
            created = session.get("created_at", "")
            created_str = created[:19].replace("T", " ") if created else ""
            console.print(
                f"  [dim]{created_str}[/]  [{status}]{status}[/]  "
                f"[magenta]{role}[/]  [dim]{tmux}[/]"
            )


def _render_handoff_events(events: list, worktree_root: str | None = None) -> None:
    """Render handoff events in reverse chronological order."""
    if not events:
        console.print("[dim]  no handoff events[/]")
        return

    from vibe3.ui.flow_ui_primitives import resolve_ref_path

    for event in reversed(events):
        time_str = event.created_at[:19].replace("T", " ")
        console.print(
            f"[dim]{time_str}[/]  [magenta]{event.event_type}[/]  [dim]{event.actor}[/]"
        )
        if event.detail:
            console.print(f"  {event.detail}")
        if event.refs:
            files = event.refs.get("files") if isinstance(event.refs, dict) else None
            if files and isinstance(files, list):
                for f in files:
                    display_f = resolve_ref_path(f, worktree_root)
                    console.print(f"  [dim]- {display_f}[/]")
            ref = event.refs.get("ref") if isinstance(event.refs, dict) else None
            if ref:
                display_ref = resolve_ref_path(ref, worktree_root)
                console.print(f"  [dim]- {display_ref}[/]")
        console.print()


def _preview_update_message(message: str, truncate: bool = True) -> str:
    """Preview update message with truncation if needed."""
    if not truncate or len(message) <= UPDATE_LOG_MESSAGE_PREVIEW_LIMIT:
        return message

    # Truncate to limit, preserving word boundaries
    truncated = message[:UPDATE_LOG_MESSAGE_PREVIEW_LIMIT]
    # Find last space to avoid cutting words mid-way
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + "..."


def _render_updates_log(updates: list[dict[str, str]], truncate: bool = True) -> None:
    """Render updates in log format."""
    if not updates:
        console.print("[dim]  no updates yet[/]")
        return

    kind_colors = {"finding": "yellow", "blocker": "red", "next": "blue", "note": "dim"}
    for update in updates:
        timestamp = update["timestamp"]
        actor = update["actor"]
        kind = update["kind"]
        message = update["message"]
        kind_color = kind_colors.get(kind, "dim")
        time_str = timestamp[:19].replace("T", " ")
        console.print(f"[dim]{time_str}[/]  [{kind_color}]{kind}[/]  [dim]{actor}[/]")
        if message:
            for msg_line in _preview_update_message(message, truncate).split("\n"):
                # Use overflow='ellipsis' for clean path truncation if needed
                console.print(f"  {msg_line}", overflow="ellipsis")
        console.print()
