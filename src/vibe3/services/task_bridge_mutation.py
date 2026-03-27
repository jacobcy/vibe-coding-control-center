"""Task bridge mutation operations - 远端 task 写入操作。"""

from typing import Any

from loguru import logger

from vibe3.models.project_item import LinkError, ProjectItemError
from vibe3.models.task_bridge import TaskBridgeModel
from vibe3.services.label_service import LabelService


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
    # 确保 vibe-task label（幂等）
    LabelService().confirm_vibe_task(issue_number, should_exist=True)

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
