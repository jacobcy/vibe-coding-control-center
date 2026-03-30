"""Task service implementation."""

from typing import TYPE_CHECKING, Literal, cast

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.flow import FlowStatusResponse, IssueLink
from vibe3.models.project_item import LinkError, ProjectItemError
from vibe3.models.task_bridge import (
    FieldSource,
    HydratedTaskView,
    HydrateError,
    TaskBridgeModel,
)
from vibe3.services.flow_query_mixin import FlowQueryMixin
from vibe3.services.signature_service import SignatureService
from vibe3.services.task_bridge_mutation import auto_link_issue_to_project

if TYPE_CHECKING:
    from vibe3.clients.github_project_client import GitHubProjectClient


class TaskService(FlowQueryMixin):
    """Service for managing task state.

    task 状态真源在 GitHub Project，本地 SQLite 只存 flow 执行现场状态。
    bridge 操作（hydrate / auto_link_issue_to_project）直接集成于本类。
    """

    def __init__(
        self,
        store: SQLiteClient | None = None,
        project_client: "GitHubProjectClient | None" = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self._project_client: "GitHubProjectClient | None" = project_client

    # ------------------------------------------------------------------
    # GitHub Project bridge (from task_bridge_mixin.py)
    # ------------------------------------------------------------------

    def _get_project_client(self) -> "GitHubProjectClient | None":
        """Get or lazily initialize GitHubProjectClient from config."""
        if self._project_client is not None:
            return cast("GitHubProjectClient", self._project_client)

        try:
            from vibe3.clients.github_project_client import GitHubProjectClient
            from vibe3.config.settings import VibeConfig

            cfg = VibeConfig.get_defaults()
            gh_cfg = cfg.github_project
            effective_owner = gh_cfg.owner or gh_cfg.org
            if effective_owner and gh_cfg.project_number:
                self._project_client = GitHubProjectClient(
                    org=effective_owner,
                    project_number=gh_cfg.project_number,
                    owner_type=gh_cfg.owner_type,
                    owner=effective_owner,
                )
                return cast("GitHubProjectClient", self._project_client)
        except Exception as e:
            logger.bind(domain="task", action="get_project_client").warning(
                f"Failed to initialize GitHubProjectClient: {e}"
            )
        return None

    def hydrate(self, branch: str) -> HydratedTaskView | HydrateError:
        """从远端 GitHub Project 读取 task 真值，合并为 HydratedTaskView（只读）。"""
        return _hydrate_task(self, branch)

    def auto_link_issue_to_project(
        self, branch: str, issue_number: int
    ) -> TaskBridgeModel | LinkError:
        """issue 绑定为 task/dependency 时，自动将其加入 GitHub Project 并记录。"""
        return auto_link_issue_to_project(self, branch, issue_number)

    # ------------------------------------------------------------------
    # Core task operations
    # ------------------------------------------------------------------

    def link_issue(
        self,
        branch: str,
        issue_number: int,
        role: Literal["task", "related", "dependency"] = "related",
        actor: str | None = None,
    ) -> IssueLink:
        """Link an issue to a flow."""
        logger.bind(
            domain="task",
            action="link_issue",
            branch=branch,
            issue_number=issue_number,
            role=role,
        ).info("Linking issue to flow")

        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )

        self.store.add_issue_link(branch, issue_number, role)

        if role == "task":
            # task_issue_number is no longer stored in flow_state.
            # We only update latest_actor to track activity.
            self.store.update_flow_state(
                branch,
                latest_actor=effective_actor,
            )

        self.store.add_event(
            branch,
            "issue_linked",
            effective_actor,
            f"Issue #{issue_number} linked as {role}",
        )

        if role in {"task", "dependency"}:
            link_result = self.auto_link_issue_to_project(branch, issue_number)
            if isinstance(link_result, LinkError):
                logger.bind(
                    domain="task",
                    action="link_issue",
                    branch=branch,
                    issue_number=issue_number,
                    role=role,
                ).warning(f"Auto project link skipped: {link_result.message}")

        return IssueLink(
            branch=branch,
            issue_number=issue_number,
            issue_role=role,
        )

    def get_task(self, branch: str) -> FlowStatusResponse | None:
        """Get task (flow) details."""
        logger.bind(domain="task", action="get", branch=branch).debug("Getting task")
        return self.get_flow_status(branch)


# ---------------------------------------------------------------------------
# Task hydration logic (from task_bridge_lookup.py)
# ---------------------------------------------------------------------------


def _hydrate_task(
    svc: TaskService,
    branch: str,
) -> HydratedTaskView | HydrateError:
    """从远端 GitHub Project 读取 task 真值，合并为 HydratedTaskView（只读）。"""
    flow_data = svc.store.get_flow_state(branch)
    if not flow_data:
        return HydrateError(
            type="no_remote_identity",
            message=f"Branch '{branch}' 没有 flow 记录，无法查看 task",
        )

    issue_links = svc.store.get_issue_links(branch)
    task_issue = IssueLink.resolve_task_number(issue_links)

    project_item_id = flow_data.get("project_item_id")
    if not project_item_id:
        return HydrateError(
            type="no_remote_identity",
            message=(
                f"Branch '{branch}' 未绑定 GitHub Project item，"
                "请先运行 vibe3 flow bind <issue_number> 绑定 task/dependency"
            ),
        )

    local_node_id = flow_data.get("project_node_id")
    view = HydratedTaskView(branch=branch)
    view.project_item_id = FieldSource(value=project_item_id, source="local")
    if task_issue:
        view.task_issue_number = FieldSource(value=task_issue, source="local")
    if flow_data.get("spec_ref"):
        view.spec_ref = FieldSource(value=flow_data["spec_ref"], source="local")
    if flow_data.get("next_step"):
        view.next_step = FieldSource(value=flow_data["next_step"], source="local")
    if flow_data.get("blocked_by"):
        view.blocked_by = FieldSource(value=flow_data["blocked_by"], source="local")

    client = svc._get_project_client()
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
