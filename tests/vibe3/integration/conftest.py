"""Shared fixtures for integration tests."""

import os
import shutil
import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vibe3.clients import SQLiteClient

if TYPE_CHECKING:
    pass


# ============================================================================
# Existing fixtures
# ============================================================================


@pytest.fixture
def temp_store(tmp_path: Path) -> SQLiteClient:
    """Create a temporary SQLiteClient for testing."""
    import sqlite3

    from vibe3.clients.sqlite_schema import init_schema

    db_path = tmp_path / "handoff.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    return SQLiteClient(db_path=str(db_path))


# ============================================================================
# Cross-project smoke test fixtures
# ============================================================================


def _clean_git_env() -> dict[str, str]:
    """Return env for nested git commands run from hooks or other git subprocesses."""
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX"):
        env.pop(key, None)
    return env


@pytest.fixture(scope="session")
def installed_vibe_home(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path]:
    """Create a temp directory simulating ~/.vibe with runtime assets installed.

    This fixture:
    - Creates a temp directory
    - Copies config/prompts/ → <tmp>/config/prompts/
    - Copies supervisor/ → <tmp>/supervisor/
    - Creates <tmp>/settings.yaml with paths pointing to temp dir
    - Returns the temp Path

    Yields:
        Path to the temporary ~/.vibe-like directory
    """
    temp_home = tmp_path_factory.mktemp("vibe_home")

    # Get the project root (where this test is running from)
    project_root = Path(__file__).resolve().parents[3]

    # Copy config/prompts/
    src_prompts = project_root / "config" / "prompts"
    dst_prompts = temp_home / "config" / "prompts"
    if src_prompts.exists():
        dst_prompts.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_prompts, dst_prompts)

    # Copy supervisor/
    src_supervisor = project_root / "supervisor"
    dst_supervisor = temp_home / "supervisor"
    if src_supervisor.exists():
        shutil.copytree(src_supervisor, dst_supervisor)

    # Create settings.yaml with paths pointing to temp directory
    settings_content = f"""# Vibe Center Global Configuration (test)
paths:
  policies_root: "{temp_home}/supervisor/policies"
  prompts_root: "{temp_home}/config/prompts"
"""
    settings_file = temp_home / "settings.yaml"
    settings_file.write_text(settings_content, encoding="utf-8")

    yield temp_home

    # Cleanup is automatic with tmp_path_factory


@pytest.fixture
def target_repo(tmp_path: Path) -> Generator[Path]:
    """Create a minimal target repo for cross-project testing.

    This fixture:
    - Creates a temp directory
    - Initializes git repo with minimal commit
    - Creates minimal CLAUDE.md
    - Returns the temp Path

    Args:
        tmp_path: pytest's built-in tmp_path fixture

    Yields:
        Path to the temporary target repository
    """
    repo_path = tmp_path / "target_repo"
    repo_path.mkdir()

    # Initialize git repo
    git_env = _clean_git_env()
    subprocess.run(
        ["git", "init"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env=git_env,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env=git_env,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env=git_env,
    )

    # Create minimal commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env=git_env,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env=git_env,
    )

    # Create minimal .vibe directory
    vibe_dir = repo_path / ".vibe"
    vibe_dir.mkdir()

    # Create minimal CLAUDE.md
    claude_md = repo_path / "CLAUDE.md"
    claude_md.write_text(
        "# Test Project\n\nThis is a test project for cross-project smoke tests.\n",
        encoding="utf-8",
    )

    yield repo_path

    # Cleanup is automatic with tmp_path
