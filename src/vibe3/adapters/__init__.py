"""Adapter registry for vibe3 distributions."""

from vibe3.config.adapter_manifest import AdapterManifest

# Registry of known adapters
_ADAPTERS: dict[str, AdapterManifest] = {}


def register_adapter(manifest: AdapterManifest) -> None:
    """Register an adapter manifest.

    Args:
        manifest: Adapter manifest to register
    """
    _ADAPTERS[manifest.name] = manifest


def get_adapter(name: str) -> AdapterManifest | None:
    """Get a registered adapter by name.

    Args:
        name: Adapter name

    Returns:
        Adapter manifest or None if not found
    """
    return _ADAPTERS.get(name)


def list_adapters() -> list[str]:
    """List all registered adapter names.

    Returns:
        List of adapter names
    """
    return list(_ADAPTERS.keys())
