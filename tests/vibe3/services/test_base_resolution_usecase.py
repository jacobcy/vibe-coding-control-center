"""Tests for shared base resolution usecase."""

from unittest.mock import MagicMock, patch

import pytest

from tests.vibe3.pr_patch_constants import PR_BASE_RESOLUTION
from vibe3.exceptions import UserError
from vibe3.services.pr.base_resolution import BaseResolutionUsecase


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


def test_resolve_inspect_base_falls_back_to_main_when_parent_merged() -> None:
    """When auto-detected parent is already merged, should use origin/main."""
    with patch(f"{PR_BASE_RESOLUTION}.is_branch_merged_to_main") as mock_merged:
        mock_merged.return_value = True
        usecase = BaseResolutionUsecase(
            parent_branch_finder=lambda branch: "task/old-branch"
        )

        resolved = usecase.resolve_inspect_base(None, current_branch="task/child")

        assert resolved.base_branch == "origin/main"
        assert resolved.auto_detected is True
        mock_merged.assert_called_once_with("task/old-branch")


def test_resolve_inspect_base_keeps_parent_when_not_merged() -> None:
    """When auto-detected parent is not merged, should use it as base."""
    with patch(f"{PR_BASE_RESOLUTION}.is_branch_merged_to_main") as mock_merged:
        mock_merged.return_value = False
        usecase = BaseResolutionUsecase(
            parent_branch_finder=lambda branch: "task/active-branch"
        )

        resolved = usecase.resolve_inspect_base(None, current_branch="task/child")

        assert resolved.base_branch == "task/active-branch"
        assert resolved.auto_detected is True
        mock_merged.assert_called_once_with("task/active-branch")


def test_resolve_base_prefers_creation_source_for_parent_token() -> None:
    """creation_source should take precedence over dynamic parent detection."""
    parent_finder = MagicMock(return_value="feature/dynamic-parent")
    usecase = BaseResolutionUsecase(parent_branch_finder=parent_finder)

    resolved = usecase.resolve_base(
        requested_base=None,
        current_branch="task/child",
        default_policy="parent",
        creation_source="origin/main",
    )

    assert resolved.base_branch == "origin/main"
    assert resolved.auto_detected is False
    parent_finder.assert_not_called()


def test_resolve_base_falls_back_to_parent_detection_without_creation_source() -> None:
    """Without creation_source, parent token falls back to dynamic detection."""
    usecase = BaseResolutionUsecase(parent_branch_finder=lambda branch: "feature/root")

    resolved = usecase.resolve_base(
        requested_base=None,
        current_branch="task/child",
        default_policy="parent",
        creation_source=None,
    )

    assert resolved.base_branch == "feature/root"
    assert resolved.auto_detected is True


def test_resolve_base_ignores_creation_source_for_non_parent_token() -> None:
    """creation_source must not override an explicit non-parent base token."""
    usecase = BaseResolutionUsecase(parent_branch_finder=lambda branch: "feature/root")

    resolved = usecase.resolve_base(
        requested_base="main",
        current_branch="task/child",
        default_policy="parent",
        creation_source="origin/develop",
    )

    assert resolved.base_branch == "origin/main"


def test_resolve_inspect_base_prefers_creation_source() -> None:
    """resolve_inspect_base should forward creation_source to resolve_base."""
    parent_finder = MagicMock(return_value="feature/dynamic-parent")
    usecase = BaseResolutionUsecase(parent_branch_finder=parent_finder)

    resolved = usecase.resolve_inspect_base(
        None, current_branch="task/child", creation_source="origin/main"
    )

    assert resolved.base_branch == "origin/main"
    assert resolved.auto_detected is False
    parent_finder.assert_not_called()


def test_resolve_review_base_prefers_creation_source() -> None:
    """resolve_review_base should forward creation_source to resolve_base."""
    parent_finder = MagicMock(return_value="feature/dynamic-parent")
    usecase = BaseResolutionUsecase(parent_branch_finder=parent_finder)

    resolved = usecase.resolve_review_base(
        None, current_branch="task/child", creation_source="origin/main"
    )

    assert resolved.base_branch == "origin/main"
    assert resolved.auto_detected is False
    parent_finder.assert_not_called()


