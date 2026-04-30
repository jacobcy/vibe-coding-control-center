# inspect + snapshot 联合优化方案

> 更新日期：2026-04-30
> 替代：`inspect-optimization-proposal.md`（原方案过度工程化，忽视 snapshot 职责）

## 核心认识：互补而非重复

经过对 snapshot 模块的深入调研，inspect 和 snapshot 并非重叠的命令，而是**明确分工的互补系统**。

### 职责划分

| 维度 | inspect | snapshot |
|------|---------|----------|
| **分析单元** | 单文件 / 单变更 | 项目级结构 |
| **时间维度** | 实时分析（一次性） | 持久化分析（可对比基线） |
| **数据存储** | 无（即时输出） | `.git/vibe3/structure/snapshots/` |
| **典型问题** | "这个文件/变更怎么样？" | "项目结构变了多少？" |
| **代码位置** | `src/vibe3/commands/inspect*.py` | `src/vibe3/commands/snapshot.py` |

### 现有协作示例

`review base` 命令内部已经同时调用两者（[roles/review.py](../../src/vibe3/roles/review.py)）：

```
review base [branch]
  ├─ snapshot diff(base, current)      # 项目结构变化概览
  └─ inspect base [branch]             # 代码级风险评估
```

这形成了"结构 + 影响"的二维审查上下文。**优化目标是让用户在 review 之外也能感知和使用这种协作**。

---

## 可用性问题拆解

### 问题 1：发现性差

用户不知道这两个命令存在，更不知道边界。

**现象**：
- `vibe3 inspect` 直接显示 typer help，没有概览
- `vibe3 snapshot` 同理
- 新用户不知道该用哪个

### 问题 2：输出是终点，不是起点

单条命令的输出没有引导后续行动，导致信息孤立。

**现象**：
- `inspect dead-code` 列出可疑函数，但不知道怎么验证
- `inspect base` 给了关键路径变更，不知道怎么看全局结构
- `inspect symbols` 给了引用列表，但没建议如何深挖
- `snapshot diff` 看了结构变化，不知道代码层面的影响

### 问题 3：snapshot 没人触发，导致 baseline 永不存在

`snapshot` 有持久化能力但没融入工作流。

**现象**：
- `snapshot save` 是手动命令，用户不知道什么时候该执行
- `snapshot diff` 需要 baseline（与主分支的对比点），但用户开分支后没机会保存
- 最终 `snapshot diff` 对新分支没意义（无历史可比）

### 问题 4：inspect 自身一致性问题

- `inspect symbols` 帮助文档声称支持纯符号搜索，但实现拒绝（[inspect_symbols.py:35-44](../../src/vibe3/commands/inspect_symbols.py:35) vs [L86-92](../../src/vibe3/commands/inspect_symbols.py:86)）
- `inspect commands` 无参数输出是冗余列表，但带参数有真实价值（静态调用树分析）

---

## 优化方案（按性价比排序）

### Tier 1：必做（总计 1-2 天）

#### 1. 修文档与实现一致性 — 30 分钟

**修改项**：[src/vibe3/commands/inspect_symbols.py:35-44](../../src/vibe3/commands/inspect_symbols.py:35)

移除"模式 1：纯符号搜索"的描述，与实现对齐：

```python
# BEFORE (帮助文档声称支持三种模式)
"""
Three query modes:
1. Symbol only (search across codebase):
   vibe inspect symbols build_module_graph
2. File:Symbol (find specific symbol in file):
   ...
3. File only (show all symbols in file):
   ...
"""

# AFTER (只说支持的两种模式)
"""
Two query modes (file context required):
1. <file>:<symbol>  - Find specific symbol in file
   vibe inspect symbols src/vibe3/services/dag_service.py:build_module_graph
2. <file>           - List all symbols in file
   vibe inspect symbols src/vibe3/services/dag_service.py
"""
```

同步更新错误消息（[L86-92](../../src/vibe3/commands/inspect_symbols.py:86)），保证拒绝消息与文档一致。

#### 2. 顶层概览强调互补关系 — 2 小时

**修改项**：[src/vibe3/commands/inspect.py](../../src/vibe3/commands/inspect.py) 的 `app.no_args_is_help` 和 [src/vibe3/commands/snapshot.py](../../src/vibe3/commands/snapshot.py) 的 help

使 `vibe3 inspect` 和 `vibe3 snapshot` 不带参数时显示有用的概览。

**inspect 概览示例**：

