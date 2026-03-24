# Phase 04 Handoff Cutover Rewrite Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写 `docs/v3/handoff/04-handoff-and-cutover.md`，让它基于当前 v3 现状定义 handoff 真源、`task.md` 降级角色、review report 线索与 cutover readiness。

**Architecture:** 这是一次文档真源收敛，不改代码路径，不发明新存储层。核心做法是移除旧的 “SQLite ↔ Markdown 双向同步 + `vibe3_enabled` 切换” 叙述，改为围绕 handoff command、handoff store、`issue -> pr` 主链、`.agent/reports/` 临时证据层来重写 Phase 04，并同步入口文档的一句话描述。

**Tech Stack:** Markdown 文档、现有 standards、handoff phase docs、`rg` / `sed` / `pytest`（如需 doc-adjacent 校验）

---

## Chunk 1: Audit And Freeze The New Truth Model

### Task 1: 审计 Phase 04 的旧心智并锁定新口径

**Files:**
- Modify: `docs/v3/handoff/04-handoff-and-cutover.md`
- Read: `docs/standards/v3/handoff-governance-standard.md`
- Read: `docs/standards/v3/git-workflow-standard.md`
- Read: `docs/standards/v3/handoff-store-standard.md`
- Read: `.agent/context/task.md`
- Read: `.agent/reports/pre-push-review-*.md`

- [ ] **Step 1: 列出必须删除的旧表述**

必须删除或明确废弃：

- SQLite 与 Markdown 双向同步
- `handoff.md` marker 方案
- `vibe3 handoff sync/edit` 作为本阶段验收目标
- `.git/vibe3_enabled` 入口切换方案

- [ ] **Step 2: 锁定新的 Phase 04 核心结论**

新口径必须固定为：

- `handoff command + handoff store` 是共同真源
- `issue -> pr` 是唯一标准交付链
- `.agent/context/task.md` 只保留 workflow task list / findings / follow-up issue / final conclusion
- `.agent/reports/pre-push-review-*.md` 是临时 report 层
- `SESSION_ID` 已是可提取交接线索

- [ ] **Step 3: 运行最小审计检索，确认没有漏掉旧引用**

Run:

```bash
rg -n "handoff sync|handoff.md|vibe3_enabled|SQLite state to Markdown|Bridge SQLite state to Markdown" \
  docs/v3/handoff/04-handoff-and-cutover.md \
  docs/v3/handoff/README.md \
  docs/v3/handoff/v3-rewrite-plan.md
```

Expected: 先在改写前看到旧表述，后续任务会清掉。

## Chunk 2: Rewrite Phase 04

### Task 2: 全量重写 `04-handoff-and-cutover.md`

**Files:**
- Modify: `docs/v3/handoff/04-handoff-and-cutover.md`

- [ ] **Step 1: 重写 Goal / Truth Model / Success Criteria**

文稿必须覆盖：

- Phase Goal
- Truth Model
- `task.md` Reduced Role
- Handoff Conflict Rule
- Review Report Contract
- Cutover Meaning
- Success Criteria

- [ ] **Step 2: 明确 `task.md` 降级职责**

必须写清：

- 允许记录哪些内容
- 不允许记录哪些内容
- 为什么它不能再承担正式 handoff

- [ ] **Step 3: 明确 `SESSION_ID` 的合法地位**

必须写清：

- `SESSION_ID` 可引用
- 仅作为线索，不复制全文
- 与 report path / verdict / risk score 一起使用

- [ ] **Step 4: 自查文稿是否仍残留旧实现导向**

Run:

```bash
rg -n "handoff sync|handoff.md|marker|VIBE_STATE_START|vibe3_enabled|Markdown" \
  docs/v3/handoff/04-handoff-and-cutover.md
```

Expected: 不再出现把本阶段定义成双向同步或切换开关的表述。

## Chunk 3: Align Entry Documents

### Task 3: 同步 README 与 rewrite-plan 对 Phase 04 的一句话描述

**Files:**
- Modify: `docs/v3/handoff/README.md`
- Modify: `docs/v3/handoff/v3-rewrite-plan.md`

- [ ] **Step 1: 改写 Phase 04 Objective**

把目标从：

- Bridge SQLite state to Markdown handoff files

改成更贴近现状的表述，例如：

