"""Regression tests for ``initialize_worktree`` path resolution.

Background: ``initialize_worktree`` previously resolved ``scripts/init.sh``
from ``repo_path``. In this project ``repo_path`` is a bare repository with
no working tree, so the file never existed there and the script was silently
skipped for every newly created worktree. The fix resolves the script from
``wt_path`` (the freshly checked-out worktree) instead.
"""

from __future__ import annotations

from pathlib import Path

from vibe3.environment.worktree_support import initialize_worktree


def _make_init_script(wt_path: Path, body: str) -> Path:
    """Create an executable ``scripts/init.sh`` inside ``wt_path``."""
    scripts_dir = wt_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    init_script = scripts_dir / "init.sh"
    init_script.write_text(f"#!/usr/bin/env bash\n{body}\n")
    init_script.chmod(0o755)
    return init_script


class TestInitializeWorktree:
    """Tests for initialize_worktree path resolution."""

    def test_runs_init_script_resolved_from_worktree(self, tmp_path: Path) -> None:
        """init.sh is found and executed inside wt_path (not repo_path)."""
        wt_path = tmp_path / "wt-999"
        marker = tmp_path / "ran.marker"
        _make_init_script(wt_path, f"touch {marker}")

        initialize_worktree(wt_path, reason="test")

        assert marker.exists(), "scripts/init.sh was not executed from wt_path"

    def test_silent_noop_when_init_script_missing(self, tmp_path: Path) -> None:
        """Missing scripts/init.sh is a non-blocking no-op."""
        wt_path = tmp_path / "wt-empty"
        wt_path.mkdir(parents=True)

        initialize_worktree(wt_path, reason="test")  # must not raise

    def test_failed_init_script_does_not_raise(self, tmp_path: Path) -> None:
        """A failing init.sh is logged but does not propagate."""
        wt_path = tmp_path / "wt-fail"
        _make_init_script(wt_path, "exit 1")

        initialize_worktree(wt_path, reason="test")  # must not raise
