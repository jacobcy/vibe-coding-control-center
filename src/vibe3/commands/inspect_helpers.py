"""Inspect command helper functions."""

import sys
from typing import Union

from loguru import logger

from vibe3.models.change_source import BranchSource, CommitSource, PRSource
from vibe3.services import dag_service
from vibe3.services.pr_scoring_service import PRDimensions, generate_score_report
from vibe3.services.serena_service import SerenaService


def enable_trace() -> None:
    """启用 DEBUG 日志 + 运行时调用追踪."""
    from loguru import logger as _log

    _log.remove()
    _log.add(sys.stderr, level="DEBUG")

    indent = [0]

    def _tracer(frame: object, event: str, arg: object) -> object:
        import types

        assert isinstance(frame, types.FrameType)
        if event == "call" and "vibe3" in frame.f_code.co_filename:
            fn = frame.f_code.co_name
            _log.debug(
                f"{'  ' * indent[0]}→ "
                f"{frame.f_code.co_filename.split('vibe3/')[-1]}::{fn}()"
            )
            indent[0] += 1
        elif event == "return" and "vibe3" in frame.f_code.co_filename:
            indent[0] = max(0, indent[0] - 1)
        return _tracer

    sys.settrace(_tracer)  # type: ignore[arg-type]


def build_change_analysis(source_type: str, identifier: str) -> dict[str, object]:
    """执行改动分析流程（serena → dag → scoring）.

    Args:
        source_type: "pr" | "commit" | "branch"
        identifier: PR 编号、commit SHA 或分支名

    Returns:
        包含 impact / dag / score 的分析结果 dict
    """
    from vibe3.clients.git_client import GitClient

    log = logger.bind(
        domain="inspect", action="change_analysis", source_type=source_type
    )
    log.info("Running change analysis pipeline")

    # 构建 ChangeSource
    source: Union[PRSource, CommitSource, BranchSource]
    if source_type == "pr":
        source = PRSource(pr_number=int(identifier))
    elif source_type == "commit":
        source = CommitSource(sha=identifier)
    else:
        source = BranchSource(branch=identifier)

    # 1. Serena 符号分析
    svc = SerenaService(git_client=GitClient())
    impact = svc.analyze_changes(source)

    # 2. DAG 影响范围
    changed_files = impact.get("changed_files", [])
    assert isinstance(changed_files, list)
    dag = dag_service.expand_impacted_modules(changed_files)

    # 3. 风险评分
    dims = PRDimensions(
        changed_files=len(changed_files),
        impacted_modules=len(dag.impacted_modules),
        changed_lines=0,  # 需要从 diff 计算
        critical_path_touch=any(
            any(
                p in str(f)
                for p in ["bin/", "lib/flow", "lib/git", "src/vibe3/services/"]
            )
            for f in changed_files
        ),
        public_api_touch=any(
            any(p in str(f) for p in ["bin/vibe", "lib/flow.sh", "src/vibe3/commands/"])
            for f in changed_files
        ),
    )
    score = generate_score_report(dims)

    return {
        "impact": impact,
        "dag": dag.model_dump(),
        "score": score,
    }
