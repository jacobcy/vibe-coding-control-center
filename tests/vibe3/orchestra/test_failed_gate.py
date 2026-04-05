"""Tests for FailedGate module."""

import json
from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.failed_gate import FailedGate


def test_failed_gate_open() -> None:
    """Gate should be open when no state/failed issues are found."""
    with patch("subprocess.run") as mock_run:
        # Mock gh issue list --label state/failed --state open
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")

        gate = FailedGate(repo="owner/repo")
        result = gate.check()

        assert not result.blocked
        assert result.issue_number is None

        # Verify command
        cmd = mock_run.call_args[0][0]
        assert "gh" in cmd
        assert "issue" in cmd
        assert "list" in cmd
        assert "--label" in cmd
        assert IssueState.FAILED.to_label() in cmd


def test_failed_gate_blocked_with_explicit_reason() -> None:
    """Gate should extract explicit '原因:' or 'reason:' from latest comment."""
    with patch("subprocess.run") as mock_run:
        # Call 1: list_failed_issues
        # Call 2: _extract_reason (view comments)
        mock_run.side_effect = [
            MagicMock(
                returncode=0,
                stdout=json.dumps([{"number": 123, "title": "Fail title"}]),
            ),
            MagicMock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "comments": [
                            {"body": "Older comment", "url": "url1"},
                            {
                                "body": (
                                    "Newer comment\n原因: "
                                    "specific failure reason\nMore text"
                                ),
                                "url": "url2",
                            },
                        ]
                    }
                ),
            ),
        ]

        gate = FailedGate(repo="owner/repo")
        result = gate.check()

        assert result.blocked
        assert result.issue_number == 123
        assert result.issue_title == "Fail title"
        assert result.reason == "specific failure reason"
        assert result.comment_url == "url2"


def test_failed_gate_blocked_with_summary_fallback() -> None:
    """Gate should fallback to summary if no explicit reason marker is found."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps([{"number": 123}])),
            MagicMock(
                returncode=0,
                stdout=json.dumps(
                    {
                        "comments": [
                            {
                                "body": "Failed to execute manager: timeout error",
                                "url": "url3",
                            }
                        ]
                    }
                ),
            ),
        ]

        gate = FailedGate(repo="owner/repo")
        result = gate.check()

        assert result.blocked
        assert result.reason == "Failed to execute manager: timeout error..."
        assert result.comment_url == "url3"


def test_failed_gate_error_handling() -> None:
    """Gate should fail-closed (blocked=True) if API check fails for safety."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="API error")

        gate = FailedGate(repo="owner/repo")
        result = gate.check()

        assert result.blocked
        assert "failed gate check error" in result.reason
