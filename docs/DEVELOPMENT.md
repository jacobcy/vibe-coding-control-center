# Vibe3 开发指南

## 快速开始

### 安装依赖

```bash
# 安装所有依赖（包括开发依赖）
v3-install

# 或手动安装
uv sync --all-extras
```

### 常用开发命令

**推荐方式：使用项目 alias**

项目已配置便捷 alias（位于 `alias/vibe3.sh`）：

```bash
# 安装所有依赖
v3-install

# 运行测试
v3-test

# 类型检查
v3-mypy

# 代码格式化
v3-fmt

# 运行 pre-commit 检查
v3-check

# 运行 vibe3 CLI
v3

# 一键运行所有开发检查
v3-dev
```

**使用 `uv run` 的方式：**

```bash
# 运行测试
uv run pytest

# 类型检查
uv run mypy src

# 代码格式化
uv run black src tests
uv run ruff check src tests

# 运行 pre-commit
uv run pre-commit run --all-files

# 运行应用
uv run vibe3 --help
```

**为什么使用 `uv run`？**
- 自动确保依赖已安装
- 不需要手动激活虚拟环境
- 保证使用正确的 Python 环境

### Git Hooks 设置

```bash
# 安装 pre-commit hooks
uv run pre-commit install
```

## 依赖管理

本项目使用 `uv` 进行依赖管理。

- **主依赖**：运行应用必需的依赖（typer, rich, pydantic, loguru）
- **开发依赖**：开发工具（pytest, mypy, ruff, black, pre-commit）

```bash
# 添加主依赖
uv add package-name

# 添加开发依赖
uv add --dev package-name

# 更新依赖
uv lock --upgrade
```

## 故障排除

### 问题：ModuleNotFoundError

如果遇到 `ModuleNotFoundError: No module named 'xxx'`：

```bash
# 运行安装脚本
./scripts/install-deps.sh

# 或手动安装所有依赖
uv sync --all-extras
```

### 问题：命令找不到

如果 `vibe3` 命令找不到：

```bash
# 确保项目已安装
uv sync --all-extras

# 使用 uv run 运行
uv run vibe3 --help
```