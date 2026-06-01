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

# Eager imports - definitions 不导入其他角色模块，不会产生循环
from vibe3.roles.definitions import (
    IssueRoleSyncSpec,
    RoleDefinition,
    TriggerableRoleDefinition,
    TriggerName,
)

if TYPE_CHECKING:
    # For type checkers, import all symbols
    from vibe3.roles.governance import (
        GOVERNANCE_ROLE,
        GOVERNANCE_TASK_PROMPT,
        build_governance_execution_name,
        build_governance_recipe,
        build_governance_request,
        build_governance_snapshot_context,
        load_governance_material_catalog,
        render_governance_prompt,
        resolve_governance_options,
    )
    from vibe3.roles.governance_factory import build_default_governance_fns
    from vibe3.roles.governance_utils import (
        find_material_in_catalog,
        normalize_material_name,
    )
    from vibe3.roles.manager import (
        HANDOFF_MANAGER_ROLE,
        MANAGER_BRANCH_RESOLVER,
        MANAGER_ROLE,
        MANAGER_SYNC_SPEC,
        build_manager_request,
        build_manager_sync_request,
        resolve_manager_options,
    )
    from vibe3.roles.plan import (
        PLAN_BRANCH_RESOLVER,
        PLAN_SYNC_SPEC,
        PLANNER_ROLE,
        build_plan_prompt,
        build_plan_request,
        build_plan_sync_request,
        execute_spec_plan_async,
        execute_spec_plan_sync,
        resolve_plan_options,
        resolve_spec_plan_input,
    )
    from vibe3.roles.registry import (
        LABEL_DISPATCH_ROLES,
        build_label_dispatch_event,
    )
    from vibe3.roles.review import (
        REVIEW_BRANCH_RESOLVER,
        REVIEW_SYNC_SPEC,
        REVIEWER_ROLE,
        build_base_review_request,
        build_issue_review_request,
        build_manual_review_request_payload,
        build_review_request,
        build_review_sync_request,
        execute_manual_review_async,
        execute_manual_review_sync,
        resolve_review_options,
        validate_review_prerequisites,
    )
    from vibe3.roles.run import (
        EXECUTOR_PUBLISH_ROLE,
        EXECUTOR_ROLE,
        RUN_BRANCH_RESOLVER,
        RUN_SYNC_SPEC,
        build_run_request,
        build_run_sync_request,
        dispatch_run_command_async,
        ensure_plan_file_exists,
        execute_manual_run,
        publish_run_command_failure,
        publish_run_command_success,
        resolve_run_mode,
        resolve_run_options,
        resolve_skill_path,
        validate_run_prerequisites,
    )
    from vibe3.roles.supervisor import (
        SUPERVISOR_APPLY_ROLE,
        SUPERVISOR_CLI_SYNC_SPEC,
        SUPERVISOR_IDENTIFY_ROLE,
        build_supervisor_apply_request,
        build_supervisor_cli_request,
        build_supervisor_cli_sync_request,
        build_supervisor_handoff_payload,
        build_supervisor_task_string,
        get_supervisor_prompt_path,
        iter_supervisor_identified_events,
    )

