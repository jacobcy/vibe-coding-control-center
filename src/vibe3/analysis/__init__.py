"""Vibe3 analysis layer — public interface.

This module provides a unified public API for the analysis layer, including:
- Symbol-level analysis (SerenaService)
- Change analysis pipeline (build_change_analysis)
- DAG impact analysis (ImpactGraph, expand_impacted_modules)
- Change scope classification (classify_changed_files, is_test_file)
- PR scoring (PRDimensions, RiskLevel, calculate_risk_score, generate_score_report)
- Output adapters (as_list, as_mapping, score, impact, dag)
- Git-based diff summary (get_git_diff_summary)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Core services
    # Change scope classification
    from vibe3.analysis.change_scope_service import (
        ChangedFileScope,
        classify_changed_files,
        collect_changed_symbols,
        count_changed_lines,
        is_test_file,
    )
    from vibe3.analysis.coverage_service import CoverageService

    # DAG impact analysis
    from vibe3.analysis.dag_service import (
        ImpactGraph,
        ModuleNode,
        build_module_graph,
        expand_impacted_modules,
    )
    from vibe3.analysis.git_diff_summary import get_git_diff_summary

    # Output adapters
    from vibe3.analysis.inspect_output_adapter import (
        as_list,
        as_mapping,
        changed_symbols,
        dag,
        impact,
        pr_analysis_summary,
        score,
    )
    from vibe3.analysis.inspect_query_service import build_change_analysis
    from vibe3.analysis.local_review_report import (
        LocalReviewReport,
        find_latest_prepush_report,
    )
    from vibe3.analysis.pr_scoring import (
        PRDimensions,
        PRScoringError,
        RiskLevel,
        RiskScore,
        calculate_risk_score,
        determine_risk_level,
        generate_score_report,
    )
    from vibe3.analysis.review_kernel import (
        ReviewKernelConfigError,
        ReviewKernelEntry,
        ReviewKernelManifest,
        classify_review_kernel,
        load_review_kernel,
    )
    from vibe3.analysis.serena_service import SerenaService

# Lazy imports
_LAZY_IMPORTS = {
    "SerenaService": "vibe3.analysis.serena_service",
    "build_change_analysis": "vibe3.analysis.inspect_query_service",
    "command_analyzer": "vibe3.analysis.command_analyzer",
    "CoverageService": "vibe3.analysis.coverage_service",
    "ImpactGraph": "vibe3.analysis.dag_service",
    "ModuleNode": "vibe3.analysis.dag_service",
    "dag_service": "vibe3.analysis.dag_service",
    "expand_impacted_modules": "vibe3.analysis.dag_service",
    "build_module_graph": "vibe3.analysis.dag_service",
    "ChangedFileScope": "vibe3.analysis.change_scope_service",
    "classify_changed_files": "vibe3.analysis.change_scope_service",
    "count_changed_lines": "vibe3.analysis.change_scope_service",
    "collect_changed_symbols": "vibe3.analysis.change_scope_service",
    "is_test_file": "vibe3.analysis.change_scope_service",
    "PRDimensions": "vibe3.analysis.pr_scoring",
    "PRScoringError": "vibe3.analysis.pr_scoring",
    "RiskLevel": "vibe3.analysis.pr_scoring",
    "RiskScore": "vibe3.analysis.pr_scoring",
    "calculate_risk_score": "vibe3.analysis.pr_scoring",
    "determine_risk_level": "vibe3.analysis.pr_scoring",
    "generate_score_report": "vibe3.analysis.pr_scoring",
    "ReviewKernelConfigError": "vibe3.analysis.review_kernel",
    "ReviewKernelEntry": "vibe3.analysis.review_kernel",
    "ReviewKernelManifest": "vibe3.analysis.review_kernel",
    "classify_review_kernel": "vibe3.analysis.review_kernel",
    "load_review_kernel": "vibe3.analysis.review_kernel",
    "as_list": "vibe3.analysis.inspect_output_adapter",
    "as_mapping": "vibe3.analysis.inspect_output_adapter",
    "changed_symbols": "vibe3.analysis.inspect_output_adapter",
    "score": "vibe3.analysis.inspect_output_adapter",
    "impact": "vibe3.analysis.inspect_output_adapter",
    "dag": "vibe3.analysis.inspect_output_adapter",
    "pr_analysis_summary": "vibe3.analysis.inspect_output_adapter",
    "get_git_diff_summary": "vibe3.analysis.git_diff_summary",
    "find_latest_prepush_report": "vibe3.analysis.local_review_report",
    "LocalReviewReport": "vibe3.analysis.local_review_report",
    "structure_service": "vibe3.analysis.structure_service",
}


def __getattr__(name: str) -> object:
    """Lazy import for analysis symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        if name == module.__name__.rsplit(".", 1)[-1]:
            return module
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core services
    "SerenaService",
    "build_change_analysis",
    "command_analyzer",
    "CoverageService",
    # DAG impact analysis
    "ImpactGraph",
    "ModuleNode",
    "dag_service",
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
    "PRScoringError",
    "RiskLevel",
    "RiskScore",
    "calculate_risk_score",
    "determine_risk_level",
    "generate_score_report",
    "ReviewKernelConfigError",
    "ReviewKernelEntry",
    "ReviewKernelManifest",
    "classify_review_kernel",
    "load_review_kernel",
    # Output adapters
    "as_list",
    "as_mapping",
    "changed_symbols",
    "score",
    "impact",
    "dag",
    "pr_analysis_summary",
    # Git-based diff summary
    "get_git_diff_summary",
    "find_latest_prepush_report",
    "LocalReviewReport",
    "structure_service",
]
