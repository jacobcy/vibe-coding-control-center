"""Tests for module import independence."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestIndependentImport:
    """Test that modules can be imported independently."""

    @pytest.mark.slow
    def test_module_imports_independently(self, module_registry: list[str]) -> None:
        """Verify each module can be imported in isolation.

        Runs each module import in a separate subprocess to ensure
        it doesn't require other vibe3 modules to be imported first.
        """
        failures = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            # Run import in isolated subprocess
            result = subprocess.run(
                [sys.executable, "-c", f"import vibe3.{module_name}"],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "PYTHONPATH": str(Path("src").resolve())},
            )

            if result.returncode != 0:
                failures.append(
                    f"{module_name}: import failed\n"
                    f"  stdout: {result.stdout}\n"
                    f"  stderr: {result.stderr}"
                )

        if failures:
            pytest.fail(
                "Modules that cannot be imported independently:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )

    @pytest.mark.slow
    @pytest.mark.xfail(
        reason="Known architectural debt: 5 modules trigger unexpected cross-module "
        "imports (agents, commands, execution, prompts, server)"
    )
    def test_no_cross_module_side_effects(self, module_registry: list[str]) -> None:
        """Verify modules don't trigger unexpected cross-module imports.

        For each module, imports it in isolation and checks sys.modules
        for any other vibe3 modules that were loaded as side effects.

        Allowed side effects:
        - Imports from the same module's subpackage
        - Imports from layer-6 infrastructure modules (designed to be independent)
        """
        failures = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            # Import module and check sys.modules in subprocess
            check_script = textwrap.dedent(f"""
import sys
import vibe3.{module_name}

# Get all vibe3 modules loaded
loaded = [m for m in sys.modules.keys() if m.startswith('vibe3.')]

# Filter out expected modules
expected_prefix = 'vibe3.{module_name}'
layer6_modules = [
    'vibe3.adapters', 'vibe3.clients', 'vibe3.config', 'vibe3.exceptions',
    'vibe3.models', 'vibe3.observability', 'vibe3.utils',
    'vibe3.orchestra', 'vibe3.server', 'vibe3.runtime'
]

unexpected = []
for m in loaded:
    # Skip if from same module's subpackage
    if m.startswith(expected_prefix):
        continue
    # Skip if layer-6 infrastructure module
    if any(m.startswith(l6) for l6 in layer6_modules):
        continue
    # This is an unexpected cross-module import
    unexpected.append(m)

if unexpected:
    print('UNEXPECTED:', ','.join(unexpected))
else:
    print('OK')
""")
            result = subprocess.run(
                [sys.executable, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "PYTHONPATH": str(Path("src").resolve())},
            )

            if result.returncode != 0:
                failures.append(
                    f"{module_name}: check failed\n"
                    f"  stdout: {result.stdout}\n"
                    f"  stderr: {result.stderr}"
                )
            elif "UNEXPECTED:" in result.stdout:
                unexpected = result.stdout.split("UNEXPECTED:")[1].strip()
                failures.append(
                    f"{module_name}: unexpected cross-module imports: {unexpected}"
                )

        if failures:
            pytest.fail(
                "Unexpected cross-module side effects:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )


class TestMockFeasibility:
    """Test that classes can be mocked for unit testing."""

    @pytest.mark.slow
    def test_classes_are_mockable(self, module_registry: list[str]) -> None:
        """Verify classes exported via __all__ can be mocked.

        This validates that classes don't have exotic __init__ side effects
        (like mandatory network calls) that would break unit testing.
        """
        failures = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            # Check mockability in subprocess
            check_script = textwrap.dedent(f"""
import sys
from unittest.mock import Mock, patch

try:
    module = __import__('vibe3.{module_name}', fromlist=['__all__'])

    if not hasattr(module, '__all__'):
        print('OK: no __all__')
        sys.exit(0)

    for name in module.__all__:
        obj = getattr(module, name, None)
        if obj is None:
            continue

        # Only test classes
        if not isinstance(obj, type):
            continue

        # Try to create a Mock
        try:
            mock = Mock(spec=obj)
            # Try to patch
            with patch(f'vibe3.{module_name}.{{name}}'):
                pass
        except Exception as e:
            print(f'FAIL: {{name}} - {{e}}')
            sys.exit(1)

    print('OK')
except Exception as e:
    print(f'ERROR: {{e}}')
    sys.exit(1)
""")
            result = subprocess.run(
                [sys.executable, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, "PYTHONPATH": str(Path("src").resolve())},
            )

            if result.returncode != 0:
                failures.append(f"{module_name}: {result.stdout.strip()}")

        if failures:
            pytest.fail(
                "Classes that cannot be mocked:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )
