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
last_updated: 2026-04-18
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
- authoritative ref 只是产出证据，不是代码层自动推进状态的许可

本文档的目标不是描述理想架构，而是给当前调试中的 agent 一个稳定提醒：
**如果系统再次把业务状态推进写回代码层，极易重新引入死循环。**

## 1. 当前业务原则

当前主原则是：

- `manager` 负责正常业务判断
- `plan / run / review` 负责产生 authoritative refs
- orchestra 负责观察、调度、容量和 no-op 保护
- 系统在“没有进展”时可以 `block`，在“执行报错”时可以 `fail`
- 系统默认不应因为“看起来下一步是什么”就直接改状态
- worker 是否离开当前阶段，必须由 worker agent 自己完成；代码层只负责在它没做到时显式 `block`

换句话说：

- **正常推进** 是 agent 决策
- **断链保护** 是系统决策
- **authoritative ref 不是成功推进的替代品**

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
- 不应再用 success-handler 自动推进到 `handoff`

这能把“agent 没按约定执行”暴露为真实断链，而不是被系统自动补平后继续把错误带到下一阶段。

### 2.4 `blocked` 比伪成功更有价值

在当前调试阶段，`blocked` 不是坏结果，反而是更高质量的结果：

- `blocked` 会把 prompt 没按 contract 执行的事实暴露出来
- `blocked` 能形成稳定、可复现、可回放的失败样本
- `blocked` 允许后续针对 prompt / handoff / manager 判断做精确修复

反过来，success gate 会制造一种危险的伪成功：

- worker 没改状态，但代码层替它改了
- 从日志上看链路“跑通了”，实际上 contract 已经失真
- 后续再观察到异常时，已经分不清是 agent 做对了，还是代码替它圆过去了

当前阶段必须优先保留**可诊断失败**，而不是追求表面连续性。

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

### 3.1.1 worker no-op 的正确语义

对 `planner / executor / reviewer` 三类 worker，正确语义必须是：

- 没有产出 authoritative ref → `blocked`
- 产出了 authoritative ref，但**仍停留在原 state** → `blocked`
- 产出了 authoritative ref，且**worker 自己已把 state 改走** → 通过

也就是说：

- `plan_ref` 已有但还在 `state/claimed` → `blocked`
- `report_ref` 已有但还在 `state/in-progress` → `blocked`
- `audit_ref` 已有但还在 `state/review` → `blocked`

如果只做“缺 ref 才 block”，而不做“有 ref 但状态不变也 block”，就会出现最糟糕的死区：

- dispatch predicate 因为 ref 已存在而不再派发
- 系统又因为 ref 已存在而不 block
- issue 长期停留在原 state，形成 silent hang

### 3.2 `manager` 的 no-op gate 仍然是强业务约束

[src/vibe3/execution/gates.py](/Users/jacobcy/src/vibe-center/wt-claude-v3/src/vibe3/execution/gates.py:11) 的 `block_if_manager_noop()` 会强制要求：

- `state/ready`
- `state/handoff`

这两条 manager 路径本轮必须离开当前 state，否则直接 block。

这条不是坏逻辑，但它是**强业务约束**，不是单纯资源保护。

因此它必须始终与 [supervisor/manager.md](/Users/jacobcy/src/vibe-center/wt-claude-v3/supervisor/manager.md) 和 `vibe3-state-sync-standard.md` 保持一致。

### 3.2.1 manager no-op gate 不能被 worker success gate 绕开

manager 的 no-op gate 已经明确要求：

- manager 本轮必须离开 `state/ready` 或 `state/handoff`
- 否则直接 `blocked`

如果 worker 又被代码层偷偷用 success-handler 推到 `handoff`，会带来两个问题：

1. manager 会在一个被代码机械推进过的 scene 上继续做业务判断
2. 真实的 prompt 缺陷会被掩盖，manager 只能消费一个伪正确现场

所以 worker success gate 会直接削弱 manager no-op gate 的诊断价值。

### 3.3 人工恢复默认回到 `handoff`

[src/vibe3/services/task_resume_operations.py](/Users/jacobcy/src/vibe-center/wt-claude-v3/src/vibe3/services/task_resume_operations.py:74) 中，`--label` 的默认恢复目标仍是 `HANDOFF`。

这本身是有意设计，不属于 bug，但说明：

