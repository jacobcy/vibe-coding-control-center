"""Utility functions for governance role."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vibe3.clients import GitHubClient
from vibe3.config import get_manager_usernames
from vibe3.models import OrchestraConfig
from vibe3.services.orchestra import (
    IssueStatusEntry,
    format_issue_runtime_line,
    format_issue_summary_line,
    is_running_issue,
)
from vibe3.services.shared import (
    ORCHESTRA_GOVERNED_LABEL,
    has_orchestra_governed,
    has_roadmap_label,
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
    from vibe3.config import get_source_root

    root = repo_root or Path(".").resolve()
    src_root = root / get_source_root()
    candidates = sorted(p for p in src_root.rglob("*.py") if p.name != "__init__.py")
    if not candidates:
        return src_root / "cli.py"
    return candidates[tick_count % len(candidates)]


def resolve_test_path(module_path: Path, repo_root: Path | None = None) -> Path:
    """Resolve the test directory for a given module path.

    Maps src/vibe3/{subdir}/foo.py -> tests/vibe3/{subdir}/
    so the agent knows where to look for corresponding tests.
    """
    from vibe3.config import get_source_root

    root = repo_root or Path(".").resolve()
    src_vibe3 = root / get_source_root()
    try:
        rel = module_path.relative_to(src_vibe3)
    except ValueError:
        try:
            rel = module_path.relative_to(get_source_root())
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


def build_audit_observation_context(snapshot: Any) -> dict[str, Any]:
    """Build context for audit-observation material.

    The material owns the actual evidence collection through stable CLI
    commands. This context only orients the agent to the current runtime size.
    """
    return build_issue_context(
        (),
        server_running=snapshot.server_running,
        active_flows=snapshot.active_flows,
        active_worktrees=snapshot.active_worktrees,
        queued_issues=snapshot.queued_issues,
        circuit_breaker_state=snapshot.circuit_breaker_state,
        circuit_breaker_failures=snapshot.circuit_breaker_failures,
        issue_scope_name="blocked/aborted flow observation",
        scope_note=(
            "本材料不从 prompt 预置候选列表。请按材料中的稳定命令读取 "
            "`flow status --all --format json` 和 "
            "`task status --all --format json`，选择最近最多 3 个 "
            "blocked/aborted/failed flow，输出 observation 并写入 "
            "`governance` handoff 链。"
        ),
    )


def build_audit_suggestion_context(snapshot: Any) -> dict[str, Any]:
    """Build context for audit-suggestion material.

    Reads observation ledger from shared directory and provides aggregate
    statistics for the auditor to determine if there are enough observations
    to form a cluster worth analyzing.

    The context does NOT read full observation content - the agent reads
    selected ones via tools per the material's instructions.
    """
    # Get shared observations directory path (cross-worktree shared location)
    from vibe3.utils import get_git_common_dir

    try:
        git_common_dir = get_git_common_dir()
        observations_dir = Path(git_common_dir) / "shared" / "observations"
    except Exception:
        # Fallback: use relative path from current working tree
        observations_dir = Path(".git/shared/observations")

    # Count observation files
    observation_count = 0
    observed_failure_modes: set[str] = set()

    if observations_dir.exists():
        # Read observation files (up to 20 for context stats)
        observation_files = sorted(observations_dir.glob("audit-observation-*.yaml"))
        observation_count = len(observation_files)

        # Quick parse to extract failure modes (don't read full content)
        for obs_file in observation_files[:20]:
            try:
                content = obs_file.read_text()
                # Extract failure mode from YAML (simple pattern match)
                if "observed_failure_mode:" in content:
                    for line in content.split("\n"):
                        if "observed_failure_mode:" in line:
                            mode = line.split(":", 1)[1].strip().strip('"').strip("'")
                            if mode:
                                observed_failure_modes.add(mode)
                            break
            except Exception:
                continue

    result = build_issue_context(
        (),
        server_running=snapshot.server_running,
        active_flows=snapshot.active_flows,
        active_worktrees=snapshot.active_worktrees,
        queued_issues=snapshot.queued_issues,
        circuit_breaker_state=snapshot.circuit_breaker_state,
        circuit_breaker_failures=snapshot.circuit_breaker_failures,
        issue_scope_name="observation cluster analysis",
        scope_note=(
            f"观察记录统计：\n"
            f"- 可用观察记录数：{observation_count}\n"
            f"- 检测到的失败模式："
            f"{', '.join(sorted(observed_failure_modes)) or '无'}\n\n"
            "请使用 Read 工具读取 `.git/shared/observations/"
            "audit-observation-*.yaml` 文件，"
            "按材料中的聚类规则分析，达到最小重复度"
            "（2+ 同类观察）才生成建议。"
            f"{'目前无观察记录，跳过本轮。' if observation_count == 0 else ''}"
        ),
    )

    # Add observation-specific fields for programmatic access
    result["observation_count"] = observation_count
    result["new_since_last_run"] = observation_count  # Simplified: assume all are new
    result["observed_failure_modes"] = sorted(observed_failure_modes)

    return result


def build_audit_report_context(snapshot: Any) -> dict[str, Any]:
    """Build context for audit-report material.

    Reads observation and suggestion ledgers from shared directories and
    provides aggregate statistics for the reporter. The material owns the
    actual analysis through audit-ledger-summary.py.
    """
    from vibe3.utils import get_git_common_dir

    try:
        git_common_dir = get_git_common_dir()
        shared_dir = Path(git_common_dir) / "shared"
    except Exception:
        shared_dir = Path(".git/shared")

    observations_dir = shared_dir / "observations"
    suggestions_dir = shared_dir / "suggestions"

    observation_count = 0
    suggestion_count = 0
    observed_failure_modes: set[str] = set()

    if observations_dir.exists():
        obs_files = sorted(observations_dir.glob("audit-observation-*.yaml"))
        observation_count = len(obs_files)
        for obs_file in obs_files[:20]:
            try:
                content = obs_file.read_text()
                if "observed_failure_mode:" in content:
                    for line in content.split("\n"):
                        if "observed_failure_mode:" in line:
                            mode = line.split(":", 1)[1].strip().strip('"').strip("'")
                            if mode:
                                observed_failure_modes.add(mode)
                            break
            except Exception:
                continue

    if suggestions_dir.exists():
        sug_files = sorted(suggestions_dir.glob("audit-suggestion-*.yaml"))
        suggestion_count = len(sug_files)

    result = build_issue_context(
        (),
        server_running=snapshot.server_running,
        active_flows=snapshot.active_flows,
        active_worktrees=snapshot.active_worktrees,
        queued_issues=snapshot.queued_issues,
        circuit_breaker_state=snapshot.circuit_breaker_state,
        circuit_breaker_failures=snapshot.circuit_breaker_failures,
        issue_scope_name="root-cause report generation",
        scope_note=(
            f"审计报告上下文：\n"
            f"- 可用观察记录：{observation_count}\n"
            f"- 可用建议记录：{suggestion_count}\n"
            f"- 检测到的失败模式："
            f"{', '.join(sorted(observed_failure_modes)) or '无'}\n\n"
            "请运行 `uv run python scripts/audit-ledger-summary.py` "
            "获取机械摘要，然后深度读取满足条件的 cluster "
            "（2+ observation 或有明确 suggestion 引用），"
            "生成 root-cause 报告并写入 `.git/shared/reports/`。"
            f"{'目前无观察/建议记录，跳过本轮。' if observation_count == 0 else ''}"
        ),
    )

    result["observation_count"] = observation_count
    result["suggestion_count"] = suggestion_count
    result["observed_failure_modes"] = sorted(observed_failure_modes)

    return result


def build_audit_decision_context(snapshot: Any) -> dict[str, Any]:
    """Build context for audit-decision material.

    Reads report ledger from shared directory and provides aggregate
    statistics for the decision-maker to evaluate reports and create
    the appropriate follow-up issues.

    The decision agent creates GitHub issues (not YAML files) so the
    downstream governance pipeline handles execution naturally:
    supervisor fixes go through roadmap-intake → supervisor/apply,
    while code/script fixes go through roadmap-intake → assignee-pool.

    The context does NOT read full report content - the agent reads
    selected ones via tools per the material's instructions.
    """
    from vibe3.utils import get_git_common_dir

    try:
        git_common_dir = get_git_common_dir()
        reports_dir = Path(git_common_dir) / "shared" / "reports"
    except Exception:
        reports_dir = Path(".git/shared/reports")

    report_count = 0
    evidence_strengths: set[str] = set()

    if reports_dir.exists():
        report_files = sorted(reports_dir.glob("audit-report-*.md"))
        report_count = len(report_files)

        for report_file in report_files[:5]:
            try:
                content = report_file.read_text()
                if "evidence strength:" in content.lower():
                    for line in content.split("\n"):
                        if "evidence strength:" in line.lower():
                            strength = (
                                line.split(":", 1)[1].strip().strip('"').strip("'")
                            )
                            if strength in ["strong", "medium", "weak", "inconclusive"]:
                                evidence_strengths.add(strength)
                            break
            except Exception:
                continue

    result = build_issue_context(
        (),
        server_running=snapshot.server_running,
        active_flows=snapshot.active_flows,
        active_worktrees=snapshot.active_worktrees,
        queued_issues=snapshot.queued_issues,
        circuit_breaker_state=snapshot.circuit_breaker_state,
        circuit_breaker_failures=snapshot.circuit_breaker_failures,
        issue_scope_name="decision packet analysis",
        scope_note=(
            f"决策包统计：\n"
            f"- 可用报告数：{report_count}\n"
            f"- 检测到的证据强度："
            f"{', '.join(sorted(evidence_strengths)) or '无'}\n\n"
            "请读取 `.git/shared/reports/audit-report-*.md`，"
            "按材料中的证据规则、按材料中的路由规则，为每个 decision packet "
            "创建对应的 follow-up issue（不是 YAML 文件）。\n"
            "prompt/test/config 的简单修复走 supervisor 快速通道；"
            "涉及 `src/vibe3/*` 或 `scripts/*` 的修复走常规 issue，"
            "等待 roadmap-intake / assignee-pool 接手。"
            f"{'目前无报告，跳过本轮。' if report_count == 0 else ''}"
        ),
    )

    result["report_count"] = report_count
    result["new_since_last_run"] = report_count
    result["evidence_strengths"] = sorted(evidence_strengths)

    return result


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
