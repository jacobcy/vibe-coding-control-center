---
document_type: plan
title: Phase 04 - Handoff & Cutover
status: draft
author: GPT-5 Codex
created: 2026-03-15
last_updated: 2026-03-21
related_docs:
  - docs/v3/handoff/v3-rewrite-plan.md
  - docs/standards/v2/handoff-governance-standard.md
  - docs/standards/v2/git-workflow-standard.md
  - docs/standards/v3/handoff-store-standard.md
---

# Phase 04: Handoff & Cutover

**Goal**: 收敛 v3 阶段的 handoff 真源、降级 `.agent/context/task.md` 为 workflow 辅助索引，并定义进入真正 cutover 前必须满足的交接与证据条件。

## 1. 架构约束

见 [01-command-and-skeleton.md](01-command-and-skeleton.md) §通用架构约束。

本阶段额外固定以下约束：

- `handoff command + handoff store` 是 v3 多 agent 共同维护的交接真源
- `issue -> pr` 是唯一标准交付链
- `.agent/context/task.md` 不再承担 v3 正式 handoff 语义
- 若 handoff 与 `issue / PR / git` 现场冲突，必须修正 handoff

## 2. Context Anchor

本阶段以以下真源为准：

- [handoff-governance-standard.md](../../standards/v2/handoff-governance-standard.md)
- [git-workflow-standard.md](../../standards/v2/git-workflow-standard.md)
- [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md)

必要时再回看：

- [02-flow-task-foundation.md](02-flow-task-foundation.md)
- [03-pr-domain.md](03-pr-domain.md)

## 3. Pre-requisites (Executor Entry)

- [ ] Phase 02 的 flow/task 责任链已经可写入 handoff store
- [ ] Phase 03 的 `issue -> pr` 主链已经可运行
- [ ] `pre-push` 本地 review report 已能落到 `.agent/reports/`
- [ ] review report 中的 `SESSION_ID` 已可作为可提取线索使用

## 4. Truth Model

### 4.1 共同真源

v3 阶段的共同 handoff 真源固定为：

- handoff command
- handoff store（SQLite）

它负责记录：

- 当前 flow 责任链
- `plan / report / audit` ref
- planner / executor / reviewer 署名
- session id
- blockers
- next step

### 4.2 业务事实真源

业务事实固定以以下顺序判定：

1. `git` 现场
2. `issue / PR` 事实
3. handoff store
4. 本地补充索引和临时报告

解释约束：

- handoff store 负责责任链补充，不覆盖业务事实
- `issue -> pr` 是唯一标准交付链
- `task.md`、临时 report、skill 文案都不能凌驾于 `git / issue / PR` 之上

## 5. `task.md` Reduced Role

`.agent/context/task.md` 在 v3 阶段只保留 workflow 辅助索引角色。

允许记录：

- 当前 workflow 的 task list
- 每个 task 运行过程中的 findings
- follow-up issue 是否已发
- 当前阶段的最终结论
- 下一步定位指针

不允许记录：

- 可替代 handoff store 的正式责任链
- 与 `issue / PR / git` 冲突的阶段事实
- 需要多个 agent 共同维护的正式交接状态

写作要求：

- 强调“快速定位问题”而不是“完整复制事实”
- 优先写结论、blocker、follow-up 指针
- 避免把 `task.md` 写成第二套状态数据库

## 6. Handoff Conflict Rule

若下列来源存在冲突：

- handoff store
- `.agent/context/task.md`
- `.agent/reports/*`
- skill handoff 文案

处理顺序固定为：

1. 先核查 `git / issue / PR` 现场
2. 以业务事实为准
3. 修正 handoff store
4. 视需要同步修正 `.agent/context/task.md`

禁止：

- 把 `task.md` 当作 handoff 冲突时的裁决依据
- 因为“只是临时文档”而放弃修正已过时 handoff
- 把 review report 的叙述性内容直接当成交付事实

## 7. Review Report Contract

### 7.1 临时报告位置

本地 review 临时报告放在：

```text
.agent/reports/
```

当前已存在的报告样式：

```text
.agent/reports/pre-push-review-YYYYMMDD-HHMMSS.md
```

### 7.2 可提取字段

本阶段明确承认以下字段已经可作为交接线索使用：

- report path
- risk level
- risk score
- review verdict
- `SESSION_ID`

约束：

- `SESSION_ID` 不再视为“预留空字段”
- handoff 可引用 `SESSION_ID` 与 report path
- handoff 不应复制整段 review 正文

### 7.3 与 handoff 的关系

review report 是临时证据层，不是 handoff 真源。

它的职责是：

- 提供 review 过程留痕
- 为 `pr show` / handoff / follow-up issue 提供输入线索
- 辅助定位是哪一次本地 review 产出了当前结论

它不负责：

- 取代 handoff store
- 取代 PR review evidence
- 直接定义最终 merge 结论

## 8. Cutover Meaning

本阶段的 cutover 不再定义为：

- Markdown 双向同步
- `vibe3 handoff sync`
- 通过 `.git/vibe3_enabled` 切换 `bin/vibe`

这些都属于旧方案，当前不再作为本阶段目标。

本阶段中的 cutover 仅表示：

- v3 的 handoff discipline 已经稳定
- 多 agent 共同维护的责任链已有统一真源
- workflow 辅助索引与正式 handoff 已分层
- 进入默认入口切换前的交接语义已经收敛

## 9. Success Criteria

- [ ] handoff command + handoff store 被明确定义为 v3 共同真源
- [ ] `.agent/context/task.md` 被降级为 workflow task list / findings / follow-up issue / final conclusion 的辅助索引
- [ ] 文档明确写出 `issue -> pr` 是唯一标准交付链
- [ ] 文档明确写出 handoff 冲突必须按 `git / issue / PR` 事实修正
- [ ] 文档明确写出 `.agent/reports/pre-push-review-*.md` 是临时 report 层
- [ ] 文档明确写出 `SESSION_ID` 现在是可提取字段，不再视为空字段
- [ ] Phase 04 不再引用 Markdown 双向同步和 `.git/vibe3_enabled` 切换方案

## 10. Development Notes

### 10.1 需要对齐的入口文档

至少同步以下文档对本阶段的一句话描述：

- `docs/v3/handoff/README.md`
- `docs/v3/handoff/v3-rewrite-plan.md`

对齐目标：

- 不再把 Phase 04 描述成 “SQLite -> Markdown sync”
- 不再把成功标准写成 `handoff.md` 双向一致性

### 10.2 对 skill 的影响

后续需要逐步清理 skill 文案中的旧心智：

- 若 skill 仍把 `.agent/context/task.md` 当主 handoff，应修订
- 若 skill 仍把 handoff 冲突解释成 `task.md` 决定，应修订
- 若 skill 未明确 `issue -> pr` 主链，应补齐

本阶段先收敛文档，不要求一次改完全部 skill。

### 10.3 与 Phase 05 的边界

本阶段只负责：

- handoff 真源与辅助索引分层
- report / session id 作为线索的合法地位
- cutover readiness 语义收敛

本阶段不负责：

- 直接切换 `bin/vibe` 默认入口
- 完成 `pr show` 对本地 report 的消费
- 完成 review prompt 质量优化

这些应作为后续独立任务推进。

## 11. Handoff for Executor 05

- [ ] 按本文件改写后，确认 README / rewrite-plan 的 Phase 04 描述已同步
- [ ] 审计 skill 文案中是否仍把 `task.md` 当正式 handoff
- [ ] 以 `issue -> pr` 主链检查 Phase 05 的验收语言是否仍有旧切换心智
