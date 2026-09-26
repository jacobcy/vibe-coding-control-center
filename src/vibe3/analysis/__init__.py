"""Public analysis APIs that expose direct, validated evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.analysis.change_scope_service import (
        ChangedFileScope,
        classify_changed_files,
        count_changed_lines,
        is_test_file,
    )
    from vibe3.analysis.coverage_service import CoverageService
    from vibe3.analysis.local_review_report import (
        LocalReviewReport,
        find_latest_prepush_report,
    )
    from vibe3.analysis.python_file_inspector import inspect_python_file
    from vibe3.analysis.review_kernel import (
        ReviewKernelConfigError,
        ReviewKernelEntry,
        ReviewKernelManifest,
        classify_review_kernel,
        load_review_kernel,
    )
    from vibe3.analysis.review_observation import (
        build_committed_summary,
        build_review_observation,
    )
    from vibe3.analysis.symbol_reference_service import (
        ProviderSymbol,
        SerenaSymbolReferenceProvider,
        SymbolInspectionResult,
        SymbolReferenceProvider,
        inspect_symbol,
    )

_LAZY_IMPORTS = {
    "ChangedFileScope": "vibe3.analysis.change_scope_service",
    "classify_changed_files": "vibe3.analysis.change_scope_service",
    "count_changed_lines": "vibe3.analysis.change_scope_service",
    "is_test_file": "vibe3.analysis.change_scope_service",
    "CoverageService": "vibe3.analysis.coverage_service",
    "find_latest_prepush_report": "vibe3.analysis.local_review_report",
    "LocalReviewReport": "vibe3.analysis.local_review_report",
    "inspect_python_file": "vibe3.analysis.python_file_inspector",
    "ReviewKernelConfigError": "vibe3.analysis.review_kernel",
    "ReviewKernelEntry": "vibe3.analysis.review_kernel",
    "ReviewKernelManifest": "vibe3.analysis.review_kernel",
    "classify_review_kernel": "vibe3.analysis.review_kernel",
    "load_review_kernel": "vibe3.analysis.review_kernel",
    "build_committed_summary": "vibe3.analysis.review_observation",
    "build_review_observation": "vibe3.analysis.review_observation",
    "ProviderSymbol": "vibe3.analysis.symbol_reference_service",
    "SerenaSymbolReferenceProvider": "vibe3.analysis.symbol_reference_service",
    "SymbolInspectionResult": "vibe3.analysis.symbol_reference_service",
    "SymbolReferenceProvider": "vibe3.analysis.symbol_reference_service",
    "inspect_symbol": "vibe3.analysis.symbol_reference_service",
}


def __getattr__(name: str) -> object:
    """Lazy import analysis symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ChangedFileScope",
    "CoverageService",
    "LocalReviewReport",
    "ProviderSymbol",
    "ReviewKernelConfigError",
    "ReviewKernelEntry",
    "ReviewKernelManifest",
    "SerenaSymbolReferenceProvider",
    "SymbolInspectionResult",
    "SymbolReferenceProvider",
    "build_committed_summary",
    "build_review_observation",
    "classify_changed_files",
    "classify_review_kernel",
    "count_changed_lines",
    "find_latest_prepush_report",
    "inspect_python_file",
    "inspect_symbol",
    "is_test_file",
    "load_review_kernel",
]