```
=== Inspect: Single-file & change analysis ===

When to use inspect:
  - Analyzing one file structure (LOC, functions, imports)
  - Looking up where a symbol is used
  - Finding dead code
  - Analyzing impact of a single change (PR / commit / branch)

Subcommands:
  files [<file>]             Structure of one file (default: all Python files)
  symbols <file>:<symbol>    Find symbol references
  base [<branch>]            Key impact vs base branch
  pr <number>                Impact analysis of a GitHub PR
  commit <sha>               Impact analysis of one commit
  uncommit                   Impact analysis of uncommitted changes
  dead-code [<root>]         Find unused functions
  commands [<cmd> <subcmd>]  Static analysis of CLI command structure

For project-level structure snapshots → use:
  vibe3 snapshot             (persistent structure tracking)

Examples:
  vibe3 inspect files src/vibe3/services/
  vibe3 inspect symbols src/vibe3/cli.py:app
  vibe3 inspect base main
```

**snapshot 概览示例**：

```
=== Snapshot: Project-level structure tracking ===

When to use snapshot:
  - Tracking project structure evolution (save points)
  - Comparing structure vs baseline / branches
  - Finding structural changes (module, dependency, LOC growth)

Subcommands:
  build [--branch]           Build current structure (memory only)
  save [--as-baseline]       Persist structure to .git/vibe3/structure/snapshots/
  list                       List all saved snapshots
  show [<snapshot-id>]       Show structure details
  diff [<baseline>]          Compare structure vs baseline

For single-file analysis → use:
  vibe3 inspect              (real-time file & change analysis)

Examples:
  vibe3 snapshot save
  vibe3 snapshot diff main
  vibe3 snapshot show
```

#### 3. 输出末尾添加"下一步"提示 — 半天

让单命令成为**协作链条的入口**，不是终点。每条命令末尾追加 `_suggest_next_steps()` helper。

| 命令 | 输出末尾建议 |
|------|-----------|
| `inspect base [branch]` | "→ Run `vibe3 snapshot diff` to see project-level structure changes" |
| `inspect files <file>` | "→ Run `vibe3 inspect symbols <file>:<func>` to see where this symbol is used" |
| `inspect symbols ...` | "→ Run `vibe3 inspect dead-code` if checking for unused code" |
| `inspect dead-code` | "→ Run `vibe3 inspect symbols <file>:<func>` to verify each finding" |
| `snapshot diff [base]` | "→ Run `vibe3 inspect base` for code-level impact in changed files" |
| `snapshot show [id]` | "→ Run `vibe3 inspect files <path>` for detailed file structure" |

**实现方式**：

```python
def _suggest_next_steps(context: str) -> None:
    """Print suggested next commands based on context."""
    suggestions = {
        "inspect_base": "→ vibe3 snapshot diff [base]  (see project-level changes)",
        "snapshot_diff": "→ vibe3 inspect base [base]  (see code-level impact)",
        # ... 其他建议
    }
    if context in suggestions:
        typer.echo(f"\n{suggestions[context]}")

# 支持 --quiet 关闭提示（兼容脚本调用）
_quiet: Annotated[bool, typer.Option("--quiet")] = False
if not _quiet:
    _suggest_next_steps("inspect_base")
```

#### 4. 改善 `inspect commands` 无参数输出 — 1 小时

不删除该命令，但让无参数时显示**真正有用的内容**。

**修改项**：[src/vibe3/commands/inspect.py:141-157](../../src/vibe3/commands/inspect.py:141)

```python
# BEFORE
if not command:
    names = _list_analyzable_top_level_commands()
    # ... 处理 json/yaml/tree/mermaid 格式 ...
    else:
        names_str = ", ".join(names)
        typer.echo(f"Available commands: {names_str}")  # ← 冗余输出
        return

# AFTER
if not command:
    names = _list_analyzable_top_level_commands()
    # ... 处理 json/yaml/tree/mermaid 格式 ...
    else:
        typer.echo("=== vibe3 command structure ===")
        typer.echo(f"Top-level commands: {', '.join(names)}")
        typer.echo()
        typer.echo("Use this command to inspect a specific call tree:")
        typer.echo("  vibe3 inspect commands pr show          # YAML format")
        typer.echo("  vibe3 inspect commands pr show --tree   # ASCII tree")
        typer.echo("  vibe3 inspect commands pr show --mermaid # Mermaid diagram")
        typer.echo()
        typer.echo("Examples:")
        typer.echo("  vibe3 inspect commands review")
        return
```

---

### Tier 2：建议做（2-3 天）

#### 5. 让 snapshot baseline 自动产生 — 1 天

当前 `snapshot diff` 缺基线就报错。让 baseline 在工作流入口处**自动产生**。

**修改项**：
- [skills/vibe-new/](../../skills/vibe-new/) - 分支创建时自动保存 snapshot
- Flow 创建钩子 - 同样保存 baseline

**实现**：

```bash
# 在 vibe-new 完成后
vibe3 snapshot save --as-baseline

# 这样后续 snapshot diff 永远有可用基线
vibe3 snapshot diff main   # 不再报错
```

