---
document_type: standard
title: Vibe3 No-Op Gate Boundary Standard
status: active
scope: project-wide
authority:
  - vibe3-noop-gate
  - orchestra-business-boundary
  - manager-decision-boundary
author: GPT-5 Codex
created: 2026-04-17
last_updated: 2026-04-17
related_docs:
  - docs/standards/vibe3-state-sync-standard.md
  - docs/standards/vibe3-orchestra-runtime-standard.md
  - docs/standards/vibe3-architecture-convergence-standard.md
  - supervisor/manager.md
  - config/settings.yaml
---

# Vibe3 No-Op Gate Boundary Standard

本文档定义当前 Vibe3 / Orchestra / Manager 链路的核心业务边界：

- 系统默认只做 `gate / block / fail / dispatch`
- 正常业务决策默认由 agent，尤其是 manager，负责
- 代码层不应偷偷替 agent 决定下一业务状态

本文档的目标不是描述理想架构，而是给当前调试中的 agent 一个稳定提醒：
**如果系统再次把业务状态推进写回代码层，极易重新引入死循环。**

## 1. 当前业务原则

当前主原则是：

- `manager` 负责正常业务判断
- `plan / run / review` 负责产生 authoritative refs
- orchestra 负责观察、调度、容量和 no-op 保护
- 系统在“没有进展”时可以 `block`，在“执行报错”时可以 `fail`
- 系统默认不应因为“看起来下一步是什么”就直接改状态

换句话说：

- **正常推进** 是 agent 决策
- **断链保护** 是系统决策

这是当前实现的真实意图。

## 2. 这样做的好处

### 2.1 代码层不背复杂业务逻辑

如果把 `handoff -> in-progress -> review -> merge-ready -> done` 的业务判断全部写成 if/else：

- prompt 和代码会各自维护一套状态机
- 修改业务规则时需要同时改 supervisor 文案和代码
- debug 时很难判断“是 agent 判断错了，还是代码写死了”

保持 no-op gate 后，代码层只需要处理：

- authoritative ref 是否缺失
- 当前轮是否完全没有推进
- session / capacity / dispatch 是否健康

这能明显降低 orchestration 层的认知负担。

### 2.2 manager 仍然是业务 owner

当前 [supervisor/manager.md](/Users/jacobcy/src/vibe-center/wt-claude-v3/supervisor/manager.md) 明确把 manager 定义为单 issue 的 `Issue Owner`。

这样做的收益是：

- 业务判断集中在一个角色上
- 复杂的“是否可信”“是否应该重跑”“是否该直接 block”留给 manager
- 代码层只做最小保护，不替 manager 提前做结论

### 2.3 no-op 失败会显性暴露

当前 `plan / run / review` 的 role sync spec 已改成：

- 缺 ref 就 block
- 报错就 fail
- 不再自动 success-handler 推进到 `handoff`

这能把“agent 没按约定执行”暴露为真实断链，而不是被系统自动补平后继续把错误带到下一阶段。

## 3. 这样做的坏处

### 3.1 agent 一旦不执行，链路会直接断

这不是 bug，而是当前设计的直接代价：

- manager 不改状态，系统就会 block
- planner / executor / reviewer 不登记 authoritative ref，系统就会 block
- review 结论模糊，manager 就必须自己判断，否则也会卡住

也就是说，这个架构对 prompt 质量、执行纪律和可观测性要求非常高。

- **正确**: 基于人类命令或 agent prompt 修改当前 flow 对应的 issue 标签
- **错误**: 修改代码实现自动化的标签处理逻辑

`IssueFailed` / `IssueBlocked` 的 handler 职责是记录失败/阻塞状态，不是做业务决策。无论哪个角色触发，handler 的行为一致：记录状态、写 comment、设置 label。不需要也不应该根据角色做差异化处理。

### 3.2 `manager` 的 no-op gate 仍然是强业务约束

[src/vibe3/execution/gates.py](/Users/jacobcy/src/vibe-center/wt-claude-v3/src/vibe3/execution/gates.py:11) 的 `block_if_manager_noop()` 会强制要求：

- `state/ready`
- `state/handoff`

这两条 manager 路径本轮必须离开当前 state，否则直接 block。

这条不是坏逻辑，但它是**强业务约束**，不是单纯资源保护。

因此它必须始终与 [supervisor/manager.md](/Users/jacobcy/src/vibe-center/wt-claude-v3/supervisor/manager.md) 和 `vibe3-state-sync-standard.md` 保持一致。

### 3.3 人工恢复默认回到 `handoff`

[src/vibe3/services/task_resume_operations.py](/Users/jacobcy/src/vibe-center/wt-claude-v3/src/vibe3/services/task_resume_operations.py:74) 中，`--label` 的默认恢复目标仍是 `HANDOFF`。

这本身是有意设计，不属于 bug，但说明：

- `handoff` 仍然是系统默认的重新分诊入口
- 一旦 prompt 或代码残留强制 `handoff` 语义，就会很容易在这个状态上形成往返

## 4. 核心原则总结

**label 处理的唯一正确方式**：

- ✅ **正确**: 人类命令或 agent prompt 修改 issue label
- ❌ **错误**: 代码实现自动化的标签处理逻辑

这条原则适用于所有角色（planner / executor / reviewer / manager），不需要区分 agent 角色。系统只做 `gate / block / fail / dispatch`，不替 agent 做业务决策。


