"""Tests for shared issue collection service."""

from __future__ import annotations

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.shared.collections import IssueCollectionService


def test_collect_open_issues_calls_github_once_without_label_filter() -> None:
    github = MagicMock()
    github.list_issues.return_value = [
        {
            "number": 1521,
            "title": "Unified issue collection",
            "labels": [{"name": "roadmap/epic"}],
            "assignees": [],
            "milestone": None,
            "state": "OPEN",
        },
        {
            "number": 1492,
            "title": "Ready task",
            "labels": [{"name": "state/ready"}],
            "assignees": [{"login": "vibe-manager-agent"}],
            "milestone": None,
            "state": "OPEN",
        },
    ]

    service = IssueCollectionService(github, repo="owner/repo")
    issues = service.collect_open_issues()

    github.list_issues.assert_called_once_with(
        limit=100,
        state="open",
        assignee=None,
        repo="owner/repo",
    )
    assert [issue.number for issue in issues] == [1521, 1492]
    assert issues[0].state is None
    assert issues[1].state == IssueState.READY
