---
document_type: implementation-guide
title: Vibe 3.0 - 命令参数标准
status: active
author: Claude Sonnet 4.6
created: 2026-03-17
last_updated: 2026-03-17
related_docs:
  - docs/v3/implementation/02-architecture.md
  - docs/v3/implementation/03-coding-standards.md
  - docs/v3/implementation/05-logging.md
  - docs/review_plan/references/command-debug-design.md
  - docs/v3/implementation/08-command-quick-ref.md
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
- ✅ 短选项（`-v`）和长选项（`--verbose`）并存
- ✅ 布尔选项不带参数（`--trace`）
- ✅ 帮助信息清晰（`-h/--help` 由 typer 自动提供）

---

## 核心参数集（强制）

所有 `vibe` 命令必须支持以下核心参数：

| 参数 | 短选项 | 长选项 | 类型 | 默认值 | 用途 |
|------|--------|--------|------|--------|------|
| **追踪** | - | `--trace` | bool | False | 启用运行时调用链路追踪 |
| **详细** | `-v` | `--verbose` | bool | False | 启用详细输出（DEBUG 日志） |
| **JSON** | - | `--json` | bool | False | JSON 格式输出 |
| **确认** | `-y` | `--yes` | bool | False | 自动确认交互（默认拒绝） |
| **帮助** | `-h` | `--help` | - | - | 显示帮助（typer 自动提供） |

---

## 参数详细说明

### 1. `--trace` - 运行时追踪

**用途**: 启用运行时调用链路追踪，记录函数调用、参数和返回值

**行为**:
- 追踪所有函数调用（通过 `sys.settrace`）
- 输出调用栈、参数、返回值
- 标记错误位置
- 不影响命令执行结果

**实现**:

```python
import sys
from typing import Any
from loguru import logger

def enable_tracing():
    """启用运行时追踪"""
    indent = [0]

    def trace_calls(frame: Any, event: str, arg: Any) -> Any:
        if event == "call":
            filename = frame.f_code.co_filename
            function = frame.f_code.co_name
            if "vibe3" in filename:
                print(f"{'  ' * indent[0]}├─ {filename}::{function}()")
                indent[0] += 1
        elif event == "return":
            indent[0] -= 1
        return trace_calls

    sys.settrace(trace_calls)

@app.command()
def some_command(trace: bool = False):
    """示例命令"""
    if trace:
        enable_tracing()

    # 正常逻辑
    ...
```

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

---

### 2. `-v/--verbose` - 详细输出

**用途**: 启用详细输出，显示 DEBUG 级别日志

**行为**:
- 设置日志级别为 DEBUG
- 输出详细调试信息
- 不追踪调用链路

**实现**:

```python
import logging
from loguru import logger

@app.command()
def some_command(verbose: bool = False):
    """示例命令"""
    if verbose:
        # 设置日志级别为 DEBUG
        logger.remove()
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
        )

    # 正常逻辑
    ...
```

**使用场景**:
```bash
# 查看详细日志
vibe review pr 42 --verbose

# 调试信息不足时
vibe inspect metrics -v
```

---

### 3. `--json` - JSON 输出

**用途**: 以 JSON 格式输出结果，便于脚本解析

**行为**:
- 输出结构化 JSON 数据
- 不包含人类可读的格式化
- 适合管道和脚本处理

**实现**:

```python
import json
import typer

@app.command()
def some_command(json_output: bool = False):
    """示例命令"""
    result = {
        "status": "success",
        "data": {...}
    }

    if json_output:
        typer.echo(json.dumps(result, indent=2))
    else:
        # 人类可读格式
        typer.echo("=== Result ===")
        typer.echo(f"Status: {result['status']}")
```

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

**实现**:

```python
import typer

@app.command()
def dangerous_command(yes: bool = False):
    """危险操作示例"""
    if not yes:
        # 默认：需要用户确认
        confirm = typer.confirm(
            "This will delete all data. Continue?",
            default=False  # 默认拒绝
        )
        if not confirm:
            typer.echo("Operation cancelled.")
            raise typer.Exit(1)

    # 执行操作
    typer.echo("Executing dangerous operation...")

    # 使用 --yes 跳过确认
```

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
# 追踪 + 详细
vibe review pr 42 --trace --verbose

# JSON + 详细
vibe inspect metrics --json -v

# 追踪 + JSON
vibe inspect pr 42 --trace --json
```

### 冲突处理

| 组合 | 冲突？ | 说明 |
|------|--------|------|
| `--trace` + `--verbose` | ✅ 允许 | 追踪 + DEBUG 日志 |
| `--json` + `--verbose` | ⚠️ 不推荐 | JSON 输出与详细日志格式冲突 |
| `--trace` + `--json` | ✅ 允许 | JSON 输出追踪结果 |

**建议**: `--json` 与 `--verbose` 不要同时使用，输出格式会混乱。

---

## 实现模板

### 标准命令模板

```python
import typer
from typing import Optional

app = typer.Typer()

