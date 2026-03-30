"""Orchestra UI rendering."""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from vibe3.orchestra.services.status_service import OrchestraSnapshot


def render_orchestra_status(snapshot: OrchestraSnapshot, json_output: bool) -> None:
    """Render orchestra status snapshot.

    Args:
        snapshot: Orchestra status snapshot
        json_output: If True, output as JSON; otherwise formatted text
    """
    if json_output:
        data = _serialize_snapshot(snapshot)
        print(json.dumps(data, indent=2))
    else:
        print(_format_snapshot(snapshot))


def _serialize_snapshot(snapshot: OrchestraSnapshot) -> dict[str, Any]:
    """Serialize snapshot to dict with proper enum handling."""
    data = asdict(snapshot)
    # Convert IssueState enum to string
    for entry in data.get("active_issues", []):
        if entry.get("state") and hasattr(entry["state"], "value"):
            entry["state"] = entry["state"].value
    return data


def _format_snapshot(snapshot: OrchestraSnapshot) -> str:
    """Format snapshot for CLI output."""
    ts = datetime.fromtimestamp(snapshot.timestamp).strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"Orchestra Status ({ts})",
        f"Server: {'running' if snapshot.server_running else 'stopped'}",
        "",
        "Active Issues:",
    ]

    if not snapshot.active_issues:
        lines.append("  (none)")
    else:
        for entry in snapshot.active_issues:
            state_str = entry.state.to_label() if entry.state else "state/unknown"
            flow_str = (
                f"flow={entry.flow_branch}" if entry.flow_branch else "flow=(none)"
            )
            title_short = (
                entry.title[:30] + "..." if len(entry.title) > 30 else entry.title
            )
            blocked_str = ""
            if entry.blocked_by:
                blocked_str = f" blocked_by=#{', #'.join(map(str, entry.blocked_by))}"
            lines.append(
                f"  #{entry.number:<4} {title_short:<33} "
                f"{state_str:<18} {flow_str}{blocked_str}"
            )

    lines.extend(
        [
            "",
            f"Flows: {snapshot.active_flows} active",
            f"Worktrees: {snapshot.active_worktrees} total",
            f"Circuit breaker: {snapshot.circuit_breaker_state} "
            f"(failures={snapshot.circuit_breaker_failures})",
        ]
    )

    if snapshot.circuit_breaker_last_failure:
        last_ts = datetime.fromtimestamp(
            snapshot.circuit_breaker_last_failure
        ).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"Last breaker failure: {last_ts}")

    return "\n".join(lines)
