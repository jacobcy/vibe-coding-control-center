"""Tests for ConventionResolver service.

Tests verify that:
1. Resolver returns minimal defaults when no profile specified
2. Resolver returns vibe-center defaults when profile is specified
3. Resolver detects Vibe Center repo via git remote
4. Resolved convention is immutable (frozen Pydantic model)
5. Convention can be used for branch/label generation
6. Unknown profile falls back to minimal
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from vibe3.clients.git_client import GitClient
from vibe3.config.convention_resolver import ConventionResolver
from vibe3.exceptions import GitError


def test_resolver_returns_minimal_defaults_by_default():
    """Test resolver returns minimal defaults when no profile specified."""
    # Mock git remote to return non-vibe-center repo and config file to not exist
    with (
        patch(
            "vibe3.clients.git_client.GitClient.get_git_common_dir"
        ) as mock_git_common_dir,
        patch.object(
            GitClient,
            "get_remote_url",
            return_value="https://github.com/other/repo.git",
        ),
        patch("pathlib.Path.exists") as mock_exists,
    ):
        mock_git_common_dir.return_value = "/tmp/test/.git"
        mock_exists.return_value = False  # No .vibe/config.yaml
        resolver = ConventionResolver.from_repo()
        convention = resolver.resolve()
        assert convention.branch.task_prefix == "issue-"
        assert convention.manager_usernames == ()
        assert convention.state_prefix == "state/"


def test_resolver_returns_vibe_center_when_profile_specified():
    """Test resolver returns Vibe Center defaults when profile='vibe-center'."""
    resolver = ConventionResolver.from_repo(profile="vibe-center")
    convention = resolver.resolve()
    assert convention.branch.task_prefix == "task/issue-"
    assert convention.manager_usernames == ("vibe-manager-agent",)


def test_resolver_returns_minimal_when_profile_specified():
    """Test resolver returns minimal defaults when profile='minimal'."""
    resolver = ConventionResolver.from_repo(profile="minimal")
    convention = resolver.resolve()
    assert convention.branch.task_prefix == "issue-"
    assert convention.manager_usernames == ()


def test_resolver_accepts_github_flow_without_unknown_profile_warning():
    """Test github-flow is a known portable profile."""
    resolver = ConventionResolver.from_repo(profile="github-flow")

    with patch("vibe3.config.convention_resolver.logger.warning") as mock_warning:
        convention = resolver.resolve()

    assert convention.branch.task_prefix == "issue-"
    assert convention.manager_usernames == ()
    mock_warning.assert_not_called()


def test_resolver_unknown_profile_falls_back_to_minimal():
    """Test resolver falls back to minimal for unknown profile."""
    resolver = ConventionResolver.from_repo(profile="unknown")
    convention = resolver.resolve()
    assert convention.branch.task_prefix == "issue-"
    assert convention.manager_usernames == ()


def test_resolver_uses_vibe_profile_env_var():
    """Test resolver respects VIBE_PROFILE environment variable."""
    with patch.dict(os.environ, {"VIBE_PROFILE": "vibe-center"}):
        resolver = ConventionResolver.from_repo()
        convention = resolver.resolve()
        assert convention.branch.task_prefix == "task/issue-"


def test_resolver_detects_vibe_center_repo():
    """Test resolver detects Vibe Center repo via git remote."""
    # Mock config file to not exist so git remote detection is tested
    with (
        patch(
            "vibe3.clients.git_client.GitClient.get_git_common_dir"
        ) as mock_git_common_dir,
        patch.object(
            GitClient,
            "get_remote_url",
            return_value="https://github.com/jacobcy/vibe-center.git",
        ),
        patch("pathlib.Path.exists") as mock_exists,
    ):
        mock_git_common_dir.return_value = "/tmp/test/.git"
        mock_exists.return_value = False  # No .vibe/config.yaml
        resolver = ConventionResolver.from_repo()
        convention = resolver.resolve()
        assert convention.branch.task_prefix == "task/issue-"


def test_resolver_falls_back_when_git_common_dir_lookup_fails():
    """Test resolver fallback when git common dir lookup raises GitError."""
    with (
        patch(
            "vibe3.clients.git_client.GitClient.get_git_common_dir"
        ) as mock_git_common_dir,
        patch.object(
            GitClient,
            "get_remote_url",
            return_value="https://github.com/jacobcy/vibe-center.git",
        ),
    ):
        mock_git_common_dir.side_effect = GitError("rev-parse", "not a git repository")
        resolver = ConventionResolver.from_repo()
        convention = resolver.resolve()
        assert convention.branch.task_prefix == "task/issue-"


def test_resolver_returns_immutable_convention():
    """Test that resolved convention is immutable (frozen Pydantic model)."""
    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    with pytest.raises(ValidationError):
        convention.handoff_label = "changed"


def test_convention_used_for_branch_generation():
    """Test vibe-center convention can generate branch names."""
    resolver = ConventionResolver(profile="vibe-center")
    convention = resolver.resolve()
    assert convention.branch.canonical_branch(123) == "task/issue-123"
    assert convention.state_label("handoff") == "state/handoff"


def test_convention_no_prefix_state_label():
    """Test state_label with empty prefix."""
    from vibe3.config.profile_convention import ProfileConvention

    convention = ProfileConvention(state_prefix="")
    assert convention.state_label("handoff") == "handoff"


def test_detect_profile_is_cached():
    """Test that _detect_profile result is cached to avoid repeated subprocess calls."""
    with (
        patch(
            "vibe3.clients.git_client.GitClient.get_git_common_dir"
        ) as mock_git_common_dir,
        patch.object(
            GitClient,
            "get_remote_url",
            return_value="https://github.com/other/repo.git",
        ) as mock_get_remote_url,
        patch("pathlib.Path.exists") as mock_exists,
    ):
        mock_git_common_dir.return_value = "/tmp/test/.git"
        mock_exists.return_value = False

        resolver = ConventionResolver.from_repo()

        # Call resolve twice
        convention1 = resolver.resolve()
        convention2 = resolver.resolve()

        # Both should succeed
        assert convention1.branch.task_prefix == "issue-"
        assert convention2.branch.task_prefix == "issue-"

        # get_remote_url should only be called once due to caching
        assert mock_get_remote_url.call_count == 1


def test_detect_profile_cache_invalidation():
    """Test that cache can be cleared by creating a new resolver instance."""
    with (
        patch(
            "vibe3.clients.git_client.GitClient.get_git_common_dir"
        ) as mock_git_common_dir,
        patch.object(
            GitClient,
            "get_remote_url",
            return_value="https://github.com/other/repo.git",
        ) as mock_get_remote_url,
        patch("pathlib.Path.exists") as mock_exists,
    ):
        mock_git_common_dir.return_value = "/tmp/test/.git"
        mock_exists.return_value = False

        # First resolver instance
        resolver1 = ConventionResolver.from_repo()
        convention1 = resolver1.resolve()

        # Second resolver instance (fresh cache)
        resolver2 = ConventionResolver.from_repo()
        convention2 = resolver2.resolve()

        # Both should work independently
        assert convention1.branch.task_prefix == "issue-"
        assert convention2.branch.task_prefix == "issue-"

        # Each instance should call get_remote_url once
        assert mock_get_remote_url.call_count == 2