@app.command()
def example_command(
    # 位置参数
    target: str,

    # 核心参数集（强制）
    trace: bool = typer.Option(False, "--trace", help="Enable runtime call tracing"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output (DEBUG logs)"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Auto-confirm interactions"),

    # 命令特定参数（可选）
    option1: str = typer.Option("default", "--option1", help="Specific option"),
):
    """Example command with standard parameters

    Args:
        target: Target to operate on
        trace: Enable runtime call tracing
        verbose: Enable verbose output
        json_output: Output in JSON format
        yes: Auto-confirm interactions
        option1: Specific option for this command
    """
    # 1. 处理 verbose
    if verbose:
        import sys
        from loguru import logger
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # 2. 处理 trace
    if trace:
        from vibe3.utils.tracing import enable_tracing
        enable_tracing()

    # 3. 执行核心逻辑
    result = _do_something(target, option1)

    # 4. 处理输出格式
    if json_output:
        typer.echo_json(result)
    else:
        _print_human_readable(result)

def _do_something(target: str, option1: str) -> dict:
    """核心逻辑（可测试）"""
    logger.info("Doing something", target=target, option1=option1)
    return {"status": "success", "target": target}

def _print_human_readable(result: dict):
    """人类可读输出"""
    typer.echo(f"=== Result ===")
    typer.echo(f"Status: {result['status']}")
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

    # 必须包含核心参数
    assert "trace" in params, "Missing --trace parameter"
    assert "verbose" in params, "Missing --verbose parameter"
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

    assert params["trace"].default == False
    assert params["verbose"].default == False
    assert params["json_output"].default == False
    assert params["yes"].default == False
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

def test_verbose_parameter():
    """测试 --verbose 参数"""
    result = runner.invoke(app, ["target", "--verbose"])
    assert result.exit_code == 0
    # 验证 DEBUG 日志输出

def test_json_parameter():
    """测试 --json 参数"""
    result = runner.invoke(app, ["target", "--json"])
    assert result.exit_code == 0
    # 验证 JSON 输出
    import json
    data = json.loads(result.stdout)
    assert "status" in data

def test_yes_parameter():
    """测试 --yes 参数"""
    # 不带 --yes，应该拒绝
    result = runner.invoke(app, ["target"], input="n\n")
    assert result.exit_code == 1  # 用户拒绝

    # 带 --yes，应该自动确认
    result = runner.invoke(app, ["target", "--yes"])
    assert result.exit_code == 0
```

#### 4. 参数组合测试

```python
def test_param_combinations():
    """测试参数组合"""
    # trace + verbose
    result = runner.invoke(app, ["target", "--trace", "--verbose"])
    assert result.exit_code == 0

    # json + verbose (不推荐但允许)
    result = runner.invoke(app, ["target", "--json", "-v"])
    assert result.exit_code == 0
```

---

## 验收标准

### 代码审查清单

- [ ] 所有命令包含核心参数集（`--trace`, `--verbose`, `--json`, `--yes`）
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
- **命令调试设计**: [../../review_plan/references/command-debug-design.md](../../review_plan/references/command-debug-design.md) - 静态检查 vs 动态追踪

### 实施文档

- **Phase 1 实施**: [../../review_plan/phase1-infrastructure.md](../../review_plan/phase1-infrastructure.md)
- **Phase 2 实施**: [../../review_plan/phase2-integration.md](../../review_plan/phase2-integration.md)

---

## 示例命令

### 完整示例

```python
# commands/example.py
import typer
from loguru import logger
from typing import Optional

app = typer.Typer()

@app.command()
def inspect(
    target: str = typer.Argument(..., help="Target to inspect (PR number, commit SHA, or branch)"),
    trace: bool = typer.Option(False, "--trace", help="Enable runtime call tracing"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output (DEBUG logs)"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Auto-confirm interactions"),
    format: str = typer.Option("text", "--format", help="Output format (text|markdown)"),
):
    """Inspect code changes

    Analyze code changes and provide structured information.

    Args:
        target: Target to inspect (PR number, commit SHA, or branch)
        trace: Enable runtime call tracing
        verbose: Enable verbose output
        json_output: Output in JSON format
        yes: Auto-confirm interactions
        format: Output format

    Examples:
        vibe inspect pr 42
        vibe inspect pr 42 --trace
        vibe inspect commit HEAD~1 --json
    """
    # 1. 处理 verbose
    if verbose:
        import sys
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
        logger.debug("Verbose mode enabled")

    # 2. 处理 trace
    if trace:
        from vibe3.utils.tracing import enable_tracing
        enable_tracing()
        logger.info("Tracing enabled")

    # 3. 执行核心逻辑
    try:
        result = _analyze_target(target)
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise typer.Exit(1)

    # 4. 处理输出格式
    if json_output:
        typer.echo_json(result)
    else:
        _print_human_readable(result, format)

def _analyze_target(target: str) -> dict:
    """核心逻辑（可测试）"""
    logger.info("Analyzing target", target=target)
    # 实际分析逻辑
    return {
        "target": target,
        "status": "success",
        "changes": []
    }

def _print_human_readable(result: dict, format: str):
    """人类可读输出"""
    if format == "markdown":
        typer.echo(f"# Analysis Result\n\n**Target**: {result['target']}\n\n**Status**: {result['status']}")
    else:
        typer.echo("=== Analysis Result ===")
        typer.echo(f"Target: {result['target']}")
        typer.echo(f"Status: {result['status']}")

if __name__ == "__main__":
    app()
```

---

## 总结

### 核心参数集

| 参数 | 短选项 | 长选项 | 默认值 | 用途 |
|------|--------|--------|--------|------|
| 追踪 | - | `--trace` | False | 运行时调用链路追踪 |
| 详细 | `-v` | `--verbose` | False | 详细输出（DEBUG 日志） |
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