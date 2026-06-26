#!/usr/bin/env python3
"""Identify blocked/aborted flows caused by non-objective (prompt/process) factors.

This script mines the flow event database to find flows that were blocked or
aborted due to prompt ambiguity, scope mismatch, state machine errors, or other
non-objective factors — as opposed to objective blocks like API errors, code
bugs, CI failures, or infrastructure issues.

Objective blocks (EXCLUDED from audit observation):
    - codeagent_*_error: actual API/code errors
    - capacity exceeded: infrastructure capacity
    - required ref missing: tool chain / missing artifacts
    - Worktree branch mismatch: environment issue
    - branch no longer exists: infrastructure / cleanup
    - PR closed without merge: external decision

Non-objective blocks (INCLUDED for audit observation):
    - state unchanged: process/prompt issue (state machine stuck)
    - single-step limit exceeded: process design issue
    - latest verdict missing: agent didn't produce output
    - transition_count_exceeded: state machine design issue
    - Blocked by issue #N where upstream is ALSO non-objective

Usage:
    # List all non-objective blocked flows
    uv run python scripts/audit-blocked-flows.py

    # Show only flows ready for audit observation (applies all screening criteria)
    uv run python scripts/audit-blocked-flows.py --ready-for-audit

    # With GitHub enrichment (checks issue state, PR merge status online)
    uv run python scripts/audit-blocked-flows.py --ready-for-audit --enrich

    # Include dependency chain analysis
    uv run python scripts/audit-blocked-flows.py --trace-deps

    # Output as JSON
    uv run python scripts/audit-blocked-flows.py --format json

    # Show detailed event timeline for a specific flow
    uv run python scripts/audit-blocked-flows.py --show-events --branch task/issue-2954
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Objective block reason patterns
OBJECTIVE_BLOCK_PATTERNS = [
    "codeagent_manager_error",
    "codeagent_run_error",
    "codeagent_plan_error",
    "codeagent_review_error",
    "capacity exceeded",
    "required ref missing",
    "Worktree branch mismatch",
    "no longer exists locally",
    "no longer exists",
    "closed without merge",
    "cannot_verify_remote_state",
    "PR #",
]

# Non-objective block reason patterns
NON_OBJECTIVE_BLOCK_PATTERNS = [
    "state unchanged",
    "single-step limit exceeded",
    "latest verdict missing",
    "transition_count_exceeded",
]

# Ambiguous patterns — need deeper analysis to classify
AMBIGUOUS_BLOCK_PATTERNS = [
    "CLOSED",
    "closed on GitHub",
    "no PR found",
    "PR not found",
]


# Patterns indicating a human decision to defer/skip (NOT agent failure)
HUMAN_DECISION_PATTERNS = [
    "roadmap decision",
    "deferred",
    "low priority",
    "not now",
    "revisit later",
]


@dataclass
class BlockedFlow:
    branch: str
    issue_number: int | None
    flow_status: str
    blocked_by_issue: int | None = None
    blocked_reason: str | None = None
    last_event_type: str | None = None
    last_event_detail: str | None = None
    last_event_time: str | None = None
    block_type: str = "unknown"  # "objective", "non-objective", "dependency", "ambiguous"
    block_evidence: list[str] = field(default_factory=list)
    event_timeline: list[dict[str, Any]] = field(default_factory=list)
    # Screening fields populated by --ready-for-audit
    has_worktree: bool = False
    has_plan_ref: bool = False
    has_report_ref: bool = False
    has_audit_ref: bool = False
    has_pr_ref: bool = False
    evidence_count: int = 0
    is_human_decision: bool = False
    execution_age_days: int | None = None
    # GitHub enrichment (populated by --enrich)
    issue_state: str | None = None  # "OPEN" or "CLOSED"
    has_merged_pr: bool | None = None
    pr_number: int | None = None
    screening_verdict: str = ""  # "ready", "historical", "human_decision", "insufficient_evidence"


def classify_block_reason(reason: str) -> str:
    """Classify a block reason as objective, non-objective, or ambiguous."""
    if not reason:
        return "unknown"

    for pattern in NON_OBJECTIVE_BLOCK_PATTERNS:
        if pattern.lower() in reason.lower():
            return "non-objective"

    for pattern in AMBIGUOUS_BLOCK_PATTERNS:
        if pattern.lower() in reason.lower():
            return "ambiguous"

    for pattern in OBJECTIVE_BLOCK_PATTERNS:
        if pattern.lower() in reason.lower():
            return "objective"

    return "unknown"


def is_human_decision(flow: BlockedFlow) -> bool:
    """Check if flow was blocked by a human decision, not agent failure."""
    all_text = f"{flow.blocked_reason or ''} {flow.last_event_detail or ''}"
    for e in flow.event_timeline:
        all_text += f" {e.get('detail', '')}"
    return any(p.lower() in all_text.lower() for p in HUMAN_DECISION_PATTERNS)


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
            capture_output=True, text=True, check=True, timeout=10,
        )
        data = json.loads(result.stdout)
        return {"state": data.get("state", "UNKNOWN"), "number": data["number"]}
    except Exception:
        return None


def fetch_pr_info(issue_number: int, branch: str) -> dict[str, Any] | None:
    """Check if issue has associated merged PR."""
    try:
        # Search for PRs that reference this issue
        result = subprocess.run(
            ["gh", "pr", "list", "--search", str(issue_number),
             "--json", "number,state,mergedAt,headRefName",
             "--limit", "3"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        prs = json.loads(result.stdout)
        for pr in prs:
            if pr.get("mergedAt"):
                return {"merged": True, "number": pr["number"], "branch": pr.get("headRefName", "")}
        if prs:
            return {"merged": False, "number": prs[0]["number"], "branch": prs[0].get("headRefName", "")}
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


def screen_flow(
    bf: BlockedFlow,
    flow_data: dict[str, Any],
    enrich: bool = False,
    observed_issues: set[int] | None = None,
) -> BlockedFlow:
    """Apply all screening criteria to determine if flow is ready for audit.

    Screening rules (ordered by priority):
    1. Objective block → skip (code/infrastructure, not prompt)
    2. Human decision (roadmap/deferred) → skip
    3. Already observed → skip (existing observation covers this issue)
    4. Insufficient evidence (< 2 sources) → skip
    5. Stale (> 10 days since execution) → skip
    6. All other non-objective/ambiguous/dependency → ready
    """
    # Rule 1: Objective blocks excluded
    if bf.block_type == "objective":
        bf.screening_verdict = "objective"
        return bf

    # Populate evidence fields
    bf.has_worktree = bool(flow_data.get("has_worktree"))
    bf.has_plan_ref = bool(flow_data.get("plan_ref"))
    bf.has_report_ref = bool(flow_data.get("report_ref"))
    bf.has_audit_ref = bool(flow_data.get("audit_ref"))
    bf.has_pr_ref = bool(flow_data.get("pr_ref") or flow_data.get("pr_number"))
    bf.evidence_count = count_evidence_sources(flow_data)
    bf.execution_age_days = compute_execution_age(flow_data)

    # Rule 2: Human decision
    bf.is_human_decision = is_human_decision(bf)
    if bf.is_human_decision:
        bf.screening_verdict = "human_decision"
        return bf

    # Rule 3: Already observed (skip if existing observation covers this issue)
    if observed_issues and bf.issue_number and bf.issue_number in observed_issues:
        bf.screening_verdict = "already_observed"
        return bf

    # Rule 4: Enrich with GitHub data if requested
    if enrich and bf.issue_number:
        issue_info = fetch_github_issue_state(bf.issue_number)
        if issue_info:
            bf.issue_state = issue_info["state"]
            if issue_info["state"] == "CLOSED":
                pr_info = fetch_pr_info(bf.issue_number, bf.branch)
                if pr_info:
                    bf.pr_number = pr_info["number"]
                    bf.has_merged_pr = pr_info["merged"]
                # NOTE: issue CLOSED is NOT a hard filter. Closed issues may still
                # reveal agent failures (e.g., agent didn't deliver, state machine gap).
                # They are ranked lower in priority but remain observable.

    # Rule 5: Evidence check (skip if can't even do basic analysis)
    if bf.evidence_count < 2:
        bf.screening_verdict = "insufficient_evidence"
        return bf

    # Rule 6: Age check (> 10 days → stale)
    if bf.execution_age_days is not None and bf.execution_age_days > 10:
        bf.screening_verdict = "stale"
        return bf

    # Rule 7: Ready for audit (includes CLOSED issues — ranked lower, not excluded)
    if bf.block_type in ("non-objective", "ambiguous", "dependency"):
        bf.screening_verdict = "ready"
    else:
        bf.screening_verdict = "insufficient_evidence"

    return bf


def get_blocked_flows(active_only: bool = False) -> list[BlockedFlow]:
    """Get all blocked/aborted flows from the database."""
    from vibe3.clients.sqlite_client import SQLiteClient

    client = SQLiteClient()

    if active_only:
        flows = client.get_flows_by_status("blocked") + client.get_flows_by_status("aborted")
    else:
        flows = client.get_all_flows()
        flows = [f for f in flows if f.get("flow_status") in ("blocked", "aborted")
                 and f.get("branch") != "main"]  # main branch is a test artifact, not a real flow

    results: list[BlockedFlow] = []
    for flow in flows:
        branch = flow.get("branch", "")
        issue_number = None
        # Extract issue number from various sources
        if flow.get("task_issue_number"):
            issue_number = flow["task_issue_number"]
        elif branch.startswith("task/issue-") or branch.startswith("dev/issue-"):
            try:
                issue_number = int(branch.split("issue-")[1].split("/")[0].split("-")[0])
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
            has_pr_ref=bool(flow.get("pr_ref") or flow.get("pr_number")),
            evidence_count=count_evidence_sources(flow),
            execution_age_days=compute_execution_age(flow),
        )

        # Get events for this flow to understand the block reason
        try:
            events = client.get_events(branch=bf.branch, limit=50)
        except Exception:
            events = []

        bf.event_timeline = events

        # Analyze events to determine block type
        block_events = [
            e for e in events
            if e["event_type"] in ("flow_blocked", "flow_auto_aborted", "blocked")
        ]
        error_events = [
            e for e in events
            if "error" in e["event_type"] or "aborted" in e["event_type"]
        ]
        state_transitions = [
            e for e in events
            if e["event_type"] == "state_transitioned"
        ]
        transition_exceeded = [
            e for e in events
            if e["event_type"] == "transition_count_exceeded"
        ]

        if bf.last_event_time is None and events:
            bf.last_event_time = events[0].get("created_at", "")
            bf.last_event_type = events[0].get("event_type", "")
            bf.last_event_detail = events[0].get("detail", "")

        # Classify based on events
        if transition_exceeded:
            bf.block_type = "non-objective"
            bf.block_evidence.append("transition_count_exceeded: state machine design issue")
            bf.block_evidence.append(
                f"detail: {transition_exceeded[0].get('detail', '')}"
            )

        if not bf.block_type or bf.block_type == "unknown":
            # Check if there are error events
            if error_events and all("error" in et for et in {e["event_type"] for e in error_events}):
                bf.block_type = "objective"
                bf.block_evidence.append(f"error events: {list({e['event_type'] for e in error_events})}")
            elif error_events:
                # Mixed error types - check auto-abort details
                auto_aborts = [e for e in error_events if e["event_type"] == "flow_auto_aborted"]
                if auto_aborts:
                    for e in auto_aborts:
                        detail = e.get("detail", "")
                        classification = classify_block_reason(detail)
                        if classification == "objective":
                            bf.block_type = "objective"
                            bf.block_evidence.append(f"auto-aborted: {detail[:120]}")
                            break
                        elif classification == "ambiguous":
                            bf.block_type = "ambiguous"
                            bf.block_evidence.append(f"auto-aborted (ambiguous): {detail[:120]}")
                            break
                    else:
                        if "codeagent_manager_aborted" in {e["event_type"] for e in error_events}:
                            bf.block_type = "non-objective"
                            bf.block_evidence.append("manager aborted without error events — potential prompt issue")
                        else:
                            bf.block_type = "non-objective"
                            bf.block_evidence.append("auto-aborted without clear objective reason")
                elif "codeagent_manager_aborted" in {e["event_type"] for e in error_events} and not any(
                    "error" in et for et in {e["event_type"] for e in error_events}
                ):
                    bf.block_type = "non-objective"
                    bf.block_evidence.append("manager aborted without error events — potential prompt issue")
                else:
                    bf.block_type = "unknown"
                    bf.block_evidence.append(f"mixed events: {list({e['event_type'] for e in error_events})}")

        # Check block events for reason classification
        if bf.block_type == "unknown":
            for e in block_events:
                detail = e.get("detail", "")
                classification = classify_block_reason(detail)
                if classification != "unknown":
                    bf.block_type = classification
                    bf.block_evidence.append(f"block event: {detail[:120]}")
                    break

        # Check blocked_reason
        if bf.block_type == "unknown":
            classification = classify_block_reason(bf.blocked_reason or "")
            if classification != "unknown":
                bf.block_type = classification
                bf.block_evidence.append(f"blocked_reason: {bf.blocked_reason}")

        # Check for state_transitioned -> blocked without preceding error
        if bf.block_type == "unknown":
            block_transitions = [
                e for e in state_transitions
                if "blocked" in str(e.get("refs", {}).get("after_state", "")).lower()
            ]
            if block_transitions and not error_events:
                bf.block_type = "non-objective"
                bf.block_evidence.append(
                    "transitioned to blocked without preceding error events"
                )
                bf.block_evidence.append(
                    f"transition: {block_transitions[0].get('detail', '')}"
                )

        # Dependency chain: blocked by another issue
        if bf.block_type == "unknown" and bf.blocked_by_issue:
            bf.block_type = "dependency"
            bf.block_evidence.append(f"dependency: blocked by #{bf.blocked_by_issue}")

        results.append(bf)

    return results


def trace_dependency_chain(
    issue_number: int, max_depth: int = 3
) -> list[dict[str, Any]]:
    """Trace a dependency chain to find the root blocker."""
    from vibe3.clients.sqlite_client import SQLiteClient

    client = SQLiteClient()
    chain: list[dict[str, Any]] = []
    visited: set[int] = set()
    current = issue_number

    for _ in range(max_depth):
        if current in visited:
            chain.append({"issue": current, "reason": "circular dependency", "type": "circular"})
            break
        visited.add(current)

        try:
            flows = client.get_flows_by_issue(current, role="task")
        except Exception:
            chain.append({"issue": current, "reason": "flow not found", "type": "unknown"})
            break

        if not flows:
            chain.append({"issue": current, "reason": "no flow data", "type": "unknown"})
            break

        flow = flows[0]
        blocked_by = flow.get("blocked_by_issue")
        blocked_reason = flow.get("blocked_reason", "")
        flow_status = flow.get("flow_status", "")

        classification = classify_block_reason(blocked_reason)

        chain.append({
            "issue": current,
            "status": flow_status,
            "blocked_by": blocked_by,
            "reason": blocked_reason,
            "type": classification,
        })

        if not blocked_by or flow_status not in ("blocked", "aborted"):
            break

        current = blocked_by

    return chain


def resolve_dependency_chain_type(chain: list[dict[str, Any]]) -> str:
    """Resolve the type of a dependency chain."""
    for entry in chain:
        if entry["type"] == "non-objective":
            return "non-objective"
    for entry in chain:
        if entry["type"] == "unknown":
            return "unknown"
    return "objective"


def compute_priority(bf: BlockedFlow) -> str:
    """Compute observation priority based on flow state and issue status.

    Priority is a ranking signal, NOT a filter. All levels are observable;
    higher priority means the issue is more likely to be a live problem.

    - high:   flow is actively blocked + issue is OPEN (blocking execution queue)
    - medium: flow blocked/aborted + issue OPEN (live problem, needs investigation)
    - low:    issue CLOSED (may be historical, but still observable for patterns)
    """
    issue_open = bf.issue_state != "CLOSED"  # None (not checked) treated as potentially open

    if bf.flow_status == "blocked" and bf.has_worktree and issue_open:
        return "high"
    if bf.flow_status in ("blocked", "aborted") and issue_open:
        return "medium"
    return "low"


def print_results(
    flows: list[BlockedFlow],
    format_type: str = "text",
    trace_deps: bool = False,
    ready_for_audit: bool = False,
) -> None:
    """Print results."""
    non_obj = [f for f in flows if f.block_type == "non-objective"]
    objective = [f for f in flows if f.block_type == "objective"]
    dependency = [f for f in flows if f.block_type == "dependency"]
    ambiguous = [f for f in flows if f.block_type == "ambiguous"]
    unknown = [f for f in flows if f.block_type == "unknown"]

    if ready_for_audit:
        ready = [f for f in flows if f.screening_verdict == "ready"]
        historical = [f for f in flows if f.screening_verdict == "historical"]
        human_dec = [f for f in flows if f.screening_verdict == "human_decision"]
        already_observed = [f for f in flows if f.screening_verdict == "already_observed"]
        insufficient = [f for f in flows if f.screening_verdict == "insufficient_evidence"]
        stale = [f for f in flows if f.screening_verdict == "stale"]
        objective_skipped = [f for f in flows if f.screening_verdict == "objective"]

        if format_type == "json":
            output = {
                "summary": {
                    "total_blocked_aborted": len(flows),
                    "ready_for_audit": len(ready),
                    "excluded": {
                        "objective": len(objective_skipped),
                        "human_decision": len(human_dec),
                        "already_observed": len(already_observed),
                        "insufficient_evidence": len(insufficient),
                        "stale": len(stale),
                    },
                },
                "audit_candidates": [
                    {
                        "branch": f.branch,
                        "issue_number": f.issue_number,
                        "flow_status": f.flow_status,
                        "block_type": f.block_type,
                        "block_evidence": f.block_evidence,
                        "evidence_count": f.evidence_count,
                        "has_worktree": f.has_worktree,
                        "execution_age_days": f.execution_age_days,
                        "issue_state": f.issue_state,
                        "has_merged_pr": f.has_merged_pr,
                        "recommended_priority": compute_priority(f),
                    }
                    for f in ready
                ],
            }
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(f"\n{'='*70}")
            print(f"Audit-Ready Flow Candidates (script-screened)")
            print(f"{'='*70}")
            print(f"Total blocked/aborted: {len(flows)}")
            print(f"Ready for audit:     {len(ready)} 🔴")
            print(f"Excluded:")
            print(f"  Objective:         {len(objective_skipped)} (code/infrastructure)")
            print(f"  Human decision:    {len(human_dec)} (roadmap/deferred)")
            print(f"  Already observed:  {len(already_observed)} (existing observation covers this issue)")
            print(f"  Insufficient data: {len(insufficient)} (< 2 evidence sources)")
            print(f"  Stale:             {len(stale)} (> 10 days since execution)")

            if ready:
                print(f"\n{'─'*70}")
                print(f"🔴 Audit Candidates — {len(ready)} flows ready for observation")
                print(f"{'─'*70}")
                # Sort: HIGH first, then MEDIUM, then LOW
                priority_order = {"high": 0, "medium": 1, "low": 2}
                ready_sorted = sorted(ready, key=lambda f: priority_order.get(compute_priority(f), 99))
                for f in ready_sorted:
                    priority = compute_priority(f)
                    print(f"\n  [{priority.upper()}] {f.branch}")
                    print(f"  Issue:        #{f.issue_number}", end="")
                    if f.issue_state:
                        print(f" ({f.issue_state})", end="")
                        if f.has_merged_pr:
                            print(" [merged PR]", end="")
                    print()
                    print(f"  Status:       {f.flow_status} | Type: {f.block_type}")
                    print(f"  Evidence:     {f.evidence_count} sources", end="")
                    sources = []
                    if f.has_worktree: sources.append("worktree")
                    if f.has_plan_ref: sources.append("plan")
                    if f.has_report_ref: sources.append("report")
                    if f.has_audit_ref: sources.append("audit")
                    if f.has_pr_ref: sources.append("pr")
                    if sources: print(f" ({', '.join(sources)})", end="")
                    print()
                    if f.execution_age_days is not None:
                        print(f"  Age:          {f.execution_age_days} days since execution")
                    for ev in f.block_evidence[:2]:
                        print(f"  Evidence:     {ev[:100]}")
            else:
                print(f"\n  No flows meet all screening criteria.")
                print(f"  Consider using --enrich to check GitHub for issue state.")

        return

    # Original full output mode
    if format_type == "json":
        output = {
            "summary": {
                "total_blocked_aborted": len(flows),
                "non_objective": len(non_obj),
                "objective": len(objective),
                "dependency": len(dependency),
                "ambiguous": len(ambiguous),
                "unknown": len(unknown),
            },
            "non_objective_flows": [
                {
                    "branch": f.branch,
                    "issue_number": f.issue_number,
                    "flow_status": f.flow_status,
                    "block_type": f.block_type,
                    "evidence": f.block_evidence,
                    "last_event": f.last_event_detail,
                    "last_event_time": f.last_event_time,
                }
                for f in non_obj
            ],
            "dependency_flows": [],
            "objective_flows": [
                {
                    "branch": f.branch,
                    "issue_number": f.issue_number,
                    "flow_status": f.flow_status,
                    "block_type": f.block_type,
                    "evidence": f.block_evidence,
                }
                for f in objective
            ],
            "unknown_flows": [
                {
                    "branch": f.branch,
                    "issue_number": f.issue_number,
                    "flow_status": f.flow_status,
                    "block_type": f.block_type,
                    "evidence": f.block_evidence,
                }
                for f in unknown
            ],
        }

        if trace_deps:
            for f in dependency:
                chain = trace_dependency_chain(f.issue_number or 0)
                chain_type = resolve_dependency_chain_type(chain)
                output["dependency_flows"].append({
                    "branch": f.branch,
                    "issue_number": f.issue_number,
                    "chain": chain,
                    "resolved_type": chain_type,
                })

        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*70}")
        print(f"Blocked/Aborted Flow Analysis")
        print(f"{'='*70}")
        print(f"Total: {len(flows)} | Non-objective: {len(non_obj)} | Objective: {len(objective)} | Dependency: {len(dependency)} | Ambiguous: {len(ambiguous)} | Unknown: {len(unknown)}")

        if non_obj:
            print(f"\n{'─'*70}")
            print(f"🔴 Non-Objective Blocks (candidates for audit observation) — {len(non_obj)} flows")
            print(f"{'─'*70}")
            for f in non_obj:
                print(f"\n  Branch:      {f.branch}")
                print(f"  Issue:       #{f.issue_number}")
                print(f"  Status:      {f.flow_status}")
                print(f"  Block type:  {f.block_type}")
                for ev in f.block_evidence:
                    print(f"  Evidence:    {ev[:120]}")
                if f.last_event_detail:
                    print(f"  Last event:  {f.last_event_detail[:120]}")

        if ambiguous:
            print(f"\n{'─'*70}")
            print(f"🟠 Ambiguous Blocks (need human review) — {len(ambiguous)} flows")
            print(f"{'─'*70}")
            for f in ambiguous:
                print(f"  {f.branch:35s} #{str(f.issue_number):6s} {f.block_evidence[0][:80] if f.block_evidence else ''}")

        if dependency and trace_deps:
            print(f"\n{'─'*70}")
            print(f"🟡 Dependency Chains — {len(dependency)} flows")
            print(f"{'─'*70}")
            for f in dependency:
                chain = trace_dependency_chain(f.issue_number or 0)
                chain_type = resolve_dependency_chain_type(chain)
                print(f"\n  Branch:        {f.branch}")
                print(f"  Issue:         #{f.issue_number}")
                print(f"  Chain type:    {chain_type}")
                for entry in chain:
                    print(f"    → #{entry['issue']}: {entry['type']} ({str(entry.get('reason',''))[:60]})")

        if objective:
            print(f"\n{'─'*70}")
            print(f"🟢 Objective Blocks (excluded from audit) — {len(objective)} flows")
            print(f"{'─'*70}")
            for f in objective:
                print(f"  {f.branch:35s} #{str(f.issue_number):6s} {f.block_evidence[0][:60] if f.block_evidence else ''}")


def show_flow_events(branch: str) -> None:
    """Show detailed event timeline for a specific flow."""
    from vibe3.clients.sqlite_client import SQLiteClient

    client = SQLiteClient()
    events = client.get_events(branch=branch, limit=100)

    if not events:
        print(f"No events found for branch: {branch}")
        return

    print(f"\nEvent timeline for {branch}")
    print(f"{'─'*70}")
    print(f"{'Time':22s} {'Event Type':35s} Detail")
    print(f"{'─'*70}")

    for e in events:
        ts = e.get("created_at", "")[:19].replace("T", " ")
        event_type = e["event_type"]
        detail = (e.get("detail") or "")[:100]
        marker = ""
        if "error" in event_type:
            marker = " 🔴"
        elif "blocked" in event_type or "aborted" in event_type:
            marker = " 🟡"
        elif "state_transitioned" in event_type:
            marker = " 🔵"
        print(f"{ts:22s} {event_type:35s}{marker} {detail}")

    # Summarize classification
    block_events = [e for e in events if "block" in e["event_type"].lower() or "abort" in e["event_type"].lower()]
    error_events = [e for e in events if "error" in e["event_type"]]

    print(f"\n{'─'*70}")
    print(f"Summary: {len(events)} events, {len(block_events)} block/abort events, {len(error_events)} error events")

    if block_events and not error_events:
        print("🔴 Block/abort WITHOUT error events → potential non-objective block")
        for be in block_events:
            print(f"   {be.get('detail', '')[:120]}")
    elif error_events:
        print("🟢 Block/abort WITH error events → likely objective block")
        for ee in error_events:
            print(f"   [{ee['event_type']}] {ee.get('detail', '')[:120]}")


def git_common_dir() -> Path:
    """Resolve the git common directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            check=True, text=True, capture_output=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path(".git")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Identify non-objective blocked flows for audit observation"
    )
    parser.add_argument(
        "--ready-for-audit",
        action="store_true",
        help="Apply all screening criteria: exclude objective/historical/human-decision/stale/insufficient-evidence flows",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Fetch GitHub issue state and PR merge status (requires gh CLI and network)",
    )
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Show only currently blocked/aborted flows",
    )
    parser.add_argument(
        "--trace-deps",
        action="store_true",
        help="Trace dependency chains to classify dependency-type blocks",
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
        from vibe3.clients.sqlite_client import SQLiteClient

        client = SQLiteClient()
        all_flows = client.get_all_flows()
        flow_data_map: dict[str, dict] = {}
        for f in all_flows:
            flow_data_map[f.get("branch", "")] = f

        # Load existing observation issues for dedup
        observed_issues = load_existing_observation_issues(
            git_common_dir() / "shared"
        )

        for bf in flows:
            fdata = flow_data_map.get(bf.branch, {})
            screen_flow(bf, fdata, enrich=args.enrich, observed_issues=observed_issues)

        print_results(flows, format_type=args.format, trace_deps=args.trace_deps, ready_for_audit=True)
    else:
        print_results(flows, format_type=args.format, trace_deps=args.trace_deps)


if __name__ == "__main__":
    main()