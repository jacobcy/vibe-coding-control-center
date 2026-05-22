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

    @pytest.mark.parametrize(
        "content,expected_fields",
        [
            pytest.param(
                """---
risk_level: HIGH
risk_score: 7
verdict: PASS
created_at: 2026-03-20T22:52:41
---

# Pre-push Review Report

Some content here.
""",
                {
                    "risk_level": "HIGH",
                    "risk_score": 7,
                    "verdict": "PASS",
                    "has_created_at": True,
                },
                id="yaml_frontmatter",
            ),
            pytest.param(
                """# Pre-push Review Report

## Risk Assessment
- Risk Level: HIGH
- Risk Score: 7
- Verdict: PASS

Some content here.
""",
                {"risk_level": "HIGH", "risk_score": 7, "verdict": "PASS"},
                id="inline_key_value",
            ),
            pytest.param(
                """---
risk_level: MEDIUM
created_at: 2026-03-20T22:52:41
---

# Pre-push Review Report

## Risk Assessment
- Risk Score: 5
- Verdict: CONDITIONAL
""",
                {"risk_level": "MEDIUM", "risk_score": 5, "verdict": "CONDITIONAL"},
                id="mixed_format",
            ),
        ],
    )
    def test_parse_report_success(self, content: str, expected_fields: dict) -> None:
        """Parse report with various formats."""
        result = parse_prepush_report(content)

        for key, value in expected_fields.items():
            if key == "has_created_at":
                assert "created_at" in result
                assert isinstance(result["created_at"], datetime)
            else:
                assert result[key] == value

    @pytest.mark.parametrize(
        "content,expected_empty",
        [
            pytest.param("", True, id="empty_content"),
            pytest.param(
                """# Some Report

This is just regular content.
Nothing special here.
""",
                True,
                id="no_recognized_fields",
            ),
            pytest.param(
                """---
invalid yaml content: [unclosed
---

# Report
""",
                False,  # Should not raise, returns dict (possibly empty)
                id="invalid_yaml_frontmatter",
            ),
            pytest.param(
                """# Report

Risk Level: LOW
""",
                False,
                id="partial_inline_fields",
            ),
        ],
    )
    def test_parse_report_edge_cases(self, content: str, expected_empty: bool) -> None:
        """Parse report with edge cases."""
        result = parse_prepush_report(content)
        assert isinstance(result, dict)
        if expected_empty:
            assert result == {}
        else:
            # For non-empty cases, verify specific fields were extracted
            if "Risk Level: LOW" in content:
                assert result.get("risk_level") == "LOW"


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
        reports_dir = tmp_path / ".agent" / "reports" / "review"
        reports_dir.mkdir(parents=True)

        with patch(
            "vibe3.analysis.local_review_report.Path",
            return_value=reports_dir,
        ):
            # Patch the constructor to return our tmp path
            def side_effect(path_str: str) -> Path:
                if path_str == ".agent/reports/review":
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
        reports_dir = tmp_path / ".agent" / "reports" / "review"
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
            if path_str == ".agent/reports/review":
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
        reports_dir = tmp_path / ".agent" / "reports" / "review"
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
            if path_str == ".agent/reports/review":
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
        reports_dir = tmp_path / ".agent" / "reports" / "review"
        reports_dir.mkdir(parents=True)

        report_file = reports_dir / "pre-push-review-20260320-225241.md"
        # Write binary-like content to cause decode/parse issues
        report_file.write_text("Some unstructured content")

        def side_effect(path_str: str) -> Path:
            if path_str == ".agent/reports/review":
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

    @pytest.mark.parametrize(
        "risk_level,risk_score,verdict,created_at",
        [
            pytest.param(
                "HIGH", 7, "PASS", datetime(2026, 3, 20, 22, 52, 41), id="all_fields"
            ),
            pytest.param(None, None, None, None, id="none_fields"),
        ],
    )
    def test_dataclass_creation(
        self,
        risk_level: str | None,
        risk_score: int | None,
        verdict: str | None,
        created_at: datetime | None,
    ) -> None:
        """Create LocalReviewReport with various field combinations."""
        report = LocalReviewReport(
            risk_level=risk_level,
            risk_score=risk_score,
            verdict=verdict,
            report_path=Path("/tmp/report.md"),
            created_at=created_at,
        )

        assert report.risk_level == risk_level
        assert report.risk_score == risk_score
        assert report.verdict == verdict
        assert report.report_path == Path("/tmp/report.md")
        assert report.created_at == created_at

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
