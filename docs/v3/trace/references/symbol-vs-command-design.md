# 命令设计提案：符号 vs 命令结构

> **提案目标**：规范语义，方便使用和记忆，不会用错

---

## 核心问题

### 语义混淆

当前文档中 `--symbols` 有两个完全不同的含义：

| 使用场景 | 分析对象 | 输出内容 | 文档位置 |
|---------|---------|---------|---------|
| **代码符号分析** | 用户代码文件 | 函数、类、变量列表 | phase1:559 |
| **命令结构查看** | vibe CLI 命令 | 函数调用链路（AST） | phase2:56 |

**问题**：同一个词有两个含义，违背"一词一义"原则，容易用错。

---

## 概念澄清

### 两个概念的本质区别

#### 概念1：代码符号分析

**分析对象**：用户代码文件（如 `lib/flow.sh`、`services/review.py`）

**输出内容**：
- 函数定义（`def analyze()`）
- 类定义（`class ReviewService`）
- 变量引用关系
- 跨文件引用（哪些文件调用了这个函数）

**底层服务**：`serena_service`（Serena 提供符号分析能力）

**用户场景**：
```bash
# "我想看 flow.sh 定义了哪些函数"
vibe inspect symbols lib/flow.sh
```

---

#### 概念2：命令结构查看

**分析对象**：vibe CLI 命令系统（如 `vibe review pr`）

**输出内容**：
- 命令的函数调用链路
- AST 解析的静态结构
- 不执行命令，只分析代码结构

**底层服务**：`command_analyzer`（需要从 `symbol_analyzer` 重命名）

**用户场景**：
```bash
# "我想知道 vibe review pr 调用了哪些文件"
vibe inspect commands review pr
```

---

## 设计原则

### 1. 一词一义

**原则**：每个术语只有一个明确的含义

**应用**：
- ✅ "符号"（symbol）专指代码符号（函数、类、变量）
- ✅ "命令"（command）专指 vibe CLI 命令
- ✅ "结构"（structure）专指文件/模块结构

**违反原则的例子**：
```bash
# ❌ 错误设计
vibe inspect --symbols              # 看代码符号？
vibe inspect --symbols review pr    # 还是看命令结构？
```

---

### 2. 符合行业标准

**编程领域标准语义**：

| 术语 | 标准含义 | 业界工具 |
|------|---------|---------|
| **symbol** | 函数名、类名、变量名 | LSP, ctags, Serena |
| **call tree** | 函数调用关系 | gprof, callgrind |
| **AST** | 抽象语法树 | 编译器、代码分析工具 |

**应用**：
```bash
# ✅ 符合标准
vibe inspect symbols lib/flow.sh    # 符号 = 代码符号

# ✅ 符合标准
vibe inspect commands review pr     # 查看命令的调用关系
```

---

### 3. 子命令模式

**原则**：名词作子命令，选项作修饰

**业界标准对比**：

| 工具 | 设计模式 | 示例 |
|------|---------|------|
| git | 名词作子命令 | `git status`, `git log`, `git branch` |
| gh | 名词作子命令 | `gh pr list`, `gh pr view 42` |
| docker | 名词作子命令 | `docker ps`, `docker images` |

**应用**：
```bash
# ✅ 子命令模式（推荐）
vibe inspect metrics        # 子命令
vibe inspect structure      # 子命令
vibe inspect symbols        # 子命令
vibe inspect commands       # 子命令

# ❌ 选项作子命令（反模式）
vibe inspect --metrics      # 选项当作子命令用
vibe inspect --structure    # 选项当作子命令用
```

---

## 最终设计方案

### 命令体系

#### `vibe inspect` - 信息查看命令

**职责**：提供静态信息，不执行命令

**子命令列表**：

