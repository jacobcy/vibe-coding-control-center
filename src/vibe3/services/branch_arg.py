"""Backward compatibility — migrated to services.shared.branches."""

# Re-export imports for test patch compatibility
from vibe3.config.convention_resolver import (  # noqa: F401
    ConventionResolver,
    get_convention,
)
from vibe3.services.flow_service import FlowService  # noqa: F401
from vibe3.services.shared.branches import (  # noqa: F401
    resolve_branch_and_issue,
    resolve_branch_arg,
)
