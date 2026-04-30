---
document_type: implementation-guide
title: Vibe 3.0 - Architecture Design
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-16
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/v3/handoff/v3-rewrite-plan.md
  - docs/v3/infrastructure/03-coding-standards.md
  - .agent/rules/python-standards.md
---

# Vibe 3.0 - 架构设计

本文档定义 Vibe 3.0 的架构设计。

---

## 目录结构 (强制)

```
src/vibe3/
├── cli.py                    # Typer 入口
├── commands/                 # 命令调度层
├── services/                 # 业务逻辑层
├── engine/                   # DAG + flow + state machine
├── runtime/                  # executor + scheduler + dispatcher
├── clients/                  # 外部依赖封装 (Protocol 接口)
├── models/                   # Pydantic 数据模型
├── observability/            # logging + trace + audit
├── exceptions/               # 异常定义
├── ui/                       # 展示层 (Rich)
└── config/                   # 配置模块
```

**代码规模限制**：见 **[03-coding-standards.md](03-coding-standards.md)**

---

## 技术栈与约束 (强制)

### 1. 核心依赖
见 **[03-coding-standards.md](03-coding-standards.md)**。

### 2. 禁止使用的依赖
- ❌ **argparse** (用 typer 替代)
- ❌ **ORM** (SQLAlchemy, peewee)
- ❌ **Web 框架** (Django, Flask, FastAPI)
- ❌ **print()** (用 logger 或 rich)

---

## 分层架构与职责 (强制)

Vibe 3.0 采用 domain-first 架构，收敛为以下六层：

### Layer 1: Server (server/)
- **职责**：HTTP/Webhook 暴露、进程级驱动装配、Runtime 启停。
- **要求**：禁止包含业务判断或角色特定逻辑。

### Layer 2: Runtime (runtime/)
- **职责**：Heartbeat、事件路由、将外部 Observation 翻译并交给 Domain。
- **要求**：不持有角色编排逻辑。

### Layer 3: Domain (domain/)
- **职责**：定义领域事件、处理业务逻辑编排、驱动状态机。
- **要求**：业务语义判断的唯一真源。

### Layer 4: Execution (execution/)
- **职责**：统一执行控制面（Capacity, Lifecycle, Session, Agent Launch）。
- **要求**：所有角色执行（Plan/Run/Review）的唯一启动入口。

### Layer 5: Environment (environment/)
- **职责**：资源原语（Worktree 管理、Tmux Session 隔离）。
- **要求**：不涉及业务状态逻辑。

### Layer 6: Role Adapters (manager/, orchestra/, etc.)
- **职责**：角色特定输入/输出处理、Prompt 渲染。
- **要求**：薄层适配器，不复写执行框架。

---

## 依赖流向

```
Server → Runtime → Domain → Execution → Environment
                            ↓
                      Role Adapters
```

- **禁止反向依赖**：高层不依赖低层具体实现。
- **唯一入口原则**：业务编排必经 Domain，执行启动必经 Execution。

---

## 模块职责总结

| 层级 | 目录 | 职责 | 允许调用 | 禁止调用 |
|------|------|------|---------|---------|
| Server | server/ | 传输与驱动 | Runtime, Models | Domain, Execution |
| Runtime | runtime/ | 调度与路由 | Domain, Models | Environment, Clients |
| Domain | domain/ | 业务编排 | Execution, Models | Server, UI |
| Execution | execution/ | 执行控制 | Environment, Role Adapters, Models | Server, UI |
| Environment | environment/ | 资源原语 | Models | Domain, Execution |
| Role Adapters | manager/ orchestra/ | 角色逻辑 | Models | Runtime, Server |

---

## 参考文档

- **[03-coding-standards.md](03-coding-standards.md)** - 编码标准
- **[05-logging.md](05-logging.md)** - 日志规范
- **[06-error-handling.md](06-error-handling.md)** - 异常处理
- **[.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)** - Python 标准

---

**维护者**：Vibe Team
**最后更新**：2026-03-15