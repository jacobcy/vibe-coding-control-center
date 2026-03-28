# Issue 279 Plan A: Inspect/Snapshot 命令面收敛（单入口优先）

> For Agent: 使用最小改动策略，只做入口收敛与文案统一，不引入新能力。

## Goal
收敛 `inspect` 与 `snapshot` 的认知边界，避免类似功能多入口干扰：
- `inspect`: 变更分析（review 输入）
- `snapshot`: 结构基线/历史对比（治理视角）

## Scope
- 收敛 CLI help 与 docs 文案
- 处理 `inspect metrics` 的入口策略（迁移提示或兼容别名）
- 不改 review 核心算法

## Non-Goals
- 不重写 AST/metrics/snapshot 底层服务
- 不改 pre-push gate 逻辑

## Steps
1. 建立命令边界判定表（inspect vs snapshot）并落到标准文档。
2. 将 `inspect metrics` 改为迁移入口（输出指向单一入口），保留最小兼容。
3. 更新相关测试与 help 文案，确保用户只看到一条推荐路径。
4. 更新 issue 279 的决策结论（保留/降级/删除说明）。

## Files
- Modify: `src/vibe3/commands/inspect.py`
- Modify: `src/vibe3/commands/snapshot.py`
- Modify: `docs/standards/vibe3-command-standard.md`
- Modify: `docs/standards/vibe3-state-sync-standard.md`（若涉及联动说明）
- Modify/Test: `tests/vibe3/commands/test_inspect_metrics.py`（按收敛策略改）

## Acceptance
- 对用户可见的推荐入口不再重复。
- review 主链无回归（`review base/pr` 通过）。
- 文档与 help 完全一致。

## Verification
- `uv run pytest tests/vibe3/commands/test_inspect_metrics.py -q`
- `uv run pytest tests/vibe3/commands/test_review_base.py -q`
