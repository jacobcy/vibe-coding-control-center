"""Handoff rendering utilities for CLI display.

Pure functions for rendering agent chains, handoff events, and updates log.
"""

import re

from vibe3.ui.console import console
from vibe3.ui.flow_ui_primitives import resolve_ref_path
from vibe3.utils.constants import AUTOMATED_MARKERS
from vibe3.utils.path_helpers import sanitize_event_detail_paths


def _path_to_alias(path: str) -> str:
    """Convert a ref path to shortcut alias if applicable.

    Args:
        path: Relative or absolute ref path

    Returns:
        Shortcut alias (@plan, @report, etc.) or original path
    """
    if path.startswith("docs/plans/"):
        return "@plan"
    if path.startswith("docs/reports/"):
        return "@report"
    if path.startswith("docs/specs/"):
        return "@spec"
    # Shared artifacts: extract key from .git/vibe3/handoff/<key>/
    if ".git/vibe3/handoff/" in path:
        match = re.search(r"\.git/vibe3/handoff/([^/]+)/", path)
        if match:
            return f"@{match.group(1)}"
    return path


_to_handoff_cmd = _path_to_alias


def _render_handoff_events(
    events: list,
    worktree_root: str | None = None,
    branch: str | None = None,
    verbose: bool = False,
) -> None:
    """Render successful handoff events in reverse chronological order.

    Filters out *_recorded events when corresponding handoff_* events exist
    to avoid duplicate display.

    Args:
        events: List of handoff events to render.
        worktree_root: Root path of the worktree for path resolution.
        branch: Branch name for handoff command generation.
        verbose: If True, show full event details including all refs fields.
    """
    if not events:
        console.print("[dim]  no handoff events[/]")
        return

    display_names = {
        "handoff_plan": "Plan Handoff",
        "handoff_report": "Report Handoff",
        "handoff_run": "Run Handoff",  # backward-compat: legacy name for handoff_report
        "handoff_audit": "Audit Handoff",
        "handoff_indicate": "Manager Handoff",
        "handoff_verdict": "Verdict Handoff",
        "next_step_set": "Next Step",
    }

    # Filter out recorded events if handoff events exist for same kind
    handoff_kinds = {"plan", "report", "audit"}
    has_handoff = {kind: False for kind in handoff_kinds}

    # First pass: detect which handoff types exist
    for event in events:
        for kind in handoff_kinds:
            if event.event_type == f"handoff_{kind}":
                has_handoff[kind] = True

    # Second pass: filter recorded events if handoff exists
    filtered_events = []
    for event in events:
        skip = False
        for kind in handoff_kinds:
            if event.event_type == f"{kind}_recorded" and has_handoff[kind]:
                skip = True
                break
        if not skip:
            filtered_events.append(event)

    for event in reversed(filtered_events):
        # Use full ISO timestamp in verbose mode, compact in normal mode
        if verbose:
            time_str = event.created_at
        else:
            time_str = event.created_at[:19].replace("T", " ")
        event_name = display_names.get(event.event_type, event.event_type)

        # Bug 9: Label manager handoffs vs human ones
        actor_label = f"[dim]{event.actor}[/]"
        is_manager = (
            event.event_type == "handoff_indicate"
            or "manager" in str(event.actor).lower()
        )

        if is_manager:
            actor_label = f"[bold yellow]\\[manager][/bold yellow] {actor_label}"

        console.print(f"[dim]{time_str}[/]  [magenta]{event_name}[/]  {actor_label}")

        # Skip detail rendering for handoff_verdict (verdict shown in refs)
        if event.detail and event.event_type != "handoff_verdict":
            sanitized = sanitize_event_detail_paths(
                event.detail, event.refs, worktree_root
            )
            # Add color for manager details if they start with marker
            display_detail = sanitized
            escaped_markers = [re.escape(m) for m in AUTOMATED_MARKERS]
            pattern = r"^(\s*|#{1,6}\s*)(" + "|".join(escaped_markers) + ")"
            if re.match(pattern, sanitized, re.IGNORECASE):
                display_detail = f"[yellow]{sanitized}[/]"

            console.print(f"  {display_detail}")

        # Special rendering for handoff_verdict: show verdict value from refs
        if event.event_type == "handoff_verdict" and event.refs:
            verdict_value = (
                event.refs.get("verdict") if isinstance(event.refs, dict) else None
            )
            if verdict_value:
                console.print(f"  Verdict: {verdict_value}")

        # Show refs
        if event.refs and event.event_type != "handoff_verdict":
            if verbose:
                # In verbose mode, show all refs fields
                console.print("  [cyan]refs:[/]")
                for key, value in event.refs.items():
                    if key == "files" and isinstance(value, list):
                        console.print("    [dim]files:[/]")
                        for f in value:
                            display_f = resolve_ref_path(f, worktree_root)
                            console.print(
                                f"      [dim]- " f"{_to_handoff_cmd(display_f)}[/]"
                            )
                    elif key == "ref":
                        display_ref = resolve_ref_path(value, worktree_root)
                        console.print(
                            "    [dim]ref: " f"{_to_handoff_cmd(display_ref)}[/]"
                        )
                    else:
                        console.print(f"    [dim]{key}: {value}[/]")
            else:
                # Normal mode: show only files and ref
                files = (
                    event.refs.get("files") if isinstance(event.refs, dict) else None
                )
                if files and isinstance(files, list):
                    for f in files:
                        display_f = resolve_ref_path(f, worktree_root)
                        console.print("  [dim]- " f"{_to_handoff_cmd(display_f)}[/]")
                ref = event.refs.get("ref") if isinstance(event.refs, dict) else None
                if ref:
                    display_ref = resolve_ref_path(ref, worktree_root)
                    console.print("  [dim]- " f"{_to_handoff_cmd(display_ref)}[/]")
        console.print()
