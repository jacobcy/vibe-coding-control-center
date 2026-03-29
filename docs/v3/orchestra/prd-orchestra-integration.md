---
document_type: prd
title: "Orchestra 调度器 PRD（MVP + 分阶段路线）"
version: v3-mvp
author: "Kiro"
created: "2026-03-16"
last_updated: "2026-03-29"
related_docs:
  - docs/v3/orchestra/README.md
  - src/vibe3/orchestra/serve.py
  - src/vibe3/orchestra/heartbeat.py
  - src/vibe3/orchestra/services/assignee_dispatch.py
  - src/vibe3/orchestra/services/pr_review_dispatch.py
status: active
---

# Orchestra 调度器 PRD

## 0. 产品目标

Orchestra 的最终目标是支持“无人值守”的 issue 到 PR 自动推进。
但该目标无法一次性完成，本 PRD 采用“主干优先 + 自动化增量”的策略：

1. 本版只交付可运行的最小闭环（MVP）。
2. 复杂编排能力拆分到 follow-up issue 分步实现。
3. 不牺牲主干稳定性，不引入难以回滚的复杂机制。

名词边界（避免误导）：
- 本 PRD 的 self-hosted 指“自托管 webhook 接收 + 本机执行”。
- 本 PRD 不涉及 GitHub Actions self-hosted runner（`runs-on: self-hosted`）。

## 1. 当前已落地能力（2026-03-29）

### 1.1 Self-hosted webhook server（非 Actions runner）

- `vibe3 serve start` 提供 HTTP webhook 接收与 heartbeat 兜底。
- 支持 webhook HMAC 验签。
- heartbeat 默认每 900 秒巡检一次。

### 1.2 Issue assignee 触发

- 事件：`issues/assigned`
- 条件：assignee 命中 `manager_usernames`（默认值可配置）
- 行为：
  - 检查依赖（`blocked by` / `depends on`）
  - 创建或复用 flow
  - 调用 manager 执行链

### 1.3 PR reviewer 触发

- 事件：`pull_request/review_requested`、`pull_request/ready_for_review`
- 条件：requested reviewer 命中 `manager_usernames`
- 行为：触发 `vibe3 review pr <pr_number>`

## 2. 本版范围（MVP）

### 2.1 必须支持

- self-hosted webhook server 稳定运行
- assignee 触发 manager
- reviewer 触发 review
- heartbeat 能兜底重检“当前状态”而不只依赖单次 webhook
- 可通过测试验证核心行为

### 2.2 明确不在本版

- 全量 orchestrator 智能调度（跨 issue 优先级重排与抢占）
- manager 多阶段长事务（plan/run/review 的可恢复编排状态机）
- 复杂队列持久化与失败补偿框架
- 完整监控面板

## 3. 触发与执行模型

### 3.1 输入事件

- `issues/*`（重点是 `assigned`）
- `pull_request/*`（重点是 `review_requested`、`ready_for_review`）
- `issue_comment/*`（`@vibe-manager` ACK）

### 3.2 输出动作

- manager 执行：`vibe3 run ...`（当前最小执行链）
- review 执行：`vibe3 review pr <number>`
- 状态展示：`state/*` label 仅作展示，不作为执行真源

### 3.3 核心执行语义

当 issue 或 pr 事件到达时：

1. webhook 接收并验签
2. orchestration 规则判断（assignee/reviewer 是否命中）
3. 命中 assignee 规则时执行 manager
4. 命中 reviewer 规则时执行 reviewer

### 3.4 心跳职责

- 用于漏事件兜底和当前状态重检
- 不替代 webhook 主路径
- 当前实现可进行“已分配 issue + 依赖状态 + flow 存在性”的最小决策

## 4. 架构边界

### 4.1 Orchestrator（当前版）

- 负责事件接入与最小决策（是否应触发执行）
- 负责并发上限约束（`max_concurrent_flows`）
- 不承担复杂调度策略

### 4.2 Manager（当前版）

- 负责单 issue/flow 的执行触发
- 当前以最小执行链为主
- 后续再升级为可恢复多阶段编排器（plan/run/review 子 agent 协同）

## 5. 风险与缓解

### 5.1 重复触发风险

- 缓解：flow 存在性检查 + 依赖检查 + 心跳幂等策略

### 5.2 webhook 丢失风险

- 缓解：heartbeat 周期重检

### 5.3 主干稳定性风险

- 缓解：MVP 范围内只做低耦合增量，不引入新真源

## 6. 验收标准（本版）

- `vibe3 serve start` 可启动 webhook + heartbeat
- assignee 事件可触发 manager dispatch
- reviewer 事件可触发 `vibe3 review pr`
- 相关单测通过（service/webhook/heartbeat/dispatcher）
- `docs/v3/orchestra/*` 文档语义与代码实现一致

## 7. Follow-up（分阶段）

### Phase A：Orchestrator 决策增强

- 候选 issue 列表构建
- 优先级与依赖的显式决策记录
- 统一入队/出队策略

### Phase B：Manager 执行编排增强

- plan/run/review 子 agent 流程编排
- 失败恢复、重试和状态收敛
- 与 flow/handoff 生命周期一致化

### Phase C：可观测性与治理

- 决策日志与执行指标
- 队列与失败态可视化
- 运维与告警策略