- Converge v3 handoff truth, reduce `task.md` to a workflow index, and define cutover readiness

- [ ] **Step 2: 改写 Success Criteria**

至少替换为围绕以下内容的验收：

- handoff truth model clarified
- `task.md` reduced role clarified
- review report / `SESSION_ID` recognized as evidence pointers
- cutover readiness defined without old `vibe3_enabled` switch

- [ ] **Step 3: 改写 Summary 表格中的 Phase 04 描述**

把 `Sync / Handoff.md` 一类旧词替换成：

- `Handoff Truth`
- `Truth Model`
- `Cutover Readiness`

## Chunk 4: Write The Follow-up Execution Notes

### Task 4: 在计划中明确后续执行边界

**Files:**
- Modify: `docs/plans/2026-03-21-phase04-handoff-cutover-rewrite-plan.md`

- [ ] **Step 1: 明确本次不做的事**

必须写清本次不做：

- `bin/vibe` 默认入口切换
- `pr show` 消费本地 report
- review prompt 质量优化
- skill 全量改写

- [ ] **Step 2: 明确后续跟进任务**

至少列出：

- skill 文案审计
- `pr show` 消费本地 report
- cutover 入口策略单独设计

- [ ] **Step 3: 做一次最终一致性检索**

Run:

```bash
rg -n "Bridge SQLite state to Markdown|handoff.md|vibe3_enabled|pr draft" \
  docs/v3/handoff/04-handoff-and-cutover.md \
  docs/v3/handoff/README.md \
  docs/v3/handoff/v3-rewrite-plan.md
```

Expected: Phase 04 不再使用旧双向同步与旧切换开关语言。

## Chunk 5: Final Verification

### Task 5: 做文档级回归检查

**Files:**
- Modify: `docs/v3/handoff/04-handoff-and-cutover.md`
- Modify: `docs/v3/handoff/README.md`
- Modify: `docs/v3/handoff/v3-rewrite-plan.md`
- Modify: `docs/plans/2026-03-21-phase04-handoff-cutover-rewrite-plan.md`

- [ ] **Step 1: 运行针对 Phase 04 的关键检索**

Run:

```bash
rg -n "task\\.md|SESSION_ID|issue -> pr|handoff store|cutover" \
  docs/v3/handoff/04-handoff-and-cutover.md \
  docs/v3/handoff/README.md \
  docs/v3/handoff/v3-rewrite-plan.md
```

Expected: 可以看到新的 handoff truth model 与 `SESSION_ID` 表述。

- [ ] **Step 2: 检查工作区变更**

Run:

```bash
git diff -- docs/v3/handoff/04-handoff-and-cutover.md \
  docs/v3/handoff/README.md \
  docs/v3/handoff/v3-rewrite-plan.md \
  docs/plans/2026-03-21-phase04-handoff-cutover-rewrite-plan.md
```

Expected: 变更仅限 Phase 04 文档和新计划文档。

- [ ] **Step 3: Commit**

```bash
git add docs/v3/handoff/04-handoff-and-cutover.md \
  docs/v3/handoff/README.md \
  docs/v3/handoff/v3-rewrite-plan.md \
  docs/plans/2026-03-21-phase04-handoff-cutover-rewrite-plan.md
---

## 后续执行边界

### 本次不做的事

本次文档重写**不做**以下工作：

- `bin/vibe` 默认入口切换：不在本次范围内，需要单独设计和实施
- `pr show` 消费本地 report：需要在后续任务中实现
- review prompt 质量优化：需要在后续任务中处理
- skill 全量改写：本阶段先收敛文档，不要求一次改完全部 skill

### 后续跟进任务

完成本文档重写后，需要跟进以下任务：

1. **skill 文案审计**
   - 审计所有 skill 是否仍把 `.agent/context/task.md` 当主 handoff
   - 修订仍把 handoff 冲突解释成 `task.md` 决定的 skill
   - 补齐未明确 `issue -> pr` 主链的 skill

2. **`pr show` 消费本地 report**
   - 实现 `pr show` 对 `.agent/reports/pre-push-review-*.md` 的消费
   - 集成 `SESSION_ID` 作为交接线索

3. **cutover 入口策略单独设计**
   - 设计 `bin/vibe` 默认入口切换策略
   - 评估切换时机和风险
   - 制定切换计划
