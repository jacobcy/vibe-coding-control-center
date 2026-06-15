"""UI layer — console output primitives and Rich rendering components."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.ui.console_impl import console
    from vibe3.ui.flow_ui import (
        render_error,
        render_flow_created,
        render_flow_status,
        render_flows_status_dashboard,
    )
    from vibe3.ui.flow_ui_primitives import (
        display_actor,
        kv,
        resolve_ref_path,
        status_text,
    )
    from vibe3.ui.flow_ui_timeline import (
        filter_passive_if_active_exists,
        render_flow_timeline,
    )
    from vibe3.ui.handoff_ui import render_handoff_detail
    from vibe3.ui.pr_ui import (
        render_local_review_summary,
        render_pr_confirmed,
        render_pr_created,
        render_pr_details,
        render_pr_ready,
    )
    from vibe3.ui.scan_display import (
        display_codeagent_result,
        display_execution_result,
        display_governance_dry_run,
        display_material_list,
        display_supervisor_dry_run,
    )
    from vibe3.ui.task_ui import (
        build_task_show_payload,
        render_task_comments,
        render_task_show,
    )

# Lazy import mapping
_SYMBOL_MODULES = {
    "console": "vibe3.ui.console_impl",
    "render_flow_status": "vibe3.ui.flow_ui",
    "render_flow_created": "vibe3.ui.flow_ui",
    "render_flows_status_dashboard": "vibe3.ui.flow_ui",
    "render_error": "vibe3.ui.flow_ui",
    "status_text": "vibe3.ui.flow_ui_primitives",
    "kv": "vibe3.ui.flow_ui_primitives",
    "display_actor": "vibe3.ui.flow_ui_primitives",
    "resolve_ref_path": "vibe3.ui.flow_ui_primitives",
    "render_flow_timeline": "vibe3.ui.flow_ui_timeline",
    "filter_passive_if_active_exists": "vibe3.ui.flow_ui_timeline",
    "render_handoff_detail": "vibe3.ui.handoff_ui",
    "render_pr_created": "vibe3.ui.pr_ui",
    "render_pr_confirmed": "vibe3.ui.pr_ui",
    "render_pr_ready": "vibe3.ui.pr_ui",
    "render_local_review_summary": "vibe3.ui.pr_ui",
    "render_pr_details": "vibe3.ui.pr_ui",
    "display_execution_result": "vibe3.ui.scan_display",
    "display_codeagent_result": "vibe3.ui.scan_display",
    "display_supervisor_dry_run": "vibe3.ui.scan_display",
    "display_material_list": "vibe3.ui.scan_display",
    "display_governance_dry_run": "vibe3.ui.scan_display",
    "build_task_show_payload": "vibe3.ui.task_ui",
    "render_task_show": "vibe3.ui.task_ui",
    "render_task_comments": "vibe3.ui.task_ui",
}


def __getattr__(name: str) -> object:
    """Lazy import for ui symbols to avoid circular dependencies."""
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Console
    "console",
    # Flow UI
    "render_flow_status",
    "render_flow_created",
    "render_flows_status_dashboard",
    "render_error",
    # Flow UI primitives
    "status_text",
    "kv",
    "display_actor",
    "resolve_ref_path",
    # Flow UI timeline
    "render_flow_timeline",
    "filter_passive_if_active_exists",
    # Handoff UI
    "render_handoff_detail",
    # PR UI
    "render_pr_created",
    "render_pr_confirmed",
    "render_pr_ready",
    "render_local_review_summary",
    "render_pr_details",
    # Scan display
    "display_execution_result",
    "display_codeagent_result",
    "display_supervisor_dry_run",
    "display_material_list",
    "display_governance_dry_run",
    # Task UI
    "build_task_show_payload",
    "render_task_show",
    "render_task_comments",
]
