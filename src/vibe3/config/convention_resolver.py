"""ConventionResolver service for centralized convention lookup.

This module provides a single source of truth for all profile-based
convention lookups, replacing scattered hardcoded patterns throughout
the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.config.env_override import get_env_override
from vibe3.config.profile_convention import ProfileConvention

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.config.profile_config import ProfileConfig
    from vibe3.models.adapter_manifest import AdapterManifest


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
        _profile_cache: Internal cache for detected profile
        _git_client: Optional injected GitClient instance (dependency injection)

    Example:
        >>> resolver = ConventionResolver.from_repo()
        >>> convention = resolver.resolve()
        >>> convention.branch.task_prefix
        'task/issue-'
        >>> convention.state_label("handoff")
        'state/handoff'
    """

    profile: str | None = None
    _profile_cache: str | None = None
    _git_client: GitClient | None = None
    _adapter_resolver: Callable[[str], "AdapterManifest | None"] | None = None

    def _get_git_client(self) -> GitClient:
        """Get GitClient instance with lazy initialization.

        Uses dependency injection pattern to break circular dependency
        between config and clients layers.

        Note: Not thread-safe. CLI is single-threaded so this is acceptable.

        Returns:
            GitClient instance (injected or lazy-loaded)
        """
        if self._git_client is None:
            from vibe3.clients.git_client import GitClient

            self._git_client = GitClient()
        return self._git_client

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

        Result is cached per instance to avoid repeated subprocess calls.

        Returns:
            Profile name (vibe-center or minimal)
        """
        # Check cache first
        if self._profile_cache is not None:
            return self._profile_cache

        import yaml

        # Step 1: Check explicit override
        if self.profile:
            result = self.profile
            self._profile_cache = result
            return result

        # Step 2: Check environment variable
        env_profile: str | None = get_env_override("VIBE_PROFILE")
        if env_profile:
            self._profile_cache = env_profile
            return env_profile

        # Step 3: Check .vibe/config.yaml for profile field
        try:
            from pathlib import Path

            # Delayed import to break circular dependency
            git_client = self._get_git_client()
            git_common_dir = git_client.get_git_common_dir()
            repo_root = Path(git_common_dir).parent if git_common_dir else Path.cwd()
            config_path = repo_root / ".vibe/config.yaml"
            if config_path.exists():
                with config_path.open(encoding="utf-8") as f:
                    config_yaml = yaml.safe_load(f)
                    if isinstance(config_yaml, dict) and "profile" in config_yaml:
                        result = str(config_yaml["profile"])
                        self._profile_cache = result
                        return result
        except OSError as e:
            logger.debug(f"Failed to read .vibe/config.yaml: {e}")
        except yaml.YAMLError as e:
            logger.debug(f"Invalid YAML in .vibe/config.yaml: {e}")
        except Exception as e:
            # Local import to avoid circular dep (config → exceptions)
            from vibe3.exceptions import GitError

            if not isinstance(e, GitError):
                raise
            logger.debug(f"Failed to resolve git common dir for .vibe/config.yaml: {e}")

        # Step 4: Check git remote to detect Vibe Center repo
        remote_url = self._get_git_client().get_remote_url()
        if remote_url:
            url_lower = remote_url.lower()
            if "vibe-center" in url_lower or "vibe-coding-control-center" in url_lower:
                self._profile_cache = "vibe-center"
                return "vibe-center"

        # Step 5: Default to minimal
        self._profile_cache = "minimal"
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
        from vibe3.config.profile_config import ProfileConfig

        detected_profile = self.profile or self._detect_profile()
        return ProfileConfig(
            profile=detected_profile, adapter_resolver=self._adapter_resolver
        )

    @classmethod
    def from_repo(
        cls,
        profile: str | None = None,
        git_client: GitClient | None = None,
        adapter_resolver: Callable[[str], "AdapterManifest | None"] | None = None,
    ) -> "ConventionResolver":
        """Create resolver from current repo context.

        Factory method that creates a ConventionResolver instance
        configured for the current repository.

        Args:
            profile: Optional profile name override
            git_client: Optional GitClient instance for dependency injection
            adapter_resolver: Optional adapter resolver function for
                dependency injection

        Returns:
            ConventionResolver instance configured for current repo.

        Example:
            >>> resolver = ConventionResolver.from_repo()
            >>> convention = resolver.resolve()
        """
        logger.debug(
            f"Creating ConventionResolver from repo context (profile={profile})"
        )
        return cls(
            profile=profile, _git_client=git_client, _adapter_resolver=adapter_resolver
        )


def diagnose_profile() -> str:
    """Get current profile name for diagnostic context.

    Returns:
        Profile name or "unknown" if resolution fails
    """
    try:
        resolver = get_resolver()
        return resolver._detect_profile()
    except Exception:
        return "unknown"


@cache
def get_convention() -> ProfileConvention:
    """Return cached ProfileConvention for the current repo.

    Safe to call repeatedly — profile detection runs only once per process.

    Returns:
        ProfileConvention instance with resolved conventions.

    Example:
        >>> convention = get_convention()
        >>> convention.branch.task_prefix
        'task/issue-'
    """
    return ConventionResolver.from_repo().resolve()


@cache
def get_resolver() -> ConventionResolver:
    """Return cached ConventionResolver for the current repo.

    Use when you need resolver methods (get_skill_path, get_supervisor_path, etc.).
    For convention data only, prefer get_convention().

    Returns:
        ConventionResolver instance configured for current repo.

    Example:
        >>> resolver = get_resolver()
        >>> resolver.get_skill_path("review")
        'skills/review/SKILL.md'
    """
    from vibe3.adapters import get_adapter

    return ConventionResolver.from_repo(adapter_resolver=get_adapter)
