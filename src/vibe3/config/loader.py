"""Configuration loader for Vibe Center."""

import os
import re
from pathlib import Path
from typing import Any, cast

import yaml
from loguru import logger

from vibe3.config.settings import VibeConfig, _vibe3_config_root
from vibe3.exceptions import ConfigError


def _expand_variables(
    config: dict[str, Any], context: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Expand variable references in configuration values.

    Supports ${path.to.value} syntax for referencing other config values.
    Performs iterative expansion to handle nested references with cycle detection.
    Also expands ~ to home directory in path values.
    """
    from pathlib import Path

    if context is None:
        context = config

    result: dict[str, Any] = {}

    for key, value in config.items():
        if isinstance(value, str):
            # Expand ${...} variable references iteratively
            expanded = value
            max_iterations = 10  # Prevent infinite loops
            for _ in range(max_iterations):
                pattern = r"\$\{([^}]+)\}"

                def replace_var(match: re.Match[str]) -> str:
                    var_path = match.group(1)
                    # Navigate to referenced value
                    current: Any = context
                    for part in var_path.split("."):
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            # Variable not found, keep original reference
                            return match.group(0)
                    return (
                        str(current)
                        if not isinstance(current, dict)
                        else match.group(0)
                    )

                new_expanded = re.sub(pattern, replace_var, expanded)
                if new_expanded == expanded:
                    break  # No more changes, reached fixpoint
                expanded = new_expanded

            # Expand ~ to home directory for path values
            if expanded.startswith("~") or "/~" in expanded:
                expanded = str(Path(expanded).expanduser())

            result[key] = expanded
        elif isinstance(value, dict):
            result[key] = _expand_variables(value, context)
        else:
            result[key] = value

    return result


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence."""
    merged: dict[str, Any] = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value

    return merged


def load_yaml_config(path: Path, strict: bool = False) -> dict[str, Any]:
    """Load YAML configuration file.

    Args:
        path: Path to YAML file
        strict: If True, raise ConfigError for invalid YAML; if False, return empty dict

    Returns:
        Dictionary with config data, or empty dict if file doesn't exist
        (non-strict mode)

    Raises:
        ConfigError: If strict=True and file exists but is invalid YAML
    """
    if not path.exists():
        return {}

    try:
        with path.open(encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
            if isinstance(raw, dict):
                return cast(dict[str, Any], raw)
            return {}
    except yaml.YAMLError as exc:
        if strict:
            raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
        logger.bind(domain="config", action="load", path=str(path)).warning(
            f"Invalid YAML in config file: {exc}"
        )
        return {}
    except OSError as exc:
        if strict:
            raise ConfigError(f"Cannot read config file {path}: {exc}") from exc
        logger.bind(domain="config", action="load", path=str(path)).warning(
            f"Cannot read config file: {exc}"
        )
        return {}


def find_config_file() -> Path | None:
    """Find configuration file in standard locations.

    Search order:
    1. .vibe/config.yaml (project-specific)
    2. config/v3/settings.yaml (new default config)
    3. config/settings.yaml (deprecated fallback)
    4. config/v3/settings.yaml (vibe3 installation root fallback)
    5. ~/.vibe/config.yaml (global config)

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

    # Check for config/v3/settings.yaml (new path)
    new_config = Path("config/v3/settings.yaml")
    if new_config.exists():
        logger.bind(domain="config", action="find", path=str(new_config)).debug(
            "Found new default config"
        )
        return new_config

    # Check for config/settings.yaml (deprecated path)
    old_config = Path("config/settings.yaml")
    if old_config.exists():
        logger.bind(domain="config", action="find", path=str(old_config)).warning(
            "Using deprecated config path config/settings.yaml. "
            "Please migrate to config/v3/settings.yaml"
        )
        return old_config

    # Check vibe3 installation root as fallback (for cross-project invocation)
    import_root = _vibe3_config_root()
    root_config = import_root / "config" / "v3" / "settings.yaml"
    if root_config.exists() and root_config.resolve() != new_config.resolve():
        logger.bind(domain="config", action="find", path=str(root_config)).debug(
            "Found vibe3 installation config"
        )
        return root_config

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

    Configuration layers (priority order):
    1. Explicit config_path (if provided)
    2. Project config: .vibe/settings.yaml
    3. Global config: ~/.vibe/settings.yaml
    4. Repo fallback: config/v3/settings.yaml

    Args:
        config_path: Optional explicit path to config file.
                     If None, searches standard locations.

    Returns:
        VibeConfig instance with loaded or default values
    """
    logger.bind(domain="config", action="load", config_path=str(config_path)).debug(
        "Loading configuration"
    )

    # Load keys.env fallback (for direct Python invocation, tests, background services)
    # This is a no-op if shell wrapper already loaded keys.env
    load_keys_env_fallback()

    # Find config file if not provided
    if config_path is None:
        config_path = find_config_file()

    # Load with layering support
    if config_path and config_path.exists():
        # Determine the base config path
        # If explicit config_path is provided, treat it as highest priority
        # Otherwise, use repo fallback as base
        repo_config_path = Path("config/v3/settings.yaml")
        if not repo_config_path.exists():
            repo_config_path = _vibe3_config_root() / "config" / "v3" / "settings.yaml"

        # Check if config_path is auto-detected or explicit
        auto_detected = find_config_file()
        if config_path == auto_detected:
            # Auto-detected path, use standard layering with repo as base
            base_config_data: dict[str, Any] = load_yaml_config(repo_config_path)
        else:
            # Explicit config_path provided, use it as base
            base_config_data = load_yaml_config(config_path)

        # Load and merge other layers
        global_config_path = Path.home() / ".vibe" / "settings.yaml"
        project_config_path = Path(".vibe/settings.yaml")

        # Start with base config
        config_data = base_config_data

        # Merge global config with strict=True for user-provided layers
        if global_config_path.exists() and global_config_path != config_path:
            global_config = load_yaml_config(global_config_path, strict=True)
            config_data = _deep_merge(config_data, global_config)

        # Merge project config with strict=True for user-provided layers
        if project_config_path.exists() and project_config_path != config_path:
            project_config = load_yaml_config(project_config_path, strict=True)
            config_data = _deep_merge(config_data, project_config)

        # Expand variable references
        config_data = _expand_variables(config_data)

        # Apply supplementary loading (loc_limits + prompts)
        # This ensures we don't bypass VibeConfig.from_yaml() semantics
        # Pass repo_config_path as base for resolving supplementary files
        config_data = VibeConfig._load_supplementary(config_data, repo_config_path)

        try:
            config = VibeConfig(**config_data)
            logger.info(
                "Configuration loaded with layering",
                repo_config=str(repo_config_path),
                global_config=str(global_config_path),
                project_config=str(project_config_path),
                code_limits_v2_shell_total_loc=config.code_limits.total_file_loc.v2_shell,
                code_limits_v3_python_total_loc=config.code_limits.total_file_loc.v3_python,
            )
            return config
        except Exception as e:
            # Fail-fast: 配置文件存在但加载失败，立即抛出
            logger.error(
                "Failed to load config file",
                path=str(config_path),
                error=str(e),
            )
            raise ConfigError(f"Failed to load config file {config_path}: {e}") from e

    # Return default config (from migrated config paths when available)
    logger.info("Using default configuration")
    return VibeConfig.get_defaults()


def get_config_with_env_override(config: VibeConfig | None = None) -> VibeConfig:
    """Get configuration with environment variable overrides.

    Uses centralized env_override module for all override logic.
    See OVERRIDE_RULES for complete list of supported environment variables.

    Args:
        config: Optional existing config to override.
                If None, loads default config.

    Returns:
        VibeConfig with environment overrides applied
    """
    if config is None:
        config = load_config()

    # Apply centralized env overrides
    from vibe3.config.env_override import apply_env_overrides

    overridden = apply_env_overrides(config.model_dump())
    return config.__class__.model_validate(overridden)


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


def load_keys_env_fallback() -> None:
    """Load keys.env as fallback when shell wrapper hasn't loaded it.

    This function provides a Python-layer fallback for loading keys.env,
    used in scenarios where the shell wrapper isn't invoked:

    1. Direct Python CLI invocation (uv run python src/vibe3/cli.py)
    2. Test environments
    3. Orchestra background service processes

    Priority (same as shell wrapper):
    1. Project config/keys.env
    2. ~/.vibe/config/keys.env
    3. ~/.vibe/keys.env (legacy)

    Only loads if environment variables aren't already set.
    Logs warning on failure (non-blocking, allows graceful degradation).
    """
    # Skip if any vibe env vars are already set (indicates shell wrapper loaded)
    if any(
        os.environ.get(key)
        for key in ["VIBE_MANAGER_GITHUB_TOKEN", "MANAGER_USERNAMES"]
    ):
        logger.bind(domain="config").debug(
            "keys.env fallback skipped: environment variables already present"
        )
        return

    # Try loading from standard locations
    from pathlib import Path

    keys_paths = [
        Path("config/keys.env"),  # Project-local
        Path.home() / ".vibe" / "config" / "keys.env",  # Global config
        Path.home() / ".vibe" / "keys.env",  # Legacy global
    ]

    for keys_path in keys_paths:
        if not keys_path.exists():
            continue

        try:
            with keys_path.open(encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    # Skip comments and empty lines
                    if not stripped or stripped.startswith("#"):
                        continue

                    # Parse KEY=VALUE
                    if "=" not in stripped:
                        continue

                    key, value = stripped.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")

                    # Only set if not already in environment
                    if key and not os.environ.get(key):
                        os.environ[key] = value

            logger.bind(domain="config", path=str(keys_path)).info(
                "Loaded keys.env fallback"
            )
            return  # Success, stop trying other paths

        except (OSError, UnicodeDecodeError) as e:
            logger.bind(domain="config", path=str(keys_path)).warning(
                f"Failed to read keys.env: {e}"
            )
            continue

    # No keys.env found (this is OK, user might use direnv or manual exports)
    logger.bind(domain="config").debug(
        "No keys.env found in standard locations, using existing environment"
    )