**核心变更**：让 baseline 由系统自动管理，而非依赖用户手动触发。

#### 6. `inspect dead-code` 输出可执行验证命令 — 半天

当前每条 finding 只给文件:行号。改进为给出**验证命令**。

**修改项**：[src/vibe3/commands/inspect.py:175-200](../../src/vibe3/commands/inspect.py:175) (dead-code 子命令)

```python
# BEFORE
Finding:
  [HIGH] src/vibe3/domain/handlers/_shared.py:dispatch_request
         Unused function with 0 references

# AFTER
Finding:
  [HIGH] src/vibe3/domain/handlers/_shared.py:dispatch_request
         Unused function with 0 references
         
  Verify:
    vibe3 inspect symbols src/vibe3/domain/handlers/_shared.py:dispatch_request
  Context:
    vibe3 inspect files src/vibe3/domain/handlers/_shared.py
```

让 reviewer 一键验证，降低"是否真的是死代码"的验证成本。

#### 7. 在 review 输出中显式呈现协作 — 半天

当前 [roles/review.py](../../src/vibe3/roles/review.py) 同时调用两者但输出合并，用户感受不到协作。

**改进**：在 review 报告中明确分段呈现：

```
=== Review Report ===

1. PROJECT STRUCTURE CHANGES (via snapshot diff)
   └─ Files added: 2, Modified: 5, Deleted: 0
   └─ Dependencies added: 1
   └─ LOC change: +234, -45

2. CODE-LEVEL IMPACT (via inspect base)
   └─ Risk level: Medium
   └─ Key paths affected: 3
   └─ Symbols impacted: 7

💡 Tip: Run individually for deeper analysis:
  - vibe3 snapshot diff main    (more structure detail)
  - vibe3 inspect base main     (more impact detail)
```

让用户知道可以单独跑这两条命令获得更多信息。

---

### Tier 3：不做（明确拒绝）

| 原方案条目 | 拒绝理由 | 成本节省 |
|-----------|---------|--------|
| `files` → `structure` 重命名 | `structure` 是 snapshot 的语义，会破坏现有边界分工 | 避免迁移 4 个 skill 中的引用 |
| `base` → `diff` 重命名 | 与 `git diff` 混淆，不够清晰 | 避免引入模糊性 |
| 删除 `commands` | 带参数模式有真实价值（静态调用树分析），只是无参模式需改善 | 保留有价值功能 |
| 统一 `--format` 框架 | 投入产出不匹配：5-7 天开发 vs 边际收益低（各命令输出形式天然不同） | 避免 5-7 天 yak shaving |

---

## 验收清单

- [ ] `inspect symbols` 帮助文档与实现一致（两种模式）
- [ ] `vibe3 inspect` 不带参数显示概览，明确指向 snapshot 适用场景
- [ ] `vibe3 snapshot` 不带参数显示概览，明确指向 inspect 适用场景
- [ ] 6 个 inspect/snapshot 命令末尾追加"下一步"建议（支持 `--quiet` 关闭）
- [ ] `inspect commands` 无参数时显示用法示例而非冗余列表
- [ ] `inspect dead-code` 每条 finding 附带验证命令（verify 和 context）
- [ ] `/vibe-new` 创建分支时自动保存 snapshot baseline
- [ ] `review` 报告分段呈现"结构变化"和"代码影响"，提示用户可单独查询
- [ ] 所有现有测试通过，无命令重命名相关迁移
- [ ] 发布到 skills 中更新引用（无命令变更，只是帮助文档）

---

## 成本-收益对比

| 方案 | 投入 | 收益 | 破坏性 |
|------|------|------|--------|
| **原方案**（重命名 + 统一 format） | 9-14 天 | 语义优化（间接） | 高：4+ skills 迁移 |
| **本方案** Tier 1（必做） | 1-2 天 | **直接解决 4 个可用性问题** | 零：无命令变更 |
| **本方案** Tier 1+2 全做 | 3-5 天 | Tier 1 + 自动 baseline + 验证命令 | 零 |

**本方案的核心价值**：不改名、不删除，只通过**概览**、**下一步建议**、**自动工作流**让两个命令真正**可被发现、可被互补使用**。

---

## 后续

实施后，可收集用户反馈：

1. **发现性提升**："新用户是否更容易知道 inspect vs snapshot 的区别？"
2. **协作能力**："有多少用户现在在 review 外也会同时用这两条命令？"
3. **dead-code 流程**："验证命令是否降低了 reviewer 的确认成本？"
4. **snapshot baseline**："自动 baseline 是否提高了 snapshot 的使用频率？"

如果上述指标改善，可继续推进 Tier 2。如果 Tier 1 已足够，可暂停（避免过度工程化）。
