"""Regression tests for the cli.py src bootstrap (deps-only venv model).

Guards the per-worktree code-isolation guarantee: cli.py must put its OWN local
``src/`` on ``sys.path`` so ``import vibe3`` resolves to the worktree it lives in,
even under ``python -I`` (which ignores PYTHONPATH) and with no editable install
in the shared venv.

If these fail, the cross-worktree hijack bug is back: running vibe3 in one
worktree would resolve to another worktree's code.

See docs/superpowers/specs/2026-05-28-install-env-worktree-model-design.md
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PY = REPO_ROOT / "src" / "vibe3" / "cli.py"


def _env_without_pythonpath() -> dict[str, str]:
    """Strip PYTHONPATH so the only way `import vibe3` works is the bootstrap."""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def test_cli_runs_under_isolation_without_pythonpath() -> None:
    """The real cli.py self-bootstraps src/, so it imports under `python -I`
    with no PYTHONPATH and no editable install. Fails if the bootstrap is
    removed (ModuleNotFoundError: No module named 'vibe3')."""
    result = subprocess.run(
        [sys.executable, "-I", str(CLI_PY), "version"],
        capture_output=True,
        text=True,
        env=_env_without_pythonpath(),
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        "cli.py failed under `python -I` without PYTHONPATH; the src bootstrap "
        f"is likely broken.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_bootstrap_resolves_relative_to_cli_location(tmp_path: Path) -> None:
    """The bootstrap is __file__-relative: a copy of src/ in another location
    imports THAT copy's vibe3, not a hardcoded repo path. This is the
    cross-worktree isolation guarantee. Fails if the bootstrap hardcodes a path
    instead of deriving it from __file__."""
    dst_src = tmp_path / "src"
    shutil.copytree(
        REPO_ROOT / "src",
        dst_src,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    # Sentinel runs when the COPY's vibe3 package __init__ is imported.
    init = dst_src / "vibe3" / "__init__.py"
    init.write_text(
        init.read_text() + '\nimport sys as _s; print("ORIGIN=COPY", file=_s.stderr)\n'
    )

    result = subprocess.run(
        [sys.executable, "-I", str(dst_src / "vibe3" / "cli.py"), "version"],
        capture_output=True,
        text=True,
        env=_env_without_pythonpath(),
        cwd=str(tmp_path),
    )
    assert (
        result.returncode == 0
    ), f"copied cli.py failed to run:\nstderr:\n{result.stderr}"
    assert "ORIGIN=COPY" in result.stderr, (
        "cli.py resolved vibe3 to a path other than its own local src; the "
        "bootstrap is not __file__-relative, breaking per-worktree isolation."
    )
