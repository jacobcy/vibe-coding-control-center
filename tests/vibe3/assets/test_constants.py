from vibe3.assets.constants import ASSET_TYPES, ASSETS_DIR, ASSETS_VERSION


def test_assets_dir_is_user_global():
    """Assets directory must be under user home."""
    assert ASSETS_DIR.is_absolute()
    assert ".vibe" in str(ASSETS_DIR)
    assert "assets" in str(ASSETS_DIR)


def test_assets_version_is_semver():
    """Assets version must follow semver format."""
    assert isinstance(ASSETS_VERSION, str)
    parts = ASSETS_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_asset_types_are_stable():
    """Asset types must be stable keys for future resolver usage."""
    expected = {"prompts", "templates", "policies", "models", "manifests"}
    assert set(ASSET_TYPES) == expected