- `handoff` 仍然是系统默认的重新分诊入口
- 一旦 prompt 或代码残留强制 `handoff` 语义，就会很容易在这个状态上形成往返

## 4. Dispatch Predicates 原则

**Orchestra dispatch 只看 label，不看 ref**：

- ✅ **正确**: `state/claimed` → 派发 planner
- ✅ **正确**: `state/in-progress` → 派发 executor
- ✅ **正确**: `state/review` → 派发 reviewer
- ❌ **错误**: 检查 `plan_ref` 存在才派发 executor
- ❌ **错误**: 检查 `report_ref` 存在才派发 reviewer

**Why**: ref 是 agent 的产出，不是 orchestra 的判断条件。底层不应侵入上层业务逻辑。

**当前问题** (不在本 plan scope):

```python
# Executor (run.py:41-43)
dispatch_predicate=lambda fs, live: (
    bool(fs.get("plan_ref")) and not fs.get("report_ref") and not live
)
→ 检查 plan_ref/report_ref 存在性 → 底层业务判断

# Reviewer (review.py:59-61)
dispatch_predicate=lambda fs, live: (
    bool(fs.get("report_ref")) and not fs.get("audit_ref") and not live
)
→ 检查 report_ref/audit_ref 存在性 → 底层业务判断
```

这些问题属于下一个 issue scope，当前 plan 只修 post-sync gate。

## 5. 核心原则总结

**label 处理的唯一正确方式**：

- ✅ **正确**: 人类命令或 agent prompt 修改 issue label
- ❌ **错误**: 代码实现自动化的标签处理逻辑

这条原则适用于所有角色（planner / executor / reviewer / manager），不需要区分 agent 角色。系统只做 `gate / block / fail / dispatch`，不替 agent 做业务决策。

## 6. 明确禁止的反模式

以下方案看起来“能把链路跑通”，但当前一律视为错误方案：

### 6.1 `review 成功后强制回到 handoff`

错误示例：

- reviewer 只要产出 `audit_ref`
- 代码层通过 success handler 自动把 label 改成 `state/handoff`
- manager 再从 `handoff` 阶段接手判断

为什么错误：

- 这等于代码替 reviewer 完成了本该由 agent 自己完成的状态推进
- 会把“reviewer 没按 contract 改状态”的问题掩盖掉
- 会制造“有 ref 即成功”的假象
- 会让系统失去对 prompt 缺陷的观测能力

正确做法：

- reviewer 自己改状态
- reviewer 没改状态，即使已经有 `audit_ref`，也应直接 `blocked`

### 6.2 `有 ref 就视为当前阶段完成`

错误示例：

- `report_ref` 已有，就默认 run 阶段完成
- `audit_ref` 已有，就默认 review 阶段完成

为什么错误：

- authoritative ref 只能证明 worker 产出了某种 artifact
- 不能证明 worker 履行了完整 contract
- contract 还包括：**显式离开当前状态**

### 6.3 用伪正确前推去掩盖 prompt 错误

任何“为了避免卡住，先由代码层把状态推到下一阶段”的修补，都属于高风险反模式。

短期看：

- 队列似乎继续流动
- `task status` 看起来更顺

长期看：

- 系统丢失真实错误信号
- prompt 无法收敛
- manager / governance 只能在被污染的现场上继续判断
- 后续 debug 成本会更高

当前阶段，宁可多 `blocked`，也不要多伪成功。

## 7. 完整闭环：No-Op Gate 与 Resume Task

### 7.1 闭环流程

```
Agent 运行
  ↓
No-Op Gate (post_sync_hook, apply_required_ref_post_sync)
  ├── 三分支判定:
  │   1. ref 缺失 → block
  │   2. ref 存在 + state 不变 → block
  │   3. ref 存在 + state 改变 → 通过
  ↓
block 或 通过
  ↓ (block 时)
人工判断 + resume task
  ├── resume (不带 --label) → 完整重建
  │   删除 worktree / branch / flow / handoff
  │   issue 回到 state/ready，manager 从零开始
  ├── resume --label → 最小修复
  │   只修 label + 清 reason，保留 flow / worktree / refs
  │   issue 回到 state/handoff 或 state/ready
  │   手动指派给原 agent 或下一个 manager
  ↓
Re-dispatch
```

### 7.2 两种 resume 路径的设计意图

