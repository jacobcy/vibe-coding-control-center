"""Tests for vibe review base subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services (Codex, GitHub, Git) are mocked.
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.review import app

runner = CliRunner()


def _mock_review(verdict: str = "PASS"):
    m = MagicMock()
    m.verdict = verdict
    m.comments = []
    return m


def _mock_inspect_data():
    return {
        "impact": {"changed_files": ["a.py"]},
        "dag": {"impacted_modules": ["mod_a"]},
        "score": {"score": 3, "level": "LOW", "block": False, "risk_level": "LOW"},
    }


def _patch_review_deps(verdict: str = "PASS"):
    """返回 patch 上下文列表，mock 掉所有外部依赖。"""
    return [
        patch(
            "vibe3.commands.review.run_inspect_json", return_value=_mock_inspect_data()
        ),
        patch("vibe3.commands.review.GitClient"),
        patch("vibe3.commands.review.build_review_context", return_value="ctx"),
        patch(
            "vibe3.commands.review.call_codex", return_value="## Review\nLooks good."
        ),
        patch(
            "vibe3.commands.review.parse_codex_review",
            return_value=_mock_review(verdict),
        ),
    ]


def test_review_base_missing_arg_shows_error():
    result = runner.invoke(app, ["base"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_review_base_pass():
    patches = _patch_review_deps()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        result = runner.invoke(app, ["base", "feature/my-branch"])
    assert result.exit_code == 0
