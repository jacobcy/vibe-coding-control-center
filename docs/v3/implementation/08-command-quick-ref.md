---
document_type: quick-reference
title: Vibe 3.0 - 命令参数快速参考
status: active
author: Claude Sonnet 4.6
created: 2026-03-17
last_updated: 2026-03-17
related_docs:
  - docs/v3/implementation/07-command-standards.md
---

# 命令参数快速参考

> **完整标准**: [07-command-standards.md](07-command-standards.md)

---

## 核心参数集

所有 `vibe` 命令必须支持以下参数：

| 参数 | 短选项 | 长选项 | 用途 | 示例 |
|------|--------|--------|------|------|
| 追踪 | - | `--trace` | 运行时调用链路追踪 | `vibe review pr 42 --trace` |
| 详细 | `-v` | `--verbose` | 详细输出（DEBUG 日志） | `vibe inspect metrics -v` |
| JSON | - | `--json` | JSON 格式输出 | `vibe inspect pr 42 --json` |
| 确认 | `-y` | `--yes` | 自动确认交互 | `vibe clean --yes` |
| 帮助 | `-h` | `--help` | 显示帮助 | `vibe review --help` |

---

## 参数行为

### `--trace` - 追踪执行过程

**用途**: 调试命令执行，追踪调用链路

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

### `-v/--verbose` - 详细日志

**用途**: 启用 DEBUG 级别日志

**行为**:
- 输出详细调试信息
- 不追踪调用链路

---

### `--json` - JSON 输出

**用途**: 脚本化处理

**使用场景**:
```bash
# 管道处理
vibe inspect pr 42 --json | jq '.impact'

# 变量赋值
RESULT=$(vibe inspect metrics --json)
```

---

### `-y/--yes` - 自动确认

**用途**: 跳过用户确认（破坏性操作）

**安全原则**:
- ✅ 默认拒绝
- ✅ 只在明确指定 `-y` 时自动确认

---

## 实现模板

```python
import typer

@app.command()
def example(
    target: str,

    # 核心参数集（强制）
    trace: bool = typer.Option(False, "--trace", help="Enable runtime call tracing"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Enable verbose output"),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
    yes: bool = typer.Option(False, "-y", "--yes", help="Auto-confirm interactions"),
):
    """Example command"""
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
    result = _do_something(target)

    # 4. 处理输出格式
    if json_output:
        typer.echo_json(result)
    else:
        _print_human_readable(result)
```

---

## 测试清单

- [ ] 参数存在性测试：`assert "trace" in params`
- [ ] 参数默认值测试：`assert params["trace"].default == False`
- [ ] 参数功能测试：`runner.invoke(app, ["target", "--trace"])`
- [ ] 参数组合测试：`runner.invoke(app, ["target", "--trace", "--verbose"])`

---

## 参数组合

### ✅ 推荐

```bash
vibe review pr 42 --trace --verbose
vibe inspect pr 42 --json
```

### ⚠️ 不推荐

```bash
# JSON + 详细日志会格式混乱
vibe inspect pr 42 --json --verbose
```

---

## 快速验证

验证命令是否符合标准：

```python
import inspect
from vibe3.commands.example import example_command

sig = inspect.signature(example_command)
params = sig.parameters

# 检查核心参数
assert "trace" in params
assert "verbose" in params
assert "json_output" in params
assert "yes" in params

# 检查默认值
assert all(params[p].default == False for p in ["trace", "verbose", "json_output", "yes"])
```

---

**完整标准**: [07-command-standards.md](07-command-standards.md)