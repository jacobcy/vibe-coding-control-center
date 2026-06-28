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
from vibe3.models import (
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


class GitMetadataParseError(ValueError):
    """Raised when Git metadata cannot be represented without guessing."""


_GIT_STATUSES = frozenset({"A", "C", "D", "M", "R", "T", "U", "X", "B"})


def _nul_tokens(output: str, *, label: str) -> list[str]:
    if not output:
        return []
    if not output.endswith("\0"):
        raise GitMetadataParseError(f"Malformed {label}: missing NUL terminator")
    return output[:-1].split("\0")


def _parse_numstat(output: str) -> dict[str, tuple[int | None, int | None, bool]]:
    stats: dict[str, tuple[int | None, int | None, bool]] = {}
    tokens = _nul_tokens(output, label="numstat")
    index = 0
    while index < len(tokens):
        record = tokens[index]
        index += 1
        parts = record.split("\t", 2)
        if len(parts) != 3:
            raise GitMetadataParseError("Malformed numstat record")
        added, deleted, path = parts
        if not path:
            if index + 1 >= len(tokens):
                raise GitMetadataParseError("Malformed numstat rename/copy record")
            _old_path, path = tokens[index], tokens[index + 1]
            index += 2
        if not path:
            raise GitMetadataParseError("Malformed numstat record: empty path")
        binary = added == "-" or deleted == "-"
        if binary and (added, deleted) != ("-", "-"):
            raise GitMetadataParseError("Malformed numstat binary record")
        if path in stats:
            raise GitMetadataParseError(f"Duplicate numstat path: {path}")
        try:
            additions = None if binary else int(added)
            deletions = None if binary else int(deleted)
        except ValueError as exc:
            raise GitMetadataParseError("Malformed numstat line counts") from exc
        if (additions is not None and additions < 0) or (
            deletions is not None and deletions < 0
        ):
            raise GitMetadataParseError("Malformed numstat negative line count")
        stats[path] = (
            additions,
            deletions,
            binary,
        )
    return stats


def _parse_changed_files(name_status: str, numstat: str) -> list[ChangedFileFact]:
    stats = _parse_numstat(numstat)
    facts: list[ChangedFileFact] = []
    tokens = _nul_tokens(name_status, label="name-status")
    index = 0
    while index < len(tokens):
        raw_status = tokens[index]
        index += 1
        if not raw_status:
            raise GitMetadataParseError("Malformed name-status record: empty status")
        status = raw_status[:1]
        if status not in _GIT_STATUSES:
            raise GitMetadataParseError(f"Unknown name-status code: {raw_status}")
        if status in {"R", "C"}:
            if not raw_status[1:].isdigit():
                raise GitMetadataParseError(
                    f"Malformed name-status similarity score: {raw_status}"
                )
            if index + 1 >= len(tokens):
                raise GitMetadataParseError("Malformed name-status rename/copy record")
            old_path, path = tokens[index], tokens[index + 1]
            index += 2
        else:
            if raw_status != status or index >= len(tokens):
                raise GitMetadataParseError(
                    f"Malformed name-status record: {raw_status}"
                )
            old_path = None
            path = tokens[index]
            index += 1
        if not path or (old_path is not None and not old_path):
            raise GitMetadataParseError("Malformed name-status record: empty path")
        additions, deletions, binary = stats.get(path, (None, None, False))
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
    if any(fact.additions is None or fact.deletions is None for fact in facts):
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
    except (GitError, GitMetadataParseError) as exc:
        code = (
            "git_metadata_invalid"
            if isinstance(exc, GitMetadataParseError)
            else "git_comparison_failed"
        )
        return ReviewObservation(
            status="error",
            diagnostics=[Diagnostic(code=code, message=str(exc))],
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
