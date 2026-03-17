---
document_type: implementation-guide
title: Vibe 3.0 - 命令参数标准
status: active
author: Claude Sonnet 4.6
created: 2026-03-17
last_updated: 2026-03-17
related_docs:
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/v3/infrastructure/05-logging.md
  - docs/v3/trace/references/command-debug-design.md
  - docs/v3/infrastructure/08-command-quick-ref.md
---

# Vibe 3.0 - 命令参数标准

> **快速参考**: [08-command-quick-ref.md](08-command-quick-ref.md) - 核心参数速查表

本文档定义 Vibe 3.0 的命令参数标准，所有 CLI 命令必须遵守统一参数规范，确保用户体验一致性和可维护性。

---

## 核心原则

### 1. 一致性优先

所有命令必须提供一致的参数体验：
- ✅ 相同功能的参数名称相同
- ✅ 相同功能的参数行为相同
- ✅ 所有命令支持核心参数集

### 2. 符合业界标准

遵循 Unix/Linux 和 Python CLI 最佳实践：
- ✅ 短选项（`-y`）和长选项（`--yes`）并存
- ✅ 布尔选项不带参数（`--trace`）
- ✅ 帮助信息清晰（`-h/--help` 由 typer 自动提供）

---

## 核心参数集（强制）

所有 `vibe` 命令必须支持以下核心参数：

| 参数 | 短选项 | 长选项 | 类型 | 默认值 | 用途 |
|------|--------|--------|------|--------|------|
| **追踪** | - | `--trace` | bool | False | 启用调用链路追踪 + DEBUG 日志 |
| **JSON** | - | `--json` | bool | False | JSON 格式输出 |
| **确认** | `-y` | `--yes` | bool | False | 自动确认交互（默认拒绝） |
| **帮助** | `-h` | `--help` | - | - | 显示帮助（typer 自动提供） |

> **注意**：`--verbose` / `-v` 已合并入 `--trace`，不单独存在。`--trace` 同时启用调用链路追踪和 DEBUG 级别日志输出，避免两个参数语义重叠造成混淆。

---

## 参数详细说明

### 1. `--trace` - 调用链路追踪 + DEBUG 日志

**用途**: 同时启用运行时调用链路追踪和 DEBUG 级别日志输出

**行为**:
- 设置日志级别为 DEBUG（输出所有 `logger.debug(...)` 内容）
- 追踪函数调用链路（调用栈、参数、返回值）
- 标记错误位置
- 不影响命令执行结果

**使用场景**:
```bash
# 调试命令执行过程
vibe review pr 42 --trace

# 追踪错误位置
vibe inspect pr 42 --trace
```

**输出示例**:
```
commands/review.py::pr(pr_number=42)
  ├─ clients/git_client.py::get_diff()
  │  └─ ✓ return: 234 lines
  ├─ services/serena_service.py::analyze_changes()
  │  └─ ✓ return: impact.json
  ❌ ERROR in subprocess.run("codex review")
```

**详细实现**: 见 [../../trace/references/command-debug-design.md](../../v3/trace/references/command-debug-design.md)

**用途**: 以 JSON 格式输出结果，便于脚本解析

**行为**:
- 输出结构化 JSON 数据
- 不包含人类可读的格式化
- 适合管道和脚本处理

**使用场景**:
```bash
# 脚本化处理
vibe inspect pr 42 --json | jq '.impact'

# 集成到其他工具
RESULT=$(vibe inspect metrics --json)
```

---

### 4. `-y/--yes` - 自动确认

**用途**: 自动确认交互式操作，跳过用户确认

**行为**:
- 默认：拒绝所有需要用户确认的操作
- `-y`：自动确认所有操作
- 主要用于破坏性操作（删除、重置等）

**使用场景**:
```bash
# 默认：需要确认
vibe clean

# 自动确认（用于脚本）
vibe clean --yes

# 破坏性操作
vibe reset --yes
```

**安全原则**:
- ✅ 默认拒绝，明确确认
- ✅ 破坏性操作必须要求确认
- ✅ 只在明确指定 `-y` 时自动确认

---

### 5. `-h/--help` - 帮助信息

**用途**: 显示命令帮助信息

**行为**:
- 由 typer 自动提供
- 显示命令描述、参数说明、示例

**实现**: 无需手动实现，typer 自动处理

**使用场景**:
```bash
# 查看命令帮助
vibe review --help
vibe inspect --help
```

---

## 参数组合规则

### 可组合性

核心参数可以自由组合：

```bash
# 追踪（含 DEBUG 日志）+ JSON
vibe inspect pr 42 --trace --json

# 仅 JSON 输出
vibe inspect metrics --json

# 追踪调试
vibe review pr 42 --trace
```

### 冲突处理

| 组合 | 冲突？ | 说明 |
|------|--------|------|
| `--trace` + `--json` | ✅ 允许 | JSON 格式输出追踪结果 |

**建议**: `--json` 与 `--trace` 同时使用时，追踪日志输出到 stderr，JSON 结果输出到 stdout，互不干扰。

---

## 实现模板

### 标准命令模板

```python
import typer
from typing import Annotated

app = typer.Typer()

@app.command()
def example_command(
    # 位置参数
    target: str,

    # 核心参数集（强制）
    trace: Annotated[bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="JSON 格式输出")] = False,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="自动确认交互")] = False,

    # 命令特定参数（可选）
    option1: str = typer.Option("default", "--option1", help="Specific option"),
):
    """Example command with standard parameters"""
    # 1. 处理 trace（同时启用 DEBUG 日志 + 调用链路追踪）
    if trace:
        import sys
        from loguru import logger
        from vibe3.observability.trace import trace_context
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # 2. 执行核心逻辑
    result = _do_something(target, option1)

    # 3. 处理输出格式
    if json_output:
        typer.echo_json(result)
    else:
        _print_human_readable(result)
```

