"""Configuration loader for Vibe Center."""

import os
from pathlib import Path

from loguru import logger

from vibe3.config.settings import VibeConfig


def find_config_file() -> Path | None:
    """Find configuration file in standard locations.

    Search order:
    1. .vibe/config.yaml (project-specific)
    2. config/settings.yaml (default config)
    3. ~/.vibe/config.yaml (global config)

    Returns:
        Path to config file or None if not found
    """
    # Check current directory for .vibe/config.yaml
    project_config = Path(".vibe/config.yaml")
    if project_config.exists():
        logger.bind(domain="config", action="find", path=str(project_config)).debug(
            "Found project config"
        )
        return project_config

    # Check for config/settings.yaml
    default_config = Path("config/settings.yaml")
    if default_config.exists():
        logger.bind(domain="config", action="find", path=str(default_config)).debug(
            "Found default config"
        )
        return default_config

    # Check global config
    global_config = Path.home() / ".vibe" / "config.yaml"
    if global_config.exists():
        logger.bind(domain="config", action="find", path=str(global_config)).debug(
            "Found global config"
        )
        return global_config

    logger.warning("No config file found, using defaults")
    return None


def load_config(config_path: Path | None = None) -> VibeConfig:
    """Load configuration from file or use defaults.

    Args:
        config_path: Optional explicit path to config file.
                     If None, searches standard locations.

    Returns:
        VibeConfig instance with loaded or default values
    """
    logger.bind(domain="config", action="load", config_path=str(config_path)).debug(
        "Loading configuration"
    )

    # Find config file if not provided
    if config_path is None:
        config_path = find_config_file()

    # Load from file if found
    if config_path and config_path.exists():
        try:
            config = VibeConfig.from_yaml(config_path)
            logger.info(
                "Configuration loaded from file",
                path=str(config_path),
                code_limits_v2_shell_total_loc=config.code_limits.v2_shell.total_loc,
                code_limits_v3_python_total_loc=config.code_limits.v3_python.total_loc,
            )
            return config
        except Exception as e:
            logger.error(
                "Failed to load config file, using defaults",
                path=str(config_path),
                error=str(e),
            )
            return VibeConfig()

    # Return default config
    logger.info("Using default configuration")
    return VibeConfig()


def get_config_with_env_override(config: VibeConfig | None = None) -> VibeConfig:
    """Get configuration with environment variable overrides.

    Environment variables:
    - VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC
    - VIBE_CODE_LIMITS_V3_PYTHON_TOTAL_LOC
    - VIBE_TEST_COVERAGE_SERVICES

    Args:
        config: Optional existing config to override.
                If None, loads default config.

    Returns:
        VibeConfig with environment overrides applied
    """
    if config is None:
        config = load_config()

    # Apply environment variable overrides
    if env_total_loc := os.getenv("VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC"):
        try:
            config.code_limits.v2_shell.total_loc = int(env_total_loc)
            logger.debug(
                "Applied env override",
                key="VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC",
                value=int(env_total_loc),
            )
        except ValueError:
            logger.warning(
                "Invalid env value, ignoring",
                key="VIBE_CODE_LIMITS_V2_SHELL_TOTAL_LOC",
                value=env_total_loc,
            )

    if env_total_loc := os.getenv("VIBE_CODE_LIMITS_V3_PYTHON_TOTAL_LOC"):
        try:
            config.code_limits.v3_python.total_loc = int(env_total_loc)
            logger.debug(
                "Applied env override",
                key="VIBE_CODE_LIMITS_V3_PYTHON_TOTAL_LOC",
                value=int(env_total_loc),
            )
        except ValueError:
            logger.warning(
                "Invalid env value, ignoring",
                key="VIBE_CODE_LIMITS_V3_PYTHON_TOTAL_LOC",
                value=env_total_loc,
            )

    if env_coverage := os.getenv("VIBE_TEST_COVERAGE_SERVICES"):
        try:
            config.quality.test_coverage.services = int(env_coverage)
            logger.debug(
                "Applied env override",
                key="VIBE_TEST_COVERAGE_SERVICES",
                value=int(env_coverage),
            )
        except ValueError:
            logger.warning(
                "Invalid env value, ignoring",
                key="VIBE_TEST_COVERAGE_SERVICES",
                value=env_coverage,
            )

    return config


# Global config instance (lazy loaded)
_config: VibeConfig | None = None


def get_config() -> VibeConfig:
    """Get global configuration instance.

    Returns:
        VibeConfig instance (loaded on first call)
    """
    global _config
    if _config is None:
        _config = get_config_with_env_override()
    return _config


def reload_config() -> VibeConfig:
    """Reload configuration from files.

    Returns:
        Newly loaded VibeConfig instance
    """
    global _config
    _config = None
    return get_config()
