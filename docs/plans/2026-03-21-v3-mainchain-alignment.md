# V3 Mainchain Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收敛 v3 当前代码与主链架构，使 `issue -> task -> flow -> pr -> handoff` 的核心语义不再互相打架，并为后续 `task -> GitHub Project` 与 orchestrator 设计留下稳定边界。

**Architecture:** 本次只做“主链语义收敛”的最小改动，不发明新的本地真源，不补完整 orchestrator，也不把 task 做成本地 registry。代码上先统一 `flow_status`、`issue_role`、关键 `flow_events` 命名和 PR 合并后的 flow 状态；文档上把本轮收敛目标和后续缺口写清，避免执行者继续沿错误心智扩展。

**Tech Stack:** Markdown, Python 3.10+, Typer, Pydantic, SQLite, pytest, uv

---

### Task 1: 写清主链收敛范围与非目标

**Files:**
- Modify: `docs/v3/handoff/04-handoff-and-cutover.md`
- Modify: `docs/v3/ROADMAP.md`
- Modify: `docs/v3/handoff/README.md`
- Test: `rg` consistency checks only

**Step 1: 检查文档是否仍把本地层写成真源或正文存储**

Run: `rg -n "唯一真源|JSON <-> SQLite|handoff.md|plan.json|report.json|audit.json|task 状态通过 .*SQLite" docs/v3 docs/standards/v3 -S`

Expected: 只允许出现在“禁止/反例/已废弃”语境，不允许作为当前实现目标。

**Step 2: 保持 Phase 04 与 roadmap 口径一致**

确认并补齐以下口径：

- `repo issue -> pr` 是用户主链
- `task` 需要补齐到 GitHub Project，但本轮不建立本地 task 真源
- `handoff` 只做索引、责任链和证据指针
- `orchestrator` 是下一阶段，在 handoff 稳定后再设计

**Step 3: 跑一致性检索**

Run: `rg -n "handoff truth model|workflow index|SESSION_ID|GitHub Project|本地真源" docs/v3/handoff/04-handoff-and-cutover.md docs/v3/handoff/README.md docs/v3/ROADMAP.md -S`

Expected: 三份文档都能反映同一主链口径。

### Task 2: 收敛核心枚举与事件语义

**Files:**
- Modify: `src/vibe3/models/flow.py`
- Modify: `src/vibe3/services/flow_service.py`
- Modify: `src/vibe3/services/task_service.py`
- Modify: `src/vibe3/services/pr_service.py`
- Modify: `src/vibe3/commands/flow.py`
- Modify: `src/vibe3/commands/task.py`
- Test: `tests/vibe3/services/test_flow_creation.py`
- Test: `tests/vibe3/services/test_flow_binding.py`
- Test: `tests/vibe3/services/test_flow_status.py`
- Test: `tests/vibe3/services/test_task_linking.py`
- Test: `tests/vibe3/services/test_task_management.py`

**Step 1: 先写或修改测试，锁定新的语义**

需要锁定：

- `flow_status` 只接受 `active`, `blocked`, `done`, `stale`
- `issue_role` 只接受 `task`, `repo`
- PR 合并后写回 `flow_status="done"`
- 核心事件名与标准对齐：至少 `flow_bind`, `pr_draft`, `pr_merge`

**Step 2: 运行这些测试，确认现状失败**

Run: `uv run pytest tests/vibe3/services/test_flow_creation.py tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_flow_status.py tests/vibe3/services/test_task_linking.py tests/vibe3/services/test_task_management.py -q`

Expected: 至少有和旧枚举/旧事件名相关的失败。

**Step 3: 做最小实现改动**

实现要求：

- `FlowState.flow_status` 改成标准枚举
- `IssueLink.issue_role` 改成标准枚举
- `task link --role` 改成 `task|repo`
- `flow bind` 事件名改成 `flow_bind`
- `pr create` 事件名改成 `pr_draft`
- `pr merge` 事件名改成 `pr_merge`
- `pr merge` 更新 flow 状态为 `done`

**Step 4: 再跑服务层测试**

Run: `uv run pytest tests/vibe3/services/test_flow_creation.py tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_flow_status.py tests/vibe3/services/test_task_linking.py tests/vibe3/services/test_task_management.py -q`

Expected: 目标测试全部通过。

### Task 3: 收敛 CLI 参数面和用户文案

**Files:**
- Modify: `src/vibe3/commands/task.py`
- Modify: `src/vibe3/ui/task_ui.py`
- Modify: `src/vibe3/ui/flow_ui.py`
- Test: `tests/vibe3/commands/` 中与 `task` / `flow` 相关测试

**Step 1: 对齐 CLI 暴露的枚举和值**

要求：

- `task link --role` 不再出现 `related`
- `flow list --status` 不再出现 `idle` / `missing`
- 如果有帮助文本、UI 输出引用旧词，也一起改掉

**Step 2: 跑对应命令测试**

Run: `uv run pytest tests/vibe3/commands -q`

Expected: 若有旧枚举相关测试失败，再补最小修正直到通过。

### Task 4: 补一层架构防回退说明

**Files:**
- Modify: `docs/v3/handoff/04-handoff-and-cutover.md`
- Modify: `docs/plans/2026-03-21-v3-mainchain-alignment.md`

**Step 1: 在文档中明确本轮不做的事情**

必须写清：

- 不实现本地 task registry
- 不把 task 状态做成本地真源
- 不补 orchestrator
- 不新增 handoff 正文表

**Step 2: 在文档中明确后续真正要补的部分**

必须写清：

- `task -> GitHub Project` 对接
- pointer-only handoff command
- review report 与 PR 展示的整合
- orchestrator 只在 handoff 稳定后设计

### Task 5: 做一次总代码审查和验证

**Files:**
- Review only

**Step 1: 跑主链相关测试集合**

Run: `uv run pytest tests/vibe3/services/test_flow_creation.py tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_flow_status.py tests/vibe3/services/test_task_linking.py tests/vibe3/services/test_task_management.py tests/vibe3/commands -q`

Expected: 本轮涉及测试通过；若有无关失败，需要在最终报告中明确区分。

**Step 2: 跑类型检查（至少覆盖相关模块）**

Run: `uv run mypy src/vibe3/models/flow.py src/vibe3/services/flow_service.py src/vibe3/services/task_service.py src/vibe3/services/pr_service.py src/vibe3/commands/flow.py src/vibe3/commands/task.py`

Expected: 无新增类型错误。

**Step 3: 做最终审查**

审查点：

- 是否仍残留 `idle` / `missing` / `related`
- 是否仍把 PR merge 写成本地 `merged` flow 状态
- 是否出现新的“本地真源”心智

Run: `rg -n "\"idle\"|\"missing\"|\"related\"|flow_status=\"merged\"|issue_body|project_item_json|plan.json|report.json|audit.json" src/vibe3 docs/v3 docs/standards/v3 tests/vibe3 -S`

Expected: 只允许出现在历史报告、设计反例或明确说明“旧语义”的文档里。

## 后续说明

本计划完成后，进入下一轮的前提是：

1. 核心对象语义已经统一
2. 本地 store 仍然只是索引和交接记录
3. `task -> GitHub Project` 被明确识别为下一阶段能力，而不是继续用本地字段假装完成
