#!/usr/bin/env python3
"""Collect blocked/aborted flow facts for audit observation.

This script stays in the mechanical layer:
- reads blocked/aborted flow records
- expands event timelines into raw signal tags
- enriches with exact shared-ledger dedup signals
- optionally fetches remote issue / PR facts

It does NOT decide whether a flow is a prompt problem, a human decision,
an objective bug, or whether the candidate is worth observing. Those
judgments belong to the governance agent and prompt material.

Usage:
    # List all non-objective blocked flows
    uv run python scripts/audit-blocked-flows.py

    # Show mechanically screened candidates for audit observation
    uv run python scripts/audit-blocked-flows.py --ready-for-audit

    # With GitHub enrichment (checks issue state, PR merge status online)
    uv run python scripts/audit-blocked-flows.py --ready-for-audit --enrich

    # Output as JSON
    uv run python scripts/audit-blocked-flows.py --format json

    # Show detailed event timeline for a specific flow
    uv run python scripts/audit-blocked-flows.py --show-events --branch task/issue-2954
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REASON_PATTERNS = [
    "state unchanged",
    "single-step limit exceeded",
    "latest verdict missing",
    "transition_count_exceeded",
    "capacity exceeded",
    "required ref missing",
    "Worktree branch mismatch",
    "closed without merge",
    "cannot_verify_remote_state",
    "no PR found",
    "PR not found",
    "closed on GitHub",
]


@dataclass
class BlockedFlow:
    branch: str
    issue_number: int | None
    flow_status: str
    blocked_by_issue: int | None = None
    blocked_reason: str | None = None
    last_event_detail: str | None = None
    last_event_time: str | None = None
    signal_tags: list[str] = field(default_factory=list)
    reason_pattern_hits: list[str] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    block_evidence: list[str] = field(default_factory=list)
    event_timeline: list[dict[str, Any]] = field(default_factory=list)
    # Screening fields populated by --ready-for-audit
    has_worktree: bool = False
    has_plan_ref: bool = False
    has_report_ref: bool = False
    has_audit_ref: bool = False
    evidence_count: int = 0
    execution_age_days: int | None = None
    # GitHub enrichment (populated by --enrich)
    issue_state: str | None = None  # "OPEN" or "CLOSED"
    has_merged_pr: bool | None = None
    pr_number: int | None = None
    screening_verdict: str = (
        ""  # "candidate", "already_observed", "covered_by_open_decision"
    )


def collect_reason_pattern_hits(reason: str) -> list[str]:
    """Collect exact reason-pattern hits without interpreting what they mean."""
    if not reason:
        return []
    lower_reason = reason.lower()
    return [pattern for pattern in REASON_PATTERNS if pattern.lower() in lower_reason]


def count_evidence_sources(flow_data: dict[str, Any]) -> int:
    """Count available evidence sources for a flow."""
    count = 0
    if flow_data.get("plan_ref"):
        count += 1
    if flow_data.get("report_ref"):
        count += 1
    if flow_data.get("audit_ref"):
        count += 1
    if flow_data.get("pr_ref") or flow_data.get("pr_number"):
        count += 1
    if flow_data.get("issue_number") or flow_data.get("task_issue_number"):
        count += 1
    return count


def compute_execution_age(flow_data: dict[str, Any]) -> int | None:
    """Compute days since execution started/updated."""
    ts_str = (
        flow_data.get("execution_started_at")
        or flow_data.get("execution_completed_at")
        or flow_data.get("updated_at")
    )
    if not ts_str:
        return None
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).days
    except (ValueError, TypeError):
        return None


def fetch_github_issue_state(issue_number: int) -> dict[str, Any] | None:
    """Fetch issue state from GitHub via gh CLI. Returns None if unavailable."""
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "state,number,title"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
        return {"state": data.get("state", "UNKNOWN"), "number": data["number"]}
    except Exception:
        return None


def fetch_pr_info(issue_number: int) -> dict[str, Any] | None:
    """Check if issue has associated merged PR."""
    try:
        # Search for PRs that reference this issue
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--search",
                str(issue_number),
                "--json",
                "number,state,mergedAt,headRefName",
                "--limit",
                "3",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        prs = json.loads(result.stdout)
        for pr in prs:
            if pr.get("mergedAt"):
                return {
                    "merged": True,
                    "number": pr["number"],
                    "branch": pr.get("headRefName", ""),
                }
        if prs:
            return {
                "merged": False,
                "number": prs[0]["number"],
                "branch": prs[0].get("headRefName", ""),
            }
        return None
    except Exception:
        return None


def load_existing_observation_issues(shared_dir: Path) -> set[int]:
    """Scan existing observation files to find which issues already have observations.

    Parses valid observation YAML files and extracts issue_number from subject.
    Returns a set of issue numbers that already have observations.
    """
    observed_issues: set[int] = set()
    obs_dir = shared_dir / "observations"
    if not obs_dir.exists():
        return observed_issues

    import yaml

    for path in sorted(obs_dir.glob("audit-observation-*.y*ml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict) or "audit_observation" not in data:
                continue
            obs = data["audit_observation"]
            if not isinstance(obs, dict):
                continue
            subject = obs.get("subject", {})
            if isinstance(subject, dict) and subject.get("issue_number"):
                observed_issues.add(int(subject["issue_number"]))
        except Exception:
            continue

    return observed_issues


def extract_affected_issue_numbers(body: str) -> set[int]:
    """Extract exact source issue numbers from an Affected Issues markdown section."""
    match = re.search(
        r"^## Affected Issues\s*(.*?)(?=^## |\Z)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return set()

    return {
        int(issue_number)
        for issue_number in re.findall(
            r"^\s*-\s*#(\d+)\b", match.group(1), re.MULTILINE
        )
    }


def load_open_decision_covered_issues() -> set[int]:
    """Load exact source issue numbers already covered by open audit decision issues."""
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--search",
                '"[audit]"',
                "--state",
                "open",
                "--limit",
                "50",
                "--json",
                "body",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        issues = json.loads(result.stdout)
    except Exception:
        return set()

    covered_issue_numbers: set[int] = set()
    for item in issues:
        body = str(item.get("body") or "")
        covered_issue_numbers.update(extract_affected_issue_numbers(body))
    return covered_issue_numbers


def screen_flow(
    bf: BlockedFlow,
    enrich: bool = False,
    observed_issues: set[int] | None = None,
    covered_issue_numbers: set[int] | None = None,
) -> BlockedFlow:
    """Apply only mechanical screening and fact population."""
    # Exact ledger dedup only.
    if observed_issues and bf.issue_number and bf.issue_number in observed_issues:
        bf.screening_verdict = "already_observed"
        return bf

    if (
        covered_issue_numbers
        and bf.issue_number
        and bf.issue_number in covered_issue_numbers
    ):
        bf.screening_verdict = "covered_by_open_decision"
        return bf

    if enrich and bf.issue_number:
        issue_info = fetch_github_issue_state(bf.issue_number)
        if issue_info:
            bf.issue_state = issue_info["state"]
            pr_info = fetch_pr_info(bf.issue_number)
            if pr_info:
                bf.pr_number = pr_info["number"]
                bf.has_merged_pr = pr_info["merged"]

    bf.screening_verdict = "candidate"

    return bf


def get_blocked_flows(active_only: bool = False) -> list[BlockedFlow]:
    """Get all blocked/aborted flows from the database."""
    from vibe3.clients.sqlite_client import SQLiteClient

    client = SQLiteClient()

    if active_only:
        flows = client.get_flows_by_status("blocked") + client.get_flows_by_status(
            "aborted"
        )
    else:
        flows = client.get_all_flows()
        flows = [
            f
            for f in flows
            if f.get("flow_status") in ("blocked", "aborted")
            and f.get("branch") != "main"
        ]  # main branch is a test artifact, not a real flow

    results: list[BlockedFlow] = []
    for flow in flows:
        branch = flow.get("branch", "")
        issue_number = None
        # Extract issue number from various sources
        if flow.get("task_issue_number"):
            issue_number = flow["task_issue_number"]
        elif branch.startswith("task/issue-") or branch.startswith("dev/issue-"):
            try:
                issue_number = int(
                    branch.split("issue-")[1].split("/")[0].split("-")[0]
                )
            except (ValueError, IndexError):
                pass
        if issue_number is None:
            flow_slug = flow.get("flow_slug", "")
            if flow_slug.startswith("issue-"):
                try:
                    issue_number = int(flow_slug.split("issue-")[1])
                except ValueError:
                    pass

        bf = BlockedFlow(
            branch=branch,
            issue_number=issue_number,
            flow_status=flow.get("flow_status", "unknown"),
            blocked_by_issue=flow.get("blocked_by") or flow.get("blocked_by_issue"),
            blocked_reason=flow.get("blocked_reason"),
            # Evidence fields from flow data
            has_worktree=bool(flow.get("has_worktree")),
            has_plan_ref=bool(flow.get("plan_ref")),
            has_report_ref=bool(flow.get("report_ref")),
            has_audit_ref=bool(flow.get("audit_ref")),
            evidence_count=count_evidence_sources(flow),
            execution_age_days=compute_execution_age(flow),
        )

        # Get events for this flow to understand the block reason
        try:
            events = client.get_events(branch=bf.branch, limit=50)
        except Exception:
            events = []

        bf.event_timeline = events

        event_types = sorted({e["event_type"] for e in events})
        block_events = [
            e
            for e in events
            if e["event_type"] in ("flow_blocked", "flow_auto_aborted", "blocked")
        ]
        error_events = [e for e in events if "error" in e["event_type"]]
        transition_exceeded = [
            e for e in events if e["event_type"] == "transition_count_exceeded"
        ]

        if bf.last_event_time is None and events:
            bf.last_event_time = events[0].get("created_at", "")
            bf.last_event_detail = events[0].get("detail", "")
        bf.event_types = event_types
        bf.reason_pattern_hits = collect_reason_pattern_hits(bf.blocked_reason or "")
        bf.signal_tags = []
        if error_events:
            bf.signal_tags.append("has_error_events")
        if transition_exceeded:
            bf.signal_tags.append("transition_count_exceeded")
            bf.block_evidence.append(
                f"transition_count_exceeded: {transition_exceeded[0].get('detail', '')[:120]}"  # noqa: E501
            )
        if bf.blocked_by_issue:
            bf.signal_tags.append("blocked_by_issue")
            bf.block_evidence.append(f"blocked_by_issue: #{bf.blocked_by_issue}")
        if block_events:
            bf.signal_tags.append("has_block_events")
            bf.block_evidence.append(
                f"block_event_detail: {(block_events[0].get('detail') or '')[:120]}"
            )
        if bf.reason_pattern_hits:
            bf.block_evidence.append(
                f"blocked_reason_patterns: {', '.join(bf.reason_pattern_hits)}"
            )

        results.append(bf)

    return results


def flow_to_dict(bf: BlockedFlow) -> dict[str, Any]:
    """Serialize a flow into the shared fact shape used by outputs."""
    return {
        "branch": bf.branch,
        "issue_number": bf.issue_number,
        "flow_status": bf.flow_status,
        "signal_tags": bf.signal_tags,
        "reason_pattern_hits": bf.reason_pattern_hits,
        "event_types": bf.event_types,
        "block_evidence": bf.block_evidence,
        "evidence_count": bf.evidence_count,
        "has_worktree": bf.has_worktree,
        "execution_age_days": bf.execution_age_days,
        "issue_state": bf.issue_state,
        "has_merged_pr": bf.has_merged_pr,
        "pr_number": bf.pr_number,
        "last_event": bf.last_event_detail,
        "last_event_time": bf.last_event_time,
    }


def flow_sources(bf: BlockedFlow) -> list[str]:
    """Return the names of evidence sources available for a flow."""
    sources: list[str] = []
    if bf.has_worktree:
        sources.append("worktree")
    if bf.has_plan_ref:
        sources.append("plan")
    if bf.has_report_ref:
        sources.append("report")
    if bf.has_audit_ref:
        sources.append("audit")
    if bf.pr_number is not None or bf.has_merged_pr is not None:
        sources.append("pr")
    return sources


def print_flow_fact_lines(bf: BlockedFlow) -> None:
    """Print a compact fact block for one flow."""
    print(f"\n  {bf.branch}")
    print(f"  Issue:        #{bf.issue_number}", end="")
    if bf.issue_state:
        print(f" ({bf.issue_state})", end="")
        if bf.has_merged_pr:
            print(" [merged PR]", end="")
    print()
    print(f"  Status:       {bf.flow_status}")
    if bf.signal_tags:
        print(f"  Signal tags:  {', '.join(bf.signal_tags)}")
    if bf.reason_pattern_hits:
        print(f"  Reason hits:  {', '.join(bf.reason_pattern_hits)}")
    sources = flow_sources(bf)
    print(f"  Evidence:     {bf.evidence_count} sources", end="")
    if sources:
        print(f" ({', '.join(sources)})", end="")
    print()
    if bf.execution_age_days is not None:
        print(f"  Age:          {bf.execution_age_days} days since execution")
    for ev in bf.block_evidence[:2]:
        print(f"  Evidence:     {ev[:100]}")


def format_event_line(event: dict[str, Any]) -> str:
    """Format one raw flow event as a plain fact row."""
    ts = str(event.get("created_at", ""))[:19].replace("T", " ")
    event_type = str(event.get("event_type", ""))
    detail = str(event.get("detail") or "")[:100]
    return f"{ts:22s} {event_type:35s} {detail}"


def print_results(
    flows: list[BlockedFlow],
    format_type: str = "text",
    ready_for_audit: bool = False,
) -> None:
    """Print results."""
    if ready_for_audit:
        ready = [f for f in flows if f.screening_verdict == "candidate"]
        already_observed = [
            f for f in flows if f.screening_verdict == "already_observed"
        ]
        covered_by_open_decision = [
            f for f in flows if f.screening_verdict == "covered_by_open_decision"
        ]

        if format_type == "json":
            output = {
                "summary": {
                    "total_blocked_aborted": len(flows),
                    "candidate_count": len(ready),
                    "excluded": {
                        "already_observed": len(already_observed),
                        "covered_by_open_decision": len(covered_by_open_decision),
                    },
                },
                "audit_candidates": [flow_to_dict(f) for f in ready],
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(f"\n{'=' * 70}")
            print("Audit Observation Facts (mechanically screened)")
            print(f"{'=' * 70}")
            print(f"Total blocked/aborted: {len(flows)}")
            print(f"Candidates:          {len(ready)}")
            print("Excluded:")
            print(
                f"  Already observed:  {len(already_observed)} (existing observation covers this issue)"  # noqa: E501
            )
            print(
                f"  Open decision:     {len(covered_by_open_decision)} (exact issue already in open decision)"  # noqa: E501
            )

            if ready:
                print(f"\n{'─' * 70}")
                print(f"Facts for Agent Judgment — {len(ready)} flows")
                print(f"{'─' * 70}")
                for f in ready:
                    print_flow_fact_lines(f)

        return

    # Original full output mode
    if format_type == "json":
        output = {
            "summary": {
                "total_blocked_aborted": len(flows),
            },
            "flows": [flow_to_dict(f) for f in flows],
        }

        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'=' * 70}")
        print("Blocked/Aborted Flow Facts")
        print(f"{'=' * 70}")
        print(f"Total: {len(flows)}")

        for f in flows:
            print_flow_fact_lines(f)


def show_flow_events(branch: str) -> None:
    """Show detailed event timeline for a specific flow."""
    from vibe3.clients.sqlite_client import SQLiteClient

    client = SQLiteClient()
    events = client.get_events(branch=branch, limit=100)

    if not events:
        print(f"No events found for branch: {branch}")
        return

    print(f"\nEvent timeline for {branch}")
    print(f"{'─' * 70}")
    print(f"{'Time':22s} {'Event Type':35s} Detail")
    print(f"{'─' * 70}")

    for e in events:
        print(format_event_line(e))


def git_common_dir() -> Path:
    """Resolve the git common directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            check=True,
            text=True,
            capture_output=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path(".git")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect blocked/aborted flow facts for audit observation"
    )
    parser.add_argument(
        "--ready-for-audit",
        action="store_true",
        help="Apply only mechanical ledger dedup and optional remote fact enrichment",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Fetch GitHub issue state and PR merge status (requires gh CLI and network)",  # noqa: E501
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Show only currently blocked/aborted flows",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--show-events",
        action="store_true",
        help="Show detailed event timeline for a specific branch",
    )
    parser.add_argument(
        "--branch",
        type=str,
        help="Branch name for --show-events",
    )
    args = parser.parse_args()

    # Suppress loguru debug logging for clean output
    from loguru import logger

    logger.remove()
    logger.add(sys.stderr, level="ERROR")

    if args.show_events:
        if not args.branch:
            print("Error: --branch is required with --show-events", file=sys.stderr)
            sys.exit(1)
        show_flow_events(args.branch)
        return

    flows = get_blocked_flows(active_only=args.active_only)

    # Apply screening if --ready-for-audit
    if args.ready_for_audit:
        # Load existing observation issues for dedup
        observed_issues = load_existing_observation_issues(git_common_dir() / "shared")
        covered_issue_numbers = load_open_decision_covered_issues()

        for bf in flows:
            screen_flow(
                bf,
                enrich=args.enrich,
                observed_issues=observed_issues,
                covered_issue_numbers=covered_issue_numbers,
            )

        print_results(flows, format_type=args.format, ready_for_audit=True)
    else:
        print_results(flows, format_type=args.format)


if __name__ == "__main__":
    main()
