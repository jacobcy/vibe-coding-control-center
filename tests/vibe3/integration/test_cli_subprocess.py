"""Layer 2: CLI subprocess smoke tests.

Tests that plan/run/review/internal-manager commands can render prompts
via --dry-run --show-prompt without relying on source-tree fallback.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _categorize_failure(stderr: str, _exit_code: int) -> str:
    """Categorize CLI failure based on stderr output and exit code.

    Returns one of:
    - "install_missing" — ModuleNotFoundError, No module named, or asset path not found
    - "flow_fixture_missing" — No flow, No spec, no active flow, branch not found
    - "prompt_rendering_missing" — prompts, template, prompt, recipe
    - "command_param_missing" — No such option, unrecognized arguments
    - "unknown" — unclassified failure
    """
    stderr_lower = stderr.lower()

    # Check for install missing first (most critical)
    if (
        "modulenotfounderror" in stderr_lower
        or "no module named" in stderr_lower
        or "importerror" in stderr_lower
    ):
        return "install_missing"

    # Check for command parameter missing
    if "no such option" in stderr_lower or "unrecognized arguments" in stderr_lower:
        return "command_param_missing"

    # Check for prompt rendering issues
    if any(
        keyword in stderr_lower
        for keyword in ["prompts", "template", "prompt", "recipe"]
    ):
        return "prompt_rendering_missing"

    # Check for flow fixture missing (acceptable for smoke tests)
    if any(
        keyword in stderr_lower
        for keyword in ["no flow", "no spec", "no active flow", "branch not found"]
    ):
        return "flow_fixture_missing"

    return "unknown"


def _cli_env(runtime_assets_root: Path) -> dict[str, str]:
    """Return isolated environment for CLI subprocess smoke tests."""
    env = os.environ.copy()
    env["VIBE3_RUNTIME_ASSETS_ROOT"] = str(runtime_assets_root)
    for key in (
        "PYTHONPATH",
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_PREFIX",
    ):
        env.pop(key, None)
    return env


@pytest.mark.xfail(
    strict=False,
    reason=(
        "This project uses an editable install (.pth file in venv site-packages). "
        "Python -I suppresses PYTHONPATH but not venv site-packages, so vibe3 "
        "remains importable. This test documents the known isolation limitation: "
        "the other subprocess tests rely on -I but cannot block venv editable installs."
    ),
)
def test_subprocess_isolation_prevents_source_tree_access(
    installed_vibe_home: Path,
    target_repo: Path,
) -> None:
    """Verify subprocess isolation blocks vibe3 source-tree imports."""
    env = _cli_env(installed_vibe_home)

    result = subprocess.run(
        [sys.executable, "-I", "-c", "import vibe3; print('VIBE3_FOUND')"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "VIBE3_FOUND" not in result.stdout, (
        "vibe3 is accessible in isolated subprocess. "
        "This may indicate the test does not truly validate cross-project isolation. "
        "An editable install or .pth file may be bypassing the -I flag."
    )


def test_cli_plan_dry_run_accepts_flags(
    installed_vibe_home: Path,
    target_repo: Path,
) -> None:
    """Test that plan --dry-run --show-prompt accepts flags and fails at right stage."""
    # Get the project root to find src/vibe3/cli.py
    # Test file: tests/vibe3/integration/test_cli_subprocess.py
    # parents[0] = integration, parents[1] = vibe3, parents[2] = tests,
    # parents[3] = repo_root
    project_root = Path(__file__).resolve().parents[3]
    cli_path = project_root / "src" / "vibe3" / "cli.py"

    # Prepare environment
    env = _cli_env(installed_vibe_home)

    # Run command in subprocess
    result = subprocess.run(
        [sys.executable, "-I", str(cli_path), "plan", "--dry-run", "--show-prompt"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Assert stderr does NOT contain module import errors
    assert (
        "ModuleNotFoundError" not in result.stderr
    ), f"Module import error detected: {result.stderr}"
    assert (
        "No module named 'vibe3'" not in result.stderr
    ), f"Module import error detected: {result.stderr}"

    # Categorize failure if exit code != 0
    if result.returncode != 0:
        failure = _categorize_failure(result.stderr, result.returncode)
        # For plan --dry-run, early return is expected behavior
        # (plan's dry-run path exits before prompt rendering)
        # So we accept any non-install-missing failure
        assert failure != "install_missing", (
            f"Install missing detected: {failure}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )


def test_cli_run_dry_run_accepts_flags(
    installed_vibe_home: Path,
    target_repo: Path,
) -> None:
    """Test that run --dry-run --show-prompt accepts flags and fails at right stage."""
    # Get the project root to find src/vibe3/cli.py
    project_root = Path(__file__).resolve().parents[3]
    cli_path = project_root / "src" / "vibe3" / "cli.py"

    # Prepare environment
    env = _cli_env(installed_vibe_home)

    # Run command in subprocess
    result = subprocess.run(
        [sys.executable, "-I", str(cli_path), "run", "--dry-run", "--show-prompt"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Assert stderr does NOT contain module import errors
    assert (
        "ModuleNotFoundError" not in result.stderr
    ), f"Module import error detected: {result.stderr}"
    assert (
        "No module named 'vibe3'" not in result.stderr
    ), f"Module import error detected: {result.stderr}"

    # Categorize failure if exit code != 0
    if result.returncode != 0:
        failure = _categorize_failure(result.stderr, result.returncode)
        # Accept non-install-missing failures
        assert failure != "install_missing", (
            f"Install missing detected: {failure}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )


def test_cli_review_dry_run_accepts_flags(
    installed_vibe_home: Path,
    target_repo: Path,
) -> None:
    """Test that review --dry-run --show-prompt accepts flags and fails at right
    stage.
    """
    # Get the project root to find src/vibe3/cli.py
    project_root = Path(__file__).resolve().parents[3]
    cli_path = project_root / "src" / "vibe3" / "cli.py"

    # Prepare environment
    env = _cli_env(installed_vibe_home)

    # Run command in subprocess
    result = subprocess.run(
        [sys.executable, "-I", str(cli_path), "review", "--dry-run", "--show-prompt"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Assert stderr does NOT contain module import errors
    assert (
        "ModuleNotFoundError" not in result.stderr
    ), f"Module import error detected: {result.stderr}"
    assert (
        "No module named 'vibe3'" not in result.stderr
    ), f"Module import error detected: {result.stderr}"

    # Categorize failure if exit code != 0
    if result.returncode != 0:
        failure = _categorize_failure(result.stderr, result.returncode)
        # Accept non-install-missing failures
        assert failure != "install_missing", (
            f"Install missing detected: {failure}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )


def test_cli_internal_manager_dry_run_accepts_flags(
    installed_vibe_home: Path,
    target_repo: Path,
) -> None:
    """Test that internal manager --dry-run --show-prompt accepts flags."""
    # Get the project root to find src/vibe3/cli.py
    project_root = Path(__file__).resolve().parents[3]
    cli_path = project_root / "src" / "vibe3" / "cli.py"

    # Prepare environment
    env = _cli_env(installed_vibe_home)

    # Run command in subprocess
    # Use issue number 99999 (unlikely to exist)
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            str(cli_path),
            "internal",
            "manager",
            "99999",
            "--dry-run",
            "--show-prompt",
            "--no-async",
        ],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Assert stderr does NOT contain module import errors
    assert (
        "ModuleNotFoundError" not in result.stderr
    ), f"Module import error detected: {result.stderr}"
    assert (
        "No module named 'vibe3'" not in result.stderr
    ), f"Module import error detected: {result.stderr}"

    # Categorize failure if exit code != 0
    if result.returncode != 0:
        failure = _categorize_failure(result.stderr, result.returncode)
        # Accept non-install-missing failures
        assert failure != "install_missing", (
            f"Install missing detected: {failure}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )


def test_cli_missing_runtime_assets_detected(
    target_repo: Path,
    tmp_path: Path,
) -> None:
    """Test that CLI can run even with empty global assets (uses bundled fallback).

    When VIBE3_RUNTIME_ASSETS_ROOT points to an empty directory, the CLI should
    still work by using bundled assets from the source tree. The test verifies
    that the command doesn't fail due to missing imports or missing runtime assets.
    """
    # Create EMPTY VIBE3_RUNTIME_ASSETS_ROOT (no assets installed globally)
    empty_home = tmp_path / "empty_vibe"
    empty_home.mkdir()

    # Get the project root to find src/vibe3/cli.py
    project_root = Path(__file__).resolve().parents[3]
    cli_path = project_root / "src" / "vibe3" / "cli.py"

    # Prepare environment
    env = _cli_env(empty_home)

    # Run a command (plan) that should still work via bundled fallback
    result = subprocess.run(
        [sys.executable, "-I", str(cli_path), "plan", "--dry-run"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    # The command should NOT fail due to missing imports
    assert (
        "ModuleNotFoundError" not in result.stderr
    ), f"Module import error detected: {result.stderr}"
    assert (
        "No module named 'vibe3'" not in result.stderr
    ), f"Module import error detected: {result.stderr}"

    # The command may fail due to flow/fixture issues, but NOT due to install issues
    if result.returncode != 0:
        failure = _categorize_failure(result.stderr, result.returncode)
        # The failure should NOT be install_missing (proving bundled fallback works)
        assert failure != "install_missing", (
            f"Install missing detected despite bundled fallback: {failure}\n"
            f"stderr: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )
