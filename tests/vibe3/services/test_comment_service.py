"""Tests for comment_service — human vs automated comment filtering."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibe3.services.comment_service import is_human_comment


def _make_comment(login: str = "alice", body: str = "") -> dict:
    return {"author": {"login": login}, "body": body}


class TestIsHumanComment:
    """Unit tests for is_human_comment."""

    def test_human_comment_returns_true(self) -> None:
        assert is_human_comment(_make_comment("alice", "Thanks for the PR!")) is True

    def test_empty_login_returns_true(self) -> None:
        assert is_human_comment(_make_comment("", "")) is True

    def test_missing_author_returns_true(self) -> None:
        assert is_human_comment({"body": "hello"}) is True

    def test_linear_bot_returns_false(self) -> None:
        assert is_human_comment(_make_comment("linear", "Status update")) is False

    def test_bot_login_returns_false(self) -> None:
        assert is_human_comment(_make_comment("dependabot[bot]", "Bump foo")) is False

    def test_manager_marker_returns_false(self) -> None:
        assert (
            is_human_comment(_make_comment("alice", "[manager] Status: done")) is False
        )

    def test_plan_marker_returns_false(self) -> None:
        assert is_human_comment(_make_comment("bob", "[plan] Scope defined")) is False

    def test_run_marker_returns_false(self) -> None:
        assert is_human_comment(_make_comment("bob", "[run] Complete")) is False

    def test_review_marker_returns_false(self) -> None:
        assert is_human_comment(_make_comment("bob", "[review] LGTM")) is False

    def test_resume_marker_returns_false(self) -> None:
        assert is_human_comment(_make_comment("bob", "[resume] Continuing")) is False

    def test_generic_agent_marker_returns_false(self) -> None:
        assert is_human_comment(_make_comment("bob", "[agent:planner] Done")) is False

    def test_heading_with_marker_returns_false(self) -> None:
        assert (
            is_human_comment(_make_comment("bob", "### [manager] Status report"))
            is False
        )

    def test_marker_not_at_start_of_line_is_human(self) -> None:
        assert (
            is_human_comment(_make_comment("alice", "See [manager] docs for details"))
            is True
        )

    @patch("vibe3.services.comment_service.load_orchestra_config")
    def test_bot_username_from_config(self, mock_config: MagicMock) -> None:
        config = MagicMock()
        config.bot_username = "mybot"
        mock_config.return_value = config
        assert is_human_comment(_make_comment("mybot", "hi")) is False

    @patch("vibe3.services.comment_service._get_manager_usernames")
    @patch("vibe3.services.comment_service.load_orchestra_config")
    def test_manager_username_from_config(
        self, mock_config: MagicMock, mock_usernames: MagicMock
    ) -> None:
        config = MagicMock()
        config.bot_username = None
        mock_config.return_value = config
        mock_usernames.return_value = ("manager-user",)
        assert is_human_comment(_make_comment("manager-user", "hi")) is False

    @patch("vibe3.services.comment_service.load_orchestra_config")
    def test_config_load_failure_falls_through(self, mock_config: MagicMock) -> None:
        mock_config.side_effect = RuntimeError("config unavailable")
        assert is_human_comment(_make_comment("alice", "hello")) is True

    @patch("vibe3.services.comment_service._get_manager_usernames")
    @patch("vibe3.services.comment_service.load_orchestra_config")
    def test_empty_manager_usernames_list(
        self, mock_config: MagicMock, mock_usernames: MagicMock
    ) -> None:
        config = MagicMock()
        config.bot_username = None
        mock_config.return_value = config
        mock_usernames.return_value = ()
        assert is_human_comment(_make_comment("alice", "hi")) is True
