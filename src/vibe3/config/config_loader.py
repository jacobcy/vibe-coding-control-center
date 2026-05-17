"""Configuration loader placeholder for future .vibe/config.yaml support.

This is a minimal placeholder that will be implemented in Issue #934
to support profile-based configuration loading.

For now, it provides a no-op implementation that ConventionResolver
can use while maintaining the specified API contract.
"""


class ConfigLoader:
    """Placeholder for configuration loading.

    Future implementation (Issue #934) will:
    - Read .vibe/config.yaml
    - Parse profile selection
    - Provide configuration values to ConventionResolver

    Current implementation returns empty config (no values).
    """

    def load(self) -> dict:
        """Load configuration from .vibe/config.yaml.

        Returns:
            Empty dict for now (placeholder implementation)

        Note:
            Issue #934 will implement actual YAML loading and parsing.
        """
        # Placeholder: return empty config
        # Future: load from .vibe/config.yaml
        return {}
