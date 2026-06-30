"""Issue body managed section service."""

import re
from typing import Final, Literal, cast

from vibe3.models import FlowStateProjection

# Managed section markers
MANAGED_SECTION_START: Final[str] = "<!-- vibe3-flow-state-start -->"
MANAGED_SECTION_END: Final[str] = "<!-- vibe3-flow-state-end -->"
MANAGED_SECTION_PATTERN = re.compile(
    rf"{MANAGED_SECTION_START}(.*?){MANAGED_SECTION_END}",
    re.DOTALL,
)


def parse_projection(body: str) -> FlowStateProjection:
    """Parse flow-state projection from issue body.

    Args:
        body: Full issue body text

    Returns:
        FlowStateProjection (default if not found)
    """
    match = MANAGED_SECTION_PATTERN.search(body)
    if not match:
        return FlowStateProjection()

    section = match.group(1).strip()
    if not section:
        return FlowStateProjection()

    # Parse key-value pairs
    state: str = "active"
    blocked_by: list[int] = []
    blocked_reason: str | None = None

    for line in section.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("- **State**:"):
            value = line.split(":", 1)[1].strip()
            if value in ("active", "blocked", "done", "aborted"):
                state = value

        elif line.startswith("- **Blocked by**:"):
            nums = line.split(":", 1)[1].strip()
            blocked_by.extend([int(n) for n in re.findall(r"\d+", nums)])

        elif line.startswith("- **Blocked reason**:"):
            blocked_reason = line.split(":", 1)[1].strip() or None

        elif line.startswith("- **Dependencies**:"):
            nums = line.split(":", 1)[1].strip()
            blocked_by.extend([int(n) for n in re.findall(r"\d+", nums)])

    blocked_by = sorted(list(set(blocked_by)))

    return FlowStateProjection(
        state=cast(Literal["active", "blocked", "done", "aborted"], state),
        blocked_by=blocked_by,
        blocked_reason=blocked_reason,
    )


def merge_projection(body: str, proj: FlowStateProjection) -> str:
    """Merge flow-state projection into issue body.

    Preserves user content, replaces managed section.

    Args:
        body: Original issue body
        proj: FlowStateProjection instance

    Returns:
        Merged body text
    """
    rendered = _render_projection(proj)

    # Remove existing managed section
    cleaned = MANAGED_SECTION_PATTERN.sub("", body).strip()

    # Append new section if non-empty
    if not rendered:
        return cleaned

    return f"{cleaned}\n\n{rendered}"


def _render_projection(proj: FlowStateProjection) -> str:
    """Render flow-state projection to managed section.

    Internal helper for merge_projection.
    """
    if proj.is_empty():
        return ""

    lines = [
        MANAGED_SECTION_START,
        "",
        "**Vibe3 Flow State**",
        "",
        f"- **State**: {proj.state}",
    ]

    if proj.blocked_by:
        blocked_str = ", ".join(f"#{n}" for n in proj.blocked_by)
        lines.append(f"- **Blocked by**: {blocked_str}")

    if proj.blocked_reason:
        lines.append(f"- **Blocked reason**: {proj.blocked_reason}")

    lines.extend(["", MANAGED_SECTION_END])
    return "\n".join(lines)
