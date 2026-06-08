"""Core budget enforcement for runtime kernel.

Ensures the resident core (runtime + orchestra) stays minimal and does not
grow into a monolith by enforcing:
1. Explicit core module set naming
2. No module-level imports from business/plugin modules
3. Startup import surface stays within budget

Core Budget Contract — the core may own ONLY:
  - process lifecycle / PID / health
  - heartbeat timer and reconciliation trigger
  - event ingestion
  - job queue lifecycle
  - locks / concurrency / circuit breaker
  - status metadata

The core must NOT own:
  - plan/run/review/internal manager business semantics
  - governance decision material or prompt rendering logic
  - GitHub label policy decisions
  - command-specific worktree/tmux/codeagent-wrapper launch details
  - plugin/module-specific implementation details

Reference: GitHub issue #2182
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import helper from test_taxonomy.py for extracting module-level imports
# Re-using the canonical implementation to avoid duplication
from tests.vibe3.test_modularity.test_taxonomy import _get_module_level_imports
from vibe3.runtime.taxonomy import (
    MODULE_CATEGORY_MAP,
    ModuleCategory,
)

# Minimum parts for a valid vibe3 import (vibe3.module_name)
_MIN_VIBE3_IMPORT_PARTS = 2

# Core module set — explicit definition of runtime kernel packages
CORE_MODULES: frozenset[str] = frozenset({"runtime", "orchestra"})

# Core responsibilities — documented allowlist mapping responsibility
# categories to the kernel submodules that own them
CORE_RESPONSIBILITIES: dict[str, list[str]] = {
    "process_lifecycle": [
        "runtime.orchestra_instance",
        "runtime.service_protocol",
    ],
    "heartbeat_timer": [
        "runtime.heartbeat",
        "runtime.periodic_check_executor",
    ],
    "event_ingestion": [
        "runtime.heartbeat",  # on_tick drives event ingestion
    ],
    "job_queue_lifecycle": [
        "orchestra.queue_operations",
        "orchestra.queue_entry",
        "orchestra.queue_persistence_service",
    ],
    "concurrency_circuit_breaker": [
        "runtime.circuit_breaker",
    ],
    "status_metadata": [
        "orchestra.logging",
        "orchestra.dispatch_health_check",
    ],
    "dispatch_coordination": [
        "orchestra.global_dispatch_coordinator",
        "orchestra.dispatch_coordinator_factory",
        "orchestra.flow_dispatch",
        "orchestra.failed_gate",
        "orchestra.issue_loader",
    ],
    "protocols": [
        "orchestra.protocols",
    ],
    "domain_types": [
        "orchestra.domain_types",
    ],
    "cleanup": [
        "runtime.cleanup_executor",
    ],
    "taxonomy": [
        "runtime.taxonomy",
    ],
}

# Top-level modules the core must not import from at module level.
# Aligns with #2293 kernel startup boundary (FORBIDDEN list).
# Note: "domain" is intentionally excluded here — see FORBIDDEN_CORE_DOMAIN_PREFIXES
# and test_core_no_domain_business_entity_imports for domain-specific debt tracking.
FORBIDDEN_CORE_SOURCES: frozenset[str] = frozenset(
    {
        "services",  # command adapter business services
        "execution",  # command adapter execution primitives
        "roles",  # policy: dispatch predicates & material loading
        "agents",  # execution primitives
        "prompts",  # prompt rendering logic
    }
)

# Domain sub-paths strictly forbidden in core (aligns with #2293).
# Only event-handler registration and the orchestration facade must never be
# loaded eagerly — domain models and domain.protocols are allowed.
FORBIDDEN_CORE_DOMAIN_PREFIXES: frozenset[str] = frozenset(
    {
        "vibe3.domain.handlers",
        "vibe3.domain.orchestration_facade",
    }
)

# domain.protocols is allowed (interface definitions, not business logic).
_ALLOWED_DOMAIN_PROTOCOL_PREFIX = "vibe3.domain.protocols"

# Infrastructure modules the core may freely import
ALLOWED_CORE_SOURCES: frozenset[str] = frozenset(
    {
        "runtime",  # self-import within kernel
        "orchestra",  # self-import within kernel
        "clients",  # L6 infrastructure
        "config",  # L6 infrastructure
        "models",  # L6 infrastructure
        "observability",  # L6 infrastructure
        "utils",  # L6 infrastructure
        "environment",  # L5 environment tools
        "exceptions",  # L6 infrastructure
    }
)


class TestCoreBudget:
    """Test suite for core budget enforcement."""

    def test_core_module_set_explicit(self) -> None:
        """Verify CORE_MODULES is explicitly defined and complete.

        Acceptance criterion 1: Test names the core package/module set explicitly.
        """
        # Verify CORE_MODULES is non-empty
        assert CORE_MODULES, "CORE_MODULES must not be empty"

        # Verify it contains exactly the expected modules
        assert {"runtime", "orchestra"} == CORE_MODULES, (
            f"CORE_MODULES must contain exactly {{'runtime', 'orchestra'}}, "
            f"got {CORE_MODULES}"
        )

        # Verify each module has a corresponding __init__.py
        for module_name in CORE_MODULES:
            module_path = Path("src/vibe3") / module_name / "__init__.py"
            assert (
                module_path.exists()
            ), f"Module {module_name} must have __init__.py at {module_path}"

        # Verify each module maps to KERNEL category in taxonomy
        for module_name in CORE_MODULES:
            category = MODULE_CATEGORY_MAP.get(module_name)
            assert category == ModuleCategory.KERNEL, (
                f"Module {module_name} must map to ModuleCategory.KERNEL, "
                f"got {category}"
            )

    def test_core_no_business_imports_at_module_level(self) -> None:
        """Verify core does not import business modules at module level.

        Acceptance criterion 2: Test fails when core imports command-specific
        business modules at startup. Aligned with #2293 kernel startup boundary:
        - Top-level forbidden: services, execution, roles, agents, prompts
        - Domain sub-path forbidden: domain.handlers, domain.orchestration_facade
        - domain.protocols (interface definitions) and plain domain models are
          tracked separately in test_core_no_domain_business_entity_imports.
        """
        violations: list[str] = []

        for module_name in CORE_MODULES:
            module_dir = Path("src/vibe3") / module_name

            for py_file in module_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue

                imports = _get_module_level_imports(str(py_file))

                for imp in imports:
                    parts = imp.split(".")
                    if len(parts) < _MIN_VIBE3_IMPORT_PARTS or parts[0] != "vibe3":
                        continue
                    top_level = parts[1]

                    # Check top-level forbidden modules
                    if top_level in FORBIDDEN_CORE_SOURCES:
                        violations.append(
                            f"{py_file.relative_to('src/vibe3')}: "
                            f"imports from {top_level} ({imp})",
                        )
                    # Check forbidden domain sub-paths
                    elif any(
                        imp.startswith(prefix)
                        for prefix in FORBIDDEN_CORE_DOMAIN_PREFIXES
                    ):
                        violations.append(
                            f"{py_file.relative_to('src/vibe3')}: "
                            f"imports from forbidden domain path ({imp})",
                        )

        if violations:
            violation_list = "\n".join(f"  - {v}" for v in violations)
            pytest.fail(
                f"Core modules must not import from business/plugin modules "
                f"at module level:\n{violation_list}",
            )

    def test_core_no_domain_business_entity_imports(self) -> None:
        """Verify core does not import domain business entities at module level.

        domain.protocols (interface definitions) are allowed — these are contracts
        that core legitimately depends on.
        All other direct domain imports in core are architectural debt (#2318).
        """
        violations: list[str] = []

        for module_name in CORE_MODULES:
            module_dir = Path("src/vibe3") / module_name

            for py_file in module_dir.rglob("*.py"):
                if py_file.name == "__init__.py":
                    continue

                imports = _get_module_level_imports(str(py_file))

                for imp in imports:
                    parts = imp.split(".")
                    if (
                        len(parts) >= _MIN_VIBE3_IMPORT_PARTS
                        and parts[0] == "vibe3"
                        and parts[1] == "domain"
                        and not imp.startswith(_ALLOWED_DOMAIN_PROTOCOL_PREFIX)
                    ):
                        violations.append(
                            f"{py_file.relative_to('src/vibe3')}: {imp}",
                        )

        if violations:
            violation_list = "\n".join(f"  - {v}" for v in violations)
            pytest.fail(
                f"Core must not import domain business entities at module level "
                f"(domain.protocols is allowed):\n{violation_list}",
            )

    def test_core_responsibility_allowlist_documented(self) -> None:
        """Verify all kernel files have documented responsibilities.

        Acceptance criteria:
        - Criterion 3: Test includes a concise responsibility allowlist
        - Criterion 4: Future pluginization work can rely on this boundary
        """
        # Build a set of all modules covered by CORE_RESPONSIBILITIES
        covered_modules: set[str] = set()
        for modules in CORE_RESPONSIBILITIES.values():
            covered_modules.update(modules)

        # Check all .py files in runtime/ and orchestra/
        missing_modules: list[str] = []

        for module_name in CORE_MODULES:
            module_dir = Path("src/vibe3") / module_name

            for py_file in module_dir.rglob("*.py"):
                # Skip __init__.py
                if py_file.name == "__init__.py":
                    continue

                # Build module path (e.g., "runtime.heartbeat")
                relative_path = py_file.relative_to("src/vibe3")
                module_path = str(relative_path.with_suffix("")).replace("/", ".")

                # Check if module is covered
                if module_path not in covered_modules:
                    missing_modules.append(module_path)

        # Fail if any module is missing responsibility assignment
        if missing_modules:
            missing_list = "\n".join(f"  - {m}" for m in missing_modules)
            pytest.fail(
                f"Kernel modules must have documented responsibilities in "
                f"CORE_RESPONSIBILITIES:\n{missing_list}\n\n"
                f"Add each module to an appropriate responsibility category "
                f"or create a new category if needed.",
            )
