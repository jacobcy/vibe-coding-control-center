"""Discover local review verdict evidence without risk-score inference."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LocalReviewReport:
    """A local review verdict and its source artifact."""

    verdict: str | None
    report_path: Path
    created_at: datetime | None


def find_latest_prepush_report() -> LocalReviewReport | None:
    """Return the newest pre-push review artifact by modification time."""
    reports_dir = Path(".agent/reports/review")
    if not reports_dir.is_dir():
        return None
    report_files = list(reports_dir.glob("pre-push-review-*.md"))
    if not report_files:
        return None
    latest = max(report_files, key=lambda path: path.stat().st_mtime)
    created_at = datetime.fromtimestamp(latest.stat().st_mtime)
    try:
        parsed = parse_prepush_report(latest.read_text(encoding="utf-8"))
        verdict = parsed.get("verdict")
    except Exception:
        verdict = None
    return LocalReviewReport(
        verdict=verdict if isinstance(verdict, str) else None,
        report_path=latest,
        created_at=created_at,
    )


def parse_prepush_report(content: str) -> dict[str, Any]:
    """Extract only explicit verdict and created-at evidence."""
    result: dict[str, Any] = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter = yaml.safe_load(parts[1].strip())
                if isinstance(frontmatter, dict):
                    verdict = frontmatter.get("verdict")
                    if isinstance(verdict, str):
                        result["verdict"] = verdict
                    created_at = frontmatter.get("created_at")
                    if isinstance(created_at, datetime):
                        result["created_at"] = created_at
                    elif created_at is not None:
                        try:
                            result["created_at"] = datetime.fromisoformat(
                                str(created_at)
                            )
                        except (TypeError, ValueError):
                            pass
            except yaml.YAMLError:
                pass

    for line in content.splitlines():
        stripped = line.strip()
        if "Verdict:" not in stripped or "verdict" in result:
            continue
        value = stripped.split(":", 1)[1].strip().strip("-")
        if value:
            result["verdict"] = value
    return result
