"""PR show must not republish unsupported inspect risk claims."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


@pytest.fixture
def mock_pr() -> MagicMock:
    pr = MagicMock()
    pr.number = 123
    pr.title = "Test PR"
    pr.state.value = "OPEN"
    pr.draft = False
    pr.head_branch = "feature/test"
    pr.base_branch = "main"
    pr.url = "https://github.com/test/test/pull/123"
    pr.metadata = None
    pr.body = "Test body"
    pr.review_comments = []
    pr.comments = []
    pr.model_dump.return_value = {
        "number": 123,
        "title": "Test PR",
        "state": "OPEN",
        "head_branch": "feature/test",
        "base_branch": "main",
    }
    return pr


def _mock_service(pr: MagicMock) -> MagicMock:
    service = MagicMock()
    service.get_pr.return_value = pr
    service.git_client.get_current_branch.return_value = "other/branch"
    service.github_client.get_pr.return_value = pr
    return service


def _report_dir(tmp_path: Path) -> Path:
    reports = tmp_path / ".agent" / "reports" / "review"
    reports.mkdir(parents=True)
    (reports / "pre-push-review-20260320-225241.md").write_text(
        "---\nrisk_level: HIGH\nrisk_score: 7\nverdict: PASS\n---\n",
        encoding="utf-8",
    )
    return reports


def test_pr_show_json_omits_unreliable_analysis_fields(
    tmp_path: Path, mock_pr: MagicMock
) -> None:
    reports = _report_dir(tmp_path)

    def path_factory(value: str) -> Path:
        return reports if value == ".agent/reports/review" else Path(value)

    with (
        patch("vibe3.commands.pr_query.PRService", return_value=_mock_service(mock_pr)),
        patch("vibe3.analysis.local_review_report.Path", side_effect=path_factory),
    ):
        result = runner.invoke(app, ["pr", "show", "123", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    rendered = json.dumps(payload)
    assert "analysis" not in payload
    assert "risk_score" not in rendered
    assert "risk_level" not in rendered
    assert "impacted_modules" not in rendered
    assert payload["local_review"]["verdict"] == "PASS"


def test_pr_show_human_keeps_verdict_without_risk_claims(
    tmp_path: Path, mock_pr: MagicMock
) -> None:
    reports = _report_dir(tmp_path)

    def path_factory(value: str) -> Path:
        return reports if value == ".agent/reports/review" else Path(value)

    with (
        patch("vibe3.commands.pr_query.PRService", return_value=_mock_service(mock_pr)),
        patch("vibe3.analysis.local_review_report.Path", side_effect=path_factory),
    ):
        result = runner.invoke(app, ["pr", "show", "123"])

    assert result.exit_code == 0
    assert "Verdict" in result.output
    assert "Risk Score" not in result.output
    assert "Risk Level" not in result.output
