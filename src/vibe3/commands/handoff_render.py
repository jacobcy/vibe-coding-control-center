"""Handoff rendering utilities for CLI display.

Pure functions for rendering agent chains, handoff events, and updates log.
"""

import re

from vibe3.services.shared import ref_to_handoff_cmd, sanitize_event_detail_paths
from vibe3.ui import console, resolve_ref_path
from vibe3.utils import AUTOMATED_MARKERS

_to_handoff_cmd = ref_to_handoff_cmd


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
                            console.print(f"      [dim]- {display_f}[/]")
                    elif key.endswith("_ref"):
                        # Handle explicit *_ref fields with path resolution
                        # Skip generic "ref" field as it lacks type information
                        display_ref = resolve_ref_path(value, worktree_root)
                        console.print(
                            f"    [dim]{key}: "
                            f"{_to_handoff_cmd(display_ref, branch, key)}[/]"
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
                        console.print(f"  [dim]- {display_f}[/]")
                # Normal mode: show explicit *_ref fields
                # Skip generic "ref" field as it lacks type information
                ref_keys = [
                    "plan_ref",
                    "audit_ref",
                    "report_ref",
                    "indicate_ref",
                    "spec_ref",
                ]
                for key in ref_keys:
                    ref_value = (
                        event.refs.get(key) if isinstance(event.refs, dict) else None
                    )
                    if ref_value and isinstance(ref_value, str):
                        display_ref = resolve_ref_path(ref_value, worktree_root)
                        console.print(
                            f"  [dim]- {_to_handoff_cmd(display_ref, branch, key)}[/]"
                        )
        console.print()
