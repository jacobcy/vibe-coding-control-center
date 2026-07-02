"""Supervisor apply domain events.

This module re-exports SupervisorIssueIdentified (defined in vibe3.models)
so the roles layer can import it without a direct models dependency.

The actual supervisor apply execution chain uses CLI self-invocation
(via supervisor_scan handler) and CodeagentExecutionService, not the
event-driven apply lifecycle that was originally spec'd.
"""

# Re-exported from models to allow roles layer to import without domain dependency
from vibe3.models import SupervisorIssueIdentified

__all__ = [
    "SupervisorIssueIdentified",
]
