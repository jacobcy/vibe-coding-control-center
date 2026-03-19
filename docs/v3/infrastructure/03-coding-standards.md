---
document_type: implementation-guide
title: Vibe 3.0 - Coding Standards
status: active
author: Claude Sonnet 4.6
created: 2026-03-15
last_updated: 2026-03-16
related_docs:
  - docs/standards/v3/handoff-store-standard.md
  - docs/standards/v3/github-remote-call-standard.md
  - docs/v3/infrastructure/02-architecture.md
  - .agent/rules/python-standards.md
---

# Vibe 3.0 - 编码标准

本文档定义 Vibe 3.0 的**架构相关编码标准**。

**通用 Python 标准**：见 **[.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)**

---

## 技术栈（强制）

### 必须使用的依赖

| 包名 | 版本要求 | 用途 | 强制程度 |
|------|----------|------|----------|
| typer | ^0.9.0 | CLI 框架 | **必须** |
| rich | ^13.0.0 | 美化输出 | **必须** |
| pydantic | ^2.0.0 | 数据验证 | **必须** |
| loguru | ^0.7.0 | 结构化日志 | **必须** |

### 禁止使用的依赖

- ❌ **argparse** (用 typer 替代)
- ❌ **ORM** (SQLAlchemy, peewee)
- ❌ **Web 框架** (Django, Flask, FastAPI)
- ❌ **print()** (用 logger 或 rich)

---

## 类型注解与命名规范

见 **[.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)** §类型注解、§命名规范

---

## 代码复杂度（强制）

### 代码规模限制

为保持代码可理解性，必须遵守以下文件和函数规模限制：

| 层级 | 文件最大行数 | 函数最大行数 | 理由 |
|------|------------|------------|------|
| CLI (cli.py) | < 50 行 | < 20 行 | 只做转发 |
| Commands | < 150 行 | < 50 行 | 参数验证 + 调用 |
| Services | < 300 行 | < 100 行 | 业务逻辑 |
| Clients | 无限制 | < 150 行 | 封装复杂度 |

### 复杂度限制

- **禁止**：嵌套超过 3 层
- **禁止**：单个函数超过 10 个参数
- **禁止**：循环复杂度 > 10

### 重构建议

```python
# ❌ 错误：嵌套太深
def process_pr(pr):
    if pr.state == "open":
        if pr.draft:
            if pr.author == "me":
                # 逻辑太深
                ...

# ✅ 正确：提前返回
def process_pr(pr):
    if pr.state != "open":
        return
    if not pr.draft:
        return
    if pr.author != "me":
        return
    # 逻辑清晰
    ...
```

---

## 错误处理（强制）

详见 **[06-error-handling.md](06-error-handling.md)**

---

## 日志规范（强制）

详见：**[05-logging.md](05-logging.md)** (Agent-Centric Logging Standard)

---

## 测试要求

详见 **[04-test-standards.md](04-test-standards.md)**

---

## 代码审查检查清单

### 类型安全

- [ ] 所有公共函数有类型注解
- [ ] 不使用 `Any` 类型
- [ ] mypy 检查通过

### 代码质量

- [ ] 函数不超过最大行数
- [ ] 嵌套不超过 3 层
- [ ] 不使用裸 `except`

### 测试

- [ ] 核心路径有测试
- [ ] 测试覆盖率 >= 80%
- [ ] 异常场景有测试

### 日志

- [ ] 不使用 `print`
- [ ] 关键操作有日志
- [ ] 错误日志包含上下文

---

## 开发环境（强制）

### 依赖管理

本项目使用 **uv** 进行 Python 依赖管理。

#### 安装依赖

```bash
# 安装所有依赖
uv sync

# 安装开发依赖
uv sync --all-extras
```

#### 执行命令

**所有 Python 命令必须使用 `uv run` 前缀**，确保使用正确的虚拟环境。

```bash
# ✅ 正确
uv run pytest tests/
uv run mypy src/

# ❌ 错误
pytest tests/  # 可能使用错误的 Python 环境
mypy src/
```

### 运行测试

```bash
# 运行所有测试
uv run pytest tests/

# 运行指定测试文件
uv run pytest tests/vibe3/services/test_flow_service.py -v

# 运行并显示覆盖率
uv run pytest tests/ --cov=src/vibe3 --cov-report=term-missing
```

### 类型检查

```bash
# 运行 mypy 严格模式检查
uv run mypy --strict src/vibe3/
```

### 代码质量

```bash
# 运行 ruff linter
uv run ruff check src/

# 格式化代码
uv run black src/

# 自动修复 lint 问题
uv run ruff check --fix src/
```

### 常见问题

#### Python 版本要求

项目使用 Python 3.10+ 特性，确保你的 Python 版本 >= 3.10。

#### 类型注解要求

**类型注解是强制性的**，所有代码必须通过 `mypy --strict` 检查。

---

## 工具配置

### pyproject.toml

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_ignores = true

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.black]
line-length = 100
target-version = ["py310"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --strict-markers"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow tests",
]
```

---

## 参考文档

- **[.agent/rules/python-standards.md](../../../.agent/rules/python-standards.md)** - 完整 Python 标准
- **[02-architecture.md](02-architecture.md)** - 架构设计
- **[06-error-handling.md](06-error-handling.md)** - 异常处理

---

**维护者**：Vibe Team
**最后更新**：2026-03-15
