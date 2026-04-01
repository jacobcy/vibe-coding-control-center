"""Tests for CommentReplyService."""

from unittest.mock import patch

import pytest

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent
from vibe3.orchestra.services.comment_reply import (
    CommentReplyService,
    _build_mention_pattern,
)


def _svc() -> CommentReplyService:
    return CommentReplyService(OrchestraConfig(polling_interval=900, dry_run=True))


def _event(
    action: str, body: str, issue_number: int = 42, author: str = "someuser"
) -> GitHubEvent:
    return GitHubEvent(
        event_type="issue_comment",
        action=action,
        payload={
            "comment": {
                "body": body,
                "user": {"login": author},
            },
            "issue": {"number": issue_number},
        },
        source="webhook",
    )


def test_mention_pattern_matches_configured_username() -> None:
    pattern = _build_mention_pattern(["vibe-manager-agent"])
    assert pattern.search("hey @vibe-manager-agent please review")


def test_mention_pattern_case_insensitive() -> None:
    pattern = _build_mention_pattern(["vibe-manager-agent"])
    assert pattern.search("@VIBE-MANAGER-AGENT help")


def test_mention_pattern_multi_username() -> None:
    pattern = _build_mention_pattern(["vibe-manager-agent", "vibe-manager"])
    assert pattern.search("@vibe-manager-agent check this")
    assert pattern.search("@vibe-manager check this")


def test_no_mention_no_match() -> None:
    pattern = _build_mention_pattern(["vibe-manager-agent"])
    assert not pattern.search("just a regular comment")


@pytest.mark.asyncio
async def test_dry_run_no_post() -> None:
    svc = _svc()
    event = _event("created", "hey @vibe-manager-agent can you help?")
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
    event = _event("edited", "@vibe-manager-agent updated question")
    with patch.object(svc, "_post_ack") as mock_post:
        await svc.handle_event(event)
        mock_post.assert_called_once_with(42)


@pytest.mark.asyncio
async def test_ignores_own_ack_by_sentinel() -> None:
    svc = CommentReplyService(OrchestraConfig(polling_interval=900, dry_run=False))
    event = _event("created", "@vibe-manager-agent fixed it <!-- vibe-ack -->")
    with patch.object(svc, "_post_ack") as mock_post:
        await svc.handle_event(event)
        mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_ignores_bot_author() -> None:
    config = OrchestraConfig(
        polling_interval=900, dry_run=False, bot_username="vibe-bot"
    )
    svc = CommentReplyService(config)
    event = _event("created", "hey @vibe-manager-agent", author="vibe-bot")
    with patch.object(svc, "_post_ack") as mock_post:
        await svc.handle_event(event)
        mock_post.assert_not_called()


@pytest.mark.asyncio
async def test_replies_to_valid_mention() -> None:
    svc = CommentReplyService(OrchestraConfig(polling_interval=900, dry_run=False))
    event = _event("created", "please check this @vibe-manager-agent")
    with patch.object(svc, "_post_ack") as mock_post:
        await svc.handle_event(event)
        mock_post.assert_called_once_with(42)
