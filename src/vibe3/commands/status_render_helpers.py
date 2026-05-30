"""Helper functions for status rendering."""

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.ui.console import console
from vibe3.utils.error_message_cleaner import (
    CODEAGENT_WRAPPER_ANYWHERE_RE,
    clean_error_message,
)


def extract_blocked_reason_summary(blocked_reason: str) -> str:
    """Extract key information from blocked_reason for status display.

    Filters out verbose runtime details (TMPDIR, Recent Errors, stdin mode).
    Preserves short status messages and error codes for quick diagnosis.
    """
    if not blocked_reason:
        return ""

    lines = blocked_reason.strip().split("\n")
    if not lines:
        return ""

    # First, remove the "codeagent-wrapper failed (code X):" prefix
    # Use ANYWHERE version to handle "E_EXEC_NO_OUTPUT: codeagent-wrapper..."
    first_line = CODEAGENT_WRAPPER_ANYWHERE_RE.sub("", lines[0].strip())

    # If first line becomes empty or only contains error code
    # (e.g., "E_EXEC_NO_OUTPUT:"), try next line for more descriptive error
    if (not first_line or first_line.rstrip(":").startswith("E_")) and len(lines) > 1:
        next_line = lines[1].strip()
        if next_line:
            first_line = next_line

    if len(first_line) <= 60 and "CLAUDE_CODE_TMPDIR" not in first_line:
        result = first_line
    else:
        cleaned = clean_error_message(first_line)

        if len(cleaned) <= 80:
            result = cleaned
        else:
            # Try to find a sentence boundary
            for sep in ["。", "."]:
                pos = cleaned.rfind(sep, 0, 80)
                if pos > 0:
                    result = cleaned[: pos + 1]
                    break
            else:
                # No sentence boundary found, just truncate
                result = cleaned[:80]

    # Don't end with colon - it looks awkward in "reason: xxx:" format
    if result.endswith(":"):
        result = result[:-1]

    return result


def render_task_item_details(
    flow: FlowStatusResponse | None,
    config: OrchestraConfig,
    assignee: str | None = None,
) -> None:
    """Render shared task detail lines for task-oriented dashboard sections."""
    flow_info = (
        f"[dim]flow:[/] [cyan]{flow.branch}[/]"
        if flow
        else "[dim]flow:[/] [dim](none)[/]"
    )
    detail_parts = [flow_info]
    if assignee:
        detail_parts.append(f"[dim]assignee:[/] [cyan]{assignee}[/]")
    console.print("             " + "  ".join(detail_parts))

    if not flow:
        return

    if flow.plan_ref:
        console.print(f"             [dim]plan:[/] [cyan]{flow.plan_ref}[/]")
    if flow.report_ref:
        console.print(f"             [dim]report:[/] [cyan]{flow.report_ref}[/]")
    if flow.latest_verdict:
        v = flow.latest_verdict
        color = {
            "PASS": "green",
            "MINOR": "cyan",
            "MAJOR": "yellow",
            "BLOCK": "red",
            "REFUSE": "magenta",
        }.get(v.verdict, "cyan")
        console.print(
            f"             [dim]verdict:[/] "
            f"[{color}]{v.verdict}[/] [dim]({v.actor})[/]"
        )
    if flow.pr_number:
        pr_ref = (
            f"https://github.com/{config.repo}/pull/{flow.pr_number}"
            if config.repo
            else f"PR #{flow.pr_number}"
        )
        console.print(f"             [dim]PR:[/] [cyan]{pr_ref}[/]")
