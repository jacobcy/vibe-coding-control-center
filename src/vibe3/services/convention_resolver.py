"""ConventionResolver service for centralized convention lookup.

This module provides a single source of truth for all profile-based
convention lookups, replacing scattered hardcoded patterns throughout
the codebase.
"""

from dataclasses import dataclass

from loguru import logger

from vibe3.config.config_loader import ConfigLoader
from vibe3.config.profile_convention import ProfileConvention


@dataclass
class ConventionResolver:
    """Central resolver for profile-based conventions.

    Provides a single source of truth for all convention lookups,
    replacing scattered hardcoded patterns throughout the codebase.

    Resolution order:
        1. Repo config (.vibe/config.yaml)
        2. Profile defaults (vibe-center, minimal, github-flow)
        3. Builtin fallback (minimal)

    Attributes:
        config_loader: Configuration loader for reading .vibe/config.yaml

    Example:
        >>> resolver = ConventionResolver.from_repo()
        >>> convention = resolver.resolve()
        >>> convention.branch.task_prefix
        'task/issue-'
        >>> convention.state_label("handoff")
        'state/handoff'
    """

    config_loader: ConfigLoader

    def resolve(self) -> ProfileConvention:
        """Resolve the effective convention for current repo.

        Returns the ProfileConvention based on repo configuration or defaults.
        Currently returns Vibe Center defaults; future implementation will
        read profile from config.

        Returns:
            ProfileConvention instance with resolved conventions.

        Example:
            >>> resolver = ConventionResolver.from_repo()
            >>> convention = resolver.resolve()
            >>> convention.branch.canonical_branch(123)
            'task/issue-123'
        """
        # TODO: Read profile from config
        # For now, return Vibe Center defaults for current repo
        logger.debug("Resolving convention (using Vibe Center defaults)")
        return ProfileConvention.vibe_center()

    @classmethod
    def from_repo(cls) -> "ConventionResolver":
        """Create resolver from current repo context.

        Factory method that creates a ConventionResolver instance
        configured for the current repository.

        Returns:
            ConventionResolver instance configured for current repo.

        Example:
            >>> resolver = ConventionResolver.from_repo()
            >>> convention = resolver.resolve()
        """
        logger.debug("Creating ConventionResolver from repo context")
        return cls(config_loader=ConfigLoader())
