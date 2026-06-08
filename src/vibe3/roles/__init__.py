"""Role package — 统一公共接口导出。

所有角色定义、注册表、请求构建函数均可从此模块直接导入，
无需访问子模块（如 ``vibe3.roles.manager``）。

.. note::

    使用延迟导入避免循环依赖。`definitions` 立即可用；
    其他角色模块和注册表的符号在首次访问时才导入。
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # For type checkers, import all symbols that are externally used
    from vibe3.roles.definitions import TriggerableRoleDefinition
    from vibe3.roles.governance import (
        build_governance_execution_name,
        load_governance_material_catalog,
    )
    from vibe3.roles.governance_factory import build_default_governance_fns
    from vibe3.roles.governance_utils import find_material_in_catalog
    from vibe3.roles.manager import (
        MANAGER_SYNC_SPEC,
        build_manager_request,
        resolve_manager_token,
    )
    from vibe3.roles.plan import (
        build_plan_request,
        execute_spec_plan_async,
        execute_spec_plan_sync,
        resolve_spec_plan_input,
    )
    from vibe3.roles.registry import (
        LABEL_DISPATCH_ROLES,
        build_label_dispatch_event,
    )
    from vibe3.roles.review import (
        REVIEW_SYNC_SPEC,
        build_base_review_request,
        build_review_request,
        execute_manual_review_async,
        execute_manual_review_sync,
        validate_review_prerequisites,
    )
    from vibe3.roles.run import (
        build_run_request,
        ensure_plan_file_exists,
        execute_manual_run,
        resolve_run_mode,
        resolve_skill_path,
        validate_run_prerequisites,
    )
    from vibe3.roles.scan_service import (
        dispatch_governance_execution,
        dispatch_supervisor_execution,
        fetch_supervisor_candidates,
        get_available_governance_materials,
        governance_material_exists,
        list_governance_materials,
    )
    from vibe3.roles.supervisor import (
        SUPERVISOR_APPLY_ROLE,
        SUPERVISOR_CLI_SYNC_SPEC,
        iter_supervisor_identified_events,
    )

# Lazy import mapping: symbol_name -> module_path
# Symbol name is the same in both this module and the source module
_LAZY_IMPORTS: dict[str, str] = {
    # definitions
    "TriggerableRoleDefinition": "vibe3.roles.definitions",
    # registry
    "LABEL_DISPATCH_ROLES": "vibe3.roles.registry",
    "build_label_dispatch_event": "vibe3.roles.registry",
    # manager
    "MANAGER_SYNC_SPEC": "vibe3.roles.manager",
    "build_manager_request": "vibe3.roles.manager",
    "resolve_manager_token": "vibe3.roles.manager",
    # planner
    "build_plan_request": "vibe3.roles.plan",
    "execute_spec_plan_async": "vibe3.roles.plan",
    "execute_spec_plan_sync": "vibe3.roles.plan",
    "resolve_spec_plan_input": "vibe3.roles.plan",
    # executor
    "build_run_request": "vibe3.roles.run",
    "ensure_plan_file_exists": "vibe3.roles.run",
    "execute_manual_run": "vibe3.roles.run",
    "resolve_run_mode": "vibe3.roles.run",
    "resolve_skill_path": "vibe3.roles.run",
    "validate_run_prerequisites": "vibe3.roles.run",
    # reviewer
    "REVIEW_SYNC_SPEC": "vibe3.roles.review",
    "build_base_review_request": "vibe3.roles.review",
    "build_review_request": "vibe3.roles.review",
    "execute_manual_review_async": "vibe3.roles.review",
    "execute_manual_review_sync": "vibe3.roles.review",
    "validate_review_prerequisites": "vibe3.roles.review",
    # supervisor
    "SUPERVISOR_APPLY_ROLE": "vibe3.roles.supervisor",
    "SUPERVISOR_CLI_SYNC_SPEC": "vibe3.roles.supervisor",
    "iter_supervisor_identified_events": "vibe3.roles.supervisor",
    # governance
    "build_governance_execution_name": "vibe3.roles.governance",
    "load_governance_material_catalog": "vibe3.roles.governance",
    # governance factory & utils
    "build_default_governance_fns": "vibe3.roles.governance_factory",
    "find_material_in_catalog": "vibe3.roles.governance_utils",
    # scan_service
    "dispatch_governance_execution": "vibe3.roles.scan_service",
    "dispatch_supervisor_execution": "vibe3.roles.scan_service",
    "fetch_supervisor_candidates": "vibe3.roles.scan_service",
    "get_available_governance_materials": "vibe3.roles.scan_service",
    "governance_material_exists": "vibe3.roles.scan_service",
    "list_governance_materials": "vibe3.roles.scan_service",
}


def __getattr__(name: str) -> object:
    """Lazy import for role symbols to avoid circular imports."""
    if name in _LAZY_IMPORTS:
        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        # Cache in module globals for subsequent access
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # definitions
    "TriggerableRoleDefinition",
    # registry
    "LABEL_DISPATCH_ROLES",
    "build_label_dispatch_event",
    # manager
    "MANAGER_SYNC_SPEC",
    "build_manager_request",
    "resolve_manager_token",
    # planner
    "build_plan_request",
    "execute_spec_plan_async",
    "execute_spec_plan_sync",
    "resolve_spec_plan_input",
    # executor
    "build_run_request",
    "ensure_plan_file_exists",
    "execute_manual_run",
    "resolve_run_mode",
    "resolve_skill_path",
    "validate_run_prerequisites",
    # reviewer
    "REVIEW_SYNC_SPEC",
    "build_base_review_request",
    "build_review_request",
    "execute_manual_review_async",
    "execute_manual_review_sync",
    "validate_review_prerequisites",
    # supervisor
    "SUPERVISOR_APPLY_ROLE",
    "SUPERVISOR_CLI_SYNC_SPEC",
    "iter_supervisor_identified_events",
    # governance
    "build_governance_execution_name",
    "load_governance_material_catalog",
    # governance factory & utils
    "build_default_governance_fns",
    "find_material_in_catalog",
    # scan_service
    "dispatch_governance_execution",
    "dispatch_supervisor_execution",
    "fetch_supervisor_candidates",
    "get_available_governance_materials",
    "governance_material_exists",
    "list_governance_materials",
]

# Consistency check: ensure __all__ matches lazy symbols
# This catches drift when adding/renaming symbols during development
_lazy_exports = set(_LAZY_IMPORTS.keys())
assert set(__all__) == _lazy_exports, (
    f"Export list mismatch: __all__ ({len(__all__)} symbols) != "
    f"lazy ({len(_lazy_exports)})"
)
