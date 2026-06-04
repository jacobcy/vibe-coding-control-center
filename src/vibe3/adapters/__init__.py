"""Adapter registry for vibe3 distributions."""

from vibe3.models.adapter_manifest import AdapterManifest

# Registry of known adapters
_ADAPTERS: dict[str, AdapterManifest] = {}

# Track which adapters have been loaded
_LOADED: set[str] = set()


def register_adapter(manifest: AdapterManifest) -> None:
    """Register an adapter manifest.

    Args:
        manifest: Adapter manifest to register
    """
    _ADAPTERS[manifest.name] = manifest
    _LOADED.add(manifest.name)


def get_adapter(name: str) -> AdapterManifest | None:
    """Get a registered adapter by name with lazy loading.

    Lazily imports built-in adapters on first access.

    Args:
        name: Adapter name

    Returns:
        Adapter manifest or None if not found
    """
    # Lazy import of built-in adapters
    if name == "vibe-center" and "vibe-center" not in _LOADED:
        import vibe3.adapters.vibe_center  # noqa: F401

    if name == "github-flow" and "github-flow" not in _LOADED:
        import vibe3.adapters.github_flow  # noqa: F401

    return _ADAPTERS.get(name)


def list_adapters() -> list[str]:
    """List all registered adapter names.

    Returns:
        List of adapter names
    """
    return list(_ADAPTERS.keys())


__all__ = [
    "AdapterManifest",
    "register_adapter",
    "get_adapter",
    "list_adapters",
]
