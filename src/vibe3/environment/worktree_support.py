"""Support helpers for worktree lifecycle operations."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger

if TYPE_CHECKING:
    from vibe3.models.orchestra_config import OrchestraConfig


def align_auto_scene_to_base(
    config: "OrchestraConfig", cwd: Path, flow_branch: str
) -> bool:
    """Align auto task scenes to configured base ref when safe."""
    if not flow_branch.startswith("task/issue-"):
        return True

    base_ref = str(getattr(config, "scene_base_ref", "origin/main") or "")
    if not base_ref.strip():
        return True

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-n", "1", flow_branch],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        has_commits = result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        has_commits = False

    commands = [["git", "fetch", "--all", "--prune"]]
    if not has_commits:
        commands.extend(
            [
                ["git", "checkout", flow_branch],
                ["git", "reset", "--hard", base_ref],
                ["git", "clean", "-fd"],
            ]
        )
    else:
        logger.info(
            "Skipping destructive alignment for existing task branch with commits",
            branch=flow_branch,
            cwd=str(cwd),
        )

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception as exc:
            logger.warning(
                f"Failed to align auto scene: {exc}",
                branch=flow_branch,
                cwd=str(cwd),
                base_ref=base_ref,
            )
            return False
        if result.returncode != 0:
            logger.warning(
                "Failed to align auto scene to base ref: "
                f"{(result.stderr or result.stdout).strip()}",
                branch=flow_branch,
                cwd=str(cwd),
                base_ref=base_ref,
            )
            return False

    logger.info(
        "Aligned auto scene to configured base ref",
        branch=flow_branch,
        cwd=str(cwd),
        base_ref=base_ref,
    )
    return True


def initialize_worktree(repo_path: Path, wt_path: Path, reason: str) -> None:
    """Run project init script inside a newly created worktree."""
    init_script = repo_path / "scripts" / "init.sh"
    if not init_script.exists():
        return

    try:
        result = subprocess.run(
            ["bash", str(init_script)],
            cwd=wt_path,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except Exception as exc:
        logger.warning(
            "Failed to execute init script for worktree",
            reason=reason,
            path=str(wt_path),
            error=str(exc),
        )
        return

    if result.returncode != 0:
        logger.warning(
            "Init script failed for worktree",
            reason=reason,
            path=str(wt_path),
            stderr=(result.stderr or result.stdout).strip(),
        )
        return

    logger.info(
        "Initialized worktree environment",
        reason=reason,
        path=str(wt_path),
    )


def find_worktree_by_path(repo_path: Path, target_path: Path) -> bool:
    """Return True if path is a registered git worktree."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        target_abs = target_path.resolve()
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                path = Path(line.split(" ", 1)[1]).resolve()
                if path == target_abs:
                    return True
        return False
    except Exception:
        return False


def recycle_worktree_path(repo_path: Path, target: Path) -> None:
    """Recycle a worktree path, unregistering it first."""
    try:
        sessions = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_path}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if sessions.returncode == 0:
            for line in sessions.stdout.strip().split("\n"):
                if not line:
                    continue
                if ":" in line:
                    session_name, session_path = line.split(":", 1)
                    if str(target) in session_path or session_path.startswith(
                        str(target)
                    ):
                        logger.warning(
                            "Skipping worktree cleanup: active tmux session found",
                            worktree=str(target),
                            session=session_name,
                            session_path=session_path,
                        )
                        return
    except FileNotFoundError:
        pass
    except Exception as exc:
        logger.warning(
            "Failed to check tmux sessions, proceeding with cleanup",
            error=str(exc),
            worktree=str(target),
        )

    try:
        result = subprocess.run(
            ["git", "worktree", "remove", str(target), "--force"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("Removed worktree via git", path=str(target))
            return
    except Exception:
        pass

    try:
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception:
        pass

    if target.exists():
        shutil.rmtree(target)
        logger.info("Forcefully removed worktree directory", path=str(target))


def find_worktree_for_branch(repo_path: Path, branch: str) -> Optional[Path]:
    """Find existing worktree for a branch."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    current_path = None
    current_branch = None
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            current_path = Path(line.split(" ", 1)[1])
        elif line.startswith("branch "):
            full_branch = line.split(" ", 1)[1]
            if full_branch.startswith("refs/heads/"):
                current_branch = full_branch[len("refs/heads/") :]
            else:
                current_branch = full_branch
            if current_branch == branch and current_path:
                return current_path

    return None


def is_current_branch(repo_path: Path, branch: str) -> bool:
    """Check whether repo_path currently points at the target branch."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    if result.returncode != 0:
        return False
    return result.stdout.strip() == branch
