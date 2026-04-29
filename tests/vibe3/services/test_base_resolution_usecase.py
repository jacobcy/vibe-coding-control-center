"""Tests for shared base resolution usecase."""

from unittest.mock import MagicMock

import pytest

from vibe3.exceptions import UserError
from vibe3.services.base_resolution_usecase import BaseResolutionUsecase


def test_resolve_pr_create_base_defaults_to_main() -> None:
    """PR creation should keep main as the default base when omitted."""
    usecase = BaseResolutionUsecase()

    assert usecase.resolve_pr_create_base(None) == "main"


def test_resolve_pr_create_base_preserves_explicit_value() -> None:
    """Explicit PR create base should pass through unchanged."""
    usecase = BaseResolutionUsecase()

    assert usecase.resolve_pr_create_base("origin/develop") == "origin/develop"


def test_resolve_review_base_uses_parent_detector_when_omitted() -> None:
    """Review base should auto-detect parent branch when omitted."""
    usecase = BaseResolutionUsecase(parent_branch_finder=lambda branch: "feature/root")

    resolved = usecase.resolve_review_base(None, current_branch="feature/child")

    assert resolved.base_branch == "feature/root"
    assert resolved.auto_detected is True


def test_resolve_inspect_base_defaults_to_parent_policy() -> None:
    """Inspect base should default to parent policy when omitted."""
    usecase = BaseResolutionUsecase(parent_branch_finder=lambda branch: "feature/root")

    resolved = usecase.resolve_inspect_base(None, current_branch="feature/child")

    assert resolved.base_branch == "feature/root"
    assert resolved.auto_detected is True


def test_resolve_base_supports_current_and_main_tokens() -> None:
    """Unified resolver should support current/main policy tokens."""
    usecase = BaseResolutionUsecase(parent_branch_finder=lambda branch: "feature/root")

    current = usecase.resolve_base(
        requested_base="current",
        current_branch="task/demo",
        default_policy="main",
    )
    main = usecase.resolve_base(
        requested_base="main",
        current_branch="task/demo",
        default_policy="current",
    )

    assert current.base_branch == "task/demo"
    assert main.base_branch == "origin/main"


def test_resolve_review_base_raises_when_parent_missing() -> None:
    """Review base should fail clearly when no parent branch can be inferred."""
    usecase = BaseResolutionUsecase(parent_branch_finder=lambda branch: None)

    with pytest.raises(UserError, match="Could not auto-detect parent branch"):
        usecase.resolve_review_base(None, current_branch="feature/child")


def test_collect_branch_material_uses_git_client() -> None:
    """Branch material collection should reuse GitClient-backed operations."""
    git_client = MagicMock()
    git_client.get_commit_subjects.return_value = ["feat: add base resolver"]
    git_client.get_changed_files.return_value = ["src/vibe3/commands/pr_create.py"]
    usecase = BaseResolutionUsecase(git_client=git_client)

    material = usecase.collect_branch_material(
        base_branch="origin/main",
        branch="task/demo",
    )

    assert material.base_branch == "origin/main"
    assert material.commits == ["feat: add base resolver"]
    assert material.changed_files == ["src/vibe3/commands/pr_create.py"]
    git_client.get_commit_subjects.assert_called_once_with("origin/main", "task/demo")
    git_client.get_changed_files.assert_called_once()
