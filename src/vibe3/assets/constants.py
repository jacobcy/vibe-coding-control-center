"""Global assets constants and directory contract."""

from pathlib import Path

# Global assets directory under user home
ASSETS_DIR = Path.home() / ".vibe" / "assets"

# Asset manifest version (semver)
ASSETS_VERSION = "1.0.0"

# Stable asset type keys for resolver lookup
ASSET_TYPES = ("prompts", "templates", "policies", "models", "manifests")
