"""Repository-level Review Kernel manifest guards."""

from pathlib import Path

from vibe3.analysis.review_kernel import load_review_kernel
from vibe3.runtime import MODULE_CATEGORY_MAP, ModuleCategory


def test_review_kernel_manifest_paths_exist_and_are_unique() -> None:
    manifest = load_review_kernel(Path("config/v3/review_kernel.yaml"))
    paths = [entry.path for entry in manifest.entries]

    assert len(paths) == len(set(paths))
    assert all(Path(path).is_file() for path in paths)


def test_every_architecture_kernel_file_is_in_review_manifest() -> None:
    manifest = load_review_kernel(Path("config/v3/review_kernel.yaml"))
    manifest_paths = {entry.path for entry in manifest.entries}
    architecture_paths = {
        path.as_posix()
        for package in ("runtime", "orchestra")
        for path in (Path("src/vibe3") / package).rglob("*.py")
        if path.name != "__init__.py"
    }

    assert architecture_paths <= manifest_paths


def test_review_manifest_architecture_packages_match_taxonomy() -> None:
    manifest = load_review_kernel(Path("config/v3/review_kernel.yaml"))
    taxonomy_packages = {
        name
        for name, category in MODULE_CATEGORY_MAP.items()
        if category == ModuleCategory.KERNEL
    }

    assert set(manifest.architecture_packages) == taxonomy_packages
