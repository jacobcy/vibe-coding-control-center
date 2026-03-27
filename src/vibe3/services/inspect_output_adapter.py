"""Normalize inspect JSON output access for review/pr consumers."""

from typing import Any, cast


def as_mapping(value: object) -> dict[str, Any]:
    """Return a dict view for inspect section-like objects."""
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    return {}


def as_list(value: object) -> list[Any]:
    """Return a list view for inspect list-like sections."""
    if isinstance(value, list):
        return cast(list[Any], value)
    return []


def changed_symbols(analysis: dict[str, object]) -> dict[str, list[str]] | None:
    """Extract changed_symbols from inspect output."""
    raw = as_mapping(analysis.get("changed_symbols", {}))
    if not raw:
        return None
    normalized: dict[str, list[str]] = {}
    for file, symbols in raw.items():
        if isinstance(file, str):
            symbol_list = [item for item in as_list(symbols) if isinstance(item, str)]
            if symbol_list:
                normalized[file] = symbol_list
    return normalized or None


def score(analysis: dict[str, object]) -> dict[str, Any]:
    """Extract score section from inspect output."""
    return as_mapping(analysis.get("score", {}))


def impact(analysis: dict[str, object]) -> dict[str, Any]:
    """Extract impact section from inspect output."""
    return as_mapping(analysis.get("impact", {}))


def dag(analysis: dict[str, object]) -> dict[str, Any]:
    """Extract dag section from inspect output."""
    return as_mapping(analysis.get("dag", {}))


def pr_analysis_summary(analysis: dict[str, object]) -> dict[str, Any]:
    """Build command-facing PR analysis summary."""
    score_items = score(analysis)
    impact_items = impact(analysis)
    dag_items = dag(analysis)
    changed_files = as_list(impact_items.get("changed_files"))
    impacted_modules = as_list(dag_items.get("impacted_modules"))
    return {
        "risk_level": score_items.get("level"),
        "risk_score": score_items.get("score"),
        "changed_files_count": len(changed_files),
        "impacted_modules_count": len(impacted_modules),
        "raw": analysis,
    }
