"""Task bridge mutation operations - 远端 task 写入操作。"""

from typing import Any, cast

from loguru import logger

from vibe3.models.project_item import LinkError, ProjectItemError
from vibe3.models.task_bridge import TaskBridgeModel


def update_remote_task_status(
    self: Any, branch: str, status: str
) -> bool | ProjectItemError:
    """通过 GitHub API 更新远端 Project item 的 task 状态（唯一合法写入路径）。"""
    flow_data = self.store.get_flow_state(branch)
    if not flow_data:
        return ProjectItemError(
            type="not_found",
            message=f"Branch '{branch}' 未找到本地 flow",
        )

    project_node_id = flow_data.get("project_node_id")
    if not project_node_id:
        return ProjectItemError(
            type="not_found",
            message=(
                f"Branch '{branch}' 未绑定 GitHub Project item，"
                "请先运行 vibe task bridge link-project <id>"
            ),
        )

    client = self._get_project_client()
    if not client:
        return ProjectItemError(
            type="auth_error",
            message=(
                "GitHubProjectClient 未初始化，"
                "请检查 config/settings.yaml 中的 github_project 配置"
            ),
        )

    result = client.update_item_status(project_node_id, status)
    if result is True:
        self.store.add_event(
            branch,
            "remote_status_updated",
            "system",
            f"Remote task status updated to '{status}'",
        )
    return cast("bool | ProjectItemError", result)


def link_project_item(
    self: Any, branch: str, project_item_id: str, force: bool = False
) -> TaskBridgeModel | LinkError:
    """将本地 task bridge 与远端 GitHub Project item 绑定。"""
    # Auto-ensure flow for branch
    from vibe3.models.flow import MainBranchProtectedError
    from vibe3.services.flow_service import FlowService

    try:
        FlowService().ensure_flow_for_branch(branch)
    except MainBranchProtectedError as e:
        return LinkError(
            type="main_branch_protected",
            message=str(e),
        )

    flow_data = self.store.get_flow_state(branch)
    if not flow_data:
        # Should not happen after ensure_flow_for_branch, handle defensively
        return LinkError(
            type="flow_not_found",
            message=f"Branch '{branch}' flow creation failed unexpectedly",
        )

    client = self._get_project_client()
    if not client:
        return LinkError(
            type="item_not_found",
            message=(
                "GitHubProjectClient 未初始化，"
                "请检查 config/settings.yaml 中的 github_project 配置"
            ),
        )

    remote = client.get_item(project_item_id)
    if isinstance(remote, ProjectItemError):
        return LinkError(
            type="item_not_found",
            message=(
                f"GitHub Project item '{project_item_id}' 不存在"
                if remote.type == "not_found"
                else f"无法验证 item 存在性: {remote.message}"
            ),
        )

    existing_id = flow_data.get("project_item_id")
    if existing_id and existing_id != project_item_id and not force:
        return LinkError(
            type="already_bound",
            message=(
                f"Branch '{branch}' 已绑定 "
                f"project_item_id='{existing_id}'，"
                "如需覆盖请传入 --force"
            ),
        )

    self.store.update_bridge_fields(
        branch,
        project_item_id=project_item_id,
        project_node_id=remote.node_id,
    )
    self.store.add_event(
        branch,
        "project_item_linked",
        "system",
        f"Linked to GitHub Project item '{project_item_id}'",
    )
    logger.bind(
        domain="task",
        action="link_project_item",
        branch=branch,
        project_item_id=project_item_id,
    ).info("Linked project item")

    flow_data = self.store.get_flow_state(branch) or {}
    return TaskBridgeModel(
        branch=branch,
        project_item_id=flow_data.get("project_item_id"),
        project_node_id=flow_data.get("project_node_id"),
        task_issue_number=flow_data.get("task_issue_number"),
        spec_ref=flow_data.get("spec_ref"),
        plan_ref=flow_data.get("plan_ref"),
        next_step=flow_data.get("next_step"),
        blocked_by=flow_data.get("blocked_by"),
        latest_actor=flow_data.get("latest_actor"),
    )


def auto_link_issue_to_project(
    self: Any, branch: str, issue_number: int
) -> TaskBridgeModel | LinkError:
    """issue 绑定为 task/dependency 时，自动将其加入 GitHub Project 并记录。

    执行顺序：
    1. 确保 issue 有 vibe-task label
    2. 检查 issue 是否已在项目里（find_item_by_issue）
    3. 若不存在，调用 add_issue_to_project 添加
    4. 将 project_item_id / project_node_id 写入本地 SQLite
    """
    from vibe3.services.task_label_service import TaskLabelService

    # 确保 vibe-task label
    label_svc = TaskLabelService()
    label_svc.ensure_vibe_task_label(issue_number)

    client = self._get_project_client()
    if not client:
        return LinkError(
            type="item_not_found",
            message="GitHubProjectClient 未初始化，跳过自动 project 绑定",
        )

    # 先查 issue 是否已在项目里
    existing = client.find_item_by_issue(issue_number)
    if not isinstance(existing, ProjectItemError):
        item = existing
        logger.bind(
            domain="task",
            action="auto_link_issue_to_project",
            issue_number=issue_number,
            item_id=item.item_id,
        ).info("Issue already in project, reusing existing item")
    else:
        if existing.type != "not_found":
            return LinkError(type="item_not_found", message=existing.message)
        # 不在项目里，添加
        added = client.add_issue_to_project(issue_number)
        if isinstance(added, ProjectItemError):
            return LinkError(type="item_not_found", message=added.message)
        item = added

    # 幂等性检查：如果已经绑定相同的 project_item_id，则跳过更新和事件写入
    flow_data = self.store.get_flow_state(branch) or {}
    existing_item_id = flow_data.get("project_item_id")
    if existing_item_id == item.item_id:
        logger.bind(
            domain="task",
            action="auto_link_issue_to_project",
            branch=branch,
            issue_number=issue_number,
            project_item_id=item.item_id,
        ).info("Project item already linked, skipping duplicate event")
        return TaskBridgeModel(
            branch=branch,
            project_item_id=flow_data.get("project_item_id"),
            project_node_id=flow_data.get("project_node_id"),
            task_issue_number=flow_data.get("task_issue_number"),
            spec_ref=flow_data.get("spec_ref"),
            plan_ref=flow_data.get("plan_ref"),
            next_step=flow_data.get("next_step"),
            blocked_by=flow_data.get("blocked_by"),
            latest_actor=flow_data.get("latest_actor"),
        )

    self.store.update_bridge_fields(
        branch,
        project_item_id=item.item_id,
        project_node_id=item.node_id,
    )
    self.store.add_event(
        branch,
        "project_item_linked",
        "system",
        f"Auto-linked issue #{issue_number} to project item '{item.item_id}'",
    )
    logger.bind(
        domain="task",
        action="auto_link_issue_to_project",
        branch=branch,
        issue_number=issue_number,
        project_item_id=item.item_id,
    ).info("Auto-linked issue to GitHub Project")

    flow_data = self.store.get_flow_state(branch) or {}
    return TaskBridgeModel(
        branch=branch,
        project_item_id=flow_data.get("project_item_id"),
        project_node_id=flow_data.get("project_node_id"),
        task_issue_number=flow_data.get("task_issue_number"),
        spec_ref=flow_data.get("spec_ref"),
        plan_ref=flow_data.get("plan_ref"),
        next_step=flow_data.get("next_step"),
        blocked_by=flow_data.get("blocked_by"),
        latest_actor=flow_data.get("latest_actor"),
    )
