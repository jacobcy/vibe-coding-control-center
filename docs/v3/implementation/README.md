---
document_type: implementation-index
title: Vibe 3.0 Implementation Documentation Index
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
  - .agent/rules/python-standards.md
---

# Vibe 3.0 实施文档索引

## 快速开始

**新手指南**：请按以下顺序阅读核心文档以了解 Vibe 3.0 的构建标准：

1. **[架构设计](02-architecture.md)** - 目录结构、分层职责与技术栈约束（必读 🔴）
2. **[编码标准](03-coding-standards.md)** - 类型注解、复杂度控制与错误处理规范（必读 🔴）
3. **[日志系统](05-logging.md)** - 面向 Agent 的结构化日志规范（必读 🔴）
4. **[异常处理](06-error-handling.md)** - 异常层级、统一捕获实现指南

---

## 核心规范 (真源)

| 文档 | 职责 | 优先级 |
|------|------|--------|
| [02-architecture.md](02-architecture.md) | 架构设计原则、分层职责、禁止使用的依赖 | 🔴 必读 |
| [03-coding-standards.md](03-coding-standards.md) | 编码风格、复杂度限制、类型检查、测试要求 | 🔴 必读 |
| [05-logging.md](05-logging.md) | Agent 友好的日志字段绑定、DEBUG 格式标准 | 🔴 必读 |
| [06-error-handling.md](06-error-handling.md) | 异常类定义与 CLI 层统一捕获 | 🔴 必读 |

---

## 实施原则

### ✅ 必须做
1. **Agent 消费适配**：日志必须包含语义上下文（详见 05）。
2. **强类型约束**：所有公共函数必须带有类型注解（详见 03）。
3. **职责分离**：严格遵守 5 层架构，逻辑必须下沉到 Service（详见 02）。

### ❌ 不做
1. **重复记录**：不要在多个文档中定义相同的规范，以本目录文档为真源。
2. **自由发挥**：禁止引入规范之外的第三方依赖。

---

## 归档文档

以下文档已整合至上述核心规范或已完成，仅供历史参考：
- `_archived-00-skeleton-setup.md`
- `_archived-01-config-management.md`
- `_archived-04-cli-design.md`
- `_archived-07-testing-requirements.md`
- `_archived-08-implementation-checklist.md`

---

**最后更新**：2026-03-15
**维护者**：Vibe Team