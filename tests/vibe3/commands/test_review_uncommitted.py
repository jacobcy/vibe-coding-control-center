"""Tests for vibe review uncommitted subcommand.

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


def test_review_uncommitted_no_changes():
    """uncommitted 无改动时友好提示，exit 0。"""
    mock_git = MagicMock()
    mock_git.return_value.get_diff.return_value = ""
    with patch("vibe3.commands.review.GitClient", mock_git):
        result = runner.invoke(app, ["uncommitted"])
    assert result.exit_code == 0
    assert "No uncommitted changes" in result.output


def test_review_uncommitted_with_changes():
    mock_git = MagicMock()
    mock_git.return_value.get_diff.return_value = "diff --git a/foo.py ..."
    with (
        patch("vibe3.commands.review.GitClient", mock_git),
        patch("vibe3.commands.review.build_review_context", return_value="ctx"),
        patch("vibe3.commands.review.call_codex", return_value="## Review"),
        patch("vibe3.commands.review.parse_codex_review", return_value=_mock_review()),
    ):
        result = runner.invoke(app, ["uncommitted"])
    assert result.exit_code == 0


def test_review_uncommitted_help():
    result = runner.invoke(app, ["uncommitted", "--help"])
    assert result.exit_code == 0
