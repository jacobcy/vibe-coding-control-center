"""Git diff hunk parsing utilities."""

import re
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.exceptions import GitError
from vibe3.models.change_source import (
    BranchSource,
    ChangeSource,
    ChangeSourceType,
    CommitSource,
    PRSource,
)

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient


def get_diff_hunk_ranges(
    git_client: "GitClient", file_path: str, source: ChangeSource
) -> list[tuple[int, int]]:
    """Get changed line ranges from git diff for a specific file.

    Simple heuristic: parse diff hunks to find changed line numbers.
    Useful for finding which functions were changed.

    Args:
        git_client: GitClient instance
        file_path: Relative file path
        source: Change source (commit/branch/pr)

    Returns:
        List of (start_line, end_line) tuples for changed hunks

    Example:
        >>> client = GitClient()
        >>> source = CommitSource(sha="abc123")
        >>> ranges = get_diff_hunk_ranges(client, "src/foo.py", source)
        >>> # [(10, 15), (42, 50)]
    """
    log = logger.bind(
        domain="git",
        action="get_diff_hunk_ranges",
        file=file_path,
        source_type=source.type,
    )
    log.debug("Getting diff hunk ranges")

    if source.type == ChangeSourceType.UNCOMMITTED:
        untracked_files = set(git_client.get_untracked_files())
        if file_path in untracked_files:
            try:
                content = Path(file_path).read_text(encoding="utf-8")
            except OSError:
                return []
            line_count = max(1, len(content.splitlines()))
            return [(1, line_count)]

    try:
        # Get diff for this specific file
        diff = _get_file_diff(git_client, file_path, source)

        if not diff:
            return []

        # Parse diff hunks: @@ -old_start,old_count +new_start,new_count @@
        hunk_pattern = re.compile(
            r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE
        )
        ranges: list[tuple[int, int]] = []

        for match in hunk_pattern.finditer(diff):
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) else 1
            end = start + count - 1
            ranges.append((start, end))

        log.bind(hunk_count=len(ranges)).debug("Got diff hunk ranges")
        return ranges

    except GitError:
        # If git command fails, return empty (graceful degradation)
        log.warning("Failed to get diff hunks, returning empty")
        return []


def _get_file_diff(
    git_client: "GitClient", file_path: str, source: ChangeSource
) -> str:
    """Get diff for a specific file from various change sources.

    Args:
        git_client: GitClient instance
        file_path: Relative file path
        source: Change source

    Returns:
        Diff content for the file

    Raises:
        GitError: If git command fails
    """
    if source.type == ChangeSourceType.COMMIT:
        assert isinstance(source, CommitSource)
        return git_client._run(["diff", f"{source.sha}^", source.sha, "--", file_path])
    elif source.type == ChangeSourceType.BRANCH:
        assert isinstance(source, BranchSource)
        return git_client._run(
            ["diff", f"{source.base}...{source.branch}", "--", file_path]
        )
    elif source.type == ChangeSourceType.PR:
        assert isinstance(source, PRSource)
        # Use GitHub API to get the full PR diff, then extract this file
        if not git_client._github_client:
            raise GitError(
                "get_diff_hunk_ranges",
                "PR source requires GitHubClient injection",
            )
        # Get diff from cache or fetch it
        if source.pr_number not in git_client._pr_diff_cache:
            git_client._pr_diff_cache[source.pr_number] = (
                git_client._github_client.get_pr_diff(source.pr_number)
            )
        full_diff = git_client._pr_diff_cache[source.pr_number]
        # Late import to avoid circular dependency:
        # git_diff_hunks -> git_client -> git_diff_utils -> git_diff_hunks
        from vibe3.clients.git_diff_utils import extract_file_diff

        return extract_file_diff(full_diff, file_path)
    else:
        # Uncommitted changes
        return git_client._run(["diff", "HEAD", "--", file_path])
