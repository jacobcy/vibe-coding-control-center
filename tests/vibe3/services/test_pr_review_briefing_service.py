"""Tests for PR review briefing service."""

from unittest.mock import MagicMock, patch

from vibe3.services.pr_review_briefing_service import SENTINEL, PRReviewBriefingService


def test_render_briefing_contains_essential_sections():
    # Mock analysis object
    analysis = MagicMock()
    analysis.total_files = 5
    analysis.total_commits = 3
    analysis.score = {"score": 5.5, "level": "MEDIUM", "reason": "Risk found"}
    analysis.critical_files = [{"path": "src/core.py", "public_api": True}]
    analysis.critical_symbols = {"src/core.py": ["process_data"]}
    analysis.impacted_modules = ["vibe3.core", "vibe3.api"]

    service = PRReviewBriefingService(MagicMock())
    body = service._render_briefing(analysis)

    assert SENTINEL in body
    assert "MEDIUM" in body
    assert "5.5" in body
    assert "Files Changed:** 5" in body
    assert "src/core.py" in body
    assert "[API]" in body
    assert "process_data" in body
    assert "vibe3.core" in body


def test_publish_briefing_creates_new_comment_if_none_exists():
    gh_client = MagicMock()
    gh_client.list_pr_comments.return_value = []
    gh_client.create_pr_comment.return_value = "https://github.com/comment/1"

    analysis = MagicMock()
    analysis.score = {}
    analysis.critical_files = []
    analysis.critical_symbols = {}
    analysis.impacted_modules = []

    # Patch where it is imported/used, or where it is defined.
    # Since it is a local import in PRReviewBriefingService.publish_briefing,
    # we MUST patch the original definition.
    with patch(
        "vibe3.commands.inspect_pr_helpers.build_pr_analysis", return_value=analysis
    ):
        service = PRReviewBriefingService(gh_client)
        url = service.publish_briefing(123)

        assert url == "https://github.com/comment/1"
        gh_client.create_pr_comment.assert_called_once()
        gh_client.update_pr_comment.assert_not_called()


def test_publish_briefing_updates_existing_comment_if_found():
    gh_client = MagicMock()
    existing_comment = {"id": "999", "body": f"Old briefing {SENTINEL}"}
    gh_client.list_pr_comments.return_value = [existing_comment]
    gh_client.update_pr_comment.return_value = "https://github.com/comment/999"

    analysis = MagicMock()
    analysis.score = {}
    analysis.critical_files = []
    analysis.critical_symbols = {}
    analysis.impacted_modules = []

    with patch(
        "vibe3.commands.inspect_pr_helpers.build_pr_analysis", return_value=analysis
    ):
        service = PRReviewBriefingService(gh_client)
        url = service.publish_briefing(123)

        assert url == "https://github.com/comment/999"
        gh_client.create_pr_comment.assert_not_called()
        gh_client.update_pr_comment.assert_called_once()
