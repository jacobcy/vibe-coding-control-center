# Agent Governance

本目录是 agent 治理的轻量真源。

目标不是重造 agent runtime，而是用最小声明式规则表达两类治理能力：

1. `policy`
   AutoHarness 的稳定边界、trace 契约和评估目标。
   它不是最终学习逻辑本体，而是学习机制的声明式入口。

2. `supervisor`
   周期性巡检，供定时任务或人工触发的审计命令使用。
   关注执行后的仓库卫生、流程一致性、文档支撑和语义冲突。

## 边界

- 本目录只定义治理对象、规则结构、检查点和违规动作。
- 本目录不定义具体 shell 命令实现，不直接取代 `vibe * (shell)`。
- 本目录不直接重述 `SOUL.md`、`CLAUDE.md`、`.agent/rules/*` 中已存在的通用原则。
- 共享状态仍以 `vibe * (shell)` 和 git 现场为准；handoff 不是治理真源。

## 设计原则

- 声明式优先：稳定边界和评估要求放 YAML，执行器保持极薄。
- 单一职责：每条 rule / check 只聚焦一个点，不做万能治理器。
- 人类与 agent 分离：人类可被提示和确认，autonomous agent 进入学习型约束闭环。
- Context first：治理结论必须可追溯到仓库事实、git 现场或远程 API 结果。
- 渐进收敛：先让 trace、finding 和 replay 跑通，再逐步提升 harness。

## 目录

- `policies/`
  - AutoHarness 运行时行为约束
- `supervisors/`
  - 周期性巡检定义

## 与现有真源的关系

- 项目原则：详见 `SOUL.md`
- 硬规则与分层：详见 `CLAUDE.md`
- 旧版轻量约束样式：参考 `.agent/agent-spec.yaml`
- 收敛期治理阈值：参考 `.agent/governance.yaml`

## 当前草案

- `policies/autoharness.yaml`
  - AutoHarness 的稳定边界与学习契约草案
- `supervisors/periodic-audit.yaml`
  - 周期性巡检草案
