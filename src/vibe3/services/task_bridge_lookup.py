"""Task bridge lookup operations - 远端 task 读取操作。"""

from typing import Any

from loguru import logger

from vibe3.models.project_item import ProjectItemError
from vibe3.models.task_bridge import FieldSource, HydratedTaskView, HydrateError


def hydrate_task(
    self: Any,
    branch: str,
) -> HydratedTaskView | HydrateError:
    """从远端 GitHub Project 读取 task 真值，合并为 HydratedTaskView（只读）。"""
    # Auto-ensure flow for branch
    from vibe3.models.flow import MainBranchProtectedError
    from vibe3.services.flow_service import FlowService

    try:
        FlowService().ensure_flow_for_branch(branch)
    except MainBranchProtectedError as e:
        return HydrateError(
            type="main_branch_protected",
            message=str(e),
        )

    flow_data = self.store.get_flow_state(branch)
    if not flow_data:
        # Should not happen after ensure_flow_for_branch, handle defensively
        return HydrateError(
            type="no_remote_identity",
            message=f"Branch '{branch}' flow creation failed unexpectedly",
        )

    project_item_id = flow_data.get("project_item_id")
    if not project_item_id:
        return HydrateError(
            type="no_remote_identity",
            message=(
                f"Branch '{branch}' 未绑定 GitHub Project item，"
                "请先运行 vibe task bridge link-project <id>"
            ),
        )

    local_node_id = flow_data.get("project_node_id")
    view = HydratedTaskView(branch=branch)
    view.project_item_id = FieldSource(value=project_item_id, source="local")
    if flow_data.get("task_issue_number"):
        view.task_issue_number = FieldSource(
            value=flow_data["task_issue_number"], source="local"
        )
    if flow_data.get("spec_ref"):
        view.spec_ref = FieldSource(value=flow_data["spec_ref"], source="local")
    if flow_data.get("next_step"):
        view.next_step = FieldSource(value=flow_data["next_step"], source="local")
    if flow_data.get("blocked_by"):
        view.blocked_by = FieldSource(value=flow_data["blocked_by"], source="local")

    client = self._get_project_client()
    if not client:
        view.offline_mode = True
        return view

    result = client.get_item(project_item_id)
    if isinstance(result, ProjectItemError):
        logger.bind(domain="task", action="hydrate", branch=branch).warning(
            f"Remote fetch failed: {result.type} - {result.message}"
        )
        if result.type == "not_found":
            return HydrateError(
                type="binding_invalid",
                message=(
                    f"Branch '{branch}' 绑定的 GitHub Project item "
                    f"'{project_item_id}' 已失效: {result.message}"
                ),
            )
        view.offline_mode = True
        return view

    if local_node_id and result.node_id and local_node_id != result.node_id:
        view.identity_drift = True

    if result.title:
        view.title = FieldSource(value=result.title, source="remote")
    if result.body:
        view.body = FieldSource(value=result.body, source="remote")
    if result.status:
        view.status = FieldSource(value=result.status, source="remote")
    if result.priority:
        view.priority = FieldSource(value=result.priority, source="remote")
    if result.assignees:
        view.assignees = FieldSource(value=result.assignees, source="remote")

    return view
