# PRD: Agent Governance

## 1. Overview

本需求为仓库引入一套轻量 agent 治理机制，用来约束无人值守 agent 的执行行为，并周期性巡检仓库状态与流程卫生。

本需求不重造外部 agent，也不试图把所有治理能力塞进一个入口。治理能力拆成两类：

1. **AutoHarness**
   不是静态拦截器，而是一个可追踪、可分析、可沉淀、可提升的约束学习机制，只针对 autonomous agent。
2. **Supervisor**
   周期性巡检与报告，面向仓库状态、流程一致性和文档支撑。

## 2. Problem

当前仓库已有大量规则和工作流约束，但主要分布在文档、skill 和人工流程中。对于 unattended agent，现有约束仍然偏认知性而非执行性，存在四个问题：

1. agent 运行时可能越过项目边界，例如跨 worktree、直接写共享真源、执行未授权 git 动作
2. 仓库卫生缺少持续巡检，例如 PR 文档支撑缺失、分支清理拖延、handoff 与现场漂移
3. 缺少对 agent 实际操作的结构化记录，导致无法回答“到底哪里做错了、哪里误伤了、哪里应该优化”
4. 缺少把 runtime 症状提升为仓库层 finding 的机制，导致语义冲突、设计缺口和真实 bug 难以沉淀
5. 规则很多，但缺少一套轻量声明式真源来承载治理对象、记录契约和检查结果

## 3. Goals

- 为 autonomous agent 提供可执行且可学习的治理边界，而不只靠 prompt 提醒
- 为仓库提供周期性治理审计，持续发现漂移、脏状态和文档缺口
- 打通 flow 事件、handoff findings 与 agent 具体操作，形成可回顾的治理证据链
- 让 AutoHarness 学会发现并沉淀仓库自身的问题，包括错误语义、设计缺口和代码 bug
- 让 `flow done` 成为一次回顾和沉淀节点，而不只是结束动作
- 保持轻量：声明式 YAML 为主，解释器极薄
- 保持单一职责：每条 policy / check 只聚焦一个点
- 保持人类主导：人类可以 override，agent 不可以

## 4. Non-Goals

- 不实现通用规则引擎
- 不修改外部 `codeagent-wrapper` 本体
- 不把所有治理判断变成大型 AST/LLM 平台
- 不把所有 human-in-the-loop 协作场景都改造成硬阻断
- 不把 AutoHarness 简化为一次性写死的 blocker 表

## 5. Users and Modes

### A. Human + Interactive Agent

- 场景：Codex/Claude 与人类共同协作
- 约束方式：提醒、告警、确认
- 不做强制改写和静默阻断

### B. Autonomous Agent

- 场景：通过 `codeagent-wrapper` 或其调用链启动的 unattended 执行
- 约束方式：最小运行时 decision + trace record + retrospective learning
- 必须遵守仓库治理 policy

## 6. Scope

### In Scope

#### AutoHarness

- 基于 `.agent/governance/policies/*.yaml` 定义稳定边界、trace 契约与评估指标
- 在 `codeagent-wrapper` 调用边界增加极薄 runtime harness
- 把 runtime decisions 写入 flow event timeline
- 把高价值 trace 提升为 handoff findings
- 把 runtime 发现升级为多类型 finding，而不只局限于行为违规
- 为 harness refinement 提供 replay corpus
- 把 `flow done` 作为 harness retrospective 节点

#### Supervisor

- 基于 `.agent/governance/supervisors/*.yaml` 定义周期性 check
- 本地可运行，GitHub Actions 可定时运行
- 首批检查：
  - PR 是否有 plan/spec/doc 支撑
  - 本地/远程分支清理状态
  - handoff 与 git / shared truth 漂移
  - glossary / governance 语义冲突

### Out of Scope

- 所有规则的自动修复
- 外部 agent CLI 的内核修改
- 复杂权限系统或多租户治理平台

## 7. Product Shape

### 7.1 Governance Source

治理真源位于：

- `.agent/governance/policies/`
- `.agent/governance/supervisors/`

这是治理声明层，不是具体执行器。

### 7.2 Runtime Shape

AutoHarness 的执行入口应该位于 repo 自己控制的调用边界，而不是外部 wrapper 内部。

推荐路径：

`vibe run/review` -> thin runtime harness -> decision + trace -> `codeagent-wrapper`

### 7.3 Learning Shape

AutoHarness 的核心不是 block，而是学习闭环。

推荐路径：

`agent action` -> `trace` -> `flow event` -> `handoff finding` -> `retrospective` -> `harness refinement` -> `replay evaluation`

finding 不只包含行为违规，也可以包含：

- 语义冲突
- 设计缺口
- 契约漂移
- 疑似 bug
- 低质量 rewrite 模式

### 7.4 Audit Shape

Supervisor 的执行入口应该是本地 CLI + GitHub Actions schedule 共用的同一套 check runner。

推荐路径：

`CLI or GitHub Actions` -> supervisor runner -> per-check evaluation -> report / issue / comment

## 8. Success Criteria

- autonomous agent 运行链路中可以输出结构化 trace
- flow timeline 中可以看到 harness trace evidence
- handoff 中可以沉淀高价值 harness findings
- finding 可以区分 agent 行为问题与仓库本身问题
- 至少一轮 harness refinement 可以基于 replay 样本进行比较
- supervisor 可以按 YAML 定义执行至少 3 条独立 check
- GitHub Actions 可按 schedule 运行 supervisor
- 报告格式统一，可追溯到具体 evidence

## 9. Risks

### 风险 1：外部 wrapper 不暴露足够的硬拦截能力

缓解：
- 第一阶段通过 repo-owned adapter 落地，而不是改外部 wrapper
- 先做 runtime trace 与最小决策，不做深度内核拦截

### 风险 2：治理规则膨胀成“大而全系统”

缓解：
- 每条 rule / check 只聚焦一个点
- schema 固定，解释器极薄
- 优先增加规则，不优先增加框架复杂度

### 风险 3：只记录不沉淀，最终无法学习

缓解：
- 区分 raw trace 与 promoted finding
- 在 `flow done` 和 supervisor 中加入 retrospective

### 风险 4：human 与 agent 规则混淆

缓解：
- schema 显式区分 `subject` 与 `mode`
- advisory / confirm 与 rewrite / block 分开建模

## 10. Deliverables

1. `.agent/governance/` 目录下的声明式治理真源
2. AutoHarness 实现计划
3. Supervisor 实现计划
4. 后续对应的 CLI / service / workflow 落地
