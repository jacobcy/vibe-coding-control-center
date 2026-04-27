# Python Standards (Vibe 3.0 - Project Specific)

本文件定义 Vibe 3.0 项目特定的 Python 实现标准。

通用 Python 最佳实践见：`~/.claude/rules/common/python-standards.md`

---

## 版本与依赖

### Python 版本

- **最低版本**：Python 3.12+
- **类型语法**：使用 Python 3.12+ 类型语法（`str | None` 而非 `Optional[str]`）

### 依赖管理（强制）

**本项目使用 uv 管理依赖和虚拟环境**：

- **配置文件**：`pyproject.toml`（项目根目录）
- **安装依赖**：`uv sync`
- **添加依赖**：`uv add <package>`
- **移除依赖**：`uv remove <package>`
- **运行命令**：`uv run <command>`
- **运行 Python**：`uv run python`（**禁止直接使用 `python` 或 `python3`**）

**禁止**：

- ❌ 使用 `python`、`python3`、`pip`、`pip3` 等命令
- ❌ 手动创建虚拟环境（`python -m venv`）
- ❌ 使用 `requirements.txt`（统一用 `pyproject.toml`）

**正确示例**：

```bash
# ✅ 运行 Python 脚本
uv run python src/vibe3/cli.py

# ✅ 运行测试
uv run pytest

# ✅ 运行 mypy
uv run mypy src/vibe3

# ❌ 错误：直接使用 python
python src/vibe3/cli.py

# ❌ 错误：使用 pip
pip install requests
```

### 核心依赖（必须）

| 包名              | 版本    | 用途       | 强制程度 |
| ----------------- | ------- | ---------- | -------- |
| typer             | ^0.9.0  | CLI 框架   | **必须** |
| rich              | ^13.0.0 | 美化输出   | **必须** |
| pydantic          | ^2.0.0  | 数据验证   | **必须** |
| pydantic-settings | ^2.0.0  | 配置管理   | **必须** |
| loguru            | ^0.7.0  | 结构化日志 | **必须** |

### 可选依赖

| 包名   | 版本   | 用途      | 强制程度 |
| ------ | ------ | --------- | -------- |
| pyyaml | ^6.0.0 | YAML 配置 | 可选     |

### 开发依赖（必须）

| 包名   | 版本    | 用途       | 强制程度 |
| ------ | ------- | ---------- | -------- |
| mypy   | ^1.5.0  | 类型检查   | **必须** |
| pytest | ^7.4.0  | 测试框架   | **必须** |
| ruff   | ^0.1.0  | Linting    | **必须** |
| black  | ^23.0.0 | 代码格式化 | **必须** |

### 禁止的依赖

- ❌ 数据库 ORM (SQLAlchemy, peewee)
- ❌ 复杂 API SDK
- ❌ 不需要的框架 (Django, Flask, FastAPI)
- ❌ 分布式系统库

---

## 架构分层（强制）

### 目录结构

```
src/vibe3/
├── cli.py                    # Typer 入口
├── commands/                 # 命令调度层（薄层）
│   ├── pr.py                # PR 命令
│   ├── flow.py              # Flow 命令
│   └── task.py              # Task 命令
├── services/                 # 业务逻辑层
│   ├── pr_service.py
│   ├── flow_service.py
│   └── task_service.py
├── clients/                  # 外部依赖封装
│   ├── git_client.py
│   ├── github_client.py
│   └── store_client.py
├── models/                   # Pydantic 数据模型
│   ├── exceptions.py        # 异常定义
│   ├── pr.py
│   ├── flow.py
│   └── task.py
├── ui/                       # 展示层
│   └── console.py
└── config/                   # 配置模块
    ├── settings.py
    └── logging.py
```

### 分层职责

#### Layer 1: CLI (cli.py)

- **职责**：解析命令行参数，调用 commands
- **代码量**：< 20 行
- **禁止**：业务逻辑、直接 I/O

#### Layer 2: Commands (commands/)

- **职责**：参数验证，调用 service，格式化输出
- **代码量**：每个文件 < 50 行
- **禁止**：直接调用 subprocess、数据库操作

#### Layer 3: Services (services/)

- **职责**：业务逻辑编排
- **代码量**：每个文件 < 80 行
- **禁止**：直接 I/O、UI 逻辑

#### Layer 4: Clients (clients/)

- **职责**：封装外部依赖（Git, GitHub, SQLite）
- **允许**：subprocess、文件 I/O、数据库操作
- **必须**：提供接口用于 mock

#### Layer 5: Models (models/)

- **职责**：Pydantic 数据模型
- **要求**：所有字段必须有类型注解

#### Layer 6: UI (ui/)

- **职责**：Rich 输出格式化
- **禁止**：业务逻辑

### 依赖方向（强制）

```
CLI → Commands → Services → Clients → Models
                ↓
                UI
```

**禁止反向依赖**：

- ❌ Clients 不能调用 Services
- ❌ Services 不能调用 Commands
- ❌ Models 不能调用任何层

---

## 函数大小限制

遵循项目级规范见 `coding-standards.md` 的分层差异表格。

---

## 测试结构（强制）

### 测试路径

```
tests/
├── vibe2/                    # V2 Shell 测试
└── vibe3/                    # V3 Python 测试
    ├── test_config/
    │   └── test_settings.py
    ├── test_services/
    │   ├── test_pr_service.py
    │   ├── test_flow_service.py
    │   └── test_task_service.py
    ├── test_clients/
    │   ├── test_git_client.py
    │   └── test_github_client.py
    └── test_commands/
        ├── test_pr.py
        ├── test_flow.py
        └── test_task.py
```

---

## 工具配置

### pyproject.toml

```toml
[project]
name = "vibe3"
version = "3.0.0"
requires-python = ">=3.12"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.black]
line-length = 88
target-version = ["py312"]
```

---

## 参考文档

- **[~/.claude/rules/common/python-standards.md](通用 Python 最佳实践)**
- **[docs/v3/infrastructure/](../../docs/v3/infrastructure/README.md)** - 实施指南
- **[SOUL.md](../../SOUL.md)** - 项目宪法
- **[CLAUDE.md](../../CLAUDE.md)** - 项目上下文

---

**维护者**：Vibe Team  
**最后更新**：2026-04-27