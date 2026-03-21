---
document_type: plan
title: Phase 04 - Handoff And Cutover
status: draft
author: GPT-5 Codex
created: 2026-03-15
last_updated: 2026-03-21
related_docs:
  - docs/v3/handoff/v3-rewrite-plan.md
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v2/handoff-governance-standard.md
  - docs/plans/2026-03-13-vibe3-parallel-rebuild-design.md
  - docs/v3/infrastructure/01-data-standard.md
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/v3/infrastructure/04-test-standards.md
---

# Phase 04: Handoff And Cutover

**Goal**: 收敛 v3 的 handoff 真相模型，明确多 agent 交接边界，降级 `.agent/context/task.md` 为 workflow 辅助索引，并定义 cutover readiness。

## 1. Truth Model

本阶段固定以下口径：

- `repo issue -> pr` 是唯一标准交付链
- `git` 与 GitHub 现场负责业务事实
- SQLite handoff store 只负责 flow 责任链与最小索引
- `plan_ref / report_ref / audit_ref` 只存引用，不复制正文
- `.agent/context/task.md` 是本地 workflow handoff，不是真源
- review report 与 `SESSION_ID` 只作证据指针，不替代 issue / PR / git 事实

补充说明：

- handoff 在 v3 中的角色不是第二套内容数据库，而是跨 agent 的上下文索引层
- 执行 agent 应能看到 planner / reviewer 留下的正式产物引用、当前 flow 的 findings 线索、下一步建议与阻塞信息
- 如果 handoff 与 `issue / pr / git` 现场冲突，必须修正 handoff，而不是修正现场

## 2. Why This Phase Exists

Phase 02 已落地 `flow_state` 主表与最小事件表，能够承载：

- `task_issue_number`
- `pr_number`
- `spec_ref / plan_ref / report_ref / audit_ref`
- `planner / executor / reviewer` 责任链字段
- `blocked_by / next_step / latest_actor`

但当前仍缺少三件事情：

1. 用统一口径说明 handoff store 到底存什么、不存什么
2. 给 `.agent/context/task.md` 一个降级后的明确职责
3. 给 review report 和 `SESSION_ID` 一个合法但受限的证据地位

本阶段的重点是**收敛真相模型**，不是继续扩张本地存储层。

## 3. Architecture Constraints

见 [01-command-and-skeleton.md](01-command-and-skeleton.md) §通用架构约束。

本阶段额外固定以下约束：

- 不新增以正文为中心的 `handoff_items.content` 主存储
- 不引入 `JSON <-> SQLite` 双向同步仲裁
- 不把 `.agent/handoff/*.json` 设计成正式存储层
- 不让本地 store 缓存 issue 正文、PR 正文、Project mirror 或 report 全文
- 不把 `task.md` 升格为可覆盖 SQLite / GitHub / git 的事实层

## 4. Current State And Gaps

### 4.1 已有基础

已有实现：

- `src/vibe3/models/flow.py` 中的 `FlowState`
- `src/vibe3/clients/sqlite_client.py` 中的 `flow_state` / `flow_issue_links` / `flow_events`
- `src/vibe3/services/flow_service.py`
- `src/vibe3/services/pr_service.py`

这些能力已经说明 v3 当前的最小 handoff store 主体仍然是：

- `flow_state` 作为每个 branch 一条责任链主记录
- `flow_issue_links` 作为 flow 与 issue 的关联表
- `flow_events` 作为最小审计事件表

### 4.2 Cutover 前必须承认的实现分叉

在继续实现 handoff command 之前，必须先承认并收敛以下不一致：

- `flow_status` 当前实现使用 `active / idle / missing / stale`，而标准文档定义的是 `active / blocked / done / stale`
- `issue_role` 当前实现使用 `task / related`，而标准文档定义的是 `task / repo`
- `flow_events.event_type` 当前实现与标准列举尚未统一
- `PRService` 当前会把 `flow_status=\"merged\"` 写回本地 store，这不符合现行标准枚举

这些问题不要求在本阶段全部改完，但必须在本阶段文档中被明确识别为后续实现 blocker，避免继续在漂移语义上叠加新层。

## 5. Data Responsibility

### 5.1 本地 store 允许承载的内容

SQLite handoff store 只允许承载：

- flow 身份锚点：`branch`, `flow_slug`
- 主闭环关联：`task_issue_number`, `pr_number`
- 正式产物引用：`spec_ref`, `plan_ref`, `report_ref`, `audit_ref`
- 责任链字段：`planner_actor`, `executor_actor`, `reviewer_actor`, `latest_actor`
- 最小执行现场：`blocked_by`, `next_step`, `flow_status`, `updated_at`
- 最小事件审计：`flow_events`

### 5.2 本地 store 不允许承载的内容

SQLite handoff store 不允许承载：

- issue 正文
- PR 正文
- Project item JSON
- report / plan / audit 全文
- review comment 全量镜像
- agent 对话全文
- `.agent/context/task.md` 的自由文本副本

### 5.3 Handoff 的推荐表达方式

handoff 应优先表达为“责任链 + 指针”，而不是“责任链 + 内容副本”。

推荐读取体验：

