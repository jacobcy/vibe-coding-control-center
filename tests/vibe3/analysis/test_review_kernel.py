"""Review Kernel manifest and classification contract tests."""

from pathlib import Path

import pytest

from vibe3.analysis.review_kernel import (
    ReviewKernelConfigError,
    classify_review_kernel,
    load_review_kernel,
)


def _write_manifest(
    root: Path,
    entries: list[dict[str, object]],
) -> Path:
    import yaml

    path = root / "config" / "v3" / "review_kernel.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump({"version": 1, "entries": entries}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _entry(
    path: str,
    *,
    responsibilities: list[str] | None = None,
    review_floor: str = "focused",
) -> dict[str, object]:
    return {
        "path": path,
        "responsibilities": responsibilities or ["test_responsibility"],
        "reason": f"Protect {path}",
        "review_floor": review_floor,
    }


def _touch(root: Path, relative_path: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# fixture\n", encoding="utf-8")


def test_architecture_hit_is_large_and_repeated(tmp_path: Path) -> None:
    relative_path = "src/vibe3/runtime/heartbeat.py"
    _touch(tmp_path, relative_path)
    manifest_path = _write_manifest(
        tmp_path,
        [
            _entry(
                relative_path,
                responsibilities=["heartbeat_timer", "event_ingestion"],
                review_floor="repeated",
            )
        ],
    )

    manifest = load_review_kernel(manifest_path)
    kernel, review = classify_review_kernel({relative_path: {"committed"}}, manifest)

    assert kernel.status == "ready"
    assert kernel.impact == "large"
    assert kernel.architecture_hits[0].path == relative_path
    assert kernel.architecture_hits[0].sources == ["committed"]
    assert kernel.architecture_hits[0].responsibilities == [
        "heartbeat_timer",
        "event_ingestion",
    ]
    assert review.minimum_depth == "repeated"


def test_non_architecture_review_hit_is_small(tmp_path: Path) -> None:
    relative_path = "src/vibe3/config/loader.py"
    _touch(tmp_path, relative_path)
    manifest = load_review_kernel(_write_manifest(tmp_path, [_entry(relative_path)]))

    kernel, review = classify_review_kernel(
        {relative_path: {"unstaged", "staged"}}, manifest
    )

    assert kernel.impact == "small"
    assert kernel.architecture_hits == []
    assert kernel.review_hits[0].sources == ["staged", "unstaged"]
    assert review.minimum_depth == "focused"


def test_no_review_kernel_hit_is_none_and_normal(tmp_path: Path) -> None:
    protected_path = "src/vibe3/config/loader.py"
    _touch(tmp_path, protected_path)
    manifest = load_review_kernel(_write_manifest(tmp_path, [_entry(protected_path)]))

    kernel, review = classify_review_kernel({"docs/README.md": {"committed"}}, manifest)

    assert kernel.impact == "none"
    assert kernel.architecture_hits == []
    assert kernel.review_hits == []
    assert review.minimum_depth == "normal"


def test_manifest_rejects_directory_entry(tmp_path: Path) -> None:
    directory = "src/vibe3/services/"
    (tmp_path / directory).mkdir(parents=True)
    manifest_path = _write_manifest(tmp_path, [_entry(directory)])

    with pytest.raises(ReviewKernelConfigError, match="exact file"):
        load_review_kernel(manifest_path)


def test_manifest_rejects_duplicate_path(tmp_path: Path) -> None:
    relative_path = "src/vibe3/config/loader.py"
    _touch(tmp_path, relative_path)
    manifest_path = _write_manifest(
        tmp_path,
        [_entry(relative_path), _entry(relative_path)],
    )

    with pytest.raises(ReviewKernelConfigError, match="duplicate"):
        load_review_kernel(manifest_path)


def test_manifest_rejects_missing_file(tmp_path: Path) -> None:
    manifest_path = _write_manifest(
        tmp_path,
        [_entry("src/vibe3/config/missing.py")],
    )

    with pytest.raises(ReviewKernelConfigError, match="does not exist"):
        load_review_kernel(manifest_path)
