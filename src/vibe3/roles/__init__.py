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
    from vibe3.roles.manager import build_manager_request
    from vibe3.roles.plan import build_plan_request
    from vibe3.roles.registry import (
        LABEL_DISPATCH_ROLES,
        build_label_dispatch_event,
    )
    from vibe3.roles.review import build_review_request
    from vibe3.roles.run import (
        build_run_request,
        resolve_skill_path,
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
    "build_manager_request": "vibe3.roles.manager",
    # planner
    "build_plan_request": "vibe3.roles.plan",
    # executor
    "build_run_request": "vibe3.roles.run",
    "resolve_skill_path": "vibe3.roles.run",
    # reviewer
    "build_review_request": "vibe3.roles.review",
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
    "build_manager_request",
    # planner
    "build_plan_request",
    # executor
    "build_run_request",
    "resolve_skill_path",
    # reviewer
    "build_review_request",
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
]

# Consistency check: ensure __all__ matches lazy symbols
# This catches drift when adding/renaming symbols during development
_lazy_exports = set(_LAZY_IMPORTS.keys())
assert set(__all__) == _lazy_exports, (
    f"Export list mismatch: __all__ ({len(__all__)} symbols) != "
    f"lazy ({len(_lazy_exports)})"
)
