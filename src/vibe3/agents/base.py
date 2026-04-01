from typing import Protocol, runtime_checkable

from vibe3.models.review_runner import AgentOptions, AgentResult


@runtime_checkable
class AgentBackend(Protocol):
    """可替换的 agent 执行后端接口。"""

    def run(
        self,
        prompt: str,
        options: AgentOptions,
        task: str | None = None,
        dry_run: bool = False,
        session_id: str | None = None,
    ) -> AgentResult:
        """运行 agent。

        Args:
            prompt: 输入给 agent 的指令或提示词。
            options: 运行选项（agent 预设、模型覆盖、超时等）。
            task: 可选的任务名称（用于标识）。
            dry_run: 是否为预览模式（不真正执行）。
            session_id: 可选的会话 ID（用于接续之前的执行）。

        Returns:
            AgentResult: 执行结果。
        """
        ...
