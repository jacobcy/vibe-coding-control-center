"""Unit tests for IssueTitleCacheService."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.issue_title_cache_service import IssueTitleCacheService


@pytest.fixture
def mock_store():
    """Create a mock SQLiteClient."""
    return MagicMock()


@pytest.fixture
def mock_github():
    """Create a mock GitHubClient."""
    return MagicMock()


class TestIssueTitleCacheService:
    """Unit tests for IssueTitleCacheService."""

    def test_get_title_cache_hit(self, mock_store, mock_github):
        """Test get_title returns cached value."""
        mock_store.get_flow_context_cache.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": 123,
            "issue_title": "Test Issue",
        }

        service = IssueTitleCacheService(mock_store, mock_github)
        title = service.get_title("task/issue-123")

        assert title == "Test Issue"
        # Should not call GitHub on cache hit
        mock_github.view_issue.assert_not_called()

    def test_get_title_cache_miss(self, mock_store, mock_github):
        """Test get_title returns None on cache miss."""
        mock_store.get_flow_context_cache.return_value = None

        service = IssueTitleCacheService(mock_store, mock_github)
        title = service.get_title("task/issue-123")

        assert title is None

    def test_get_title_with_fallback_cache_hit(self, mock_store, mock_github):
        """Test fallback returns cached title without GitHub call."""
        mock_store.get_flow_context_cache.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": 123,
            "issue_title": "Cached Title",
        }

        service = IssueTitleCacheService(mock_store, mock_github)
        title, error = service.get_title_with_fallback("task/issue-123")

        assert title == "Cached Title"
        assert error is False
        mock_github.view_issue.assert_not_called()

    def test_get_title_with_fallback_fetches_from_github(self, mock_store, mock_github):
        """Test fallback to GitHub API on cache miss."""
        # Cache miss
        mock_store.get_flow_context_cache.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": 123,
            "issue_title": None,  # No cached title
        }

        # GitHub returns issue
        mock_github.view_issue.return_value = {
            "number": 123,
            "title": "Fetched Title",
        }

        service = IssueTitleCacheService(mock_store, mock_github)
        title, error = service.get_title_with_fallback("task/issue-123")

        assert title == "Fetched Title"
        assert error is False
        mock_github.view_issue.assert_called_once_with(123)

    def test_get_titles_batch(self, mock_store, mock_github):
        """Test batch title retrieval."""
        service = IssueTitleCacheService(mock_store, mock_github)

        with patch.object(service, "get_title") as mock_get:
            mock_get.side_effect = lambda branch: (
                f"Title for {branch}" if branch == "task/issue-123" else None
            )

            titles = service.get_titles(["task/issue-123", "task/issue-456"])

            assert titles == {"task/issue-123": "Title for task/issue-123"}
            assert "task/issue-456" not in titles

    def test_update_title(self, mock_store, mock_github):
        """Test updating title for a branch."""
        mock_store.get_flow_context_cache.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": 123,
            "pr_number": 42,
            "pr_title": "PR Title",
        }

        service = IssueTitleCacheService(mock_store, mock_github)
        service.update_title("task/issue-123", "New Title")

        mock_store.upsert_flow_context_cache.assert_called_once_with(
            branch="task/issue-123",
            task_issue_number=123,
            issue_title="New Title",
            pr_number=42,
            pr_title="PR Title",
        )

    def test_invalidate(self, mock_store, mock_github):
        """Test invalidating cache for a branch."""
        mock_store.get_flow_context_cache.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": 123,
            "issue_title": "Old Title",
            "pr_number": 42,
            "pr_title": "PR Title",
        }

        service = IssueTitleCacheService(mock_store, mock_github)
        service.invalidate("task/issue-123")

        mock_store.upsert_flow_context_cache.assert_called_once_with(
            branch="task/issue-123",
            task_issue_number=123,
            issue_title=None,  # Cleared
            pr_number=42,
            pr_title="PR Title",
        )

    def test_network_error_handling(self, mock_store, mock_github):
        """Test network error is returned correctly."""
        mock_store.get_flow_context_cache.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": 123,
            "issue_title": None,
        }
        mock_github.view_issue.return_value = "network_error"

        service = IssueTitleCacheService(mock_store, mock_github)
        title, error = service.get_title_with_fallback("task/issue-123")

        assert title is None
        assert error is True

    def test_github_client_lazy_initialization(self, mock_store):
        """Test GitHub client is lazy-initialized when needed."""
        service = IssueTitleCacheService(mock_store, github_client=None)

        # Should raise error because we can't import GitHubClient in tests
        # But the property exists
        assert service._github_client is None

    def test_get_titles_with_fallback_batch(self, mock_store, mock_github):
        """Test batch title retrieval with fallback."""

        # Setup cache hits and misses
        def get_cache_side_effect(branch):
            if branch == "task/issue-123":
                return {
                    "branch": branch,
                    "task_issue_number": 123,
                    "issue_title": "Cached Title",
                }
            elif branch == "task/issue-456":
                return {
                    "branch": branch,
                    "task_issue_number": 456,
                    "issue_title": None,  # Cache miss
                }
            return None

        mock_store.get_flow_context_cache.side_effect = get_cache_side_effect

        # GitHub returns title for issue 456
        mock_github.view_issue.return_value = {
            "number": 456,
            "title": "Fetched Title",
        }

        service = IssueTitleCacheService(mock_store, mock_github)
        titles, error = service.get_titles_with_fallback(
            ["task/issue-123", "task/issue-456"]
        )

        assert titles["task/issue-123"] == "Cached Title"
        assert titles["task/issue-456"] == "Fetched Title"
        assert error is False
        # Should only call GitHub for cache miss
        mock_github.view_issue.assert_called_once_with(456)

    def test_fetch_and_cache_no_issue_number(self, mock_store, mock_github):
        """Test _fetch_and_cache_title returns None when no issue number."""
        mock_store.get_flow_context_cache.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": None,  # No issue number
            "issue_title": None,
        }

        service = IssueTitleCacheService(mock_store, mock_github)
        title, error = service._fetch_and_cache_title("task/issue-123")

        assert title is None
        assert error is False
        mock_github.view_issue.assert_not_called()

    def test_fetch_and_cache_no_cache_entry(self, mock_store, mock_github):
        """Test _fetch_and_cache_title returns None when no cache entry."""
        mock_store.get_flow_context_cache.return_value = None

        service = IssueTitleCacheService(mock_store, mock_github)
        title, error = service._fetch_and_cache_title("task/issue-123")

        assert title is None
        assert error is False
        mock_github.view_issue.assert_not_called()

    def test_update_pr(self, mock_store, mock_github):
        """Test updating PR information for a branch."""
        mock_store.get_flow_context_cache.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": 123,
            "issue_title": "Issue Title",
            "pr_number": None,
            "pr_title": None,
        }

        service = IssueTitleCacheService(mock_store, mock_github)
        service.update_pr("task/issue-123", 456, "PR Title")

        mock_store.upsert_flow_context_cache.assert_called_once_with(
            branch="task/issue-123",
            task_issue_number=123,
            issue_title="Issue Title",
            pr_number=456,
            pr_title="PR Title",
        )

    def test_update_pr_new_entry(self, mock_store, mock_github):
        """Test updating PR information when no existing cache entry."""
        mock_store.get_flow_context_cache.return_value = None

        service = IssueTitleCacheService(mock_store, mock_github)
        service.update_pr("task/issue-123", 456, "PR Title")

        mock_store.upsert_flow_context_cache.assert_called_once_with(
            branch="task/issue-123",
            task_issue_number=None,
            issue_title=None,
            pr_number=456,
            pr_title="PR Title",
        )
