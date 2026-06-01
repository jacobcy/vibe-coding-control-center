"""Project check service for vibe3 ecosystem cold-start environment validation."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from loguru import logger


@dataclass
class CheckItem:
    """Single check item result."""

    name: str
    status: Literal["pass", "fail", "warning", "skip"]
    message: str
    detail: str = ""
    fixable: bool = False


@dataclass
class CheckCategory:
    """Category of related check items."""

    name: str
    items: list[CheckItem] = field(default_factory=list)


@dataclass
class ProjectCheckResult:
    """Complete project check result."""

    categories: list[CheckCategory] = field(default_factory=list)
    overall: bool = True

    def count_results(self) -> dict[str, int]:
        """Count items by status."""
        counts = {"pass": 0, "fail": 0, "warning": 0, "skip": 0}
        for category in self.categories:
            for item in category.items:
                counts[item.status] += 1
        return counts


class ProjectCheckService:
    """Service for checking vibe3 ecosystem project environment."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize project check service.

        Args:
            project_root: Project root directory.
                If None, uses current working directory.
        """
        self.project_root = project_root or Path.cwd()
        self._git_root: Path | None = None

    def _run_git(self, *args: str, check: bool = False) -> subprocess.CompletedProcess:
        """Run git command in project root.

        Args:
            *args: Git command arguments
            check: If True, raise on non-zero exit

        Returns:
            CompletedProcess with stdout, stderr, returncode
        """
        cmd = ["git", *args]
        return subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=check,
        )

    def _get_git_root(self) -> Path | None:
        """Get git repository root directory.

        Correctly handles:
        - Worktrees: --show-toplevel returns worktree root
        - Repo root: --show-toplevel returns repository root
        - Subdirectories: --show-toplevel returns repository root

        Returns:
            Path to git root or None if not in a git repo
        """
        if self._git_root is not None:
            return self._git_root

        # Get the top-level directory (handles worktrees correctly)
        # For main repo: returns the repository root
        # For worktree: returns the worktree root (not the main repo)
        # For subdirectory: returns the repository root
        result = self._run_git("rev-parse", "--show-toplevel")
        if result.returncode == 0:
            git_root = Path(result.stdout.strip()).resolve()
            self._git_root = git_root
            return self._git_root
        return None

    def check_git_repository(self) -> CheckCategory:
        """Check git repository status.

        Returns:
            CheckCategory with git-related check items
        """
        category = CheckCategory(name="Git Repository")

        # Check 1: In git repository
        git_root = self._get_git_root()
        if git_root:
            category.items.append(
                CheckItem(
                    name="In git repository",
                    status="pass",
                    message="Current directory is in a git repository",
                    detail=str(git_root),
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name="In git repository",
                    status="fail",
                    message="Not in a git repository",
                    detail="Run 'git init' to initialize a repository",
                )
            )
            # Early return if not in a git repo
            category.items.extend(
                [
                    CheckItem(
                        name="Remote origin exists",
                        status="skip",
                        message="Skipped: not in a git repository",
                    ),
                    CheckItem(
                        name="main/master branch exists",
                        status="skip",
                        message="Skipped: not in a git repository",
                    ),
                ]
            )
            return category

        # Check 2: Remote origin exists
        result = self._run_git("remote", "get-url", "origin")
        if result.returncode == 0 and result.stdout.strip():
            origin_url = result.stdout.strip()
            category.items.append(
                CheckItem(
                    name="Remote origin exists",
                    status="pass",
                    message="Remote origin is configured",
                    detail=origin_url,
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name="Remote origin exists",
                    status="fail",
                    message="No remote origin configured",
                    detail="Add with: git remote add origin <url>",
                )
            )

        # Check 3: main/master branch exists
        main_exists = (
            self._run_git("rev-parse", "--verify", "origin/main").returncode == 0
        )
        master_exists = (
            self._run_git("rev-parse", "--verify", "origin/master").returncode == 0
        )

        if main_exists or master_exists:
            branch_name = "main" if main_exists else "master"
            category.items.append(
                CheckItem(
                    name="main/master branch exists",
                    status="pass",
                    message=f"Primary branch '{branch_name}' exists on remote",
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name="main/master branch exists",
                    status="warning",
                    message="Neither 'main' nor 'master' branch found on remote",
                    detail="This may be a new repository without pushed branches",
                )
            )

        return category

    def check_vibe3_config(self) -> CheckCategory:
        """Check vibe3 configuration directories.

        Returns:
            CheckCategory with vibe3 config check items
        """
        category = CheckCategory(name="vibe3 Configuration")
        git_root = self._get_git_root()

        if not git_root:
            category.items.append(
                CheckItem(
                    name=".git/vibe3/ directory exists",
                    status="skip",
                    message="Skipped: not in a git repository",
                )
            )
            category.items.append(
                CheckItem(
                    name=".git/vibe3/handoff.db accessible",
                    status="skip",
                    message="Skipped: not in a git repository",
                )
            )
            category.items.append(
                CheckItem(
                    name=".claude/ directory exists",
                    status="skip",
                    message="Skipped: not in a git repository",
                )
            )
            category.items.append(
                CheckItem(
                    name=".claude/settings.json exists",
                    status="skip",
                    message="Skipped: not in a git repository",
                )
            )
            return category

        # Check 1: .git/vibe3/ directory exists
        vibe3_dir = git_root / ".git" / "vibe3"
        if vibe3_dir.exists():
            category.items.append(
                CheckItem(
                    name=".git/vibe3/ directory exists",
                    status="pass",
                    message="vibe3 configuration directory exists",
                    detail=str(vibe3_dir),
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name=".git/vibe3/ directory exists",
                    status="fail",
                    message=".git/vibe3/ directory missing",
                    detail="Will be created on first use",
                    fixable=True,
                )
            )

        # Check 2: handoff.db accessible
        handoff_db = vibe3_dir / "handoff.db"
        if handoff_db.exists():
            try:
                # Test database connection
                with sqlite3.connect(handoff_db) as conn:
                    conn.execute("SELECT 1")
                category.items.append(
                    CheckItem(
                        name=".git/vibe3/handoff.db accessible",
                        status="pass",
                        message="Handoff database is accessible",
                        detail=str(handoff_db),
                    )
                )
            except sqlite3.Error as e:
                category.items.append(
                    CheckItem(
                        name=".git/vibe3/handoff.db accessible",
                        status="fail",
                        message="Handoff database exists but is not accessible",
                        detail=f"SQLite error: {e}",
                    )
                )
        else:
            category.items.append(
                CheckItem(
                    name=".git/vibe3/handoff.db accessible",
                    status="warning",
                    message="Handoff database does not exist yet",
                    detail="Will be created on first use",
                )
            )

        # Check 3: .claude/ directory exists
        claude_dir = git_root / ".claude"
        if claude_dir.exists():
            category.items.append(
                CheckItem(
                    name=".claude/ directory exists",
                    status="pass",
                    message="Claude configuration directory exists",
                    detail=str(claude_dir),
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name=".claude/ directory exists",
                    status="fail",
                    message=".claude/ directory missing",
                    detail="Required for Claude Code settings",
                    fixable=True,
                )
            )

        # Check 4: .claude/settings.json exists
        settings_file = claude_dir / "settings.json"
        if settings_file.exists():
            category.items.append(
                CheckItem(
                    name=".claude/settings.json exists",
                    status="pass",
                    message="Claude settings file exists",
                    detail=str(settings_file),
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name=".claude/settings.json exists",
                    status="warning",
                    message=".claude/settings.json not found",
                    detail="Optional: for custom Claude Code configuration",
                )
            )

        return category

    def check_dependencies(self) -> CheckCategory:
        """Check project dependencies and tools.

        Returns:
            CheckCategory with dependency check items
        """
        category = CheckCategory(name="Dependencies")

        # Check 1: pyproject.toml or package.json
        pyproject = self.project_root / "pyproject.toml"
        package_json = self.project_root / "package.json"

        if pyproject.exists():
            category.items.append(
                CheckItem(
                    name="Project manifest found",
                    status="pass",
                    message="pyproject.toml found",
                    detail=str(pyproject),
                )
            )
        elif package_json.exists():
            category.items.append(
                CheckItem(
                    name="Project manifest found",
                    status="pass",
                    message="package.json found",
                    detail=str(package_json),
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name="Project manifest found",
                    status="warning",
                    message="No pyproject.toml or package.json found",
                    detail=(
                        "Project may not have dependencies "
                        "or use a different package manager"
                    ),
                )
            )

        # Check 2: vibe3 CLI available
        vibe3_path = shutil.which("vibe3")
        if vibe3_path:
            category.items.append(
                CheckItem(
                    name="vibe3 CLI available",
                    status="pass",
                    message="vibe3 command is available in PATH",
                    detail=vibe3_path,
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name="vibe3 CLI available",
                    status="fail",
                    message="vibe3 command not found in PATH",
                    detail="Install vibe3 or ensure it's in PATH",
                )
            )

        # Check 3: Python version
        python_version = sys.version_info
        if python_version >= (3, 11):
            category.items.append(
                CheckItem(
                    name="Python 3.11+ available",
                    status="pass",
                    message=(
                        f"Python {python_version.major}."
                        f"{python_version.minor} detected"
                    ),
                    detail=sys.executable,
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name="Python 3.11+ available",
                    status="fail",
                    message=(
                        f"Python {python_version.major}."
                        f"{python_version.minor} detected "
                        "(3.11+ required)"
                    ),
                    detail="Upgrade Python to 3.11 or later",
                )
            )

        return category

    def check_orchestra_config(self) -> CheckCategory:
        """Check Orchestra configuration.

        Returns:
            CheckCategory with Orchestra config check items
        """
        category = CheckCategory(name="Orchestra Configuration")
        git_root = self._get_git_root()

        # Check 1: config/v3/settings.yaml or global config
        config_path = None
        if git_root:
            config_path = git_root / "config" / "v3" / "settings.yaml"

        if config_path and config_path.exists():
            category.items.append(
                CheckItem(
                    name="config/v3/settings.yaml found",
                    status="pass",
                    message="Orchestra configuration file found",
                    detail=str(config_path),
                )
            )
        else:
            # Try global config
            global_config = Path.home() / ".config" / "vibe3" / "settings.yaml"
            if global_config.exists():
                category.items.append(
                    CheckItem(
                        name="Global Orchestra config found",
                        status="pass",
                        message="Global Orchestra configuration file found",
                        detail=str(global_config),
                    )
                )
            else:
                category.items.append(
                    CheckItem(
                        name="Orchestra config found",
                        status="warning",
                        message="No Orchestra configuration found (local or global)",
                        detail="Run 'vibe3 serve' to initialize default configuration",
                    )
                )

        # Check 2: repo configuration (basic check)
        # This is a simplified check - full validation would require parsing the config
        category.items.append(
            CheckItem(
                name="repo configuration valid",
                status="skip",
                message=(
                    "Repository configuration check skipped " "(requires running vibe3)"
                ),
                detail="Run 'vibe3 inspect base' for detailed configuration validation",
            )
        )

        # Check 3: scene_base_ref validity
        if git_root:
            # Try to get scene_base_ref from config
            scene_base_ref = None
            try:
                from vibe3.config.settings import VibeConfig

                config = VibeConfig.get_defaults()
                scene_base_ref = config.orchestra.scene_base_ref
            except Exception:
                # Fallback to default if config loading fails
                scene_base_ref = "origin/main"

            # Verify the scene_base_ref exists
            result = self._run_git("rev-parse", "--verify", scene_base_ref)
            if result.returncode == 0:
                category.items.append(
                    CheckItem(
                        name="scene_base_ref valid",
                        status="pass",
                        message=f"scene_base_ref '{scene_base_ref}' is valid",
                    )
                )
            else:
                category.items.append(
                    CheckItem(
                        name="scene_base_ref valid",
                        status="warning",
                        message=f"scene_base_ref '{scene_base_ref}' not found",
                        detail="Verify after remote sync or configure base ref",
                    )
                )
        else:
            category.items.append(
                CheckItem(
                    name="scene_base_ref valid",
                    status="skip",
                    message="Skipped: not in a git repository",
                )
            )

        return category

    def check_github_integration(self) -> CheckCategory:
        """Check GitHub integration setup.

        Returns:
            CheckCategory with GitHub integration check items
        """
        category = CheckCategory(name="GitHub Integration")

        # Check 1: gh CLI available
        gh_path = shutil.which("gh")
        if gh_path:
            category.items.append(
                CheckItem(
                    name="gh CLI available",
                    status="pass",
                    message="GitHub CLI is available in PATH",
                    detail=gh_path,
                )
            )
        else:
            category.items.append(
                CheckItem(
                    name="gh CLI available",
                    status="warning",
                    message="GitHub CLI not found in PATH",
                    detail="Install gh CLI for GitHub integration features",
                )
            )
            # Skip remaining GitHub checks if gh not available
            category.items.extend(
                [
                    CheckItem(
                        name="GitHub authenticated",
                        status="skip",
                        message="Skipped: gh CLI not available",
                    ),
                    CheckItem(
                        name="Repository write access",
                        status="skip",
                        message="Skipped: gh CLI not available",
                    ),
                ]
            )
            return category

        # Check 2: GitHub authentication
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                category.items.append(
                    CheckItem(
                        name="GitHub authenticated",
                        status="pass",
                        message="GitHub CLI is authenticated",
                    )
                )
            else:
                category.items.append(
                    CheckItem(
                        name="GitHub authenticated",
                        status="fail",
                        message="GitHub CLI is not authenticated",
                        detail="Run 'gh auth login' to authenticate",
                    )
                )
                # Skip write access check if not authenticated
                category.items.append(
                    CheckItem(
                        name="Repository write access",
                        status="skip",
                        message="Skipped: not authenticated",
                    )
                )
                return category
        except subprocess.TimeoutExpired:
            category.items.append(
                CheckItem(
                    name="GitHub authenticated",
                    status="warning",
                    message="GitHub auth check timed out",
                    detail="Network may be slow or unavailable",
                )
            )
            category.items.append(
                CheckItem(
                    name="Repository write access",
                    status="skip",
                    message="Skipped: auth check timed out",
                )
            )
            return category
        except Exception as e:
            category.items.append(
                CheckItem(
                    name="GitHub authenticated",
                    status="warning",
                    message=f"GitHub auth check failed: {e}",
                )
            )
            category.items.append(
                CheckItem(
                    name="Repository write access",
                    status="skip",
                    message="Skipped: auth check failed",
                )
            )
            return category

        # Check 3: Repository write access
        git_root = self._get_git_root()
        if git_root:
            result = self._run_git("remote", "get-url", "origin")
            if result.returncode == 0 and result.stdout.strip():
                origin_url = result.stdout.strip()
                # Parse owner/repo from URL
                # Support both https://github.com/owner/repo
                # and git@github.com:owner/repo
                try:
                    if "github.com" in origin_url:
                        parts = (
                            origin_url.split("github.com")[-1].strip("/:").rstrip("/")
                        )
                        owner_repo = parts.split("/", 1)
                        if len(owner_repo) == 2:
                            owner, repo = owner_repo
                            # Remove .git suffix if present
                            if repo.endswith(".git"):
                                repo = repo[:-4]

                            # Check write access
                            try:
                                result = subprocess.run(
                                    ["gh", "api", f"repos/{owner}/{repo}"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5,
                                )
                                if result.returncode == 0:
                                    category.items.append(
                                        CheckItem(
                                            name="Repository write access",
                                            status="pass",
                                            message=(
                                                f"Can access repository "
                                                f"{owner}/{repo}"
                                            ),
                                        )
                                    )
                                else:
                                    category.items.append(
                                        CheckItem(
                                            name="Repository write access",
                                            status="warning",
                                            message=(
                                                "Cannot verify repository "
                                                "write access"
                                            ),
                                            detail=(
                                                "May not have write permissions "
                                                "or repo may not exist"
                                            ),
                                        )
                                    )
                            except subprocess.TimeoutExpired:
                                category.items.append(
                                    CheckItem(
                                        name="Repository write access",
                                        status="warning",
                                        message="Repository access check timed out",
                                        detail="Network may be slow or unavailable",
                                    )
                                )
                        else:
                            category.items.append(
                                CheckItem(
                                    name="Repository write access",
                                    status="warning",
                                    message=(
                                        "Could not parse repository " "from remote URL"
                                    ),
                                )
                            )
                    else:
                        category.items.append(
                            CheckItem(
                                name="Repository write access",
                                status="skip",
                                message="Skipped: remote is not a GitHub repository",
                                detail=origin_url,
                            )
                        )
                except Exception as e:
                    category.items.append(
                        CheckItem(
                            name="Repository write access",
                            status="warning",
                            message=f"Repository access check failed: {e}",
                        )
                    )
            else:
                category.items.append(
                    CheckItem(
                        name="Repository write access",
                        status="skip",
                        message="Skipped: no remote origin configured",
                    )
                )
        else:
            category.items.append(
                CheckItem(
                    name="Repository write access",
                    status="skip",
                    message="Skipped: not in a git repository",
                )
            )

        return category

    def run_checks(self, fix: bool = False) -> ProjectCheckResult:
        """Run all project checks.

        Args:
            fix: If True, attempt to fix fixable issues

        Returns:
            ProjectCheckResult with all check categories and items
        """
        logger.info("Starting project environment check")

        result = ProjectCheckResult()

        # Run all check categories
        result.categories.append(self.check_git_repository())
        result.categories.append(self.check_vibe3_config())
        result.categories.append(self.check_dependencies())
        result.categories.append(self.check_orchestra_config())
        result.categories.append(self.check_github_integration())

        # Apply fixes if requested
        if fix:
            self._apply_fixes(result)

        # Determine overall result
        for category in result.categories:
            for item in category.items:
                if item.status == "fail":
                    result.overall = False
                    break

        logger.info(f"Project check complete: {'PASS' if result.overall else 'FAIL'}")
        return result

    def _apply_fixes(self, result: ProjectCheckResult) -> None:
        """Apply fixes for fixable issues.

        Args:
            result: ProjectCheckResult to update after fixes
        """
        git_root = self._get_git_root()
        if not git_root:
            logger.warning("Cannot apply fixes: not in a git repository")
            return

        for category in result.categories:
            for item in category.items:
                if item.status == "fail" and item.fixable:
                    logger.info(f"Attempting to fix: {item.name}")

                    if item.name == ".git/vibe3/ directory exists":
                        vibe3_dir = git_root / ".git" / "vibe3"
                        try:
                            vibe3_dir.mkdir(parents=True, exist_ok=True)
                            item.status = "pass"
                            item.message = ".git/vibe3/ directory created"
                            logger.info(f"Created: {vibe3_dir}")
                        except Exception as e:
                            logger.error(f"Failed to create {vibe3_dir}: {e}")

                    elif item.name == ".claude/ directory exists":
                        claude_dir = git_root / ".claude"
                        try:
                            claude_dir.mkdir(parents=True, exist_ok=True)
                            item.status = "pass"
                            item.message = ".claude/ directory created"
                            logger.info(f"Created: {claude_dir}")
                        except Exception as e:
                            logger.error(f"Failed to create {claude_dir}: {e}")