```bash
# 仓库整体信息
vibe inspect                    # 综合信息（默认显示摘要）
vibe inspect metrics            # 代码量指标
vibe inspect structure          # 文件结构

# 代码分析
vibe inspect symbols [file]     # 代码符号分析（默认：当前目录）
vibe inspect symbols lib/flow.sh  # 分析指定文件的符号

# 命令系统
vibe inspect commands           # 列出所有 vibe 命令
vibe inspect commands review    # 列出 review 的子命令
vibe inspect commands review pr # 查看 review pr 的静态结构

# Git 改动分析
vibe inspect pr 42              # PR 改动分析
vibe inspect commit SHA         # Commit 改动分析
vibe inspect base main          # 相对分支的改动分析
```

**选项**：
- `--json` - JSON 输出格式
- `--trace` - 调用链路追踪 + DEBUG 日志

---

#### `vibe review` - 代码审核命令

**职责**：执行代码审核，发现问题

**子命令列表**：

```bash
vibe review pr 42              # 审核 PR
vibe review pr 42 --trace      # 审核 PR 并追踪执行过程
vibe review --uncommitted      # 审核未提交改动
vibe review base main          # 审核相对分支的改动
vibe review commit SHA         # 审核指定 commit
```

**选项**：
- `--trace` - 调用链路追踪 + DEBUG 日志（运行时）
- `--json` - JSON 输出格式

---

### 服务命名

| 服务名称 | 职责 | 分析对象 | 文件名 |
|---------|------|---------|--------|
| **metrics_service** | 代码量分析 | 仓库 | `services/metrics_service.py` |
| **structure_service** | 文件结构分析 | 仓库 | `services/structure_service.py` |
| **serena_service** | 代码符号分析 | 代码文件 | `services/serena_service.py` |
| **command_analyzer** | 命令调用链路分析 | vibe 命令 | `services/command_analyzer.py` |
| **dag_service** | 模块依赖图分析 | 仓库 | `services/dag_service.py` |
| **pr_scoring_service** | 风险评分 | Git 改动 | `services/pr_scoring_service.py` |

**关键变更**：
- ❌ `symbol_analyzer` → ✅ `command_analyzer`（避免与 Serena 符号分析混淆）

---

### 语义规范

| 术语 | 定义 | 示例 |
|------|------|------|
| **符号**（symbol） | 代码中的函数名、类名、变量名 | `flow.sh:42` 定义的 `check_status()` 函数 |
| **命令**（command） | vibe CLI 的命令 | `vibe review pr`、`vibe inspect` |
| **结构**（structure） | 文件和模块的组织方式 | 目录树、模块划分 |
| **调用链路**（call tree） | 函数之间的调用关系 | `review.py::pr()` 调用 `serena.analyze_changes()` |

---

## 用户标准落实

### 标准：`vibe inspect` 静态检查 vs `vibe <command> --trace` 动态追踪

#### ✅ `vibe inspect` 静态检查

**特点**：
- 不执行命令
- 只分析代码结构
- 快速、安全

**示例**：
```bash
# 静态查看代码符号
vibe inspect symbols lib/flow.sh

# 静态查看命令结构（不执行命令）
vibe inspect commands review pr
```

---

#### ✅ `vibe <command> --trace` 动态追踪

**特点**：
- 实际执行命令
- 记录运行时调用链路
- 包含参数、返回值、错误位置

**示例**：
```bash
# 执行 review pr 并追踪
vibe review pr 42 --trace
```

**输出示例**：
```
commands/review.py::pr(pr_number=42)
  ├─ clients/git_client.py::get_diff(source=PRSource(42))
  │  └─ ✓ return: 234 lines
  ├─ services/serena_service.py::analyze_changes(...)
  │  └─ ✓ return: impact.json
  ❌ ERROR in subprocess.run("codex review")
```

---

## 对比分析

### 新设计 vs 旧设计

| 维度 | 旧设计 | 新设计 | 改进 |
|------|--------|--------|------|
| **语义清晰** | ❌ `--symbols` 有两个含义 | ✅ `symbols` 和 `commands` 分离 | 一词一义 |
| **命令模式** | ❌ 选项作子命令用 | ✅ 子命令模式 | 符合业界标准 |
| **记忆负担** | 🟡 需要记住选项 | ✅ 名词作子命令，直觉化 | 易于记忆 |
| **不会用错** | ❌ 容易混淆 | ✅ 职责清晰，参数明确 | 降低错误 |
| **代码实现** | ❌ 参数定义困难 | ✅ 每个子命令独立 | 易于维护 |
| **可发现性** | 🟡 需要 --help 才能看到 | ✅ 子命令列表清晰 | 易于探索 |

