"""ConventionResolver service for centralized convention lookup.

This module provides a single source of truth for all profile-based
convention lookups, replacing scattered hardcoded patterns throughout
the codebase.
"""

from dataclasses import dataclass

from loguru import logger

from vibe3.config.profile_convention import ProfileConvention


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
        import os
        import subprocess

        # Step 1: Check explicit profile override
        if self.profile:
            if self.profile == "vibe-center":
                logger.debug("Using Vibe Center profile defaults (explicit)")
                return ProfileConvention.vibe_center()
            elif self.profile == "minimal":
                logger.debug("Using minimal profile defaults (explicit)")
                return ProfileConvention()
            else:
                logger.warning(
                    f"Unknown profile '{self.profile}', using minimal defaults"
                )
                return ProfileConvention()

        # Step 2: Check environment variable
        env_profile = os.getenv("VIBE_PROFILE")
        if env_profile == "vibe-center":
            logger.debug("Using Vibe Center profile defaults (VIBE_PROFILE)")
            return ProfileConvention.vibe_center()
        elif env_profile == "minimal":
            logger.debug("Using minimal profile defaults (VIBE_PROFILE)")
            return ProfileConvention()

        # Step 3: Check git remote to detect Vibe Center repo
        # Temporary heuristic until .vibe/config.yaml is implemented
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
                    logger.debug("Using Vibe Center profile defaults (detected repo)")
                    return ProfileConvention.vibe_center()
        except Exception:
            pass  # Ignore git errors, fall through to minimal

        # Step 4: Default to minimal (portable core runtime)
        logger.debug("Using minimal profile defaults (portable)")
        return ProfileConvention()

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

    def get_policy_path(self, policy_name: str) -> str | None:
        """Get policy file path for given policy name.

        Returns the path to a policy file based on the current profile.
        For vibe-center profile, returns repo-local .agent/policies/{policy_name}.md.
        For minimal profile, returns None (no policies by default).

        Args:
            policy_name: Policy name (plan, run, review, common)

        Returns:
            Path to policy file, or None if not available for current profile.

        Example:
            >>> resolver = ConventionResolver(profile="vibe-center")
            >>> resolver.get_policy_path("plan")
            '.agent/policies/plan.md'
        """
        # Vibe Center profile has repo-local policies
        if self.profile == "vibe-center" or (
            not self.profile and self._detect_vibe_center_repo()
        ):
            policy_path = f".agent/policies/{policy_name}.md"
            logger.debug(f"Using repo-local policy path: {policy_path}")
            return policy_path

        # Minimal profile has no default policies
        logger.debug(f"No policy path for profile: {self.profile or 'minimal'}")
        return None

    def _detect_vibe_center_repo(self) -> bool:
        """Detect if current repo is Vibe Center repo.

        Temporary heuristic until .vibe/config.yaml is implemented.

        Returns:
            True if repo appears to be Vibe Center repo.
        """
        import os
        import subprocess

        # Check environment variable
        env_profile = os.getenv("VIBE_PROFILE")
        if env_profile == "vibe-center":
            return True

        # Check git remote
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
                    return True
        except Exception:
            pass

        return False
