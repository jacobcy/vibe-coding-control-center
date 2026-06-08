"""Command adapter registry for lazy loading of command job handlers.

This module provides a registry that maps command types (from vibe3.models.job)
to import paths, resolving the actual callable only at execution time.

Uses CommandType from the job contracts module (#2163) as the canonical
type definition. ResolvedAdapter.callable is typed as Callable[..., Any]
pending #2165 executor integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from vibe3.models import CommandType


@dataclass(frozen=True)
class CommandAdapterEntry:
    """Registry entry for a command adapter.

    Attributes:
        job_type: The command this adapter handles
        import_path: Dotted module path (e.g., "vibe3.roles.plan")
        callable_name: Function/class name within the module
        description: Human-readable description
    """

    job_type: CommandType
    import_path: str
    callable_name: str
    description: str


class CommandAdapterError(Exception):
    """Error raised when adapter resolution fails."""

    pass


@dataclass(frozen=True)
class ResolvedAdapter:
    """Resolved adapter with loaded module metadata.

    Attributes:
        entry: The original registry entry
        callable: The loaded callable
        module_name: Name of the module containing the callable
        qualname: Fully qualified name of the callable
    """

    entry: CommandAdapterEntry
    callable: Callable[..., Any]
    module_name: str
    qualname: str


class CommandAdapterRegistry:
    """Registry for lazy loading of command job handlers.

    Maps command job types to import paths, resolving the actual callable
    only when resolve() is called. This avoids eager imports of command
    business logic during startup.
    """

    def __init__(self) -> None:
        self._entries: dict[CommandType, CommandAdapterEntry] = {}
        self._resolved: dict[CommandType, ResolvedAdapter] = {}

    def register(self, entry: CommandAdapterEntry) -> None:
        """Register an adapter entry.

        Args:
            entry: The adapter entry to register

        Raises:
            CommandAdapterError: If job_type is already registered
        """
        if entry.job_type in self._entries:
            raise CommandAdapterError(
                f"Job type {entry.job_type} is already registered"
            )
        self._entries[entry.job_type] = entry

    def resolve(self, job_type: CommandType) -> ResolvedAdapter:
        """Resolve an adapter for a job type.

        Imports the module and retrieves the callable on first call,
        then caches the result.

        Args:
            job_type: The job type to resolve

        Returns:
            ResolvedAdapter with the loaded callable

        Raises:
            CommandAdapterError: If job_type is not registered or
                import/attribute lookup fails
        """
        # Return cached result if available
        if job_type in self._resolved:
            return self._resolved[job_type]

        # Get the entry
        entry = self._entries.get(job_type)
        if entry is None:
            raise CommandAdapterError(f"No adapter registered for {job_type}")

        # Import the module and get the callable
        try:
            import importlib

            module = importlib.import_module(entry.import_path)
            callable_obj = getattr(module, entry.callable_name)
        except ImportError as e:
            raise CommandAdapterError(
                f"Failed to import module {entry.import_path} for {job_type}: {e}"
            ) from e
        except AttributeError as e:
            raise CommandAdapterError(
                f"Callable {entry.callable_name} not found in {entry.import_path} "
                f"for {job_type}: {e}"
            ) from e

        # Build resolved adapter
        resolved = ResolvedAdapter(
            entry=entry,
            callable=callable_obj,
            module_name=module.__name__,
            qualname=f"{entry.import_path}.{entry.callable_name}",
        )

        # Cache and return
        self._resolved[job_type] = resolved
        return resolved

    def is_registered(self, job_type: CommandType) -> bool:
        """Check if a job type is registered.

        Args:
            job_type: The job type to check

        Returns:
            True if registered, False otherwise
        """
        return job_type in self._entries

    def list_registered(self) -> list[CommandType]:
        """List all registered job types.

        Returns:
            List of registered job types
        """
        return list(self._entries.keys())


def build_default_registry() -> CommandAdapterRegistry:
    """Build and return a registry with all canonical vibe3 commands.

    This function registers entries for all built-in command types but
    does NOT resolve them (no imports of command modules occur).

    Returns:
        Populated CommandAdapterRegistry
    """
    registry = CommandAdapterRegistry()

    # Register all canonical commands
    registry.register(
        CommandAdapterEntry(
            job_type=CommandType.MANAGER,
            import_path="vibe3.roles.manager",
            callable_name="MANAGER_SYNC_SPEC",
            description="Manager role for issue state transitions",
        )
    )

    registry.register(
        CommandAdapterEntry(
            job_type=CommandType.PLAN,
            import_path="vibe3.roles.plan",
            callable_name="PLAN_SYNC_SPEC",
            description="Planner role for creating implementation plans",
        )
    )

    registry.register(
        CommandAdapterEntry(
            job_type=CommandType.RUN,
            import_path="vibe3.roles.run_request",
            callable_name="RUN_SYNC_SPEC",
            description="Executor role for running implementation",
        )
    )

    registry.register(
        CommandAdapterEntry(
            job_type=CommandType.REVIEW,
            import_path="vibe3.roles.review",
            callable_name="REVIEW_SYNC_SPEC",
            description="Reviewer role for code review",
        )
    )

    registry.register(
        CommandAdapterEntry(
            job_type=CommandType.GOVERNANCE_SCAN,
            import_path="vibe3.roles.governance",
            callable_name="GOVERNANCE_ROLE",
            description="Governance role for system-wide operations",
        )
    )

    registry.register(
        CommandAdapterEntry(
            job_type=CommandType.SUPERVISOR_APPLY,
            import_path="vibe3.roles.supervisor",
            callable_name="SUPERVISOR_CLI_SYNC_SPEC",
            description="Supervisor role for orchestration",
        )
    )

    # Verify all CommandType values are registered
    registered = set(registry.list_registered())
    missing = set(CommandType) - registered
    if missing:
        raise CommandAdapterError(f"Incomplete registry: {missing} not registered")

    return registry
