"""Tests for local review verdict evidence."""

from pathlib import Path
from unittest.mock import patch

from vibe3.analysis.local_review_report import (
    find_latest_prepush_report,
    parse_prepush_report,
)


def test_parser_ignores_risk_fields_and_keeps_verdict() -> None:
    result = parse_prepush_report(
        "---\nrisk_level: HIGH\nrisk_score: 7\nverdict: PASS\n---\n"
    )

    assert result == {"verdict": "PASS"}


def test_parser_reads_inline_verdict() -> None:
    assert parse_prepush_report("- Verdict: MAJOR\n") == {"verdict": "MAJOR"}


def test_latest_report_returns_artifact_and_verdict(tmp_path: Path) -> None:
    reports = tmp_path / ".agent" / "reports" / "review"
    reports.mkdir(parents=True)
    report = reports / "pre-push-review-1.md"
    report.write_text("Verdict: PASS\n", encoding="utf-8")

    def path_factory(value: str) -> Path:
        return reports if value == ".agent/reports/review" else Path(value)

    with patch("vibe3.analysis.local_review_report.Path", side_effect=path_factory):
        result = find_latest_prepush_report()

    assert result is not None
    assert result.verdict == "PASS"
    assert result.report_path == report


def test_latest_report_returns_none_when_directory_missing() -> None:
    with patch("vibe3.analysis.local_review_report.Path.is_dir", return_value=False):
        assert find_latest_prepush_report() is None
