# Meta Layer 设计文档

> **状态**: 设计阶段（未实现）
> **关联项目**: Vibe Center - 作为可选的增强层

## 概述

Meta Layer 是一个独立服务，用于为 AI Agent 提供：
- **上下文注入** - Git 状态、最近文件、错误信息
- **经验记忆** - 从执行过程中自动学习 skill
- **事件追踪** - 记录 tool/test/user 行为

## 文档索引

### 1. 理论基础
- [harness-is-everything.md](harness-is-everything.md) - Harness 8 层理论框架

### 2. 产品需求
- [metalayer-prd.md](metalayer-prd.md) - Meta Layer 完整 PRD + 参考实现代码

### 3. 设计约束
- [metaskill-simple-spec.md](metaskill-simple-spec.md) - 极简设计原则（强制约束）

### 4. 集成接口
- [harness-integration.md](harness-integration.md) - Harness 向 Meta Layer 上报事件

### 5. 技术架构（可选）
- [metaclaw-hybrid-architecture.md](metaclaw-hybrid-architecture.md) - 云端+本地 LoRA 混合架构

## 与 Vibe Center 的关系

### 已实现的功能

| Meta Layer 功能 | Vibe Center 对应 | 状态 |
|-----------------|------------------|------|
| 事件记录 | `handoff.db` event system | ✅ 已实现 |
| 经验记忆 | `claude-memory` MCP server | ✅ 已实现 |
| 上下文注入 | `.agent/policies/` + `config/` | ✅ 已实现 |
| 工具执行追踪 | Flow/Task timeline | ✅ 已实现 |

### Meta Layer 的定位

Meta Layer 可以作为 Vibe Center 的**增强层**：
- 提供独立服务化的记忆系统
- 支持跨项目经验共享
- 可作为未来架构演进的参考

### 实施优先级

当前 Vibe Center 的内部机制已覆盖 Meta Layer 核心功能。
Meta Layer 作为独立服务的设计保留，供未来架构演进参考。

## 设计原则（来自 metaskill-simple-spec）

```
1. 不做智能判断
2. 不做复杂筛选
3. 不做训练
4. 一切保持可解释、可 debug
```

## 核心流程

```
记录 → 总结 → 注入（少量）
```

## 参考

- [Anthropic Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- [Claude Code Memory System](../../references/claude-code-memory.md)
