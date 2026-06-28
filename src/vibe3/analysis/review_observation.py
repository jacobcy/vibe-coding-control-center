"""Build the evidence-only branch observation used by inspect base."""

from __future__ import annotations

from pathlib import Path

from vibe3.analysis.review_kernel import (
    ReviewKernelConfigError,
    classify_review_kernel,
    load_review_kernel,
)
from vibe3.clients import GitClient
from vibe3.exceptions import GitError
from vibe3.models.inspect_evidence import (
    ChangedFileFact,
    ChangeObservation,
    ChangePartitionSummary,
    ChangeSummary,
    ComparisonObservation,
    Diagnostic,
    KernelImpact,
    KernelObservation,
    ReviewDepth,
    ReviewObservation,
    ReviewPolicy,
)


def _normalize_numstat_path(path: str) -> str:
    """Return the destination path from Git's human-readable rename form."""
    if " => " not in path:
        return path
    if "{" in path and "}" in path:
        prefix, remainder = path.split("{", 1)
        change, suffix = remainder.split("}", 1)
        destination = change.split(" => ", 1)[1]
        return f"{prefix}{destination}{suffix}"
    return path.split(" => ", 1)[1]


def _parse_numstat(output: str) -> dict[str, tuple[int | None, int | None, bool]]:
    stats: dict[str, tuple[int | None, int | None, bool]] = {}
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        added, deleted, raw_path = parts
        path = _normalize_numstat_path(raw_path)
        binary = added == "-" or deleted == "-"
        stats[path] = (
            None if binary else int(added),
            None if binary else int(deleted),
            binary,
        )
    return stats


def _parse_changed_files(name_status: str, numstat: str) -> list[ChangedFileFact]:
    stats = _parse_numstat(numstat)
    facts: list[ChangedFileFact] = []
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        raw_status = parts[0]
        status = raw_status[:1]
        if status not in {"A", "M", "D", "R"}:
            continue
        old_path: str | None = None
        if status == "R" and len(parts) >= 3:
            old_path, path = parts[1], parts[2]
        else:
            path = parts[1]
        additions, deletions, binary = stats.get(path, (0, 0, False))
        facts.append(
            ChangedFileFact(
                path=path,
                old_path=old_path,
                status=status,  # type: ignore[arg-type]
                additions=additions,
                deletions=deletions,
                binary=binary,
            )
        )
    return sorted(facts, key=lambda fact: fact.path)


def _partition_summary(facts: list[ChangedFileFact]) -> ChangePartitionSummary:
    if any(fact.binary for fact in facts):
        additions: int | None = None
        deletions: int | None = None
    else:
        additions = sum(fact.additions or 0 for fact in facts)
        deletions = sum(fact.deletions or 0 for fact in facts)
    return ChangePartitionSummary(
        files=len(facts), additions=additions, deletions=deletions
    )


def _changed_path_sources(changes: ChangeObservation) -> dict[str, set[str]]:
    sources: dict[str, set[str]] = {}
    for source_name in ("committed", "staged", "unstaged", "untracked"):
        for fact in getattr(changes, source_name):
            sources.setdefault(fact.path, set()).add(source_name)
    return sources


def _collect_changes(git: GitClient, merge_base: str) -> ChangeObservation:
    committed = _parse_changed_files(*git.get_diff_metadata(merge_base, "HEAD"))
    staged = _parse_changed_files(*git.get_diff_metadata("HEAD", cached=True))
    unstaged = _parse_changed_files(*git.get_diff_metadata())
    untracked = [
        ChangedFileFact(path=path, status="A")
        for path in sorted(git.get_untracked_files())
    ]
    unique_paths = len(
        {
            fact.path
            for facts in (committed, staged, unstaged, untracked)
            for fact in facts
        }
    )
    return ChangeObservation(
        committed=committed,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        summary=ChangeSummary(
            committed=_partition_summary(committed),
            staged=_partition_summary(staged),
            unstaged=_partition_summary(unstaged),
            untracked=ChangePartitionSummary(
                files=len(untracked), additions=None, deletions=None
            ),
            unique_paths=unique_paths,
        ),
    )


def build_review_observation(
    requested_base: str | None,
    resolved_base: str,
    *,
    git: GitClient,
    manifest_path: Path,
) -> ReviewObservation:
    """Build exact Git facts and deterministic Review Kernel classification."""
    try:
        head_sha = git.resolve_revision("HEAD")
        merge_base = git.get_merge_base(resolved_base, head_sha)
        changes = _collect_changes(git, merge_base)
        comparison = ComparisonObservation(
            current_branch=git.get_current_branch(),
            head_sha=head_sha,
            requested_base=requested_base,
            resolved_base=resolved_base,
            merge_base_sha=merge_base,
        )
    except GitError as exc:
        return ReviewObservation(
            status="error",
            diagnostics=[Diagnostic(code="git_comparison_failed", message=str(exc))],
        )

    changed_paths = _changed_path_sources(changes)
    diagnostics: list[Diagnostic] = []
    try:
        manifest = load_review_kernel(
            manifest_path, repo_root=Path(git.get_worktree_root())
        )
        kernel, review = classify_review_kernel(changed_paths, manifest)
        status = "partial" if kernel.status == "unavailable" else "ready"
    except ReviewKernelConfigError as exc:
        diagnostic = Diagnostic(
            code="review_kernel_unavailable",
            message=str(exc),
            path=manifest_path.as_posix(),
        )
        diagnostics.append(diagnostic)
        kernel = KernelObservation(
            status="unavailable",
            impact=KernelImpact.NONE,
            diagnostics=[diagnostic],
        )
        review = ReviewPolicy(minimum_depth=ReviewDepth.NORMAL)
        status = "partial"

    return ReviewObservation(
        status=status,  # type: ignore[arg-type]
        comparison=comparison,
        changes=changes,
        kernel=kernel,
        review=review,
        diagnostics=diagnostics,
    )