# Lazy import mapping: symbol_name -> module_path
# Symbol name is the same in both this module and the source module
_LAZY_IMPORTS: dict[str, str] = {
    # registry (imports from manager, so must be lazy)
    "LABEL_DISPATCH_ROLES": "vibe3.roles.registry",
    "build_label_dispatch_event": "vibe3.roles.registry",
    # manager
    "HANDOFF_MANAGER_ROLE": "vibe3.roles.manager",
    "MANAGER_BRANCH_RESOLVER": "vibe3.roles.manager",
    "MANAGER_ROLE": "vibe3.roles.manager",
    "MANAGER_SYNC_SPEC": "vibe3.roles.manager",
    "build_manager_request": "vibe3.roles.manager",
    "build_manager_sync_request": "vibe3.roles.manager",
    "resolve_manager_options": "vibe3.roles.manager",
    # planner
    "PLAN_BRANCH_RESOLVER": "vibe3.roles.plan",
    "PLAN_SYNC_SPEC": "vibe3.roles.plan",
    "PLANNER_ROLE": "vibe3.roles.plan",
    "build_plan_prompt": "vibe3.roles.plan",
    "build_plan_request": "vibe3.roles.plan",
    "build_plan_sync_request": "vibe3.roles.plan",
    "execute_spec_plan_async": "vibe3.roles.plan",
    "execute_spec_plan_sync": "vibe3.roles.plan",
    "resolve_plan_options": "vibe3.roles.plan",
    "resolve_spec_plan_input": "vibe3.roles.plan",
    # executor
    "EXECUTOR_PUBLISH_ROLE": "vibe3.roles.run",
    "EXECUTOR_ROLE": "vibe3.roles.run",
    "RUN_BRANCH_RESOLVER": "vibe3.roles.run",
    "RUN_SYNC_SPEC": "vibe3.roles.run",
    "build_run_request": "vibe3.roles.run",
    "build_run_sync_request": "vibe3.roles.run",
    "dispatch_run_command_async": "vibe3.roles.run",
    "ensure_plan_file_exists": "vibe3.roles.run",
    "execute_manual_run": "vibe3.roles.run",
    "publish_run_command_failure": "vibe3.roles.run",
    "publish_run_command_success": "vibe3.roles.run",
    "resolve_run_mode": "vibe3.roles.run",
    "resolve_run_options": "vibe3.roles.run",
    "resolve_skill_path": "vibe3.roles.run",
    "validate_run_prerequisites": "vibe3.roles.run",
    # reviewer
    "REVIEW_BRANCH_RESOLVER": "vibe3.roles.review",
    "REVIEW_SYNC_SPEC": "vibe3.roles.review",
    "REVIEWER_ROLE": "vibe3.roles.review",
    "build_base_review_request": "vibe3.roles.review",
    "build_issue_review_request": "vibe3.roles.review",
    "build_manual_review_request_payload": "vibe3.roles.review",
    "build_review_request": "vibe3.roles.review",
    "build_review_sync_request": "vibe3.roles.review",
    "execute_manual_review_async": "vibe3.roles.review",
    "execute_manual_review_sync": "vibe3.roles.review",
    "resolve_review_options": "vibe3.roles.review",
    "validate_review_prerequisites": "vibe3.roles.review",
    # supervisor
    "SUPERVISOR_APPLY_ROLE": "vibe3.roles.supervisor",
    "SUPERVISOR_CLI_SYNC_SPEC": "vibe3.roles.supervisor",
    "SUPERVISOR_IDENTIFY_ROLE": "vibe3.roles.supervisor",
    "build_supervisor_apply_request": "vibe3.roles.supervisor",
    "build_supervisor_cli_request": "vibe3.roles.supervisor",
    "build_supervisor_cli_sync_request": "vibe3.roles.supervisor",
    "build_supervisor_handoff_payload": "vibe3.roles.supervisor",
    "build_supervisor_task_string": "vibe3.roles.supervisor",
    "get_supervisor_prompt_path": "vibe3.roles.supervisor",
    "iter_supervisor_identified_events": "vibe3.roles.supervisor",
    # governance
    "GOVERNANCE_ROLE": "vibe3.roles.governance",
    "GOVERNANCE_TASK_PROMPT": "vibe3.roles.governance",
    "build_governance_execution_name": "vibe3.roles.governance",
    "build_governance_recipe": "vibe3.roles.governance",
    "build_governance_request": "vibe3.roles.governance",
    "build_governance_snapshot_context": "vibe3.roles.governance",
    "load_governance_material_catalog": "vibe3.roles.governance",
    "render_governance_prompt": "vibe3.roles.governance",
    "resolve_governance_options": "vibe3.roles.governance",
    # governance factory & utils
    "build_default_governance_fns": "vibe3.roles.governance_factory",
    "find_material_in_catalog": "vibe3.roles.governance_utils",
    "normalize_material_name": "vibe3.roles.governance_utils",
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
    # definitions (eager)
    "IssueRoleSyncSpec",
    "RoleDefinition",
    "TriggerName",
    "TriggerableRoleDefinition",
    # registry (lazy)
    "LABEL_DISPATCH_ROLES",
    "build_label_dispatch_event",
    # manager (lazy)
    "HANDOFF_MANAGER_ROLE",
    "MANAGER_BRANCH_RESOLVER",
    "MANAGER_SYNC_SPEC",
    "MANAGER_ROLE",
    "build_manager_request",
    "build_manager_sync_request",
    "resolve_manager_options",
    # planner (lazy)
    "PLAN_BRANCH_RESOLVER",
    "PLAN_SYNC_SPEC",
    "PLANNER_ROLE",
    "build_plan_prompt",
    "build_plan_request",
    "build_plan_sync_request",
    "resolve_plan_options",
    "resolve_spec_plan_input",
    "execute_spec_plan_async",
    "execute_spec_plan_sync",
    # executor (lazy)
    "EXECUTOR_PUBLISH_ROLE",
    "EXECUTOR_ROLE",
    "RUN_BRANCH_RESOLVER",
    "RUN_SYNC_SPEC",
    "build_run_request",
    "build_run_sync_request",
    "dispatch_run_command_async",
    "ensure_plan_file_exists",
    "execute_manual_run",
    "publish_run_command_failure",
    "publish_run_command_success",
    "resolve_run_mode",
    "resolve_run_options",
    "resolve_skill_path",
    "validate_run_prerequisites",
    # reviewer (lazy)
    "REVIEW_BRANCH_RESOLVER",
    "REVIEW_SYNC_SPEC",
    "REVIEWER_ROLE",
    "build_base_review_request",
    "build_issue_review_request",
    "build_manual_review_request_payload",
    "build_review_request",
    "build_review_sync_request",
    "execute_manual_review_async",
    "execute_manual_review_sync",
    "resolve_review_options",
    "validate_review_prerequisites",
    # supervisor (lazy)
    "SUPERVISOR_APPLY_ROLE",
    "SUPERVISOR_CLI_SYNC_SPEC",
    "SUPERVISOR_IDENTIFY_ROLE",
    "build_supervisor_apply_request",
    "build_supervisor_cli_request",
    "build_supervisor_cli_sync_request",
    "build_supervisor_handoff_payload",
    "build_supervisor_task_string",
    "get_supervisor_prompt_path",
    "iter_supervisor_identified_events",
    # governance (lazy)
    "GOVERNANCE_ROLE",
    "GOVERNANCE_TASK_PROMPT",
    "build_governance_execution_name",
    "build_governance_recipe",
    "build_governance_request",
    "build_governance_snapshot_context",
    "load_governance_material_catalog",
    "render_governance_prompt",
    "resolve_governance_options",
    # governance factory & utils (lazy)
    "build_default_governance_fns",
    "find_material_in_catalog",
    "normalize_material_name",
]

# Consistency check: ensure __all__ matches eager + lazy symbols
# This catches drift when adding/renaming symbols during development
_eager_exports = {
    "IssueRoleSyncSpec",
    "RoleDefinition",
    "TriggerName",
    "TriggerableRoleDefinition",
}
_lazy_exports = set(_LAZY_IMPORTS.keys())
assert set(__all__) == _eager_exports | _lazy_exports, (
    f"Export list mismatch: __all__ ({len(__all__)} symbols) != "
    f"eager ({len(_eager_exports)}) + lazy ({len(_lazy_exports)})"
)
