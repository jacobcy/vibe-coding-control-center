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
    # Use real-looking score data with enum-like level
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
    # Mock get_pr to provide context
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
    assert "src/core.py" in body
    assert "Route:** `main` ← `feat/test`" in body
    assert "Linked Issue:** #42" in body
    assert "### Please focus on" in body
    assert "Critical Logic" in body


def test_publish_briefing_creates_new_comment_if_none_exists_by_author():
    gh_client = MagicMock()
    gh_client.get_current_user.return_value = "bot-user"
    # Existing comment by different author should be ignored
    other_comment = {
        "id": "111",
        "body": f"Briefing {SENTINEL}",
        "author": {"login": "other-user"},
    }
    gh_client.list_pr_comments.return_value = [other_comment]
    gh_client.create_pr_comment.return_value = "https://github.com/comment/new"
    gh_client.get_pr.return_value = MagicMock()  # for _render_briefing

    analysis = MagicMock()
    analysis.score = {}
    analysis.critical_files = []
    analysis.critical_symbols = []
    analysis.impacted_modules = []

    patch_path = "vibe3.commands.inspect_pr_helpers.build_pr_analysis"
    with patch(patch_path, return_value=analysis):
        service = PRReviewBriefingService(gh_client)
        url = service.publish_briefing(123)

        assert url == "https://github.com/comment/new"
        gh_client.create_pr_comment.assert_called_once()
        gh_client.update_pr_comment.assert_not_called()


def test_publish_briefing_updates_existing_comment_by_same_author():
    gh_client = MagicMock()
    gh_client.get_current_user.return_value = "bot-user"
    existing_comment = {
        "id": "999",
        "body": f"Old briefing {SENTINEL}",
        "author": {"login": "bot-user"},
    }
    gh_client.list_pr_comments.return_value = [existing_comment]
    gh_client.update_pr_comment.return_value = "https://github.com/comment/999"
    gh_client.get_pr.return_value = MagicMock()  # for _render_briefing

    analysis = MagicMock()
    analysis.score = {}
    analysis.critical_files = []
    analysis.critical_symbols = []
    analysis.impacted_modules = []

    patch_path = "vibe3.commands.inspect_pr_helpers.build_pr_analysis"
    with patch(patch_path, return_value=analysis):
        service = PRReviewBriefingService(gh_client)
        url = service.publish_briefing(123)

        assert url == "https://github.com/comment/999"
        gh_client.create_pr_comment.assert_not_called()
        gh_client.update_pr_comment.assert_called_once_with("999", ANY)
