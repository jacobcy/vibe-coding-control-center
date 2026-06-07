"""Unit tests for CommandAdapterRegistry."""

from __future__ import annotations

import sys

import pytest

from vibe3.execution.command_adapter import (
    CommandAdapterEntry,
    CommandAdapterError,
    CommandAdapterRegistry,
    ResolvedAdapter,
    build_default_registry,
)
from vibe3.models.job import CommandType


def test_command_type_enum():
    """Test that CommandType enum has all expected values."""
    assert CommandType.MANAGER == "manager"
    assert CommandType.PLAN == "plan"
    assert CommandType.RUN == "run"
    assert CommandType.REVIEW == "review"
    assert CommandType.GOVERNANCE_SCAN == "governance-scan"
    assert CommandType.SUPERVISOR_APPLY == "supervisor-apply"


def test_command_adapter_entry_frozen():
    """Test that CommandAdapterEntry is frozen (immutable)."""
    entry = CommandAdapterEntry(
        job_type=CommandType.PLAN,
        import_path="vibe3.roles.plan",
        callable_name="PLAN_SYNC_SPEC",
        description="Test entry",
    )

    # Should not be able to modify
    with pytest.raises(AttributeError):
        entry.job_type = CommandType.RUN  # type: ignore[misc]


def test_registry_construction_no_business_imports():
    """Test that building registry does not import command business modules."""
    # Record modules before
    before = set(sys.modules.keys())

    # Build registry
    registry = build_default_registry()

    # Record modules after
    after = set(sys.modules.keys())

    # Find new modules
    new_modules = after - before

    # Check for command business modules
    command_modules = [
        m
        for m in new_modules
        if any(
            pattern in m
            for pattern in [
                "commands.plan",
                "commands.run",
                "commands.review",
                "roles.plan",
                "roles.review",
                "roles.run_command",
                "roles.manager",
                "roles.governance",
                "roles.supervisor",
            ]
        )
    ]

    assert len(command_modules) == 0, (
        f"Command business modules imported during registry construction: "
        f"{command_modules}"
    )
    assert len(registry.list_registered()) == 6


def test_registry_register():
    """Test registering an adapter entry."""
    registry = CommandAdapterRegistry()

    entry = CommandAdapterEntry(
        job_type=CommandType.PLAN,
        import_path="vibe3.roles.plan",
        callable_name="PLAN_SYNC_SPEC",
        description="Planner role",
    )

    registry.register(entry)

    assert registry.is_registered(CommandType.PLAN)
    assert CommandType.PLAN in registry.list_registered()


def test_registry_register_duplicate():
    """Test that registering the same job type twice raises an error."""
    registry = CommandAdapterRegistry()

    entry1 = CommandAdapterEntry(
        job_type=CommandType.PLAN,
        import_path="vibe3.roles.plan",
        callable_name="PLAN_SYNC_SPEC",
        description="First entry",
    )

    entry2 = CommandAdapterEntry(
        job_type=CommandType.PLAN,
        import_path="vibe3.roles.plan",
        callable_name="OTHER_SPEC",
        description="Second entry",
    )

    registry.register(entry1)

    with pytest.raises(CommandAdapterError, match="already registered"):
        registry.register(entry2)


def test_registry_resolve_plan_adapter():
    """Test resolving the plan adapter."""
    registry = build_default_registry()

    resolved = registry.resolve(CommandType.PLAN)

    assert isinstance(resolved, ResolvedAdapter)
    assert resolved.entry.job_type == CommandType.PLAN
    assert resolved.entry.import_path == "vibe3.roles.plan"
    assert resolved.entry.callable_name == "PLAN_SYNC_SPEC"
    assert resolved.module_name == "vibe3.roles.plan"
    assert "PLAN_SYNC_SPEC" in resolved.qualname

    # Verify it's the actual spec
    from vibe3.roles.plan import PLAN_SYNC_SPEC

    assert resolved.callable is PLAN_SYNC_SPEC


def test_registry_resolve_run_adapter():
    """Test resolving the run adapter."""
    registry = build_default_registry()

    resolved = registry.resolve(CommandType.RUN)

    assert isinstance(resolved, ResolvedAdapter)
    assert resolved.entry.job_type == CommandType.RUN
    assert resolved.entry.import_path == "vibe3.roles.run_request"
    assert resolved.entry.callable_name == "RUN_SYNC_SPEC"

    # Verify it's the actual spec
    from vibe3.roles.run_request import RUN_SYNC_SPEC

    assert resolved.callable is RUN_SYNC_SPEC


def test_registry_resolve_review_adapter():
    """Test resolving the review adapter."""
    registry = build_default_registry()

    resolved = registry.resolve(CommandType.REVIEW)

    assert isinstance(resolved, ResolvedAdapter)
    assert resolved.entry.job_type == CommandType.REVIEW
    assert resolved.entry.import_path == "vibe3.roles.review"
    assert resolved.entry.callable_name == "REVIEW_SYNC_SPEC"

    # Verify it's the actual spec
    from vibe3.roles.review import REVIEW_SYNC_SPEC

    assert resolved.callable is REVIEW_SYNC_SPEC


def test_registry_resolve_manager_adapter():
    """Test resolving the manager adapter."""
    registry = build_default_registry()

    resolved = registry.resolve(CommandType.MANAGER)

    assert isinstance(resolved, ResolvedAdapter)
    assert resolved.entry.job_type == CommandType.MANAGER
    assert resolved.entry.import_path == "vibe3.roles.manager"
    assert resolved.entry.callable_name == "MANAGER_SYNC_SPEC"

    # Verify it's the actual spec
    from vibe3.roles.manager import MANAGER_SYNC_SPEC

    assert resolved.callable is MANAGER_SYNC_SPEC


