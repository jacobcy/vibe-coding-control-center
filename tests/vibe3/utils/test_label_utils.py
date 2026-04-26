"""Tests for label utility functions."""

from vibe3.utils.label_utils import (
    has_manager_assignee,
    normalize_assignees,
    normalize_labels,
)


class TestHasManagerAssignee:
    """Tests for has_manager_assignee function."""

    def test_empty_manager_usernames_returns_true(self) -> None:
        """Empty manager list should allow all issues (no restriction)."""
        assert has_manager_assignee(["alice", "bob"], []) is True
        assert has_manager_assignee(["alice"], ()) is True
        assert has_manager_assignee([], []) is True

    def test_assignee_in_manager_list(self) -> None:
        """Issue with manager assignee should return True."""
        assert has_manager_assignee(["alice", "bob"], ["alice", "charlie"]) is True
        assert has_manager_assignee(["bob"], ["alice", "bob", "charlie"]) is True

    def test_assignee_not_in_manager_list(self) -> None:
        """Issue without manager assignee should return False."""
        assert has_manager_assignee(["dave", "eve"], ["alice", "bob"]) is False
        assert has_manager_assignee(["dave"], ["alice"]) is False

    def test_empty_assignees_with_managers_configured(self) -> None:
        """Unassigned issue with managers configured should return False."""
        assert has_manager_assignee([], ["alice", "bob"]) is False

    def test_tuple_manager_usernames(self) -> None:
        """Function should accept both list and tuple for manager_usernames."""
        assert has_manager_assignee(["alice"], ("alice", "bob")) is True
        assert has_manager_assignee(["charlie"], ("alice", "bob")) is False


class TestNormalizeLabels:
    """Tests for normalize_labels function."""

    def test_empty_list(self) -> None:
        """Empty list should return empty list."""
        assert normalize_labels([]) == []

    def test_dict_items(self) -> None:
        """Should extract 'name' field from dict items."""
        labels = [{"name": "bug"}, {"name": "enhancement"}, {"name": "wontfix"}]
        assert normalize_labels(labels) == ["bug", "enhancement", "wontfix"]

    def test_missing_name_field(self) -> None:
        """Should skip items without 'name' field."""
        labels = [{"name": "bug"}, {"id": 123}, {"name": "feature"}]
        assert normalize_labels(labels) == ["bug", "feature"]

    def test_non_dict_items(self) -> None:
        """Should skip non-dict items."""
        labels = [{"name": "bug"}, "not-a-dict", 123]
        assert normalize_labels(labels) == ["bug"]

    def test_non_list_input(self) -> None:
        """Non-list input should return empty list."""
        assert normalize_labels("not-a-list") == []
        assert normalize_labels(None) == []
        assert normalize_labels(123) == []


class TestNormalizeAssignees:
    """Tests for normalize_assignees function."""

    def test_empty_list(self) -> None:
        """Empty list should return empty list."""
        assert normalize_assignees([]) == []

    def test_dict_items(self) -> None:
        """Should extract 'login' field from dict items."""
        assignees = [{"login": "alice"}, {"login": "bob"}, {"login": "charlie"}]
        assert normalize_assignees(assignees) == ["alice", "bob", "charlie"]

    def test_missing_login_field(self) -> None:
        """Should skip items without 'login' field."""
        assignees = [{"login": "alice"}, {"id": 123}, {"login": "bob"}]
        assert normalize_assignees(assignees) == ["alice", "bob"]

    def test_empty_login(self) -> None:
        """Should skip items with empty login."""
        assignees = [{"login": "alice"}, {"login": ""}, {"login": "bob"}]
        assert normalize_assignees(assignees) == ["alice", "bob"]

    def test_non_dict_items(self) -> None:
        """Should skip non-dict items."""
        assignees = [{"login": "alice"}, "not-a-dict", 123]
        assert normalize_assignees(assignees) == ["alice"]

    def test_non_list_input(self) -> None:
        """Non-list input should return empty list."""
        assert normalize_assignees("not-a-list") == []
        assert normalize_assignees(None) == []
        assert normalize_assignees(123) == []
