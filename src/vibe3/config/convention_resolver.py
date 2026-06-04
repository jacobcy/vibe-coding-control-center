"""ConventionResolver service for centralized convention lookup.

This module provides a single source of truth for all profile-based
convention lookups, replacing scattered hardcoded patterns throughout
the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.config.profile_convention import ProfileConvention

if TYPE_CHECKING:
    from vibe3.config.profile_config import ProfileConfig


@dataclass
class ConventionResolver:
    """Central resolver for profile-based conventions.

    Provides a single source of truth for all convention lookups,
    replacing scattered hardcoded patterns throughout the codebase.

    Resolution order:
        1. Repo config (.vibe/config.yaml) - not yet implemented
        2. Profile defaults (vibe-center, minimal, github-flow)
        3. Builtin fallback (minimal)

    Attributes:
        profile: Optional profile name override (vibe-center, minimal, github-flow)

    Example:
        >>> resolver = ConventionResolver.from_repo()
        >>> convention = resolver.resolve()
        >>> convention.branch.task_prefix
        'task/issue-'
        >>> convention.state_label("handoff")
        'state/handoff'
    """

    profile: str | None = None

    def resolve(self) -> ProfileConvention:
        """Resolve the effective convention for current repo.

        Returns the ProfileConvention based on repo configuration or defaults.
        Uses environment variable VIBE_PROFILE or checks git remote to determine
        profile. Falls back to minimal (portable) defaults if no profile specified.

        Returns:
            ProfileConvention instance with resolved conventions.

        Example:
            >>> resolver = ConventionResolver.from_repo()
            >>> convention = resolver.resolve()
            >>> convention.branch.canonical_branch(123)
            'issue-123'
        """
        # Use helper to detect profile name
        detected = self._detect_profile()

        # Map profile name to ProfileConvention
        if detected == "vibe-center":
            logger.debug("Using Vibe Center profile defaults")
            return ProfileConvention.vibe_center()
        elif detected in {"minimal", "github-flow"}:
            logger.debug(f"Using {detected} profile defaults")
            return ProfileConvention()
        else:
            # Unknown profile: warn and fallback
            logger.warning(f"Unknown profile '{detected}', using minimal defaults")
            return ProfileConvention()

    def _detect_profile(self) -> str:
        """Detect profile from repo context.

        Single source of truth for profile detection logic, used by both
        resolve() and _get_profile_config().

        Returns:
            Profile name (vibe-center or minimal)
        """
        import os
        import subprocess

        import yaml

        # Step 1: Check explicit override
        if self.profile:
            return self.profile

        # Step 2: Check environment variable
        env_profile = os.getenv("VIBE_PROFILE")
        if env_profile:
            return env_profile

        # Step 3: Check .vibe/config.yaml for profile field
        try:
            from pathlib import Path

            from vibe3.clients.git_client import GitClient
            from vibe3.exceptions import GitError

            # Resolve relative path against repo root for CWD-independent access
            git_client = GitClient()
            git_common_dir = git_client.get_git_common_dir()
            repo_root = Path(git_common_dir).parent if git_common_dir else Path.cwd()
            config_path = repo_root / ".vibe/config.yaml"
            if config_path.exists():
                with config_path.open(encoding="utf-8") as f:
                    config_yaml = yaml.safe_load(f)
                    if isinstance(config_yaml, dict) and "profile" in config_yaml:
                        return str(config_yaml["profile"])
        except OSError as e:
            logger.debug(f"Failed to read .vibe/config.yaml: {e}")
        except yaml.YAMLError as e:
            logger.debug(f"Invalid YAML in .vibe/config.yaml: {e}")
        except GitError as e:
            logger.debug(f"Failed to resolve git common dir for .vibe/config.yaml: {e}")

        # Step 4: Check git remote to detect Vibe Center repo
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            if result.returncode == 0:
                remote_url = result.stdout.strip().lower()
                if (
                    "vibe-center" in remote_url
                    or "vibe-coding-control-center" in remote_url
                ):
                    return "vibe-center"
        except Exception as e:
            logger.debug(f"Git remote check failed: {e}")

        # Step 5: Default to minimal
        return "minimal"

    def get_policy_path(self, name: str) -> str | None:
        """Get path to a policy file for current profile.

        Args:
            name: Policy name

        Returns:
            Relative path or None
        """
        return self._get_profile_config().get_policy_path(name)

    def get_skill_path(self, name: str) -> str | None:
        """Get path to a skill for current profile.

        Args:
            name: Skill name

        Returns:
            Relative path or None
        """
        return self._get_profile_config().get_skill_path(name)

    def get_supervisor_path(self, name: str = "apply") -> str | None:
        """Get path to supervisor template for current profile.

        Args:
            name: Template name (default: 'apply')

        Returns:
            Relative path or None
        """
        return self._get_profile_config().get_supervisor_path(name)

    def _get_profile_config(self) -> ProfileConfig:
        """Get ProfileConfig with detected profile.

        Helper to reduce repeated ProfileConfig instantiation pattern.

        Returns:
            ProfileConfig instance with detected or explicit profile.
        """
        from vibe3.adapters import get_adapter
        from vibe3.config.profile_config import ProfileConfig

        detected_profile = self.profile or self._detect_profile()
        return ProfileConfig(profile=detected_profile, adapter_resolver=get_adapter)

    @classmethod
    def from_repo(cls, profile: str | None = None) -> "ConventionResolver":
        """Create resolver from current repo context.

        Factory method that creates a ConventionResolver instance
        configured for the current repository.

        Args:
            profile: Optional profile name override

        Returns:
            ConventionResolver instance configured for current repo.

        Example:
            >>> resolver = ConventionResolver.from_repo()
            >>> convention = resolver.resolve()
        """
        logger.debug(
            f"Creating ConventionResolver from repo context (profile={profile})"
        )
        return cls(profile=profile)


def diagnose_profile() -> str:
    """Get current profile name for diagnostic context.

    Returns:
        Profile name or "unknown" if resolution fails
    """
    try:
        resolver = ConventionResolver.from_repo()
        return resolver._detect_profile()
    except Exception:
        return "unknown"
