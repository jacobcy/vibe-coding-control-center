---
document_type: implementation-guide
title: Vibe 3.0 - Architecture Design
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-15
related_docs:
  - docs/v3/plans/v3-rewrite-plan.md
  - docs/v3/implementation/03-coding-standards.md
  - .agent/rules/python-standards.md
---

# Vibe 3.0 - 架构设计

本文档定义 Vibe 3.0 的架构设计。

---

## 目录结构 (强制)

```
scripts/python/vibe3/
├── cli.py                    # Typer 入口 (< 50 行)
├── commands/                 # 命令调度层 (每个文件 < 100 行)
├── services/                 # 业务逻辑层 (每个文件 < 300 行)
├── clients/                  # 外部依赖封装 (Protocol 接口)
├── models/                   # Pydantic 数据模型
├── ui/                       # 展示层 (Rich)
└── config/                   # 配置模块
```

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

### Layer 1: CLI (cli.py)
- **职责**：创建 Typer app，注册子命令。
- **要求**：禁止包含任何业务逻辑，代码量 < 50 行。

### Layer 2: Commands (commands/)
- **职责**：定义命令参数，参数验证（Pydantic），格式化输出（Rich）。
- **要求**：禁止直接调用 subprocess 或操作数据库，每个文件 < 100 行。

### Layer 3: Services (services/)
- **职责**：业务逻辑编排，调用 Client。
- **要求**：禁止直接 I/O 或 UI 逻辑，每个文件 < 300 行。

### Layer 4: Clients (clients/)
- **职责**：封装外部系统（Git, GitHub, SQLite）。
- **要求**：必须提供 Protocol 接口，支持单元测试 Mock。

### Layer 5: Models (models/)
- **职责**：Pydantic 数据验证模型。
- **要求**：必须带有完整类型注解。

---

## 依赖流向

```
CLI → Commands → Services → Clients → Models
                ↓
                UI
```

- **禁止反向依赖**：高层不依赖低层具体实现。
- **Client 隔离**：只有 Client 层允许执行外部系统调用（subprocess/SQL）。

---

## 模块职责总结

| 层级 | 目录 | 职责 | 允许调用 | 禁止调用 |
|------|------|------|---------|---------|
| CLI | cli.py | 参数解析 | Commands, Models, UI | Services, Clients |
| Commands | commands/ | 参数验证 | Services, Models, UI | Clients |
| Services | services/ | 业务逻辑 | Clients, Models | Commands, UI |
| Clients | clients/ | 外部封装 | Models | Commands, Services |
| Models | models/ | 数据模型 | 无 | 所有层 |
| UI | ui/ | 输出展示 | Models | Services, Clients |

---

## 参考文档

- **[03-coding-standards.md](03-coding-standards.md)** - 编码标准
- **[05-logging.md](05-logging.md)** - 日志规范
- **[06-error-handling.md](06-error-handling.md)** - 异常处理
- **[.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)** - Python 标准

---

**维护者**：Vibe Team
**最后更新**：2026-03-15