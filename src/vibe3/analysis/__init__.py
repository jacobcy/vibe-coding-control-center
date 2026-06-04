"""Vibe3 analysis layer — public interface.

This module provides a unified public API for the analysis layer, including:
- Symbol-level analysis (SerenaService)
- Change analysis pipeline (build_change_analysis)
- DAG impact analysis (ImpactGraph, expand_impacted_modules)
- Change scope classification (classify_changed_files, is_test_file)
- PR scoring (PRDimensions, RiskLevel, calculate_risk_score, generate_score_report)
- Output adapters (as_list, as_mapping, score, impact, dag)
- Snapshot diff (compute_diff)
"""

# Core services
# Change scope classification
from vibe3.analysis.change_scope_service import (
    ChangedFileScope,
    classify_changed_files,
    collect_changed_symbols,
    count_changed_lines,
    is_test_file,
)

# DAG impact analysis
from vibe3.analysis.dag_service import (
    ImpactGraph,
    ModuleNode,
    build_module_graph,
    expand_impacted_modules,
)

# Output adapters
from vibe3.analysis.inspect_output_adapter import (
    as_list,
    as_mapping,
    dag,
    impact,
    pr_analysis_summary,
    score,
)
from vibe3.analysis.inspect_query_service import build_change_analysis
from vibe3.analysis.pr_scoring import (
    PRDimensions,
    RiskLevel,
    calculate_risk_score,
    determine_risk_level,
    generate_score_report,
)
from vibe3.analysis.serena_service import SerenaService

# Snapshot diff
from vibe3.analysis.snapshot_diff import compute_diff

# Snapshot diff section
from vibe3.analysis.snapshot_diff_section import build_snapshot_diff_section

# Snapshot service
from vibe3.analysis.snapshot_service import (
    SnapshotError,
    build_snapshot,
    find_snapshot_by_branch,
)

__all__ = [
    # Core services
    "SerenaService",
    "build_change_analysis",
    # DAG impact analysis
    "ImpactGraph",
    "ModuleNode",
    "expand_impacted_modules",
    "build_module_graph",
    # Change scope classification
    "ChangedFileScope",
    "classify_changed_files",
    "count_changed_lines",
    "collect_changed_symbols",
    "is_test_file",
    # PR scoring
    "PRDimensions",
    "RiskLevel",
    "calculate_risk_score",
    "determine_risk_level",
    "generate_score_report",
    # Output adapters
    "as_list",
    "as_mapping",
    "score",
    "impact",
    "dag",
    "pr_analysis_summary",
    # Snapshot diff
    "compute_diff",
    "SnapshotError",
    "build_snapshot",
    "find_snapshot_by_branch",
    "build_snapshot_diff_section",
]
