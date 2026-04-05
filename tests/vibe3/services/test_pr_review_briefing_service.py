"""Tests for PR review briefing service."""

from unittest.mock import ANY, MagicMock, patch

from vibe3.services.pr_review_briefing_service import (
    SENTINEL,
    PRReviewBriefingService,
)


def test_render_briefing_contains_essential_sections():
    # Mock analysis object
    analysis = MagicMock()
    analysis.pr_number = 123
    analysis.total_files = 5
    analysis.total_commits = 3
    analysis.score = {
        "score": {
            "score": 5.5,
            "level": "RiskLevel.MEDIUM",
            "reason": "Risk found",
        }
    }
    analysis.critical_files = [{"path": "src/core.py", "public_api": True}]
    analysis.critical_symbols = {"src/core.py": ["process_data"]}
    analysis.impacted_modules = ["vibe3.core", "vibe3.api"]

    gh_client = MagicMock()
    pr_details = MagicMock()
    pr_details.base_branch = "main"
    pr_details.head_branch = "feat/test"
    pr_details.metadata.task_issue = 42
    gh_client.get_pr.return_value = pr_details

    service = PRReviewBriefingService(gh_client)
    body = service._render_briefing(analysis)

    assert SENTINEL in body
    assert "MEDIUM" in body
    assert "5.5" in body
    assert "Files Changed:** 5" in body
    assert "Route:** `main` ← `feat/test`" in body


def test_publish_briefing_creates_new_if_no_sentinel_exists():
    gh_client = MagicMock()
    # Existing comment WITHOUT sentinel
    other_comment = {
        "id": "111",
        "body": "Normal comment",
        "author": {"login": "other-user"},
    }
    gh_client.list_pr_comments.return_value = [other_comment]
    gh_client.create_pr_comment.return_value = "https://github.com/comment/new"
    gh_client.get_pr.return_value = MagicMock()

    analysis = MagicMock()
    analysis.score = {}
    analysis.critical_files = []
    analysis.critical_symbols = []
    analysis.impacted_modules = []

    patch_path = "vibe3.services.pr_analysis_service.build_pr_analysis"
    with patch(patch_path, return_value=analysis):
        service = PRReviewBriefingService(gh_client)
        url = service.publish_briefing(123)

        assert url == "https://github.com/comment/new"
        gh_client.create_pr_comment.assert_called_once()


def test_publish_briefing_updates_any_existing_sentinel_regardless_of_author():
    gh_client = MagicMock()
    # Existing briefing by DIFFERENT author
    existing_briefing = {
        "id": "999",
        "body": f"Old briefing {SENTINEL}",
        "author": {"login": "other-user"},
    }
    gh_client.list_pr_comments.return_value = [existing_briefing]
    gh_client.update_pr_comment.return_value = "https://github.com/comment/999"
    gh_client.get_pr.return_value = MagicMock()

    analysis = MagicMock()
    analysis.score = {}
    analysis.critical_files = []
    analysis.critical_symbols = []
    analysis.impacted_modules = []

    patch_path = "vibe3.services.pr_analysis_service.build_pr_analysis"
    with patch(patch_path, return_value=analysis):
        service = PRReviewBriefingService(gh_client)
        url = service.publish_briefing(123)

        assert url == "https://github.com/comment/999"
        gh_client.create_pr_comment.assert_not_called()
        gh_client.update_pr_comment.assert_called_once_with("999", ANY)
