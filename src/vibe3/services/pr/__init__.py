"""PR domain services subpackage.

Public API Contract:
- PRService, PRCreateUsecase, PrReadyUsecase: Core PR services
- VerdictService, PRLocCommentService, PRReviewBriefingService: PR utilities
- Resolution functions: resolve_command_branch, resolve_branch_from_pr
- Verdict functions: passes_review, blocks_merge, requires_audit_ref

All exports are part of the public API.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.pr.base_resolution import BaseResolutionUsecase
    from vibe3.services.pr.create import PRCreateResult, PRCreateUsecase
    from vibe3.services.pr.loc_comment import PRLocCommentService
    from vibe3.services.pr.ready import PrReadyAbortedError, PrReadyUsecase
    from vibe3.services.pr.resolver import (
        resolve_branch_from_pr,
        resolve_command_branch,
    )
    from vibe3.services.pr.review import PRReviewBriefingService
    from vibe3.services.pr.service import PRService
    from vibe3.services.pr.utils import (
        build_pr_body,
        check_upstream_conflicts,
        get_metadata_from_flow,
    )
    from vibe3.services.pr.verdict_policy import (
        blocks_merge,
        passes_review,
        requires_audit_ref,
    )
    from vibe3.services.pr.verdict_service import VerdictService

__all__ = [
    # Classes
    "BaseResolutionUsecase",
    "PRCreateResult",
    "PRCreateUsecase",
    "PRLocCommentService",
    "PRReviewBriefingService",
    "PRService",
    "PrReadyAbortedError",
    "PrReadyUsecase",
    "VerdictService",
    # Functions
    "blocks_merge",
    "build_pr_body",
    "check_upstream_conflicts",
    "get_metadata_from_flow",
    "passes_review",
    "requires_audit_ref",
    "resolve_branch_from_pr",
    "resolve_command_branch",
]

_SYMBOL_MODULES = {
    # Classes
    "BaseResolutionUsecase": "vibe3.services.pr.base_resolution",
    "PRCreateResult": "vibe3.services.pr.create",
    "PRCreateUsecase": "vibe3.services.pr.create",
    "PRLocCommentService": "vibe3.services.pr.loc_comment",
    "PRReviewBriefingService": "vibe3.services.pr.review",
    "PRService": "vibe3.services.pr.service",
    "PrReadyAbortedError": "vibe3.services.pr.ready",
    "PrReadyUsecase": "vibe3.services.pr.ready",
    "VerdictService": "vibe3.services.pr.verdict_service",
    # Functions
    "blocks_merge": "vibe3.services.pr.verdict_policy",
    "build_pr_body": "vibe3.services.pr.utils",
    "check_upstream_conflicts": "vibe3.services.pr.utils",
    "get_metadata_from_flow": "vibe3.services.pr.utils",
    "passes_review": "vibe3.services.pr.verdict_policy",
    "requires_audit_ref": "vibe3.services.pr.verdict_policy",
    "resolve_branch_from_pr": "vibe3.services.pr.resolver",
    "resolve_command_branch": "vibe3.services.pr.resolver",
}


def __getattr__(name: str) -> Any:
    """Lazy import for PR services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.pr import PRService, PRCreateUsecase

    While avoiding circular imports at module load time.
    """
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