def test_registry_resolve_governance_adapter():
    """Test resolving the governance adapter."""
    registry = build_default_registry()

    resolved = registry.resolve(CommandType.GOVERNANCE_SCAN)

    assert isinstance(resolved, ResolvedAdapter)
    assert resolved.entry.job_type == CommandType.GOVERNANCE_SCAN
    assert resolved.entry.import_path == "vibe3.roles.governance"
    assert resolved.entry.callable_name == "GOVERNANCE_ROLE"

    # Verify it's the actual role definition
    from vibe3.roles.governance import GOVERNANCE_ROLE

    assert resolved.callable is GOVERNANCE_ROLE


def test_registry_resolve_supervisor_adapter():
    """Test resolving the supervisor adapter."""
    registry = build_default_registry()

    resolved = registry.resolve(CommandType.SUPERVISOR_APPLY)

    assert isinstance(resolved, ResolvedAdapter)
    assert resolved.entry.job_type == CommandType.SUPERVISOR_APPLY
    assert resolved.entry.import_path == "vibe3.roles.supervisor"
    assert resolved.entry.callable_name == "SUPERVISOR_CLI_SYNC_SPEC"

    # Verify it's the actual spec
    from vibe3.roles.supervisor import SUPERVISOR_CLI_SYNC_SPEC

    assert resolved.callable is SUPERVISOR_CLI_SYNC_SPEC


def test_registry_resolve_missing_adapter():
    """Test that resolving an unregistered job type raises an error."""
    registry = CommandAdapterRegistry()

    with pytest.raises(CommandAdapterError, match="No adapter registered"):
        registry.resolve(CommandType.PLAN)


def test_registry_resolve_bad_import_path():
    """Test that resolving with an invalid import path raises an error."""
    registry = CommandAdapterRegistry()

    entry = CommandAdapterEntry(
        job_type=CommandType.PLAN,
        import_path="vibe3.nonexistent.module",
        callable_name="SOME_CALLABLE",
        description="Bad import path",
    )

    registry.register(entry)

    with pytest.raises(CommandAdapterError, match="Failed to import module"):
        registry.resolve(CommandType.PLAN)


def test_registry_resolve_bad_callable_name():
    """Test that resolving with an invalid callable name raises an error."""
    registry = CommandAdapterRegistry()

    entry = CommandAdapterEntry(
        job_type=CommandType.PLAN,
        import_path="vibe3.roles.plan",
        callable_name="NONEXISTENT_CALLABLE",
        description="Bad callable name",
    )

    registry.register(entry)

    with pytest.raises(CommandAdapterError, match="Callable.*not found"):
        registry.resolve(CommandType.PLAN)


def test_registry_resolve_caching():
    """Test that resolve() caches results and returns the same object."""
    registry = build_default_registry()

    resolved1 = registry.resolve(CommandType.PLAN)
    resolved2 = registry.resolve(CommandType.PLAN)

    # Should be the exact same object
    assert resolved1 is resolved2
    assert resolved1.callable is resolved2.callable


def test_registry_list_registered():
    """Test listing all registered job types."""
    registry = build_default_registry()

    registered = registry.list_registered()

    assert len(registered) == 6
    assert CommandType.MANAGER in registered
    assert CommandType.PLAN in registered
    assert CommandType.RUN in registered
    assert CommandType.REVIEW in registered
    assert CommandType.GOVERNANCE_SCAN in registered
    assert CommandType.SUPERVISOR_APPLY in registered


def test_registry_is_registered():
    """Test checking if a job type is registered."""
    registry = CommandAdapterRegistry()

    assert not registry.is_registered(CommandType.PLAN)

    entry = CommandAdapterEntry(
        job_type=CommandType.PLAN,
        import_path="vibe3.roles.plan",
        callable_name="PLAN_SYNC_SPEC",
        description="Planner",
    )

    registry.register(entry)

    assert registry.is_registered(CommandType.PLAN)
    assert not registry.is_registered(CommandType.RUN)


def test_build_default_registry():
    """Test that build_default_registry returns a populated registry."""
    registry = build_default_registry()

    assert isinstance(registry, CommandAdapterRegistry)
    assert len(registry.list_registered()) == 6

    # All types should be registered
    for job_type in CommandType:
        assert registry.is_registered(job_type), f"{job_type} not registered"


def test_resolved_adapter_attributes():
    """Test that ResolvedAdapter has all expected attributes."""
    registry = build_default_registry()
    resolved = registry.resolve(CommandType.PLAN)

    assert hasattr(resolved, "entry")
    assert hasattr(resolved, "callable")
    assert hasattr(resolved, "module_name")
    assert hasattr(resolved, "qualname")

    assert isinstance(resolved.entry, CommandAdapterEntry)
    assert resolved.callable is not None
    assert isinstance(resolved.module_name, str)
    assert isinstance(resolved.qualname, str)


def test_resolved_adapter_frozen():
    """Test that ResolvedAdapter is frozen (immutable)."""
    registry = build_default_registry()
    resolved = registry.resolve(CommandType.PLAN)

    with pytest.raises(AttributeError):
        resolved.module_name = "other"  # type: ignore[misc]


def test_build_default_registry_completeness():
    """Test that build_default_registry registers all CommandType values."""
    registry = build_default_registry()
    registered = set(registry.list_registered())
    assert registered == set(CommandType)
