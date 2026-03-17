# 命令调试设计（修订版）

> **核心原则**: `vibe inspect` 提供静态信息，`vibe review` 执行并支持追踪

---

## 1. 两种需求

### 1.1 需求1：查看命令结构（静态）

**场景**: 想了解 `vibe review pr` 调用了哪些文件和方法，但**不执行**

**命令**:
```bash
vibe inspect --symbols review pr
```

**输出**:
```
vibe review pr
├─ commands/review.py::pr()
│  ├─ clients/git_client.py::get_diff()
│  ├─ services/serena_service.py::analyze_changes()
│  ├─ services/dag_service.py::expand_impact()
│  └─ services/pr_scoring_service.py::calculate_score()
```

**特点**:
- ✅ 不执行命令
- ✅ 快速查看调用链路
- ✅ 静态分析（AST 解析）

---

### 1.2 需求2：调试命令执行（运行时）

**场景**: 执行 `vibe review pr` 时报错，想追踪执行过程

**命令**:
```bash
vibe review pr 42 --trace
```

**输出**:
```
执行: vibe review pr 42

commands/review.py::pr(pr_number=42)
  ├─ clients/git_client.py::get_diff(source=PRSource(42))
  │  └─ ✓ return: 234 lines
  ├─ services/serena_service.py::analyze_changes(source=PRSource(42))
  │  ├─ clients/git_client.py::get_changed_files(...)
  │  │  └─ ✓ return: 3 files
  │  └─ ✓ return: impact.json
  ❌ ERROR in subprocess.run("codex review")
     exit_code: 1
     stderr: codex: command not found
```

**特点**:
- ✅ 实际执行命令
- ✅ 记录参数和返回值
- ✅ 标记错误位置

---

## 2. 命令职责划分

### 2.1 `vibe inspect` - 静态信息提供

**职责**: 提供命令的静态信息，**不执行命令**

**命令**:
```bash
vibe inspect --symbols              # 显示所有命令列表
vibe inspect --symbols review       # 显示 vibe review 的子命令
vibe inspect --symbols review pr    # 显示 vibe review pr 的调用链路（静态分析）
```

**实现**:
- AST 解析 Python 文件
- 提取函数定义和调用关系
- 不执行任何代码

---

### 2.2 `vibe review` - 执行并支持追踪

**职责**: 执行代码审核，支持调试模式

**命令**:
```bash
vibe review pr 42              # 正常执行
vibe review pr 42 --trace      # 执行并追踪调用链路
vibe review pr 42 --debug      # 输出详细日志
```

**实现**:
```python
# commands/review.py
@app.command()
def pr(pr_number: int, trace: bool = False):
    """审核 PR"""
    if trace:
        # 启用追踪模式
        import sys
        sys.settrace(_trace_calls)

    # 正常执行
    source = PRSource(pr_number=pr_number)
    impact = serena.analyze_changes(source)
    # ...
```

---

## 3. 核心区别

| 维度 | `vibe inspect --symbols` | `vibe review --trace` |
|------|-------------------------|---------------------|
| **执行命令** | ❌ 否 | ✅ 是 |
| **用途** | 查看命令结构 | 调试命令执行 |
| **模式** | 静态分析（AST） | 运行时追踪（sys.settrace） |
| **速度** | 快（不执行） | 慢（实际执行） |
| **输出** | 函数调用关系 | 参数、返回值、错误位置 |

---

## 4. 实现细节

### 4.1 `vibe inspect --symbols`

**位置**: `commands/inspect.py`

```python
@app.command("symbols")
def inspect_symbols(command: str, subcommand: str = ""):
    """显示命令的调用链路（静态分析）

    Examples:
        vibe inspect --symbols review pr
    """
    from vibe3.services.symbol_analyzer import SymbolAnalyzer

    analyzer = SymbolAnalyzer()
    tree = analyzer.analyze_command(command, subcommand)
    _print_call_tree(tree)
```

**特点**:
- 不执行命令
- 只解析代码结构

---

### 4.2 `vibe review --trace`

**位置**: `commands/review.py`

```python
@app.command()
def pr(pr_number: int, trace: bool = False):
    """审核 PR

    Args:
        pr_number: PR 编号
        trace: 追踪模式，输出详细调用链路
    """
    if trace:
        # 启用追踪
        _enable_tracing()

    # 正常执行
    source = PRSource(pr_number=pr_number)
    impact = serena.analyze_changes(source)
    # ...

def _enable_tracing():
    """启用调用追踪"""
    import sys

    def trace_calls(frame, event, arg):
        if event == "call":
            filename = frame.f_code.co_filename
            function = frame.f_code.co_name
            if "vibe3" in filename:
                print(f"  ├─ {filename}::{function}()")
        return trace_calls

    sys.settrace(trace_calls)
```

**特点**:
- 实际执行命令
- 追踪并输出调用过程

---

## 5. 使用场景对比

### 场景1：学习系统结构

**用户**: "我想知道 `vibe review pr` 调用了哪些文件？"

**使用**:
```bash
vibe inspect --symbols review pr
```

**效果**: 快速查看静态调用链路，不执行命令

---

### 场景2：调试命令错误

**用户**: "`vibe review pr 42` 报错了，想知道哪里出错"

**使用**:
```bash
vibe review pr 42 --trace
```

**效果**: 执行命令并追踪，看到错误位置

---

### 场景3：性能分析

**用户**: "想知道 `vibe review pr` 哪个环节慢"

**使用**:
```bash
vibe review pr 42 --trace
```

**效果**: 看到每个步骤的耗时

---

## 6. 统一的追踪支持

**所有命令都应该支持 `--trace` 参数**:

```bash
vibe review pr 42 --trace        # 追踪 review pr
vibe review commit SHA --trace   # 追踪 review commit
vibe inspect pr 42 --trace       # 追踪 inspect pr（如果需要）
```

**实现**:
```python
# 所有 Command 入口都添加 trace 参数
@app.command()
def some_command(..., trace: bool = False):
    if trace:
        _enable_tracing()
    # 正常逻辑
```

---

## 7. 总结

### 7.1 命令设计

| 命令 | 职责 | 是否执行 |
|------|------|---------|
| `vibe inspect --symbols` | 查看命令结构 | ❌ 否 |
| `vibe <command> --trace` | 调试命令执行 | ✅ 是 |

### 7.2 优势

- ✅ **职责清晰**: `inspect` 提供信息，`review` 执行操作
- ✅ **符合直觉**: 在哪个命令报错，就在哪个命令加 `--trace`
- ✅ **统一体验**: 所有命令都支持 `--trace`

### 7.3 实施任务

**Phase 1**:
- [ ] 创建 `services/symbol_analyzer.py`
  - `analyze_command()` - 静态分析（用于 `vibe inspect --symbols`）

**Phase 2**:
- [ ] 所有 Command 添加 `--trace` 参数
  - 追踪执行过程（用于调试）
  - 统一追踪基础设施