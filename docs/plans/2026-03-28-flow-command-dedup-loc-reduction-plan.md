# Plan B: Flow 命令层去重与 LOC 降压

> For Agent: 以“删重复实现”为首选，不做行为扩展。

## Goal
降低命令层重复代码和文件超长风险，优先削减 `flow` 相关重复实现，减少维护漂移。

## Scope
- 清理/合并 `flow` 命令内重复的 show/status 渲染逻辑
- 统一远端信息读取路径，减少 command 层拼装代码
- 通过复用而非新增 helper 达到减行

## Non-Goals
- 不新增 flow 子命令
- 不修改 flow 状态机语义

## Steps
1. 识别 `flow` 命令中重复路径（show/status/snapshot 输出分支）。
2. 收敛到单一命令实现，删除重复分支代码。
3. 若存在未接线旧模块，删除死代码或改为单一复用入口。
4. 补齐回归测试并检查输出兼容。

## Files
- Modify: `src/vibe3/commands/flow.py`
- Modify/Delete: `src/vibe3/commands/flow_status.py`（根据复用结果二选一）
- Modify: `src/vibe3/ui/flow_ui.py`（仅必要时）
- Test: `tests/vibe3/commands/test_flow_done.py`
- Test: `tests/vibe3/commands/test_flow_show.py`（如存在）

## Acceptance
- 命令行为不变，代码分支更少。
- 相关文件 LOC 明显下降。
- 无孤儿模块、无未引用旧实现。

## Verification
- `uv run pytest tests/vibe3/commands/test_flow_done.py -q`
- `uv run pytest tests/vibe3/services/test_flow_lifecycle.py -q`
