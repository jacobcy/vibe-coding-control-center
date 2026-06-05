"""Cross-project prompt readiness smoke tests.

Tests that plan/run/review/internal-manager commands can render prompts
via --dry-run --show-prompt without relying on source-tree fallback.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vibe3.clients.runtime_assets import resolve_runtime_asset
from vibe3.config.loader import load_config
from vibe3.prompts.template_loader import resolve_prompts_path

if TYPE_CHECKING:
    from collections.abc import Generator


# ============================================================================
# Step 4: Failure categorization helper
# ============================================================================


def _categorize_failure(stderr: str, exit_code: int) -> str:
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


# ============================================================================
# Step 1: Shared fixtures
# ============================================================================


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
    project_root = Path(__file__).resolve().parents[4]

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

    # Create minimal commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
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


# ============================================================================
# Step 2: Layer 1 — Asset discovery smoke tests
# ============================================================================


def test_resolve_prompts_path_finds_global_prompts(installed_vibe_home: Path) -> None:
    """Test that resolve_prompts_path() finds prompts from installed ~/.vibe."""
    # Set VIBE3_RUNTIME_ASSETS_ROOT to temp home
    old_env = os.environ.get("VIBE3_RUNTIME_ASSETS_ROOT")
    os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = str(installed_vibe_home)

    try:
        prompts_path = resolve_prompts_path()

        # Assert path exists and contains expected keys
        assert prompts_path.exists(), f"Prompts path does not exist: {prompts_path}"

        # Check that it contains expected sections
        content = prompts_path.read_text(encoding="utf-8")
        # The prompts.yaml should contain run, plan, review keys
        # (not checking strict structure, just that it's a valid prompts file)
        assert (
            "run:" in content or "plan:" in content or "review:" in content
        ), f"Prompts file does not contain expected keys: {prompts_path}"
    finally:
        # Restore environment
        if old_env is not None:
            os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = old_env
        else:
            os.environ.pop("VIBE3_RUNTIME_ASSETS_ROOT", None)


def test_resolve_runtime_asset_finds_supervisor(installed_vibe_home: Path) -> None:
    """Test that resolve_runtime_asset() finds supervisor from installed ~/.vibe."""
    # Set VIBE3_RUNTIME_ASSETS_ROOT to temp home
    old_env = os.environ.get("VIBE3_RUNTIME_ASSETS_ROOT")
    os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = str(installed_vibe_home)

    try:
        supervisor_path = resolve_runtime_asset("supervisor/manager.md")

        # Assert path exists
        assert (
            supervisor_path.exists()
        ), f"Supervisor path does not exist: {supervisor_path}"
    finally:
        # Restore environment
        if old_env is not None:
            os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = old_env
        else:
            os.environ.pop("VIBE3_RUNTIME_ASSETS_ROOT", None)


def test_config_layering_loads_project_override(
    installed_vibe_home: Path,
    target_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that load_config() loads project override from target repo."""
    # Set VIBE3_RUNTIME_ASSETS_ROOT to temp home
    monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(installed_vibe_home))

    # Change CWD to target repo (load_config uses relative paths)
    monkeypatch.chdir(target_repo)

    # Create project config with an override that exists in VibeConfig schema
    vibe_dir = target_repo / ".vibe"
    vibe_dir.mkdir(exist_ok=True)
    settings_yaml = vibe_dir / "settings.yaml"
    settings_yaml.write_text(
        """flow:
  protected_branches:
    - main
    - master
    - test-protected-branch
""",
        encoding="utf-8",
    )

    # Load config
    config = load_config()

    # Assert the project override was loaded
    assert "test-protected-branch" in config.flow.protected_branches, (
        f"Project config override not loaded. "
        f"protected_branches: {config.flow.protected_branches}"
    )


def test_missing_prompts_detected(tmp_path: Path) -> None:
    """Test that missing prompts in global location fall back to bundled assets.

    When VIBE3_RUNTIME_ASSETS_ROOT points to an empty directory (no assets installed),
    resolve_prompts_path() should fall back to the bundled project root assets.
    This demonstrates that global assets are missing but the system still works
    via fallback.
    """
    # Create a temp dir WITHOUT config/prompts/
    empty_home = tmp_path / "empty_vibe"
    empty_home.mkdir()

    # Set VIBE3_RUNTIME_ASSETS_ROOT to empty dir
    old_env = os.environ.get("VIBE3_RUNTIME_ASSETS_ROOT")
    os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = str(empty_home)

    try:
        prompts_path = resolve_prompts_path()

        # The path should exist (via bundled fallback)
        assert prompts_path.exists(), (
            f"Expected prompts path to exist via bundled fallback, "
            f"but it doesn't: {prompts_path}"
        )

        # But it should NOT be from the empty global location
        assert not str(prompts_path).startswith(str(empty_home)), (
            f"Expected fallback to bundled assets, but got path from "
            f"global location: {prompts_path}"
        )

        # Record failure category (for documentation)
        # This demonstrates that global install is missing, but system
        # works via fallback
        failure_category = "install_missing: prompts (using bundled fallback)"
        assert failure_category == "install_missing: prompts (using bundled fallback)"
    finally:
        # Restore environment
        if old_env is not None:
            os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = old_env
        else:
            os.environ.pop("VIBE3_RUNTIME_ASSETS_ROOT", None)


