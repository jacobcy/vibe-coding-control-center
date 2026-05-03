---
document_type: implementation-index
title: Vibe 3.0 基础设施层与技术标准
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-17
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/v3/handoff/v3-rewrite-plan.md
  - .agent/rules/python-standards.md
purpose: Phase 1 基础设施层的核心文档，包含架构设计、编码标准、测试标准等技术规范
---

# Vibe 3.0 基础设施层与技术标准

> **定位**: 本目录是 **Phase 1（Infrastructure）的核心实施文档**，包含所有技术标准和实施规范。
>
> **标准真源**:
> - 数据库字段定义见 [handoff-store-standard.md](../../standards/v3/handoff-store-standard.md)
> - GitHub 远端调用见 [github-remote-call-standard.md](../../standards/v3/github-remote-call-standard.md)

---

## Phase 1 基础设施层目标

建立统一的基础架构，确保代码质量和可维护性，包括：

- ✅ **目录结构** - 按照 02-architecture.md 创建所有目录
- ✅ **异常体系** - 统一的 VibeError 层级
- ✅ **日志系统** - Agent-Centric Logging（loguru + logger.bind()）
- ✅ **配置管理** - 配置加载、优先级、验证
- ✅ **Client 隔离** - 所有外部调用封装在 clients/，提供 Protocol 接口
- ✅ **测试标准** - 分层测试，覆盖率要求
- ✅ **编码标准** - 类型注解、复杂度控制、最佳实践
- ✅ **命令参数标准** - 统一参数规范、追踪、输出格式

---

## 核心规范（必读）

按以下顺序阅读核心文档以了解 Vibe 3.0 的构建标准：

1. **[数据标准](01-data-standard.md)** - 架构澄清、真源层级、错误示例（必读 🔴）
2. **[架构设计](02-architecture.md)** - 目录结构、分层职责与技术栈约束（必读 🔴）
3. **[编码标准](03-coding-standards.md)** - 类型注解、复杂度控制与最佳实践（必读 🔴）
4. **[测试标准](04-test-standards.md)** - 测试分层、覆盖率要求、Mock 规范（必读 🔴）
5. **[日志系统](05-logging.md)** - 面向 Agent 的结构化日志规范（必读 🔴）
6. **[异常处理](06-error-handling.md)** - 异常层级、统一捕获实现指南（必读 🔴）
7. **[命令参数标准](07-command-standards.md)** - 统一参数规范、追踪、输出格式（必读 🔴）
8. **[命令参数快速参考](08-command-quick-ref.md)** - 核心参数速查表（推荐 📖）

---

## 核心规范 (真源)

| 文档 | 职责 | 优先级 |
|------|------|--------|
| [01-data-standard.md](01-data-standard.md) | 数据架构澄清、gh CLI 真源、错误示例 | 🔴 必读 |
| [02-architecture.md](02-architecture.md) | 架构设计原则、分层职责、禁止使用的依赖 | 🔴 必读 |
| [03-coding-standards.md](03-coding-standards.md) | 编码风格、复杂度限制、类型检查 | 🔴 必读 |
| [04-test-standards.md](04-test-standards.md) | 测试分层、覆盖率要求、Mock 规范 | 🔴 必读 |
| [05-logging.md](05-logging.md) | Agent 友好的日志字段绑定、DEBUG 格式标准 | 🔴 必读 |
| [06-error-handling.md](06-error-handling.md) | 异常类定义与 CLI 层统一捕获 | 🔴 必读 |
| [07-command-standards.md](07-command-standards.md) | 统一参数规范、追踪、输出格式、交互确认 | 🔴 必读 |
| [08-command-quick-ref.md](08-command-quick-ref.md) | 核心参数速查表 | 📖 推荐 |

---

## 验收标准

Phase 1 已完成，满足以下标准：

- ✅ 所有命令包含核心参数集（`--trace`, `-v`, `--json`, `-y`）
- ✅ 所有异常继承 VibeError
- ✅ 日志系统支持 verbose 参数（0=ERROR, 1=INFO, 2=DEBUG）
- ✅ 所有外部调用在 clients/ 中封装
- ✅ 测试覆盖核心功能（Services 层关键路径已测试）
- ✅ 所有公共函数包含类型注解
- ✅ 所有文件符合规模限制（CLI < 50 行，Commands < 150 行，Services < 300 行）

---

## 实施原则

### ✅ 必须做

1. **Agent 消费适配**：日志必须包含语义上下文（详见 05-logging.md）
2. **强类型约束**：所有公共函数必须带有类型注解（详见 03-coding-standards.md）
3. **职责分离**：严格遵守 5 层架构，逻辑必须下沉到 Service（详见 02-architecture.md）
4. **测试先行**：Services 层测试覆盖率 >= 80%（详见 04-test-standards.md）

### ❌ 不做

1. **重复记录**：不要在多个文档中定义相同的规范，以本目录文档为真源
2. **自由发挥**：禁止引入规范之外的第三方依赖
3. **反向依赖**：高层不得依赖低层具体实现
4. **复杂度超标**：嵌套 > 3 层、函数 > 100 行、文件 > 300 行必须重构

---

## 与其他阶段的关系

### Phase 1（当前）→ Phase 2（Trace）

Phase 1 建立的基础设施为 Phase 2 提供支撑：
- **日志系统** → Phase 2 的追踪输出依赖日志系统
- **异常体系** → Phase 2 需要捕获和记录异常
- **命令参数标准** → Phase 2 实现 `--trace` 参数

### Phase 1（当前）→ Phase 3（Handoff）

Phase 1 的架构设计支持 Phase 3 的责任链：
- **架构分层** → Phase 3 在 Services 层实现 HandoffService
- **Client 隔离** → Phase 3 实现 StoreClient 封装 SQLite
- **测试标准** → Phase 3 需要测试责任链记录

### Phase 1（当前）→ Phase 4（Orchestra）

Phase 1 的基础设施为 Phase 4 提供扩展能力：
- **日志系统** → Phase 4 的记录追踪依赖日志系统
- **配置管理** → Phase 4 可能需要配置自动编排参数
- **Client 隔离** → Phase 4 可能需要新的 Client（如 TaskQueueClient）

---

## 快速导航

| 文档 | 职责 | 优先级 | 关键词 |
|------|------|--------|--------|
| [01-data-standard.md](01-data-standard.md) | 数据架构、真源定义 | 🔴 必读 | 真源、依赖流向、配置优先级 |
| [02-architecture.md](02-architecture.md) | 架构设计、目录结构 | 🔴 必读 | 分层职责、Client 隔离、Protocol |
| [03-coding-standards.md](03-coding-standards.md) | 编码风格、复杂度控制 | 🔴 必读 | 类型注解、复杂度限制、Pythonic |
| [04-test-standards.md](04-test-standards.md) | 测试分层、覆盖率 | 🔴 必读 | pytest、Mock、覆盖率 >= 80% |
| [05-logging.md](05-logging.md) | Agent 友好日志 | 🔴 必读 | logger.bind()、语义字段、DEBUG 格式 |
| [06-error-handling.md](06-error-handling.md) | 异常层级、统一捕获 | 🔴 必读 | VibeError、UserError、SystemError |
| [07-command-standards.md](07-command-standards.md) | 统一参数规范 | 🔴 必读 | --trace、-v、--json、-y |
| [08-command-quick-ref.md](08-command-quick-ref.md) | 参数速查表 | 📖 推荐 | 快速参考、常用组合 |

---

**维护者**：Vibe Team
**最后更新**：2026-03-17
**相关阶段**：Phase 1 - Infrastructure