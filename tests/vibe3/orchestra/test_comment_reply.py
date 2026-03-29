"""Tests for CommentReplyService."""

from unittest.mock import patch

import pytest

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent
from vibe3.orchestra.services.comment_reply import _MENTION_RE, CommentReplyService


def _svc() -> CommentReplyService:
    return CommentReplyService(OrchestraConfig(polling_interval=900, dry_run=True))


def _event(action: str, body: str, issue_number: int = 42) -> GitHubEvent:
    return GitHubEvent(
        event_type="issue_comment",
        action=action,
        payload={
            "comment": {"body": body},
            "issue": {"number": issue_number},
        },
        source="webhook",
    )


def test_mention_pattern_matches() -> None:
    assert _MENTION_RE.search("hey @vibe-manager please review")


def test_mention_pattern_case_insensitive() -> None:
    assert _MENTION_RE.search("@VIBE-MANAGER help")


def test_no_mention_no_match() -> None:
    assert not _MENTION_RE.search("just a regular comment")


@pytest.mark.asyncio
async def test_dry_run_no_post() -> None:
    svc = _svc()
    event = _event("created", "hey @vibe-manager can you help?")
    with patch.object(svc, "_post_ack") as mock_post:
        await svc.handle_event(event)
        mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_non_mention_comment_ignored() -> None:
    svc = _svc()
    event = _event("created", "looks good to me")
    with patch.object(svc, "_post_ack") as mock_post:
        await svc.handle_event(event)
        mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_edited_comment_also_triggers() -> None:
    svc = CommentReplyService(OrchestraConfig(polling_interval=900, dry_run=False))
    event = _event("edited", "@vibe-manager updated question")
    with patch.object(svc, "_post_ack") as mock_post:
        await svc.handle_event(event)
        mock_post.assert_called_once_with(42)