---

## 实施建议

### Phase 1 修正

**文件**：`docs/v3/trace/phase1-infrastructure.md`

**修正内容**：

1. **第 261-281 行**：重命名服务
   ```markdown
   ### 6. 命令调用链路分析服务（Command Analyzer）

   **目标**: 提供命令的静态结构分析，支持代码学习和调试

   **位置**: `services/command_analyzer.py`

   **使用场景**:
   vibe inspect commands review pr  # 查看 vibe review pr 的静态调用链路
   ```

2. **第 559 行**：明确 symbols 的职责
   ```markdown
   - `vibe inspect symbols [file]` - 代码符号分析（调用 serena_service）
   ```

---

### Phase 2 修正

**文件**：`docs/v3/trace/phase2-integration.md`

**修正内容**：

1. **第 47-68 行**：改为子命令模式
   ```markdown
   **位置**: `commands/inspect.py`

   **子命令列表**:
   - `vibe inspect` - 综合信息展示
   - `vibe inspect metrics` - 显示代码量指标
   - `vibe inspect structure` - 显示文件结构分析
   - `vibe inspect symbols [file]` - 代码符号分析
   - `vibe inspect commands [cmd]` - 命令结构查看
   - `vibe inspect pr <number>` - PR 改动分析
   ```

2. **实现代码**：改为子命令模式
   ```python
   import typer

   app = typer.Typer()

   @app.command()
   def metrics():
       """Show code metrics"""
       data = metrics_service.collect_metrics()
       typer.echo(data)

   @app.command()
   def structure():
       """Show file structure"""
       data = structure_service.analyze()
       typer.echo(data)

   @app.command()
   def symbols(file: str = "."):
       """Show code symbols"""
       data = serena_service.analyze_file(file)
       typer.echo(data)

   @app.command()
   def commands(command: str = "", subcommand: str = ""):
       """Show vibe command structure"""
       if not command:
           _list_all_commands()
       else:
           tree = command_analyzer.analyze(command, subcommand)
           _print_tree(tree)
   ```

---

### 服务重命名

**文件**：`services/command_analyzer.py`（原 `symbol_analyzer.py`）

**修改内容**：
```python
# 重命名服务
class CommandAnalyzer:
    """Service for analyzing command call structure"""

    def analyze_command(self, command: str, subcommand: str = "") -> CallTree:
        """Analyze command static call structure (AST-based)

        Args:
            command: Command name (e.g., "review")
            subcommand: Subcommand name (e.g., "pr")

        Returns:
            Call tree structure
        """
        # AST 解析实现
        pass
```

---

## 总结

### 设计原则

| 原则 | 说明 |
|------|------|
| ✅ 一词一义 | 每个术语只有一个明确含义 |
| ✅ 符合标准 | 遵循编程领域和业界标准 |
| ✅ 子命令模式 | 名词作子命令，符合直觉 |
| ✅ 易于记忆 | 层次清晰，语义规范 |
| ✅ 不会用错 | 职责独立，参数明确 |

### 最终方案

**命令设计**：
```bash
vibe inspect symbols [file]     # 代码符号（函数/类/变量）
vibe inspect commands [cmd]     # 命令结构（AST 调用树）
vibe review pr 42 --trace       # 运行时追踪
```

**服务命名**：
- `serena_service` - 代码符号分析
- `command_analyzer` - 命令调用链路分析

**用户标准落实**：
- ✅ `vibe inspect` 静态检查
- ✅ `vibe <command> --trace` 动态追踪

**优势**：
- 语义清晰，不会用错
- 符合业界标准
- 易于记忆和使用
- 代码实现清晰