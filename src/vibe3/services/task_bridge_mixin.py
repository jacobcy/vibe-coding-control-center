"""Task bridge mixin — GitHub Project 远端读写操作。"""

from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.models.project_item import LinkError, ProjectItemError
from vibe3.models.task_bridge import (
    FieldSource,
    HydratedTaskView,
    HydrateError,
    TaskBridgeModel,
)

if TYPE_CHECKING:
    from vibe3.clients.github_project_client import GitHubProjectClient
    from vibe3.clients.sqlite_client import SQLiteClient


class TaskBridgeMixin:
    """Mixin providing GitHub Project bridge operations for TaskService."""

    store: "SQLiteClient"
    _project_client: "GitHubProjectClient | None"

    def _get_project_client(self: Any) -> "GitHubProjectClient | None":
        """Get or lazily initialize GitHubProjectClient from config."""
        if self._project_client is not None:
            return cast("GitHubProjectClient", self._project_client)  # type: ignore[attr-defined]

        try:
            from vibe3.clients.github_project_client import GitHubProjectClient
            from vibe3.config.settings import VibeConfig

            cfg = VibeConfig.get_defaults()
            gh_cfg = cfg.github_project
            effective_owner = gh_cfg.owner or gh_cfg.org
            if effective_owner and gh_cfg.project_number:
                self._project_client = GitHubProjectClient(  # type: ignore[attr-defined]
                    org=effective_owner,
                    project_number=gh_cfg.project_number,
                    owner_type=gh_cfg.owner_type,
                    owner=effective_owner,
                )
                return cast("GitHubProjectClient", self._project_client)  # type: ignore[attr-defined]
        except Exception as e:
            logger.bind(domain="task", action="get_project_client").warning(
                f"Failed to initialize GitHubProjectClient: {e}"
            )
        return None

    def hydrate(self: Any, branch: str) -> HydratedTaskView | HydrateError:
        """从远端 GitHub Project 读取 task 真值，合并为 HydratedTaskView（只读）。"""
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return HydrateError(
                type="no_remote_identity",
                message=f"Branch '{branch}' 未找到本地 flow，请先运行 vibe flow new",
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
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return LinkError(
                type="flow_not_found",
                message=f"Branch '{branch}' 尚未创建 flow，请先运行 vibe flow new",
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

    def get_task_bridge_for_flow(self: Any, branch: str) -> HydratedTaskView:
        """获取 flow 消费用的 HydratedTaskView，远端失败时降级为 offline mode。"""
        result = self.hydrate(branch)
        if isinstance(result, HydrateError):
            flow_data = self.store.get_flow_state(branch) or {}
            view = HydratedTaskView(branch=branch, offline_mode=True)
            if flow_data.get("project_item_id"):
                view.project_item_id = FieldSource(
                    value=flow_data["project_item_id"], source="local"
                )
            if flow_data.get("task_issue_number"):
                view.task_issue_number = FieldSource(
                    value=flow_data["task_issue_number"], source="local"
                )
            if flow_data.get("next_step"):
                view.next_step = FieldSource(
                    value=flow_data["next_step"], source="local"
                )
            return view
        return cast("HydratedTaskView", result)
