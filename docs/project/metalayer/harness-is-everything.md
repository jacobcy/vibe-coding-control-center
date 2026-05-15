---
document_type: theory
title: Harness 8 层理论框架
status: reference
scope: meta-layer-design
author: External
source: AI Engineering Community
related_docs:
  - README.md
---

# The Harness is Everything

> "The Harness is Everything" — 模型（Model）只是大脑，而 Harness 是它的感官、肢体、工具包和实验室。

本文档描述构建顶级 AI Agent 系统时，Harness 的 8 个核心层级。

## 1. 运行时（Runtime）— 生存空间

AI 需要一个"身体"来执行代码、访问文件系统。

- **核心功能**：提供实体环境（Docker 容器、虚拟机、远程服务器）
- **为什么重要**：没有运行时，AI 只能"谈论"编程；有了运行时，才能真正"编写并运行"代码

## 2. 编排（Orchestration）— 思维导图

AI 面对复杂任务时容易"断片"或陷入循环。

- **核心功能**：将大目标拆解为小步骤（Plan-Act-Check）
- **为什么重要**：解决长程任务的逻辑连贯性，防止模型迷失方向

## 3. 工具化（Tooling）— 外部感官与肢体

AI 与物理/数字世界交互的接口。

- **核心功能**：搜索引擎、数据库读写、GitHub 提交、运行测试、Slack 通知等
- **为什么重要**：补足模型的知识边界（实时数据）和能力边界（操作软件）

## 4. 记忆（Memory）— 持久化上下文

模型原生的"上下文窗口"是昂贵且易忘的。

- **核心功能**：
  - 短期记忆：当前对话历史、最近操作日志
  - 长期记忆：RAG、向量数据库存储项目经验、技术规范、历史决策
- **为什么重要**：让 AI 像老员工一样"记得"历史决策

## 5. 策略（Policy）— 安全红线与行为准则

AI 拥有工具后，需要限制防止删库跑路或泄露隐私。

- **核心功能**：定义哪些文件不能碰、哪些 API 需要人类确认、Token 上限
- **为什么重要**：将 AI 从"实验室玩具"推向"企业级生产"的最后一道防线

## 6. 沙箱（Sandboxing）— 隔离保护层

Harness 中最硬核的技术部分。

- **核心功能**：确保 AI 执行的代码在受限、不可逃逸的环境中
- **为什么重要**：没有完善的沙箱，赋予 AI 运行代码的权限就是自杀

## 7. 验证（Verification）— 质量守门员

AI 经常会一本正经地胡说八道（幻觉）。

- **核心功能**：
  - 静态检查：Lint 检查语法错误
  - 动态检查：自动运行测试用例
  - 自我批评：让另一个模型实例 Review 结果
- **为什么重要**：让系统具备"自我修正"能力

## 8. 观测（Observability）— 黑盒透明化

当 AI 连续操作了 100 步后，人类必须知道它干了什么。

- **核心功能**：日志追踪（Tracing）、成本统计、推理路径可视化
- **为什么重要**：调试 AI 比调试传统程序难得多，观测性是人类信任 AI 系统的基础

---

## 总结

AI 工程化的未来，不再是追求模型参数从 1T 到 10T，而是如何把这 8 层 Harness 磨练得严丝合缝。

## 与 Vibe Center 的对应

| Harness 层级 | Vibe Center 实现 |
|-------------|-----------------|
| Runtime | worktree + tmux |
| Orchestration | supervisor/ + roles/ |
| Tooling | `vibe3` CLI commands |
| Memory | `claude-memory` MCP + handoff.db |
| Policy | `.claude/rules/` + `.agent/policies/` |
| Sandboxing | worktree 隔离 |
| Verification | `uv run pytest` + `uv run mypy` |
| Observability | `vibe3 flow show` timeline |
