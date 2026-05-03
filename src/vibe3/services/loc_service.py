"""Service for computing LOC statistics for PR diffs and branch diffs."""

from dataclasses import dataclass

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.models.change_source import BranchSource, ChangeSource, PRSource


@dataclass(frozen=True)
class LOCStats:
    """LOC statistics for a diff."""

    added: int  # Lines added in core code paths
    deleted: int  # Lines deleted in core code paths
    total: int  # Total changed lines (added + deleted)
    files_count: int  # Number of files in core code paths
    scope: str  # Description of scope (e.g., "src/vibe3/")


class LocService:
    """Service for computing LOC statistics for diffs filtered by core code paths."""

    def __init__(self, git_client: GitClient | None = None) -> None:
        """Initialize LocService.

        Args:
            git_client: Optional GitClient instance
        """
        self.git_client = git_client or GitClient()
        # Core code paths from config/loc_limits.yaml
        self.code_paths = ("src/vibe3/",)

    def get_pr_loc_stats(self, pr_number: int) -> LOCStats:
        """Get LOC stats for a PR diff, filtered by core code paths.

        Args:
            pr_number: PR number

        Returns:
            LOCStats with added/deleted/total counts for core code paths
        """
        source = PRSource(pr_number=pr_number)
        return self._compute_loc_stats(source)

    def get_branch_loc_stats(self, branch: str, base: str = "main") -> LOCStats:
        """Get LOC stats for branch diff, filtered by core code paths.

        Args:
            branch: Branch name
            base: Base branch to compare against

        Returns:
            LOCStats with added/deleted/total counts for core code paths
        """
        source = BranchSource(branch=branch, base=base)
        return self._compute_loc_stats(source)

    def _compute_loc_stats(self, source: ChangeSource) -> LOCStats:
        """Compute LOC stats from a diff source.

        Args:
            source: ChangeSource (PRSource or BranchSource)

        Returns:
            LOCStats with aggregated statistics
        """
        try:
            # Use git diff --numstat for efficient line counting
            # Format: added deleted filename
            numstat_output = self._get_numstat(source)

            added_total = 0
            deleted_total = 0
            files_count = 0

            for line in numstat_output.splitlines():
                line = line.strip()
                if not line:
                    continue

                parts = line.split("\t")
                if len(parts) < 3:
                    # Malformed line, skip
                    logger.bind(line=line).warning("Malformed numstat line, skipping")
                    continue

                added_str, deleted_str, filepath = parts[0], parts[1], parts[2]

                # Filter by core code paths
                if not self._is_core_code_file(filepath):
                    continue

                # Parse added/deleted counts
                # Note: Binary files show as "-" in numstat
                try:
                    added = int(added_str) if added_str != "-" else 0
                    deleted = int(deleted_str) if deleted_str != "-" else 0
                except ValueError:
                    logger.bind(
                        added=added_str, deleted=deleted_str, file=filepath
                    ).warning("Failed to parse numstat counts, skipping")
                    continue

                # Skip binary files (both counts are "-")
                if added_str == "-" and deleted_str == "-":
                    continue

                added_total += added
                deleted_total += deleted
                files_count += 1

            return LOCStats(
                added=added_total,
                deleted=deleted_total,
                total=added_total + deleted_total,
                files_count=files_count,
                scope=", ".join(self.code_paths),
            )

        except Exception as e:
            logger.bind(source=source).error(f"Failed to compute LOC stats: {e}")
            # Return zero stats on error
            return LOCStats(
                added=0,
                deleted=0,
                total=0,
                files_count=0,
                scope=", ".join(self.code_paths),
            )

    def _get_numstat(self, source: ChangeSource) -> str:
        """Get git diff numstat output for a source.

        Args:
            source: ChangeSource (PRSource or BranchSource)

        Returns:
            Raw numstat output from git
        """
        if isinstance(source, PRSource):
            # For PR, use the PR diff
            # Note: We need to use gh pr diff to get the PR diff directly
            # git diff --numstat doesn't work directly for PRs
            import json
            import subprocess

            try:
                # gh pr diff --name-only only gives filenames
                # We need to use git diff with the PR merge base
                # Get the PR head and base refs
                pr_info = subprocess.run(
                    [
                        "gh",
                        "pr",
                        "view",
                        str(source.pr_number),
                        "--json",
                        "baseRefName,headRefName",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                pr_data = json.loads(pr_info.stdout)
                base_ref = pr_data["baseRefName"]
                head_ref = pr_data["headRefName"]

                # Use git diff --numstat with merge-base
                base_commit = self.git_client.get_merge_base(head_ref, base_ref)
                return self.git_client._run(
                    ["diff", "--numstat", f"{base_commit}...{head_ref}"]
                )
            except Exception as e:
                logger.bind(pr_number=source.pr_number).error(
                    f"Failed to get PR numstat: {e}"
                )
                raise

        elif isinstance(source, BranchSource):
            # For branch, use git diff --numstat with merge-base
            base_commit = self.git_client.get_merge_base(source.branch, source.base)
            return self.git_client._run(
                ["diff", "--numstat", f"{base_commit}...{source.branch}"]
            )

        else:
            raise ValueError(f"Unsupported source type: {type(source)}")

    def _is_core_code_file(self, filepath: str) -> bool:
        """Check if a file is in core code paths and not a test file.

        Args:
            filepath: File path to check

        Returns:
            True if file is in core code paths and not a test file
        """
        # Check if file is in core code paths
        is_core = any(filepath.startswith(path) for path in self.code_paths)

        if not is_core:
            return False

        # Exclude test files
        # Reuse the test file detection logic from change_scope_service
        from vibe3.analysis.change_scope_service import is_test_file

        return not is_test_file(filepath)