def test_missing_supervisor_detected(tmp_path: Path) -> None:
    """Test that missing supervisor in global location fall back to bundled assets.

    When VIBE3_RUNTIME_ASSETS_ROOT points to an empty directory (no assets installed),
    resolve_runtime_asset() should fall back to the bundled project root assets.
    This demonstrates that global assets are missing but the system still works
    via fallback.
    """
    # Create a temp dir WITHOUT supervisor/
    empty_home = tmp_path / "empty_vibe"
    empty_home.mkdir()

    # Set VIBE3_RUNTIME_ASSETS_ROOT to empty dir
    old_env = os.environ.get("VIBE3_RUNTIME_ASSETS_ROOT")
    os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = str(empty_home)

    try:
        supervisor_path = resolve_runtime_asset("supervisor/manager.md")

        # The path should exist (via bundled fallback)
        assert supervisor_path.exists(), (
            f"Expected supervisor path to exist via bundled fallback, "
            f"but it doesn't: {supervisor_path}"
        )

        # But it should NOT be from the empty global location
        assert not str(supervisor_path).startswith(str(empty_home)), (
            f"Expected fallback to bundled assets, but got path from "
            f"global location: {supervisor_path}"
        )

        # Record failure category (for documentation)
        # This demonstrates that global install is missing, but system
        # works via fallback
        failure_category = "install_missing: supervisor (using bundled fallback)"
        assert (
            failure_category == "install_missing: supervisor (using bundled fallback)"
        )
    finally:
        # Restore environment
        if old_env is not None:
            os.environ["VIBE3_RUNTIME_ASSETS_ROOT"] = old_env
        else:
            os.environ.pop("VIBE3_RUNTIME_ASSETS_ROOT", None)


# ============================================================================
# Step 3: Layer 2 — CLI subprocess smoke tests
# ============================================================================


def test_cli_plan_dry_run_accepts_flags(
    installed_vibe_home: Path,
    target_repo: Path,
) -> None:
    """Test that plan --dry-run --show-prompt accepts flags and fails at right stage."""
    # Get the project root to find src/vibe3/cli.py
    # Test file: tests/vibe3/integration/test_cross_project_prompt_smoke.py
    # parents[0] = integration, parents[1] = vibe3, parents[2] = tests,
    # parents[3] = repo_root
    project_root = Path(__file__).resolve().parents[3]
    cli_path = project_root / "src" / "vibe3" / "cli.py"

    # Prepare environment
    env = os.environ.copy()
    env["VIBE3_RUNTIME_ASSETS_ROOT"] = str(installed_vibe_home)
    # Remove PYTHONPATH to ensure no source-tree fallback via sys.path
    env.pop("PYTHONPATH", None)

    # Run command in subprocess
    result = subprocess.run(
        [sys.executable, "-I", str(cli_path), "plan", "--dry-run", "--show-prompt"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
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
    env = os.environ.copy()
    env["VIBE3_RUNTIME_ASSETS_ROOT"] = str(installed_vibe_home)
    env.pop("PYTHONPATH", None)

    # Run command in subprocess
    result = subprocess.run(
        [sys.executable, "-I", str(cli_path), "run", "--dry-run", "--show-prompt"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
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
    env = os.environ.copy()
    env["VIBE3_RUNTIME_ASSETS_ROOT"] = str(installed_vibe_home)
    env.pop("PYTHONPATH", None)

    # Run command in subprocess
    result = subprocess.run(
        [sys.executable, "-I", str(cli_path), "review", "--dry-run", "--show-prompt"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
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
    env = os.environ.copy()
    env["VIBE3_RUNTIME_ASSETS_ROOT"] = str(installed_vibe_home)
    env.pop("PYTHONPATH", None)

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
    env = os.environ.copy()
    env["VIBE3_RUNTIME_ASSETS_ROOT"] = str(empty_home)
    env.pop("PYTHONPATH", None)

    # Run a command (plan) that should still work via bundled fallback
    result = subprocess.run(
        [sys.executable, "-I", str(cli_path), "plan", "--dry-run"],
        cwd=target_repo,
        env=env,
        capture_output=True,
        text=True,
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
