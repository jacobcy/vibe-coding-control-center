"""Utility functions for governance role."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vibe3.clients import GitHubClient
from vibe3.models import OrchestraConfig
from vibe3.services import (
    ORCHESTRA_GOVERNED_LABEL,
    IssueStatusEntry,
    format_issue_runtime_line,
    format_issue_summary_line,
    get_manager_usernames,
    has_orchestra_governed,
    has_roadmap_label,
    is_running_issue,
    normalize_assignees,
    normalize_labels,
)


def build_issue_context(
    active_entries: tuple[Any, ...],
    *,
    server_running: bool,
    active_flows: int,
    active_worktrees: int,
    queued_issues: tuple[int, ...],
    circuit_breaker_state: str,
    circuit_breaker_failures: int,
    issue_scope_name: str,
    scope_note: str,
) -> dict[str, Any]:
    """Build issue context dictionary for governance prompts."""
    active_count = len(active_entries)
    running_entries = tuple(
        entry for entry in active_entries if is_running_issue(entry)
    )
    suggested_entries = tuple(
        entry for entry in active_entries if not is_running_issue(entry)
    )
    issue_list = (
        "\n".join(format_issue_summary_line(entry) for entry in active_entries[:20])
        or "(无活跃 issue)"
    )
    running_issue_details = (
        "\n".join(format_issue_runtime_line(entry) for entry in running_entries[:20])
        or "(无 running issues)"
    )
    suggested_issue_details = (
        "\n".join(format_issue_runtime_line(entry) for entry in suggested_entries[:20])
        or "(无建议 issue)"
    )
    truncated_note = (
        f"\n(已截断，仅显示前 20 条 / 共 {active_count} 条活跃 issue)"
        if active_count > 20
        else ""
    )
    return {
        "issue_scope_name": issue_scope_name,
        "scope_note": scope_note,
        "server_status": "running" if server_running else "stopped",
        "active_count": active_count,
        "active_flows": active_flows,
        "active_worktrees": active_worktrees,
        "running_issue_count": len(running_entries),
        "queued_issue_count": len(queued_issues),
        "suggested_issue_count": len(suggested_entries),
        "circuit_breaker_state": circuit_breaker_state,
        "circuit_breaker_failures": circuit_breaker_failures,
        "issue_list": issue_list,
        "running_issue_details": running_issue_details,
        "suggested_issue_details": suggested_issue_details,
        "truncated_note": truncated_note,
    }


def is_doc_candidate(title: str, body: str, labels: list[str]) -> bool:
    """Check if an issue is a documentation candidate."""
    if any(label in {"type/docs", "scope/documentation"} for label in labels):
        return True
    normalized_title = title.lower()
    keywords = ("doc", "docs", "documentation", "readme", "文档", "说明")
    return any(keyword in normalized_title for keyword in keywords)


def build_broader_repo_entries(
    config: OrchestraConfig,
    *,
    current_material: str,
    github: GitHubClient | None = None,
) -> tuple[Any, ...]:
    """Build issue entries from broader repo for governance scan."""
    github = github or GitHubClient()
    raw_issues = github.list_issues(
        limit=100,
        state="open",
        assignee=None,
        repo=config.repo,
    )
    material_name = Path(current_material).name
    entries: list[Any] = []
    for item in raw_issues:
        number = item.get("number")
        title = item.get("title")
        if not isinstance(number, int) or not isinstance(title, str):
            continue

        labels = normalize_labels(item.get("labels"))
        # Three-layer governance filter + legacy compat. Roadmap intake must not
        # trust stale orchestra-governed labels on unassigned issues; it owns the
        # broader unassigned pool and should re-evaluate those candidates.
        #
        # Note: orchestra-scanned is roadmap-intake's mechanism to mark
        # "not for intake". Assignee-pool should NOT filter by
        # orchestra-scanned because:
        # 1. orchestra-scanned is only meaningful for roadmap-intake
        # 2. Issues can have both assignee and orchestra-scanned (when
        #    roadmap-intake skipped but later got assignee via vibe-roadmap
        #    dependency resolution)
        # 3. Assignee-pool's job is to process assigned issues, only checking
        #    orchestra-governed to avoid re-scanning already decided issues.
        if material_name == "roadmap-intake.md":
            if (
                "supervisor" in labels
                or "orchestra-scanned" in labels
                or has_roadmap_label(labels)
                or "orchestra" in labels
            ):
                continue
        elif (
            "supervisor" in labels
            or has_orchestra_governed(labels)
            or "orchestra" in labels
        ):
            continue

        assignees = normalize_assignees(item.get("assignees"))
        is_assignee_issue = any(
            assignee in get_manager_usernames(config) for assignee in assignees
        )

        if material_name == "roadmap-intake.md" and is_assignee_issue:
            continue

        body = str(item.get("body") or "")
        if material_name == "cron-supervisor.md":
            if is_assignee_issue or not is_doc_candidate(title, body, labels):
                continue

        issue = IssueStatusEntry(
            number=number,
            title=title,
            state=None,
            assignee=assignees[0] if assignees else None,
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
            blocked_by=(),
        )
        entries.append(issue)
    return tuple(entries)


def get_governed_issue_numbers(
    github: GitHubClient, config: OrchestraConfig
) -> set[int]:
    """Fetch issue numbers that have the orchestra-governed label.

    The orchestra-governed label marks issues that have been decided by the
    assignee-pool layer and should be skipped in future pool scans.

    Args:
        github: GitHubClient instance for API calls
        config: OrchestraConfig with repo information

    Returns:
        Set of issue numbers that have orchestra-governed label
    """
    governed_issues = github.list_issues(
        label=ORCHESTRA_GOVERNED_LABEL,
        state="open",
        repo=config.repo,
        limit=5000,  # Fetch all governed issues to avoid truncation
    )
    numbers: set[int] = set()
    for item in governed_issues:
        number = item.get("number")
        if isinstance(number, int):
            numbers.add(number)
    return numbers


def select_audit_module(tick_count: int, repo_root: Path | None = None) -> Path:
    """Select a module from src/vibe3/ for audit using tick-based rotation.

    Excludes __init__.py files.
    Returns a deterministic but rotating selection based on tick_count.
    """
    root = repo_root or Path(".").resolve()
    src_root = root / "src" / "vibe3"
    candidates = sorted(p for p in src_root.rglob("*.py") if p.name != "__init__.py")
    if not candidates:
        return src_root / "cli.py"
    return candidates[tick_count % len(candidates)]


def resolve_test_path(module_path: Path, repo_root: Path | None = None) -> Path:
    """Resolve the test directory for a given module path.

    Maps src/vibe3/{subdir}/foo.py -> tests/vibe3/{subdir}/
    so the agent knows where to look for corresponding tests.
    """
    root = repo_root or Path(".").resolve()
    src_vibe3 = root / "src" / "vibe3"
    try:
        rel = module_path.relative_to(src_vibe3)
    except ValueError:
        try:
            rel = module_path.relative_to("src/vibe3")
        except ValueError:
            return root / "tests" / "vibe3"
    return root / "tests" / "vibe3" / rel.parent


def build_code_auditor_context(
    snapshot: Any,
    *,
    tick_count: int = 0,
) -> dict[str, Any]:
    """Build governance context for code-auditor material.

    Selects a module via tick-based rotation and returns a minimal context
    containing only the module and test paths — the agent reads the code
    itself using its own tools (Read/Grep), avoiding prompt bloat.
    """
    module_path = select_audit_module(tick_count)
    test_path = resolve_test_path(module_path)
    return build_issue_context(
        (),
        server_running=snapshot.server_running,
        active_flows=snapshot.active_flows,
        active_worktrees=snapshot.active_worktrees,
        queued_issues=snapshot.queued_issues,
        circuit_breaker_state=snapshot.circuit_breaker_state,
        circuit_breaker_failures=snapshot.circuit_breaker_failures,
        issue_scope_name="代码质量审计",
        scope_note=(
            f"## 本次审计目标\n"
            f"- 模块路径：`{module_path}`\n"
            f"- 对应测试目录：`{test_path}`\n\n"
            "请使用 Read、Grep 等工具检查该模块，寻找代码质量反模式。"
        ),
    )


def normalize_material_name(material_name: str) -> str:
    """Normalize material name to canonical form for comparison.

    Converts various input formats to canonical form:
    - "roadmap-intake" → "roadmap-intake"
    - "roadmap-intake.md" → "roadmap-intake"
    - "supervisor/governance/roadmap-intake" → "roadmap-intake"
    - "supervisor/governance/roadmap-intake.md" → "roadmap-intake"
    """
    path = Path(material_name)
    # Get the filename without directory
    stem = path.stem if path.suffix == ".md" else path.name
    # If stem still has .md suffix, remove it
    if stem.endswith(".md"):
        stem = stem[:-3]
    return stem


def find_material_in_catalog(
    catalog: tuple[Any, ...], material_override: str
) -> Any | None:
    """Find material in catalog using flexible matching.

    Attempts multiple matching strategies:
    1. Exact name match (for advanced users who provide full path)
    2. Normalized match (handles partial names, missing suffixes, etc.)
    """
    # Strategy 1: Exact match
    for material in catalog:
        if material.name == material_override:
            return material

    # Strategy 2: Normalized match
    normalized_target = normalize_material_name(material_override)
    for material in catalog:
        normalized_catalog_name = normalize_material_name(material.name)
        if normalized_catalog_name == normalized_target:
            return material

    return None
