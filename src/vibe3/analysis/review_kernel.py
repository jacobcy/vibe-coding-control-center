"""Repository-owned Review Kernel manifest and deterministic classifier."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from vibe3.models.inspect_evidence import (
    Diagnostic,
    KernelHit,
    KernelImpact,
    KernelObservation,
    ReviewDepth,
    ReviewPolicy,
)
from vibe3.runtime.taxonomy import MODULE_CATEGORY_MAP, ModuleCategory


class ReviewKernelConfigError(ValueError):
    """Raised when the repository Review Kernel manifest is invalid."""


class ReviewKernelEntry(BaseModel):
    """One exact protected file and its review policy."""

    path: str
    responsibilities: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    review_floor: ReviewDepth


class ReviewKernelManifest(BaseModel):
    """Versioned collection of exact Review Kernel entries."""

    version: int = 1
    entries: list[ReviewKernelEntry]


_DEPTH_RANK = {
    ReviewDepth.NORMAL: 0,
    ReviewDepth.FOCUSED: 1,
    ReviewDepth.REPEATED: 2,
}


def _repo_root_for_manifest(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.parent.name == "v3" and resolved.parent.parent.name == "config":
        return resolved.parent.parent.parent
    return Path.cwd().resolve()


def _validate_entry_path(entry: ReviewKernelEntry, repo_root: Path) -> None:
    raw_path = entry.path
    pure_path = PurePosixPath(raw_path)
    if (
        raw_path.endswith("/")
        or pure_path.is_absolute()
        or ".." in pure_path.parts
        or any(character in raw_path for character in "*?[]")
    ):
        raise ReviewKernelConfigError(
            f"Review Kernel path must be an exact file: {raw_path}"
        )
    target = repo_root / pure_path
    if not target.is_file():
        if target.is_dir():
            raise ReviewKernelConfigError(
                f"Review Kernel path must be an exact file: {raw_path}"
            )
        raise ReviewKernelConfigError(f"Review Kernel path does not exist: {raw_path}")


def load_review_kernel(path: Path) -> ReviewKernelManifest:
    """Load and validate an exact-file Review Kernel manifest."""

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifest = ReviewKernelManifest.model_validate(payload)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ReviewKernelConfigError(f"Invalid Review Kernel manifest: {exc}") from exc

    repo_root = _repo_root_for_manifest(path)
    seen: set[str] = set()
    for entry in manifest.entries:
        if entry.path in seen:
            raise ReviewKernelConfigError(
                f"Review Kernel contains duplicate path: {entry.path}"
            )
        seen.add(entry.path)
        _validate_entry_path(entry, repo_root)
    return manifest


def is_architecture_path(path: str) -> bool:
    """Return whether a repo-relative path belongs to strict runtime kernel."""

    parts = PurePosixPath(path).parts
    if len(parts) < 4 or parts[:2] != ("src", "vibe3"):
        return False
    package = parts[2]
    return MODULE_CATEGORY_MAP.get(package) == ModuleCategory.KERNEL


def _hit(entry: ReviewKernelEntry, sources: set[str]) -> KernelHit:
    return KernelHit(
        path=entry.path,
        responsibilities=entry.responsibilities,
        reason=entry.reason,
        review_floor=entry.review_floor,
        sources=sorted(sources),
    )


def _max_depth(current: ReviewDepth, candidate: ReviewDepth) -> ReviewDepth:
    return candidate if _DEPTH_RANK[candidate] > _DEPTH_RANK[current] else current


def classify_review_kernel(
    changed_paths: dict[str, set[str]],
    manifest: ReviewKernelManifest,
) -> tuple[KernelObservation, ReviewPolicy]:
    """Classify changed paths without dependency or runtime inference."""

    entries = {entry.path: entry for entry in manifest.entries}
    architecture_hits: list[KernelHit] = []
    review_hits: list[KernelHit] = []
    diagnostics: list[Diagnostic] = []
    minimum_depth = ReviewDepth.NORMAL

    for path in sorted(changed_paths):
        sources = changed_paths[path]
        entry = entries.get(path)
        architecture = is_architecture_path(path)
        if entry is None:
            if architecture:
                minimum_depth = ReviewDepth.REPEATED
                diagnostics.append(
                    Diagnostic(
                        code="missing_manifest_entry",
                        message="Architecture Kernel file is not registered",
                        path=path,
                    )
                )
            continue
        hit = _hit(entry, sources)
        minimum_depth = _max_depth(minimum_depth, entry.review_floor)
        if architecture:
            architecture_hits.append(hit)
            minimum_depth = ReviewDepth.REPEATED
        else:
            review_hits.append(hit)

    has_architecture_change = any(is_architecture_path(path) for path in changed_paths)
    if has_architecture_change:
        impact = KernelImpact.LARGE
    elif review_hits:
        impact = KernelImpact.SMALL
    else:
        impact = KernelImpact.NONE

    status: Literal["ready", "unavailable"] = "unavailable" if diagnostics else "ready"
    reasons = [hit.reason for hit in [*architecture_hits, *review_hits]]
    reasons.extend(diagnostic.message for diagnostic in diagnostics)
    return (
        KernelObservation(
            status=status,
            impact=impact,
            architecture_hits=architecture_hits,
            review_hits=review_hits,
            diagnostics=diagnostics,
        ),
        ReviewPolicy(minimum_depth=minimum_depth, reasons=reasons),
    )
