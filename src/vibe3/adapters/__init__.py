"""Adapter registry for vibe3 distributions."""

from vibe3.clients import GitClient, runtime_assets_root
from vibe3.models import AdapterManifest

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
    # Lazy load and build vibe-center adapter
    if name == "vibe-center" and "vibe-center" not in _LOADED:
        from vibe3.adapters.vibe_center import _build_vibe_center_manifest

        # Resolve git_common_dir
        git_common_dir = None
        try:
            git_common_dir = GitClient().get_git_common_dir()
        except Exception:
            pass

        manifest = _build_vibe_center_manifest(
            git_common_dir=git_common_dir,
            global_skills=runtime_assets_root() / "skills",
        )
        _ADAPTERS[manifest.name] = manifest
        _LOADED.add(manifest.name)

    # Lazy load and build github-flow adapter
    if name == "github-flow" and "github-flow" not in _LOADED:
        from vibe3.adapters.github_flow import _build_github_flow_manifest

        manifest = _build_github_flow_manifest(
            global_skills=runtime_assets_root() / "skills",
        )
        _ADAPTERS[manifest.name] = manifest
        _LOADED.add(manifest.name)

    return _ADAPTERS.get(name)


def list_adapters() -> list[str]:
    """List all registered adapter names.

    Returns:
        List of adapter names
    """
    return list(_ADAPTERS.keys())


__all__ = [
    "register_adapter",
    "get_adapter",
    "list_adapters",
]