1. 先看 `git` 与 GitHub 现场
2. 再看 `flow_state` 中的责任链字段
3. 再根据 `plan_ref / report_ref / audit_ref` 打开正式产物
4. 必要时结合 `.agent/reports/` 中的本地 review 证据和 `SESSION_ID`

## 6. Handoff Command Contract

本阶段定义命令语义边界，不把命令面扩张为新的编辑器驱动存储系统。

### 6.1 命令职责

`vibe handoff plan`

- 更新或确认 `plan_ref`
- 更新 `planner_actor` / `latest_actor`
- 必要时更新 `next_step` / `blocked_by`
- 记录最小事件

`vibe handoff report`

- 更新或确认 `report_ref`
- 更新 `reviewer_actor` / `latest_actor`
- 必要时写入最小 verdict 线索和下一步提示
- 记录最小事件

`vibe handoff audit`

- 更新或确认 `audit_ref`
- 更新 `reviewer_actor` / `latest_actor`
- 必要时写入最小收口信息
- 记录最小事件

### 6.2 命令不负责的事

handoff command 不负责：

- 打开 JSON 文件进行正文编辑
- 在 SQLite 中维护多条 `content` item 正文
- 维护 JSON 与 SQLite 的双向同步时间戳仲裁
- 存储 planning 讨论全文或 review 全文

## 7. `task.md` Reduced Role

`.agent/context/task.md` 在 v3 中降级为 workflow 辅助索引。

### 7.1 允许记录

- 当前 workflow 的 task list
- 当前轮执行中的 findings
- follow-up issue 是否已发
- 当前阶段的最终结论
- 临时 blocker 与建议的下一步
- 便于下一位 agent 快速进入现场的关键文件提示

### 7.2 不允许记录

- 可替代 SQLite handoff store 的正式责任链
- 与 `issue / pr / git` 冲突的阶段事实
- 可替代 `plan_ref / report_ref / audit_ref` 的正式产物正文
- 任何“通常可视为最新事实副本”的镜像内容

### 7.3 读取规则

读取顺序必须遵循：

1. 先核查 `git` 与 GitHub 现场
2. 再读取 SQLite handoff store
3. 最后把 `.agent/context/task.md` 当作补充线索

## 8. Review Report And Session Evidence

`.agent/reports/pre-push-review-*.md` 在 v3 中的角色是临时证据层。

允许把以下信息作为 handoff 线索使用：

- report 文件路径
- report verdict
- risk score
- 关键 finding 摘要
- `SESSION_ID`

约束：

- `SESSION_ID` 只作为会话线索，不是共享真源字段的替代品
- report 只作证据入口，不复制全文到 SQLite
- 若 report 与 issue / PR / git 现场不一致，以现场为准
- 若 report 中有高价值结论，应通过正式文档引用、issue comment 或 PR comment 进入主链，而不是靠本地缓存长期保存

## 9. Cutover Meaning

本阶段所说的 cutover，不是：

- `bin/vibe` 默认入口立即切到 `vibe3`
- 引入 `vibe3_enabled` 开关
- 建立一套 `handoff.md` 或 `plan.json` 的替代存储

本阶段所说的 cutover，指的是：

- v3 handoff 的真相模型已经稳定
- `.agent/context/task.md` 的降级角色已经明确
- review report / `SESSION_ID` 已被识别为合法证据指针
- 后续执行 agent 可以在不发明新存储层的前提下继续补实现

## 10. Success Criteria

### 10.1 Concept Acceptance

- [ ] `repo issue -> pr` 主链和本地 handoff store 的职责边界写清
- [ ] SQLite 只存责任链与引用、不存正文的约束写清
- [ ] `.agent/context/task.md` 的降级角色写清
- [ ] review report 与 `SESSION_ID` 的证据角色写清
- [ ] cutover readiness 的含义写清

### 10.2 Implementation Readiness

- [ ] 继续实现 handoff command 时，不再以 `JSON <-> SQLite` 双向同步为前提
- [ ] 继续实现 handoff command 时，不再以 `handoff_items.content` 为主模型
- [ ] 后续执行者能从本文件明确看到当前实现分叉与 blocker

### 10.3 Non-Goals Confirmed

- [ ] 本阶段不新增第二套正文型本地存储
- [ ] 本阶段不要求切换默认 CLI 入口
- [ ] 本阶段不要求 `pr show` 立刻消费本地 report

## 11. Follow-up Work

本阶段完成后，后续实现应拆成独立任务：

1. 统一 `flow_status` / `issue_role` / `flow_events.event_type` 的标准与实现
2. 设计 pointer-first 的 `handoff command` 写入协议
3. 设计 `pr show` 如何消费 `.agent/reports/` 中的本地证据
4. 单独设计 `bin/vibe` 到 `vibe3` 的 cutover 策略

## 12. Handoff For Next Executor

- [ ] 不要再实现 `JSON <-> SQLite` 双向同步
- [ ] 不要新增以 `content` 为核心的 handoff 正文表
- [ ] 先统一状态枚举和事件命名，再继续 handoff command
- [ ] 若需要扩展 store，优先扩展“引用/证据指针”，不要扩展“正文缓存”
