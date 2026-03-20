"""Tests for review data models."""

import pytest

from vibe3.models.review import ReviewRequest, ReviewScope


class TestReviewScope:
    """Tests for ReviewScope model."""

    def test_create_base_scope(self) -> None:
        """Should create base scope with base_branch."""
        scope = ReviewScope(kind="base", base_branch="main")
        assert scope.kind == "base"
        assert scope.base_branch == "main"
        assert scope.pr_number is None

    def test_create_pr_scope(self) -> None:
        """Should create PR scope with pr_number."""
        scope = ReviewScope(kind="pr", pr_number=42)
        assert scope.kind == "pr"
        assert scope.pr_number == 42
        assert scope.base_branch is None

    def test_for_base_factory_method(self) -> None:
        """Should create base scope using factory method."""
        scope = ReviewScope.for_base("origin/develop")
        assert scope.kind == "base"
        assert scope.base_branch == "origin/develop"

    def test_for_base_default_branch(self) -> None:
        """Should default to origin/main."""
        scope = ReviewScope.for_base()
        assert scope.base_branch == "origin/main"

    def test_for_pr_factory_method(self) -> None:
        """Should create PR scope using factory method."""
        scope = ReviewScope.for_pr(123)
        assert scope.kind == "pr"
        assert scope.pr_number == 123

    def test_base_scope_requires_base_branch(self) -> None:
        """Should reject base scope without base_branch."""
        with pytest.raises(ValueError, match="base scope requires base_branch"):
            ReviewScope(kind="base")

    def test_pr_scope_requires_pr_number(self) -> None:
        """Should reject PR scope without pr_number."""
        with pytest.raises(ValueError, match="pr scope requires pr_number"):
            ReviewScope(kind="pr")

    def test_scope_is_frozen(self) -> None:
        """Should not allow mutation after creation."""
        scope = ReviewScope.for_base("main")
        with pytest.raises(AttributeError):
            scope.base_branch = "develop"  # type: ignore


class TestReviewRequest:
    """Tests for ReviewRequest model."""

    def test_create_review_request_with_scope(self) -> None:
        """Should create request with minimal scope."""
        scope = ReviewScope.for_base("main")
        request = ReviewRequest(scope=scope)
        assert request.scope == scope
        assert request.changed_symbols is None
        assert request.symbol_dag is None
        assert request.task_guidance is None

    def test_create_review_request_with_all_fields(self) -> None:
        """Should create request with all fields."""
        scope = ReviewScope.for_pr(42)
        request = ReviewRequest(
            scope=scope,
            changed_symbols={"src/foo.py": ["func1", "func2"]},
            symbol_dag={"func1": ["caller1", "caller2"]},
            task_guidance="Focus on security issues",
        )
        assert request.scope.pr_number == 42
        assert request.changed_symbols == {"src/foo.py": ["func1", "func2"]}
        assert request.symbol_dag == {"func1": ["caller1", "caller2"]}
        assert request.task_guidance == "Focus on security issues"

    def test_request_is_frozen(self) -> None:
        """Should not allow mutation after creation."""
        scope = ReviewScope.for_base("main")
        request = ReviewRequest(scope=scope)
        with pytest.raises(AttributeError):
            request.task_guidance = "new task"  # type: ignore
