"""Context builder - 将多个数据源构建成 Codex review 的输入上下文."""

from pathlib import Path

from loguru import logger

from vibe3.exceptions import VibeError


class ContextBuilderError(VibeError):
    """上下文构建失败."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Context build failed: {details}", recoverable=False)


def build_review_context(
    diff: str,
    policy_path: str = ".codex/review-policy.md",
    structure: str | None = None,
    impact: str | None = None,
    dag: str | None = None,
    score: str | None = None,
) -> str:
    """构建 Codex review 的完整上下文.

    Args:
        diff: git diff 输出
        policy_path: review-policy.md 路径
        structure: 仓库结构摘要（JSON 字符串）
        impact: Serena 符号分析结果（JSON 字符串）
        dag: 影响范围图（JSON 字符串）
        score: 风险评分（JSON 字符串）

    Returns:
        完整的上下文字符串

    Raises:
        ContextBuilderError: 构建失败
    """
    log = logger.bind(domain="context_builder", action="build_review_context")
    log.info("Building review context")

    try:
        policy = Path(policy_path).read_text(encoding="utf-8")
    except OSError as e:
        raise ContextBuilderError(f"Cannot read policy: {e}") from e

    sections: list[str] = [policy]

    if structure:
        sections.append(f"## Repository Structure Summary\n{structure}")
    if impact:
        sections.append(f"## Serena Impact Analysis\n```json\n{impact}\n```")
    if dag:
        sections.append(f"## Impact DAG\n```json\n{dag}\n```")
    if score:
        sections.append(f"## Risk Score\n```json\n{score}\n```")

    sections.append(f"## Git Diff\n```diff\n{diff}\n```")

    context = "\n\n---\n\n".join(sections)
    log.bind(context_len=len(context)).success("Review context built")
    return context


def get_git_diff(base: str = "main", head: str = "HEAD") -> str:
    """获取 git diff 输出.

    Args:
        base: 基准分支或 commit
        head: 目标分支或 commit

    Returns:
        diff 文本

    Raises:
        ContextBuilderError: git 命令失败
    """
    import subprocess

    log = logger.bind(
        domain="context_builder", action="get_git_diff", base=base, head=head
    )
    log.info("Getting git diff")

    try:
        result = subprocess.run(
            ["git", "diff", "--unified=3", f"{base}...{head}"],
            capture_output=True,
            text=True,
            check=True,
        )
        log.bind(diff_len=len(result.stdout)).success("Got git diff")
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise ContextBuilderError(f"git diff failed: {e.stderr}") from e
