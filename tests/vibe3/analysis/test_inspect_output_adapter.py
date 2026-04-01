"""Tests for inspect output adapter helpers."""

from vibe3.analysis.inspect_output_adapter import changed_symbols, pr_analysis_summary


def test_changed_symbols_filters_invalid_entries() -> None:
    analysis = {
        "changed_symbols": {
            "a.py": ["foo", 1, "bar"],
            "b.py": "not-a-list",
            1: ["ignored-non-string-key"],
        }
    }

    result = changed_symbols(analysis)

    assert result == {"a.py": ["foo", "bar"]}


def test_pr_analysis_summary_uses_safe_defaults() -> None:
    analysis = {
        "score": {"level": "low", "score": 2},
        "impact": {"changed_files": "not-a-list"},
        "dag": {"impacted_modules": ["svc.a", "svc.b"]},
    }

    summary = pr_analysis_summary(analysis)

    assert summary["risk_level"] == "low"
    assert summary["risk_score"] == 2
    assert summary["changed_files_count"] == 0
    assert summary["impacted_modules_count"] == 2
