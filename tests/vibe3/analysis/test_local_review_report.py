"""Tests for local review report discovery and parsing."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.analysis.local_review_report import (
    LocalReviewReport,
    find_latest_prepush_report,
    parse_prepush_report,
)


class TestParsePrepushReport:
    """Test report parsing logic."""

    def test_parse_yaml_frontmatter(self) -> None:
        """Parse report with YAML frontmatter."""
        content = """---
risk_level: HIGH
risk_score: 7
verdict: PASS
created_at: 2026-03-20T22:52:41
---

# Pre-push Review Report

Some content here.
"""
        result = parse_prepush_report(content)

        assert result["risk_level"] == "HIGH"
        assert result["risk_score"] == 7
        assert result["verdict"] == "PASS"
        assert "created_at" in result
        assert isinstance(result["created_at"], datetime)

    def test_parse_inline_key_value(self) -> None:
        """Parse report with inline key-value pairs."""
        content = """# Pre-push Review Report

## Risk Assessment
- Risk Level: HIGH
- Risk Score: 7
- Verdict: PASS

Some content here.
"""
        result = parse_prepush_report(content)

        assert result["risk_level"] == "HIGH"
        assert result["risk_score"] == 7
        assert result["verdict"] == "PASS"

    def test_parse_mixed_format(self) -> None:
        """Parse report with both frontmatter and inline pairs."""
        content = """---
risk_level: MEDIUM
created_at: 2026-03-20T22:52:41
---

# Pre-push Review Report

## Risk Assessment
- Risk Score: 5
- Verdict: CONDITIONAL
"""
        result = parse_prepush_report(content)

        # Frontmatter takes precedence for risk_level
        assert result["risk_level"] == "MEDIUM"
        # Inline values supplement missing frontmatter fields
        assert result["risk_score"] == 5
        assert result["verdict"] == "CONDITIONAL"

    def test_parse_empty_content(self) -> None:
        """Parse empty content returns empty dict."""
        result = parse_prepush_report("")
        assert result == {}

    def test_parse_no_recognized_fields(self) -> None:
        """Parse content without recognized fields returns empty dict."""
        content = """# Some Report

This is just regular content.
Nothing special here.
"""
        result = parse_prepush_report(content)
        assert result == {}

    def test_parse_invalid_yaml_frontmatter(self) -> None:
        """Gracefully handle invalid YAML in frontmatter."""
        content = """---
