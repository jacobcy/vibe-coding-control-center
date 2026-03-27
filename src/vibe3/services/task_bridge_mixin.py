"""Task bridge mixin — GitHub Project 远端读写操作。"""

from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.models.project_item import LinkError
from vibe3.models.task_bridge import HydratedTaskView, HydrateError, TaskBridgeModel
from vibe3.services.task_bridge_lookup import hydrate_task
from vibe3.services.task_bridge_mutation import (
    auto_link_issue_to_project,
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
        return hydrate_task(self, branch)

    def auto_link_issue_to_project(
        self: Any, branch: str, issue_number: int
    ) -> TaskBridgeModel | LinkError:
        """issue 绑定为 task/dependency 时，自动将其加入 GitHub Project 并记录。"""
        return auto_link_issue_to_project(self, branch, issue_number)
