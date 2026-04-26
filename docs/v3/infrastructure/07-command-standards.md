---
document_type: implementation-guide
title: Vibe 3.0 - 命令参数标准
status: active
author: Claude Sonnet 4.6
created: 2026-03-17
last_updated: 2026-03-18
related_docs:
  - docs/v3/infrastructure/02-architecture.md
  - docs/v3/infrastructure/03-coding-standards.md
  - docs/v3/infrastructure/05-logging.md
  - docs/v3/infrastructure/08-command-quick-ref.md
---

# Vibe 3.0 - 命令参数标准

> **快速参考**: [08-command-quick-ref.md](08-command-quick-ref.md) - 核心参数速查表

本文档定义 Vibe 3.0 的命令参数标准，所有 CLI 命令必须遵守统一参数规范，确保用户体验一致性和可维护性。

---

## 命令层级结构

Vibe 3.0 CLI 分为三层：

```
vibe3                          ← 全局层（Global）
├── flow                       ← 命令组层（Group）
│   ├── new
│   ├── list
│   └── ...
├── inspect                    ← 命令组层（Group）
│   ├── pr
│   ├── metrics
│   └── ...
└── review                     ← 命令组层（Group）
    ├── pr                     ← 子命令层（Subcommand）
    └── ...
```

每层的参数职责不同，见下表。

---

## 各层参数职责

### 全局层（`vibe3`）

| 参数 | 短选项 | 类型 | 默认值 | 用途 |
|------|--------|------|--------|------|
| `-v` | `-v` | count | 0 | 日志级别：`-v` INFO，`-vv` DEBUG |
| `--help` | `-h` | - | - | 显示帮助 |

- 不加任何参数 → 显示帮助（`no_args_is_help=True`）
- `vibe3 help` → 显示帮助（等同于 `vibe3 --help`）
- `-v` 全局生效，影响所有子命令的日志输出

### 命令组层（`flow` / `task` / `pr` / `inspect` / `review` / `hooks`）

| 参数 | 短选项 | 用途 |
|------|--------|------|
| `--help` | `-h` | 显示该组的子命令列表 |

- 不加任何参数 → 显示帮助（`no_args_is_help=True`）
- 命令组本身不执行逻辑，只路由到子命令

### 子命令层（`flow update` / `inspect pr` / `review pr` 等）

| 参数 | 短选项 | 长选项 | 类型 | 默认值 | 用途 |
|------|--------|--------|------|--------|------|
| 追踪 | - | `--trace` | bool | False | 调用链路追踪 + DEBUG 日志 |
| JSON | - | `--json` | bool | False | JSON 格式输出 |
| 确认 | `-y` | `--yes` | bool | False | 自动确认交互（破坏性操作） |
| 帮助 | `-h` | `--help` | - | - | 显示帮助 |

---

## 核心原则

### 1. 一致性优先

- ✅ 相同功能的参数名称相同
- ✅ 相同功能的参数行为相同
- ✅ 所有子命令支持核心参数集（`--trace`、`--json`）

### 2. 符合业界标准

- ✅ `-h` 是 `--help` 的简写，全局所有层级生效
- ✅ 布尔选项不带参数（`--trace`、`--json`）
- ✅ 不加参数时显示帮助，不报错

---

## 参数详细说明

### `-v / -vv` — 全局日志级别

**作用域**: 全局层，影响所有子命令

**行为**:
- 不加 `-v`：WARNING 级别（默认静默）
- `-v`：INFO 级别
- `-vv`：DEBUG 级别

**使用场景**:
```bash
vibe3 -v flow list          # INFO 日志
vibe3 -vv inspect pr 42     # DEBUG 日志
```

---

### `--trace` — 调用链路追踪

**作用域**: 子命令层

**行为**:
- 设置日志级别为 DEBUG
- 启用 `sys.settrace` 运行时调用链追踪，打印每个 vibe3 内部函数调用
- 比 `-vv` 更重量级，用于深度调试

**使用场景**:
```bash
vibe3 review pr 42 --trace
vibe3 inspect pr 42 --trace
```

**与 `-vv` 的区别**:

| | `-vv` | `--trace` |
|---|---|---|
| 日志级别 | DEBUG | DEBUG |
| 调用链追踪 | ❌ | ✅ `sys.settrace` |
| 性能开销 | 低 | 高 |
| 适用场景 | 日常调试 | 深度排查 |

---

### `--json` — JSON 输出

**作用域**: 子命令层

**行为**:
- 输出结构化 JSON 到 stdout
- 追踪日志输出到 stderr，互不干扰
- 适合管道和脚本处理

**使用场景**:
```bash
vibe3 inspect pr 42 --json | jq '.impact'
RESULT=$(vibe3 inspect base main --json)
```

---

### `-y / --yes` — 自动确认

**作用域**: 子命令层（破坏性操作）

**行为**:
- 默认：拒绝所有需要用户确认的操作
- `-y`：自动确认，用于脚本化

**使用场景**:
```bash
vibe3 clean --yes
vibe3 reset --yes
```

---

### `-h / --help` — 帮助

**作用域**: 全局所有层级

**行为**:
- 所有层级均支持 `-h` 作为 `--help` 的简写
- 不加参数时（命令组/全局）自动显示帮助

**使用场景**:
```bash
vibe3 -h
vibe3 flow -h
vibe3 inspect pr -h
```

---

## 实现模板

### 子命令标准模板

```python
import typer
from typing import Annotated

app = typer.Typer(no_args_is_help=True, rich_markup_mode="rich")

_TRACE_OPT = Annotated[bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")]
_JSON_OPT  = Annotated[bool, typer.Option("--json",  help="JSON 格式输出")]

@app.command()
def example(
    target: Annotated[str, typer.Argument(help="目标")],
    trace: _TRACE_OPT = False,
    json_out: _JSON_OPT = False,
    yes: Annotated[bool, typer.Option("-y", "--yes", help="自动确认")] = False,
) -> None:
    """命令描述。

    Example: vibe3 group example TARGET
    """
    if trace:
        from vibe3.commands.xxx_helpers import enable_trace
        enable_trace()

    result = _do_something(target)

    if json_out:
        typer.echo(json.dumps(result))
    else:
        _render(result)
```

---

## 测试标准

每个子命令必须包含：

```python
def test_missing_arg_shows_error():
    """缺少必填参数 → 友好错误，非崩溃"""
    result = runner.invoke(app, ["subcommand"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()

def test_help():
    result = runner.invoke(app, ["subcommand", "--help"])
    assert result.exit_code == 0

def test_json_output():
    with patch(...):
        result = runner.invoke(app, ["subcommand", "arg", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "expected_key" in data
```

---

## 验收清单

- [ ] 子命令包含 `--trace`、`--json`
- [ ] 破坏性操作包含 `-y/--yes`
- [ ] 所有层级支持 `-h`
- [ ] 命令组和全局不加参数时显示帮助
- [ ] 帮助信息包含 `Example:` 示例
- [ ] 测试覆盖：缺参数、`--help`、`--json`

---

## 交叉引用

- **架构标准**: [02-architecture.md](02-architecture.md)
- **编码标准**: [03-coding-standards.md](03-coding-standards.md)
- **日志标准**: [05-logging.md](05-logging.md)
- **命令调试设计**: [../../v3/trace/references/command-debug-design.md](../../v3/trace/references/command-debug-design.md)