invalid yaml content: [unclosed
---

# Report
"""
        # Should not raise, should fall back to inline parsing
        result = parse_prepush_report(content)
        assert isinstance(result, dict)

    def test_parse_partial_inline_fields(self) -> None:
        """Parse report with only some inline fields."""
        content = """# Report

Risk Level: LOW
"""
        result = parse_prepush_report(content)

        assert result["risk_level"] == "LOW"
        assert "risk_score" not in result
        assert "verdict" not in result


class TestFindLatestPrepushReport:
    """Test report discovery logic."""

    def test_find_latest_no_directory(self) -> None:
        """Return None when reports directory doesn't exist."""
        with patch("vibe3.analysis.local_review_report.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            result = find_latest_prepush_report()
            assert result is None

    def test_find_latest_empty_directory(self, tmp_path: Path) -> None:
        """Return None when no reports exist."""
        reports_dir = tmp_path / ".agent" / "reports"
        reports_dir.mkdir(parents=True)

        with patch(
            "vibe3.analysis.local_review_report.Path",
            return_value=reports_dir,
        ):
            # Patch the constructor to return our tmp path
            def side_effect(path_str: str) -> Path:
                if path_str == ".agent/reports":
                    return reports_dir
                return Path(path_str)

            with patch(
                "vibe3.analysis.local_review_report.Path",
                side_effect=side_effect,
            ):
                result = find_latest_prepush_report()
                assert result is None

    def test_find_latest_single_report(self, tmp_path: Path) -> None:
        """Find and parse a single report file."""
        reports_dir = tmp_path / ".agent" / "reports"
        reports_dir.mkdir(parents=True)

        report_file = reports_dir / "pre-push-review-20260320-225241.md"
        report_file.write_text("""---
risk_level: HIGH
risk_score: 7
verdict: PASS
created_at: 2026-03-20T22:52:41
---

# Pre-push Review Report
""")

        def side_effect(path_str: str) -> Path:
            if path_str == ".agent/reports":
                return reports_dir
            return Path(path_str)

        with patch(
            "vibe3.analysis.local_review_report.Path",
            side_effect=side_effect,
        ):
            result = find_latest_prepush_report()

            assert result is not None
            assert result.risk_level == "HIGH"
            assert result.risk_score == 7
            assert result.verdict == "PASS"
            assert result.report_path.name == "pre-push-review-20260320-225241.md"

    def test_find_latest_multiple_reports(self, tmp_path: Path) -> None:
        """Find the most recent report among multiple files."""
        reports_dir = tmp_path / ".agent" / "reports"
        reports_dir.mkdir(parents=True)

        # Create two report files with different timestamps
        report1 = reports_dir / "pre-push-review-20260319-120000.md"
        report1.write_text("Risk Level: LOW\nRisk Score: 3\nVerdict: PASS")

        report2 = reports_dir / "pre-push-review-20260320-225241.md"
        report2.write_text("Risk Level: HIGH\nRisk Score: 7\nVerdict: PASS")

        # Set modification times (report2 is newer)
        import time

        report1.touch()
        time.sleep(0.01)
        report2.touch()

        def side_effect(path_str: str) -> Path:
            if path_str == ".agent/reports":
                return reports_dir
            return Path(path_str)

        with patch(
            "vibe3.analysis.local_review_report.Path",
            side_effect=side_effect,
        ):
            result = find_latest_prepush_report()

            assert result is not None
            assert result.risk_level == "HIGH"
            assert result.report_path.name == "pre-push-review-20260320-225241.md"

    def test_find_latest_handles_parse_error(self, tmp_path: Path) -> None:
        """Return report with None fields if parsing fails."""
        reports_dir = tmp_path / ".agent" / "reports"
        reports_dir.mkdir(parents=True)

        report_file = reports_dir / "pre-push-review-20260320-225241.md"
        # Write binary-like content to cause decode/parse issues
        report_file.write_text("Some unstructured content")

        def side_effect(path_str: str) -> Path:
            if path_str == ".agent/reports":
                return reports_dir
            return Path(path_str)

        with patch(
            "vibe3.analysis.local_review_report.Path",
            side_effect=side_effect,
        ):
            result = find_latest_prepush_report()

            assert result is not None
            # Parsing failed, so fields should be None
            assert result.risk_level is None
            assert result.risk_score is None
            assert result.verdict is None
            # But path should still be set
            assert result.report_path.name == "pre-push-review-20260320-225241.md"


class TestLocalReviewReport:
    """Test LocalReviewReport dataclass."""

    def test_dataclass_creation(self) -> None:
        """Create LocalReviewReport with all fields."""
        report = LocalReviewReport(
            risk_level="HIGH",
            risk_score=7,
            verdict="PASS",
            report_path=Path("/tmp/report.md"),
            created_at=datetime(2026, 3, 20, 22, 52, 41),
        )

        assert report.risk_level == "HIGH"
        assert report.risk_score == 7
        assert report.verdict == "PASS"
        assert report.report_path == Path("/tmp/report.md")
        assert report.created_at == datetime(2026, 3, 20, 22, 52, 41)

    def test_dataclass_frozen(self) -> None:
        """LocalReviewReport is immutable."""
        report = LocalReviewReport(
            risk_level="HIGH",
            risk_score=7,
            verdict="PASS",
            report_path=Path("/tmp/report.md"),
            created_at=None,
        )

        with pytest.raises(AttributeError):
            report.risk_level = "LOW"  # type: ignore

    def test_dataclass_with_none_fields(self) -> None:
        """Create LocalReviewReport with None fields."""
        report = LocalReviewReport(
            risk_level=None,
            risk_score=None,
            verdict=None,
            report_path=Path("/tmp/report.md"),
            created_at=None,
        )

        assert report.risk_level is None
        assert report.risk_score is None
        assert report.verdict is None
