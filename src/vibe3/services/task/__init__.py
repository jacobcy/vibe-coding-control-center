"""Task domain services subpackage."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.shared.binding_guard import (
        MissingTaskIssueError,
        build_bind_task_hint,
        ensure_task_issue_bound,
        has_task_issue,
    )
    from vibe3.services.task.classifier import TaskStatusBucket, classify_task_status
    from vibe3.services.task.resume import (
        TaskResumeCandidates,
        TaskResumeOperations,
        TaskResumeUsecase,
    )
    from vibe3.services.task.service import TaskService
    from vibe3.services.task.show import (
        TaskCommentSummary,
        TaskPRSummary,
        TaskRefSummary,
        TaskShowResult,
        TaskShowService,
    )
    from vibe3.services.task.status import (
        TaskStatusData,
        classify_task_issues_for_rendering,
        fetch_task_status_data,
    )

__all__ = [
    # Classes - service
    "TaskService",
    # Classes - binding guard
    "MissingTaskIssueError",
    # Classes - show
    "TaskShowService",
    "TaskShowResult",
    "TaskRefSummary",
    "TaskCommentSummary",
    "TaskPRSummary",
    # Classes - status
    "TaskStatusData",
    # Classes - resume
    "TaskResumeUsecase",
    "TaskResumeCandidates",
    "TaskResumeOperations",
    # Classes - classifier
    "TaskStatusBucket",
    # Functions - binding guard
    "ensure_task_issue_bound",
    "has_task_issue",
    "build_bind_task_hint",
    # Functions - status
    "fetch_task_status_data",
    "classify_task_issues_for_rendering",
    # Functions - classifier
    "classify_task_status",
]

_SYMBOL_MODULES = {
    # Classes - service
    "TaskService": "vibe3.services.task.service",
    # Classes - binding guard (re-export from shared)
    "MissingTaskIssueError": "vibe3.services.shared.binding_guard",
    # Classes - show
    "TaskShowService": "vibe3.services.task.show",
    "TaskShowResult": "vibe3.services.task.show",
    "TaskRefSummary": "vibe3.services.task.show",
    "TaskCommentSummary": "vibe3.services.task.show",
    "TaskPRSummary": "vibe3.services.task.show",
    # Classes - status
    "TaskStatusData": "vibe3.services.task.status",
    # Classes - resume
    "TaskResumeUsecase": "vibe3.services.task.resume",
    "TaskResumeCandidates": "vibe3.services.task.resume",
    "TaskResumeOperations": "vibe3.services.task.resume",
    # Classes - classifier
    "TaskStatusBucket": "vibe3.services.task.classifier",
    # Functions - binding guard (re-export from shared)
    "ensure_task_issue_bound": "vibe3.services.shared.binding_guard",
    "has_task_issue": "vibe3.services.shared.binding_guard",
    "build_bind_task_hint": "vibe3.services.shared.binding_guard",
    # Functions - status
    "fetch_task_status_data": "vibe3.services.task.status",
    "classify_task_issues_for_rendering": "vibe3.services.task.status",
    # Functions - classifier
    "classify_task_status": "vibe3.services.task.classifier",
}


def __getattr__(name: str) -> Any:
    """Lazy import for Task services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.task import TaskService, TaskResumeUsecase

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