def test_try_get_pr_base_returns_base_when_pr_exists() -> None:
    """Should return PR base when branch has open PR."""
    github_client = MagicMock()
    pr_response = MagicMock()
    pr_response.base_branch = "develop"
    github_client.get_pr.return_value = pr_response

    usecase = BaseResolutionUsecase(github_client=github_client)

    result = usecase._try_get_pr_base("task/review-branch")

    assert result == "origin/develop"
    github_client.get_pr.assert_called_once_with(branch="task/review-branch")


def test_try_get_pr_base_prefixes_origin_if_missing() -> None:
    """Should prefix base with origin/ if not already present."""
    github_client = MagicMock()
    pr_response = MagicMock()
    pr_response.base_branch = "develop"
    github_client.get_pr.return_value = pr_response

    usecase = BaseResolutionUsecase(github_client=github_client)

    result = usecase._try_get_pr_base("task/branch")

    assert result == "origin/develop"


def test_try_get_pr_base_preserves_origin_prefix() -> None:
    """Should not double-prefix if base already has origin/."""
    github_client = MagicMock()
    pr_response = MagicMock()
    pr_response.base_branch = "origin/develop"
    github_client.get_pr.return_value = pr_response

    usecase = BaseResolutionUsecase(github_client=github_client)

    result = usecase._try_get_pr_base("task/branch")

    assert result == "origin/develop"


def test_try_get_pr_base_returns_none_when_no_pr() -> None:
    """Should return None when no PR found for branch."""
    github_client = MagicMock()
    github_client.get_pr.return_value = None

    usecase = BaseResolutionUsecase(github_client=github_client)

    result = usecase._try_get_pr_base("task/no-pr-branch")

    assert result is None


def test_try_get_pr_base_returns_none_when_pr_has_no_base() -> None:
    """Should return None when PR response lacks base_branch."""
    github_client = MagicMock()
    pr_response = MagicMock()
    pr_response.base_branch = None
    github_client.get_pr.return_value = pr_response

    usecase = BaseResolutionUsecase(github_client=github_client)

    result = usecase._try_get_pr_base("task/branch")

    assert result is None


def test_try_get_pr_base_handles_exceptions_gracefully() -> None:
    """Should return None on any exception (network, auth, etc.)."""
    github_client = MagicMock()
    github_client.get_pr.side_effect = Exception("Network error")

    usecase = BaseResolutionUsecase(github_client=github_client)

    result = usecase._try_get_pr_base("task/branch")

    assert result is None


def test_resolve_base_falls_back_to_pr_base_when_no_creation_source() -> None:
    """When creation_source missing, should try PR base before parent detection."""
    github_client = MagicMock()
    pr_response = MagicMock()
    pr_response.base_branch = "develop"
    github_client.get_pr.return_value = pr_response

    parent_finder = MagicMock(return_value="feature/wrong-parent")
    usecase = BaseResolutionUsecase(
        parent_branch_finder=parent_finder,
        github_client=github_client,
    )

    resolved = usecase.resolve_base(
        requested_base=None,
        current_branch="task/review-branch",
        default_policy="parent",
        creation_source=None,
    )

    # Should use PR base, not parent_finder
    assert resolved.base_branch == "origin/develop"
    assert resolved.auto_detected is False
    parent_finder.assert_not_called()


def test_resolve_base_falls_back_to_parent_when_pr_base_fails() -> None:
    """When PR base lookup fails, should fall back to parent detection."""
    github_client = MagicMock()
    github_client.get_pr.return_value = None

    usecase = BaseResolutionUsecase(
        parent_branch_finder=lambda branch: "feature/parent",
        github_client=github_client,
    )

    resolved = usecase.resolve_base(
        requested_base=None,
        current_branch="task/branch",
        default_policy="parent",
        creation_source=None,
    )

    # Should fall back to parent detection
    assert resolved.base_branch == "feature/parent"
    assert resolved.auto_detected is True
