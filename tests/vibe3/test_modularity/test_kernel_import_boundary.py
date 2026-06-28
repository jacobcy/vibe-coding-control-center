"""Kernel import boundary guard.

Ensures that importing vibe3.server does not trigger eager loading of
handler, role, agent, service, prompt, or execution modules.

The kernel should be minimal — just enough to boot the serve process
and accept stop signals. All business logic modules must be lazy-loaded
by the orchestra layer after startup.

Allowed at import time (kernel):
  vibe3.clients, vibe3.config, vibe3.models, vibe3.observability,
  vibe3.orchestra, vibe3.runtime, vibe3.server, vibe3.utils,
  vibe3.environment, vibe3.exceptions

Forbidden at import time (lazy by orchestra):
  vibe3.domain.handlers.*, vibe3.domain.orchestration_facade,
  vibe3.roles.*, vibe3.agents.*, vibe3.services.*,
  vibe3.prompts.*, vibe3.execution.*

Reference: GitHub issue #2161
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

# Modules that must NOT appear in sys.modules after kernel import.
# Checked at package granularity (e.g. vibe3.roles matches vibe3.roles.manager).
FORBIDDEN_MODULES = [
    "vibe3.domain.handlers",
    "vibe3.domain.orchestration_facade",
    "vibe3.roles",
    "vibe3.agents",
    "vibe3.services",
    "vibe3.prompts",
    "vibe3.execution",
]

# Modules that ARE allowed in kernel.
ALLOWED_MODULES = [
    "vibe3.clients",
    "vibe3.config",
    "vibe3.models",
    "vibe3.observability",
    "vibe3.orchestra",
    "vibe3.runtime",
    "vibe3.server",
    "vibe3.utils",
    "vibe3.environment",
    "vibe3.exceptions",
]


def _check_kernel_import_boundary() -> list[str]:
    """Run kernel import in subprocess and return list of forbidden modules found."""
    forbidden_repr = repr(FORBIDDEN_MODULES)
    check_script = textwrap.dedent(
        f"""\
import sys

# Import the kernel entry point
import vibe3.server.app  # noqa: F401

# Collect all loaded vibe3 modules
loaded = sorted(m for m in sys.modules if m.startswith("vibe3."))

# Check against forbidden list
forbidden_modules = {forbidden_repr}
forbidden = []
for fm in forbidden_modules:
    for m in loaded:
        if m == fm or m.startswith(fm + "."):
            forbidden.append(m)

if forbidden:
    print("FORBIDDEN:" + ",".join(forbidden))
else:
    print("OK")
"""
    )

    result = subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True,
        timeout=15,
        env={
            **os.environ,
            "PYTHONPATH": str(Path("src").resolve()),
        },
    )

    if result.returncode != 0:
        return [f"subprocess failed: {result.stderr.strip()}"]

    output = result.stdout.strip()
    if output.startswith("FORBIDDEN:"):
        return output[len("FORBIDDEN:") :].split(",")

    return []


def test_kernel_no_eager_business_imports() -> None:
    """Kernel startup must not import forbidden business modules."""
    violations = _check_kernel_import_boundary()
    assert violations == [], (
        f"Kernel imported forbidden modules: {', '.join(violations)}. "
        "Move these imports into function bodies for lazy loading."
    )


def test_allowed_modules_are_importable() -> None:
    """Verify allowed kernel modules can be imported independently."""
    failures = []
    for module_name in ALLOWED_MODULES:
        init_path = Path(f"src/vibe3/{module_name.split('.')[-1]}/__init__.py")
        if not init_path.exists():
            continue
        result = subprocess.run(
            [sys.executable, "-c", f"import {module_name}"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "PYTHONPATH": str(Path("src").resolve())},
        )
        if result.returncode != 0:
            failures.append(f"{module_name}: {result.stderr.strip()}")

    assert failures == [], f"Allowed modules failed to import: {failures}"
