"""CommitAnalyzer — 分析单次 commit 改动规模，计算复杂度分数，决定是否触发审核."""

import json
import re
import subprocess
from pathlib import Path
from typing import TypedDict

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.exceptions import CommitAnalyzerError


class CommitAnalysisResult(TypedDict):
    lines_changed: int
    files_changed: int
    complexity_score: int
    should_review: bool


def calculate_score(lines_changed: int, files_changed: int) -> int:
    """计算 commit 复杂度分数（纯函数）。

    行数得分：1–50→1，51–200→3，201–500→5，>500→8
    文件数加分：1–2→+1，3–5→+2，>5→+3
    最终分数 = min(行数得分 + 文件数加分, 10)

    Args:
        lines_changed: 总改动行数（增加 + 删除）
        files_changed: 改动文件数

    Returns:
        复杂度分数，范围 [0, 10]
    """
    log = logger.bind(domain="commit_analyzer", action="calculate_score")

    if lines_changed <= 50:
        line_score = 1
    elif lines_changed <= 200:
        line_score = 3
    elif lines_changed <= 500:
        line_score = 5
    else:
        line_score = 8

    if files_changed <= 2:
        file_bonus = 1
    elif files_changed <= 5:
        file_bonus = 2
    else:
        file_bonus = 3

    score = min(line_score + file_bonus, 10)
    log.bind(
        lines_changed=lines_changed, files_changed=files_changed, score=score
    ).debug("Score calculated")
    return score


def _load_config() -> VibeConfig:
    """从 .vibe/config.yaml 加载配置，文件不存在时使用默认值。"""
    config_path = Path(".vibe/config.yaml")
    if config_path.exists():
        return VibeConfig.from_yaml(config_path)
    return VibeConfig()


def analyze_commit(commit_sha: str) -> CommitAnalysisResult:
    """分析单个 commit 的改动规模，计算复杂度分数，决定是否触发审核。

    Args:
        commit_sha: commit SHA

    Returns:
        CommitAnalysisResult: 包含 lines_changed, files_changed,
            complexity_score, should_review

    Raises:
        CommitAnalyzerError: git 命令失败时抛出
    """
    log = logger.bind(domain="commit_analyzer", action="analyze_commit")
    log.info("Analyzing commit")

    logger.bind(
        domain="commit_analyzer",
        action="analyze_commit",
        external="git",
        sha=commit_sha,
    ).debug("Calling git: show --stat")

    try:
        result = subprocess.run(
            ["git", "show", "--stat", commit_sha],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise CommitAnalyzerError(operation="show_stat", details=e.stderr) from e

    stat_output = result.stdout
    lines_changed, files_changed = _parse_stat_output(stat_output)

    config = _load_config()
    auto_trigger = config.review.auto_trigger

    score = calculate_score(lines_changed, files_changed)

    if not auto_trigger.enabled:
        should_review = False
    else:
        should_review = score >= auto_trigger.min_complexity

    analysis: CommitAnalysisResult = {
        "lines_changed": lines_changed,
        "files_changed": files_changed,
        "complexity_score": score,
        "should_review": should_review,
    }

    log.bind(
        sha=commit_sha,
        lines_changed=lines_changed,
        files_changed=files_changed,
        score=score,
        should_review=should_review,
    ).success("Commit analyzed")

    return analysis


def _parse_stat_output(stat_output: str) -> tuple[int, int]:
    """解析 git show --stat 输出，提取 lines_changed 和 files_changed。

    末尾行格式示例：
      3 files changed, 45 insertions(+), 12 deletions(-)
      1 file changed, 5 insertions(+)
      2 files changed, 10 deletions(-)

    Args:
        stat_output: git show --stat 的输出文本

    Returns:
        (lines_changed, files_changed) 元组
    """
    lines = stat_output.strip().splitlines()

    for line in reversed(lines):
        line = line.strip()
        files_match = re.search(r"(\d+) files? changed", line)
        if not files_match:
            continue

        files_changed = int(files_match.group(1))

        insertions = 0
        deletions = 0

        ins_match = re.search(r"(\d+) insertion", line)
        if ins_match:
            insertions = int(ins_match.group(1))

        del_match = re.search(r"(\d+) deletion", line)
        if del_match:
            deletions = int(del_match.group(1))

        lines_changed = insertions + deletions
        return lines_changed, files_changed

    return 0, 0


def analyze_commit_json(sha: str) -> str:
    """分析 commit 并返回 JSON 字符串（供 CLI 调用）。

    Args:
        sha: commit SHA

    Returns:
        JSON 字符串
    """
    result = analyze_commit(sha)
    return json.dumps(result)
