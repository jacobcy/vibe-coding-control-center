"""Issue domain services subpackage."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.issue.body import (
        merge_projection,
        parse_projection,
        render_projection,
    )
    from vibe3.services.issue.branch_resolver import (
        iter_issue_branch_candidates,
        resolve_issue_branch_input,
    )
    from vibe3.services.issue.collection import IssueCollectionService
    from vibe3.services.issue.context import load_issue_info
    from vibe3.services.issue.dispatch_policy import (
        DispatchExclusion,
        IssueDispatchPolicy,
    )
    from vibe3.services.issue.failure import (
        block_executor_noop_issue,
        block_issue,
        block_manager_noop_issue,
        block_planner_noop_issue,
        block_reviewer_noop_issue,
        fail_executor_issue,
        fail_issue,
        fail_manager_issue,
        fail_planner_issue,
        fail_reviewer_issue,
        mark_issue,
    )
    from vibe3.services.issue.flow import IssueFlowService
    from vibe3.services.issue.title_cache import IssueTitleCacheService

__all__ = [
    # Classes
    "DispatchExclusion",
    "IssueCollectionService",
    "IssueDispatchPolicy",
    "IssueFlowService",
    "IssueTitleCacheService",
    # Functions - body
    "merge_projection",
    "parse_projection",
    "render_projection",
    # Functions - branch_resolver
    "iter_issue_branch_candidates",
    "resolve_issue_branch_input",
    # Functions - context
    "load_issue_info",
    # Functions - failure
    "block_executor_noop_issue",
    "block_issue",
    "block_manager_noop_issue",
    "block_planner_noop_issue",
    "block_reviewer_noop_issue",
    "fail_executor_issue",
    "fail_issue",
    "fail_manager_issue",
    "fail_planner_issue",
    "fail_reviewer_issue",
    "mark_issue",
]

_SYMBOL_MODULES = {
    # Classes
    "DispatchExclusion": "vibe3.services.issue.dispatch_policy",
    "IssueCollectionService": "vibe3.services.issue.collection",
    "IssueDispatchPolicy": "vibe3.services.issue.dispatch_policy",
    "IssueFlowService": "vibe3.services.issue.flow",
    "IssueTitleCacheService": "vibe3.services.issue.title_cache",
    # Functions - body
    "merge_projection": "vibe3.services.issue.body",
    "parse_projection": "vibe3.services.issue.body",
    "render_projection": "vibe3.services.issue.body",
    # Functions - branch_resolver
    "iter_issue_branch_candidates": "vibe3.services.issue.branch_resolver",
    "resolve_issue_branch_input": "vibe3.services.issue.branch_resolver",
    # Functions - context
    "load_issue_info": "vibe3.services.issue.context",
    # Functions - failure
    "block_executor_noop_issue": "vibe3.services.issue.failure",
    "block_issue": "vibe3.services.issue.failure",
    "block_manager_noop_issue": "vibe3.services.issue.failure",
    "block_planner_noop_issue": "vibe3.services.issue.failure",
    "block_reviewer_noop_issue": "vibe3.services.issue.failure",
    "fail_executor_issue": "vibe3.services.issue.failure",
    "fail_issue": "vibe3.services.issue.failure",
    "fail_manager_issue": "vibe3.services.issue.failure",
    "fail_planner_issue": "vibe3.services.issue.failure",
    "fail_reviewer_issue": "vibe3.services.issue.failure",
    "mark_issue": "vibe3.services.issue.failure",
}


def __getattr__(name: str) -> Any:
    """Lazy import for Issue services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.issue import IssueFlowService, IssueCollectionService

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
