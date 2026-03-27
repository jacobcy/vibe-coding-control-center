"""PR merge guard helpers for flow lifecycle."""

from typing import Any

from vibe3.exceptions import UserError
from vibe3.models.pr import PRState


def ensure_flow_pr_merged(
    gh_client: Any,
    flow_data: dict[str, Any],
    branch: str,
) -> None:
    """Ensure the flow has a merged PR before allowing flow close."""
    pr_number = flow_data.get("pr_number")
    try:
        pr = gh_client.get_pr(pr_number) if pr_number else None
        if pr is None:
            pr = gh_client.get_pr(branch=branch)
    except Exception as error:
        raise UserError(
            "无法检查当前 flow 的 PR merge 状态。\n"
            "请先确认 PR 已 merged；\n"
            "若要放弃当前 flow，请执行 `vibe3 flow aborted`。\n"
            f"原始错误: {error}"
        ) from error

    if not pr:
        raise UserError(
            "当前 flow 未找到可关闭的 PR。\n"
            "请先执行 `vibe3 pr create` 并完成 merge；"
            "若要放弃当前 flow，请执行 `vibe3 flow aborted`。"
        )

    merged = pr.state == PRState.MERGED or pr.merged_at is not None
    if not merged:
        raise UserError(
            f"PR #{pr.number} 尚未 merged，不能关闭 flow。\n"
            "请先完成 merge；若要放弃当前 flow，请执行 `vibe3 flow aborted`。"
        )
