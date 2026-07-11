"""Real-Git regression tests for PR Change Summary."""

import subprocess
from pathlib import Path

import pytest

from vibe3.analysis.review_observation import build_committed_summary
from vibe3.clients import GitClient


class TestPRChangeSummary:
    """Real-Git tests for PR Change Summary using inspect-base facts."""

    @pytest.fixture
    def temp_git_repo(self, tmp_path: Path) -> Path:
        """Create a temporary git repository for testing."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Create initial commit on main
        (repo_path / "README.md").write_text("# Test Repo\n")
        subprocess.run(
            ["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        return repo_path

    def test_committed_only_scenario(self, temp_git_repo: Path) -> None:
        """Committed-only changes should match git diff --numstat."""
        git = GitClient(cwd=str(temp_git_repo))

        # Create 3 README-only commits
        for i in range(3):
            (temp_git_repo / f"README{i}.md").write_text(f"# README {i}\n")
            subprocess.run(
                ["git", "add", f"README{i}.md"],
                cwd=temp_git_repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Add README{i}"],
                cwd=temp_git_repo,
                check=True,
                capture_output=True,
            )

        # Get change summary
        head_sha = git.resolve_revision("HEAD")
        summary = build_committed_summary(git, "HEAD~3", head_sha)

        assert summary is not None
        assert summary.files_changed == 3
        assert summary.additions >= 3  # At least one line per file
        assert summary.deletions == 0
        assert summary.binary_files == 0

    def test_rename_handling(self, temp_git_repo: Path) -> None:
        """Rename should count as 1 changed file, not 2."""
        git = GitClient(cwd=str(temp_git_repo))

        # Create a file and commit
        (temp_git_repo / "old_file.txt").write_text("content\n")
        subprocess.run(
            ["git", "add", "old_file.txt"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add old_file"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Rename the file
        (temp_git_repo / "old_file.txt").rename(temp_git_repo / "new_file.txt")
        subprocess.run(
            ["git", "add", "-A"], cwd=temp_git_repo, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Rename to new_file"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Get change summary
        head_sha = git.resolve_revision("HEAD")
        summary = build_committed_summary(git, "HEAD~1", head_sha)

        assert summary is not None
        assert summary.files_changed == 1  # Rename counts as 1 file, not 2

    def test_binary_handling(self, temp_git_repo: Path) -> None:
        """Binary files should be tracked separately."""
        git = GitClient(cwd=str(temp_git_repo))

        # Create a binary file
        binary_data = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
        (temp_git_repo / "binary.bin").write_bytes(binary_data)
        subprocess.run(
            ["git", "add", "binary.bin"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add binary file"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Get change summary
        head_sha = git.resolve_revision("HEAD")
        summary = build_committed_summary(git, "HEAD~1", head_sha)

        assert summary is not None
        assert summary.binary_files == 1
        assert summary.files_changed == 1

    def test_merge_base_resolution(self, temp_git_repo: Path) -> None:
        """Should use correct merge-base for comparison."""
        git = GitClient(cwd=str(temp_git_repo))

        # Get the initial commit hash
        initial_sha = git.resolve_revision("HEAD")

        # Create a commit on main
        (temp_git_repo / "main_file.txt").write_text("main content\n")
        subprocess.run(
            ["git", "add", "main_file.txt"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add main_file"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Create a feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Add a file on feature branch
        (temp_git_repo / "feature_file.txt").write_text("feature content\n")
        subprocess.run(
            ["git", "add", "feature_file.txt"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Add feature_file"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        # Get change summary relative to the initial commit (common ancestor)
        head_sha = git.resolve_revision("HEAD")
        summary = build_committed_summary(git, initial_sha, head_sha)

        assert summary is not None
        # Should include both main_file and feature_file
        assert summary.files_changed >= 2

    def test_empty_commit_range(self, temp_git_repo: Path) -> None:
        """Empty commit range should return zero counts."""
        git = GitClient(cwd=str(temp_git_repo))

        # Get change summary for same commit
        head_sha = git.resolve_revision("HEAD")
        summary = build_committed_summary(git, "HEAD", head_sha)

        assert summary is not None
        assert summary.files_changed == 0
        assert summary.additions == 0
        assert summary.deletions == 0
        assert summary.binary_files == 0