---

## 测试标准

### 强制测试项

每个命令必须包含以下测试：

#### 1. 参数存在性测试

```python
def test_command_has_standard_params():
    """测试命令包含所有核心参数"""
    from vibe3.commands.example import example_command
    import inspect

    sig = inspect.signature(example_command)
    params = sig.parameters

    assert "trace" in params, "Missing --trace parameter"
    assert "json_output" in params, "Missing --json parameter"
    assert "yes" in params, "Missing --yes parameter"
```

#### 2. 参数默认值测试

```python
def test_param_defaults():
    """测试参数默认值正确"""
    from vibe3.commands.example import example_command
    import inspect

    sig = inspect.signature(example_command)
    params = sig.parameters

    assert params["trace"].default is False
    assert params["json_output"].default is False
    assert params["yes"].default is False
```

#### 3. 功能测试

```python
from typer.testing import CliRunner
from vibe3.commands.example import app

runner = CliRunner()

def test_trace_parameter():
    """测试 --trace 参数"""
    result = runner.invoke(app, ["target", "--trace"])
    assert result.exit_code == 0
    # 验证追踪输出
    assert "├─" in result.stdout or "trace" in result.stdout.lower()
```

#### 4. 参数组合测试

```python
def test_param_combinations():
    """测试参数组合"""
    # trace + verbose
    result = runner.invoke(app, ["target", "--trace"])
    assert result.exit_code == 0
```

---

## 验收标准

### 代码审查清单

- [ ] 所有命令包含核心参数集（`--trace`, `--json`, `--yes`）
- [ ] 参数命名符合标准（短选项 + 长选项）
- [ ] 参数默认值正确（均为 `False`）
- [ ] 帮助信息清晰（`help="..."`）
- [ ] 参数行为符合文档说明
- [ ] 包含参数测试（存在性、默认值、功能）
- [ ] 参数可组合使用

### 测试覆盖率

- [ ] 参数存在性测试：100%
- [ ] 参数默认值测试：100%
- [ ] 参数功能测试：≥80%
- [ ] 参数组合测试：≥80%

---

## 最佳实践

### 1. 保持参数语义一致

```python
# ✅ 正确：所有命令的 --json 行为一致
vibe inspect pr 42 --json  # 输出 JSON
vibe review pr 42 --json   # 输出 JSON

# ❌ 错误：不同命令的 --json 行为不同
vibe inspect pr 42 --json  # 输出 JSON
vibe review pr 42 --json   # 输出 YAML（不一致！）
```

### 2. 避免参数爆炸

```python
# ✅ 正确：核心参数 + 必要的特定参数
@app.command()
def command(
    target: str,
    trace: bool = False,
    verbose: bool = False,
    specific: str = "value",  # 命令特定参数
):
    ...

# ❌ 错误：参数过多
@app.command()
def command(
    target: str,
    trace: bool = False,
    verbose: bool = False,
    option1: str = "...",
    option2: str = "...",
    option3: str = "...",
    option4: str = "...",
    option5: str = "...",
    option6: str = "...",  # 参数太多！
):
    ...
```

### 3. 提供清晰的帮助信息

```python
# ✅ 正确：清晰的帮助信息
@app.command()
def command(
    target: str = typer.Argument(..., help="Target file or directory"),
    trace: bool = typer.Option(False, "--trace", help="Enable runtime call tracing"),
):
    """Command description

    Detailed description of what this command does.

    Examples:
        vibe command target --trace
        vibe command target --json
    """
    ...

# ❌ 错误：缺少帮助信息
@app.command()
def command(target: str, trace: bool = False):
    """Command"""  # 描述太简略
    ...
```

---

## 交叉引用

### 相关文档

- **架构标准**: [02-architecture.md](02-architecture.md) - 分层架构定义
- **编码标准**: [03-coding-standards.md](03-coding-standards.md) - 代码风格和复杂度
- **日志标准**: [05-logging.md](05-logging.md) - 日志输出规范
- **命令调试设计**: [../../v3/trace/references/command-debug-design.md](../../v3/trace/references/command-debug-design.md) - 静态检查 vs 动态追踪

### 实施文档

- **Phase 1 实施**: [../../v3/trace/phase1-infrastructure.md](../../v3/trace/phase1-infrastructure.md)
- **Phase 2 实施**: [../../v3/trace/phase2-integration.md](../../v3/trace/phase2-integration.md)

---

## 总结

### 核心参数集

| 参数 | 短选项 | 长选项 | 默认值 | 用途 |
|------|--------|--------|--------|------|
| 追踪 | - | `--trace` | False | 调用链路追踪 + DEBUG 日志 |
| JSON | - | `--json` | False | JSON 格式输出 |
| 确认 | `-y` | `--yes` | False | 自动确认交互 |
| 帮助 | `-h` | `--help` | - | 显示帮助（typer 提供） |

### 实施要求

1. ✅ 所有命令必须支持核心参数集
2. ✅ 参数命名和行为必须一致
3. ✅ 包含完整的参数测试
4. ✅ 提供清晰的帮助信息
5. ✅ 参数可组合使用

### 验收标准

- 参数存在性测试：100%
- 参数默认值测试：100%
- 参数功能测试：≥80%
- 参数组合测试：≥80%