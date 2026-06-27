#!/usr/bin/env python3
"""Audit observation candidate collector.

Reads ``flow status --all --format json`` output from a file and prints
recent blocked/aborted/failed flow candidates for audit-observation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _is_candidate(flow: dict) -> bool:
    statuses = {
        str(flow.get("flow_status") or "").lower(),
        str(flow.get("planner_status") or "").lower(),
        str(flow.get("executor_status") or "").lower(),
        str(flow.get("reviewer_status") or "").lower(),
        str(flow.get("latest_verdict") or "").lower(),
    }
    return bool(statuses & {"blocked", "aborted", "failed", "block"})


def _sort_key(flow: dict) -> str:
    return (
        flow.get("execution_completed_at")
        or flow.get("execution_started_at")
        or flow.get("updated_at")
        or ""
    )


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/audit-candidates.py <flow-status.json> [limit]",
            file=sys.stderr,
        )
        sys.exit(1)

    path = Path(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    flows = json.loads(path.read_text())

    candidates = sorted(
        (f for f in flows if _is_candidate(f)),
        key=_sort_key,
        reverse=True,
    )[:limit]

    for flow in candidates:
        print(
            f"{flow.get('branch')} "
            f"issue={flow.get('task_issue_number')} "
            f"status={flow.get('flow_status')} "
            f"planner={flow.get('planner_status')} "
            f"executor={flow.get('executor_status')} "
            f"reviewer={flow.get('reviewer_status')} "
            f"pr={flow.get('pr_number')}"
        )


if __name__ == "__main__":
    main()
