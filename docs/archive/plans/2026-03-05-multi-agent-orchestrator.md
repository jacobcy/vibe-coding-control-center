---
title: "Implement Multi-Agent Orchestrator Loop (Agent of Agents)"
date: "2026-03-05"
---

# 终极闭环管线开发计划 (Multi-Agent Orchestrator Loop)

## 1. 目标
实现 Vibe Center 的终极愿景：基于 Model-Spec-Context (MSC) 范式，统筹 Gemini, Claude 和 Codex，形成从需求提取到编码执行，再到静态审查反馈的“无人值守”自动装配线（Agent of Agents / Super-Orchestrator）。

## 2. 核心模块设计

### 2.1 编排总线 (`lib/flow_pilot.sh` 或 `vibe flow auto`)
创建一个新的核心控制脚本，用来在后台调度 Agent 流转。
- **职责**：驱动跨 Agent 工作流，不涉及任何具体的业务代码，只做发号施令、日志记录与状态机安全流转。

### 2.2 阶段与智能体分工

#### Stage 1: Architect (Gemini/OpenClaw)
- **触发**：读取用户的高阶需求或没有设计细节的 `todo` 任务。
- **操作**：通读整个代码库与核心上下文（`SOUL.md`, `CLAUDE.md`），基于项目架构输出明确到函数的开发草案存入 `docs/plans/<task>.md`。

#### Stage 2: Coder (Claude)
- **触发**：从 Plan Gate 获得具体设计并被分配至对应的工作区（Worktree）。
- **操作**：通过系统命令行直接唤醒：`claude -c -p "$(cat plan.md) + $(cat SOUL.md)" --dangerously-skip-permissions`。
- **约束**：在高度受限的环境下落实代码，拒绝发散与过度重构。跑通基础测试。

#### Stage 3: Auditor (Codex)
- **触发**：执行者 (Claude) 进程结束，代码变更被保存。
- **操作**：执行底座命令 `vibe flow review --local`。
- **副作用 (Feedback Loop)**：如果审查识别出阻塞级缺陷（内存泄漏、测试失败、偏离规范），整理审阅意见，将其重新投喂给 Claude，进行 "Review -> Refactor" 的无人循环，最多重试 N 次。

#### Stage 4: Completer (Human Approver)
- **触发**：Codex 输出全绿。
- **操作**：引擎自动触发 `vibe flow pr` 进行云端托管。人类通过 Terminal 或在通讯软件中输入 LGTM 即可完成合并并发起 `vibe flow done` 清理现场。

## 3. 开发路径 (Execution Steps)

- [ ] 1. 在 `bin/vibe` 与 `lib/flow.sh` 中注册 `auto` (或 `pilot`) 子命令。
- [ ] 2. 编写 `lib/flow_pilot.sh` 核心逻辑引擎（基于 Bash 实现串联状态机）。
- [ ] 3. 编写 `bats` 测试保障执行失败时的熔断机制与安全限制。
- [ ] 4. 提供示例 Prompt Wrapper，在传入开源 CLI 工具前自动拼接好项目的 Guardrails。