| 路径 | flow record | worktree / branch | 适用场景 |
|------|------------|-------------------|---------|
| `resume` (不带 `--label`) | 删除 | 删除 | 完整重建，从 scratch 开始 |
| `resume --label` | 保留（只清 reason） | 保留 | agent 做了工作但 label 没改对 |

`--label` 的场景：agent 实际完成了工作（产出了 ref、代码等），但没能正确修改 issue label，导致被 no-op gate block。此时 flow record 和 worktree 里的工作成果都是有效的，只需要修正 label 就能让 agent 继续推进。

不带 `--label` 的场景：agent 的整个执行现场有问题（分支创建失败、执行报错、工作产出全废），需要从零开始。删除 flow record 防止 stale 数据被下游 dispatch 捡起。

### 7.3 反模式：系统主动检测 flow / ref（已移除）

**以下逻辑已在 2026-04-18 移除，此处记录以防止重新引入。**

#### 反模式描述

在 domain event handler（`flow_lifecycle.py`）中，`_handle_completion_with_ref_gate` 和 `require_authoritative_ref` 主动检查 flow store 中 ref 是否存在，不存在就 block issue。

#### 为什么错误

这条路径**替代了 agent 工作验证**，而非**验证 agent 工作**：

| 维度 | 正确路径 (post_sync_hook) | 错误路径 (domain event handler) |
|------|--------------------------|-------------------------------|
| 触发时机 | agent 实际运行后 | agent 可能从未运行 |
| 执行上下文 | 有 before/after snapshot | 无 snapshot，不知道 agent 是否跑过 |
| 验证对象 | agent 的实际工作产出 | flow store 中的数据状态 |
| 三分支判定 | 完整（缺 ref / 有 ref 未改 state / 通过） | 只有分支 1（缺 ref → block） |
| 架构角色 | 执行后验证 | 主动巡检、替代 agent 判断 |

#### 实际 bug（issue #301）

1. manager 创建分支失败 → issue 进入 state/failed
2. stale flow record 指向不存在的分支
3. 下游 dispatch 基于 stale flow 派发 reviewer
4. reviewer 从未实际运行
5. domain event handler 的 `require_authoritative_ref` 发现无 audit_ref → block
6. `force=True` 覆盖 failed 状态为 blocked
7. 循环往复，每 30 秒一次

根因：系统在**不知道 agent 是否跑过**的情况下，基于 flow store 状态做出了业务判断。

#### 正确做法

ref 验证只在 `apply_required_ref_post_sync`（post_sync_hook）中执行，该路径：
- 由 sync runner 在 agent 实际运行后触发
- 拥有完整的 before/after snapshot 上下文
- 实现三分支 no-op gate 逻辑
- domain event handler 只做日志记录，不做业务判断

## 8. 设计理念：最小干预

### 8.1 核心原则

**系统不主动干预 agent 工作，只做观察和保护。**

具体含义：

- **观察优先于干预**：通过 issue comment、`flow show`、log 实现 agent 工作的可见性
- **保护优先于推进**：no-op gate 只在 agent 没做好时 block，不替 agent 做下一步
- **最小权限**：系统只执行 `gate / block / fail / dispatch`，不做业务决策
- **断链优于伪成功**：宁可卡住暴露问题，也不要自动补平掩盖缺陷

### 8.2 违反最小干预的信号

以下行为表明代码在违反最小干预原则：

- 系统代码主动检查 flow store / ref 是否存在来做业务判断
- 系统代码在 agent 未实际运行的情况下修改 issue 状态
- 系统代码用 `force=True` 覆盖已有的终态（failed / blocked）
- 系统代码在 domain event 路径中执行需要执行上下文的验证逻辑

### 8.3 正确的可见性手段

| 手段 | 用途 | 真源 |
|------|------|------|
| issue comment | agent 产出和状态变更的公开记录 | GitHub issue |
| `vibe3 flow show` | flow / ref / event 的本地查看 | SQLite flow store |
| `vibe3 task status` | 全局编排状态概览 | GitHub + flow |
| orchestra events.log | dispatch 和生命周期事件追踪 | 本地日志 |
| `vibe3 handoff show` | agent 间交接上下文 | handoff store |

这些是**只读的可见性手段**，不是**主动干预的入口**。系统写入 issue comment 是为了记录和通知，不是为了替代 agent 决策。

