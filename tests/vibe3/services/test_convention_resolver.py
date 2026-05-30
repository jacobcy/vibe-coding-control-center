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
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from vibe3.exceptions import GitError
from vibe3.services.convention_resolver import ConventionResolver


def test_resolver_returns_minimal_defaults_by_default():
    """Test resolver returns minimal defaults when no profile specified."""
    # Mock git remote to return non-vibe-center repo and config file to not exist
    with (
        patch(
            "vibe3.clients.git_client.GitClient.get_git_common_dir"
        ) as mock_git_common_dir,
        patch("subprocess.run") as mock_run,
        patch("pathlib.Path.exists") as mock_exists,
    ):
        mock_git_common_dir.return_value = "/tmp/test/.git"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="https://github.com/other/repo.git\n"
        )
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
        patch("subprocess.run") as mock_run,
        patch("pathlib.Path.exists") as mock_exists,
    ):
        mock_git_common_dir.return_value = "/tmp/test/.git"
        mock_run.return_value = MagicMock(
            returncode=0, stdout="https://github.com/jacobcy/vibe-center.git\n"
        )
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
        patch("subprocess.run") as mock_run,
    ):
        mock_git_common_dir.side_effect = GitError("rev-parse", "not a git repository")
        mock_run.return_value = MagicMock(
            returncode=0, stdout="https://github.com/jacobcy/vibe-center.git\n"
        )
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
    from vibe3.config import ProfileConvention

    convention = ProfileConvention(state_prefix="")
    assert convention.state_label("handoff") == "handoff"
