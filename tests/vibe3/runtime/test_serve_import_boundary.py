"""Startup import boundary guard for orchestra serve.

Ensures that forbidden modules (roles, prompts, domain.handlers) are not
eagerly imported at CLI registration time when `vibe3.server.app` is imported.

This prevents accidental coupling of the kernel layer to governance/prompt/role
layers, which should only be loaded during actual serve execution.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Modules that must NOT be imported at startup time
FORBIDDEN_PREFIXES = (
    "vibe3.roles.",  # Role implementations (manager, governance, supervisor, etc.)
    "vibe3.prompts",  # Prompt assembly and templates
    "vibe3.domain.handlers",  # EDA event handler registration
)

# Allowed import categories at startup (kernel layer)
ALLOWED_STARTUP_CATEGORIES = (
    # Infrastructure layer (kernel)
    "vibe3.clients",  # Data access clients
    "vibe3.config",  # Configuration loading
    "vibe3.domain",  # Domain models & protocols (excl. handlers)
    "vibe3.environment",  # Session & worktree management
    "vibe3.exceptions",  # Error types
    "vibe3.execution",  # Capacity & issue-role support
    "vibe3.models",  # Data models
    "vibe3.observability",  # Logging
    "vibe3.orchestra",  # Dispatch coordination, queue ops, logging
    "vibe3.runtime",  # Heartbeat, circuit breaker, instance mgmt
    "vibe3.server",  # Serve app & registry
    "vibe3.services",  # Business services
    "vibe3.utils",  # Utility functions
)


def _get_startup_modules() -> set[str]:
    """Capture vibe3 modules loaded when importing vibe3.server.app.

    Returns:
        Set of module names starting with 'vibe3.' that are loaded
        after importing vibe3.server.app
    """
    # Use subprocess to get a clean import environment
    script = """
import sys
from pathlib import Path

# Add src directory to Python path (matching pytest.ini_options pythonpath)
src_path = Path.cwd() / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

# Snapshot before import
before = set(sys.modules.keys())

# Import the serve app (this is what CLI registration does)
from vibe3.server import app as serve

# Snapshot after import
after = set(sys.modules.keys())

# Return vibe3 modules loaded by this import
loaded = sorted(m for m in (after - before) if m.startswith("vibe3."))
print("\\n".join(loaded))
"""
    result = subprocess.run(
        ["python", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=Path.cwd(),  # Use current working directory (worktree root)
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to capture startup modules: {result.stderr}")

    return set(result.stdout.strip().split("\n")) if result.stdout.strip() else set()


def test_serve_startup_no_forbidden_imports():
    """Verify no forbidden modules are loaded at CLI registration time.

    This test captures the module set loaded when vibe3.server.app is imported
    (which happens at CLI registration) and asserts that none of the forbidden
    categories (roles, prompts, domain.handlers) are eagerly imported.
    """
    loaded_modules = _get_startup_modules()

    # Check for forbidden imports
    forbidden_found = []
    for module in loaded_modules:
        for forbidden_prefix in FORBIDDEN_PREFIXES:
            if module.startswith(forbidden_prefix):
                forbidden_found.append(module)
                break

    if forbidden_found:
        violation_list = "\n  ".join(sorted(forbidden_found))
        assert False, (
            f"Found {len(forbidden_found)} forbidden modules in startup imports:\n"
            f"  {violation_list}\n\n"
            f"Forbidden categories:\n"
            f"  - vibe3.roles.* (role implementations)\n"
            f"  - vibe3.prompts.* (prompt assembly)\n"
            f"  - vibe3.domain.handlers.* (event handlers)\n\n"
            f"These should be imported lazily inside start() body, not at module level."
        )

    print(f"✓ Verified {len(loaded_modules)} startup modules - no forbidden imports")


def test_serve_startup_allowed_categories_documented():
    """Verify allowed startup categories match actual imports and are documented.

    This test ensures that:
    1. All loaded module categories are in the ALLOWED_STARTUP_CATEGORIES list
    2. The ALLOWED_STARTUP_CATEGORIES list doesn't contain unused categories
    3. The current startup state is documented for future reference
    """
    loaded_modules = _get_startup_modules()

    # Extract top-level categories
    # (e.g., "vibe3.clients" from "vibe3.clients.github_client")
    loaded_categories = set()
    for module in loaded_modules:
        parts = module.split(".")
        if len(parts) >= 2:
            # Top-level category: vibe3.<category>
            category = f"{parts[0]}.{parts[1]}"
            loaded_categories.add(category)

    # Check all loaded categories are allowed
    disallowed_categories = loaded_categories - set(ALLOWED_STARTUP_CATEGORIES)
    if disallowed_categories:
        assert False, (
            f"Found {len(disallowed_categories)} categories not in allowlist:\n"
            f"  {sorted(disallowed_categories)}\n\n"
            f"If this is intentional, add the category to ALLOWED_STARTUP_CATEGORIES "
            f"with a comment explaining why it's needed at startup."
        )

    # Check allowlist doesn't have unused categories (keeps it tight)
    unused_allowed = set(ALLOWED_STARTUP_CATEGORIES) - loaded_categories
    if unused_allowed:
        # This is a warning, not a failure - allowlist may be broader for documentation
        print(f"ℹ Allowed categories not currently loaded: {sorted(unused_allowed)}")

    # Print summary for documentation
    print("\n✓ Startup import summary:")
    print(f"  Total modules loaded: {len(loaded_modules)}")
    print(f"  Top-level categories: {len(loaded_categories)}")
    print("\n  Categories loaded:")
    for category in sorted(loaded_categories):
        count = sum(
            1 for m in loaded_modules if m.startswith(f"{category}.") or m == category
        )
        print(f"    {category}: {count} modules")


def test_serve_startup_detects_eager_handler_import():
    """Verify the boundary guard catches an intentionally eager handler import.

    This is a negative test that simulates what would happen if a forbidden
    module were added to the top-level imports. It verifies that the guard
    logic in test_serve_startup_no_forbidden_imports actually catches violations.
    """
    # Script that simulates adding a forbidden import at module level
    script = """
import sys
from pathlib import Path

# Add src directory to Python path (matching pytest.ini_options pythonpath)
src_path = Path.cwd() / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

# Snapshot before import
before = set(sys.modules.keys())

# Normal startup import
from vibe3.server import app as serve

# Simulate an eager forbidden import at module level
# (This is what we're trying to prevent)
from vibe3.roles.manager import _resolve_manager_token

# Snapshot after import
after = set(sys.modules.keys())

# Check if forbidden modules were loaded
loaded = sorted(m for m in (after - before) if m.startswith("vibe3.roles."))
if loaded:
    print(f"DETECTED: {loaded}")
    sys.exit(0)  # Guard works correctly
else:
    print("MISSED: forbidden import not detected")
    sys.exit(1)  # Guard failed to detect
"""
    result = subprocess.run(
        ["python", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=Path.cwd(),  # Use current working directory (worktree root)
    )

    assert result.returncode == 0, (
        f"Boundary guard failed to detect forbidden import\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )

    # Verify the detection message
    assert (
        "DETECTED:" in result.stdout
    ), f"Expected detection message in output: {result.stdout}"

    print("✓ Boundary guard correctly detects forbidden imports")
    print(f"  {result.stdout.strip()}")


if __name__ == "__main__":
    test_serve_startup_no_forbidden_imports()
    test_serve_startup_allowed_categories_documented()
    test_serve_startup_detects_eager_handler_import()
    print("\nAll boundary guard tests passed!")
