# Structure Snapshot 系统设计方案

> **版本**: v0.1 初稿
> **日期**: 2026-03-21
> **状态**: 讨论中

---

## 1. 背景与问题

### 1.1 现状

我们有一个**单文件分析器**（`structure_service.py`），但缺少**项目级结构快照系统**。

**现有能力**：
- ✅ Python/Shell 文件 AST 分析
- ✅ 函数信息提取（name、line、LOC）
- ✅ 文件级依赖追踪（imports/imported_by）
- ✅ 项目级度量统计（`metrics_service.py`）
- ✅ 模块依赖图（`dag_service.py`）

**关键缺失**：
- ❌ 无持久化快照（snapshot）
- ❌ 无历史对比能力（diff）
- ❌ 无重复代码检测（duplication）
- ❌ 无模块级聚合（module-level metrics）

### 1.2 问题影响

- **无法追溯结构演变**：不知道代码结构随时间如何变化
- **无法发现重复实现**：跨模块的重复代码无法自动检测
- **Agent 缺少上下文**：无法为 AI 提供稳定的结构信息
- **Code Review 缺乏数据**：无法量化变更影响范围

---

## 2. 设计目标

参考 [OpenAI 建议稿](../../prds/structure-snapshow.md)，但结合现有代码实际：

### 2.1 核心目标

1. **持久化快照**：生成稳定的 `.structure/snapshot.json`
2. **模块聚合**：从文件级扩展到目录级（module）
3. **变更对比**：`structure diff A B` 对比两个快照
4. **重复检测**：Function Hash + Duplication Map

### 2.2 非目标（明确边界）

- ❌ Call Graph（调用图）
- ❌ 数据流分析
- ❌ 自动代码质量判断
- ❌ LLM 分析（这一层不做）

---

## 3. 命令归属讨论

### 3.1 两个选项

#### 选项A：扩展 `vibe3 inspect structure`

**理由**：
- 已经有 `vibe inspect structure <file>` 命令
- Inspect 的职责是"提供结构化信息"
- 符合现有的"信息提供层"定位

**问题**：
- 当前只支持单文件，扩展到项目级可能职责不清
- `inspect` 命令已经有 `metrics`、`symbols`、`commands` 等

**命令示例**：
```bash
vibe3 inspect structure              # 项目级快照（默认）
vibe3 inspect structure <file>       # 单文件分析（保留现有）
vibe3 inspect structure --build      # 生成快照
vibe3 inspect structure --show       # 查看快照
vibe3 inspect structure --diff A B   # 对比快照
```

#### 选项B：新建顶级命令 `vibe3 structure`

**理由**：
- Structure 是独立的能力域
- 有自己的生命周期（build/show/diff）
- 未来可能扩展更多子命令

**问题**：
- 命令数量增加
- 可能与 `inspect` 职责重叠

**命令示例**：
```bash
vibe3 structure build                # 生成快照
vibe3 structure show                 # 查看快照
vibe3 structure diff A B             # 对比快照
```

### 3.2 推荐方案

**推荐选项A：扩展 `vibe3 inspect structure`**

**理由**：
1. **职责清晰**：Inspect = 信息提供层，Structure = 结构信息
2. **最小变更**：已有命令，无需新建顶级命令
3. **语义一致**：`inspect structure` 和 `inspect metrics` 属于同一层
4. **向后兼容**：保留 `inspect structure <file>` 的单文件分析能力

**实现方式**：
```python
# src/vibe3/commands/inspect.py

@app.command()
def structure(
    file: Annotated[str, typer.Argument(help="File to analyze")] = "",
    build: Annotated[bool, typer.Option("--build", help="Build snapshot")] = False,
    show: Annotated[bool, typer.Option("--show", help="Show snapshot")] = False,
    diff: Annotated[bool, typer.Option("--diff", help="Diff snapshots")] = False,
    baseline: Annotated[str, typer.Option("--baseline", help="Baseline branch")] = "",
    json_out: _JSON_OPT = False,
    trace: _TRACE_OPT = False,
) -> None:
    """Show file structure or project snapshot.

    Examples:
        vibe3 inspect structure <file>          # Single file analysis
        vibe3 inspect structure --build         # Build project snapshot
        vibe3 inspect structure --show          # Show snapshot summary
        vibe3 inspect structure --diff main feature  # Diff branches
    """
    if trace:
        enable_trace()

    if file:
        # 现有逻辑：单文件分析
        result = structure_service.analyze_file(file)
        # ...
    elif build:
        # 新增：生成快照
        snapshot = structure_service.build_snapshot()
        # ...
    elif show:
        # 新增：查看快照
        snapshot = structure_service.load_snapshot()
        # ...
    elif diff:
        # 新增：对比快照
        diff_result = structure_service.diff_snapshots(baseline, "HEAD")
        # ...
    else:
        # 默认：项目级结构摘要
        results = []
        for p in Path("src/vibe3").glob("**/*.py"):
            # ...
```

---

## 4. 现有代码重构

### 4.1 职责重新划分

**问题**：现有 `structure_service.py` 名不副实，它只是"单文件分析器"，但名字叫"structure"太大了。

**解决方案**：拆分职责

```
file_analyzer.py (新)
  └─ 负责：单文件 AST 分析
     - analyze_python_file()
     - analyze_shell_file()
     - analyze_file()

structure_service.py (重新定义)
  └─ 负责：项目级结构快照
     - build_snapshot()     # 生成快照
     - load_snapshot()      # 加载快照
     - save_snapshot()      # 保存快照
     - diff_snapshots()     # 对比快照
     - aggregate_modules()  # 模块聚合（复用 file_analyzer）
```

### 4.2 重构步骤

**Step 1: 重命名现有文件**

```bash
# 现有文件降级
mv src/vibe3/services/structure_service.py \
   src/vibe3/services/file_analyzer.py
```

**Step 2: 更新类名**

```python
# src/vibe3/services/file_analyzer.py

class FileAnalysisError(VibeError):  # 原 StructureError
    """文件分析失败."""
    pass

class FileAnalysisResult(BaseModel):  # 原 FileStructure
    """文件分析结果."""
    path: str
    language: str
    total_loc: int
    functions: list[FunctionInfo]
    function_count: int
    imports: list[str] = []
    imported_by: list[str] = []
```

**Step 3: 新建真正的 structure_service.py**

```python
# src/vibe3/services/structure_service.py

from vibe3.services.file_analyzer import analyze_file
from vibe3.services.dag_service import build_module_graph
from vibe3.models.snapshot import Snapshot, ModuleInfo

class StructureService:
    """项目级结构快照服务."""

    def build_snapshot(self, root: Path) -> Snapshot:
        """构建项目快照."""
        # 1. 扫描所有文件（复用 file_analyzer）
        files = self._scan_files(root)
        file_results = [analyze_file(f) for f in files]

        # 2. 按模块聚合
        modules = self._aggregate_modules(file_results)

        # 3. 提取依赖关系（复用 dag_service）
        dependencies = build_module_graph()

        # 4. 计算函数 hash
        # ...

        return Snapshot(...)
```

**Step 4: 更新 CLI 调用**

```python
# src/vibe3/commands/inspect.py

# 单文件分析
from vibe3.services.file_analyzer import analyze_file

@app.command()
def structure(
    file: str = "",
    build: bool = False,
    # ...
):
    if file:
        # 单文件：调用 file_analyzer
        result = analyze_file(file)
    elif build:
        # 项目级：调用 structure_service
        from vibe3.services.structure_service import StructureService
        service = StructureService()
        snapshot = service.build_snapshot()
```

---

## 5. 数据模型设计

### 5.1 现有模型（迁移到 file_analyzer.py）

```python
# src/vibe3/services/file_analyzer.py

class FunctionInfo(BaseModel):
    name: str
    line: int
    loc: int

class FileAnalysisResult(BaseModel):  # 原 FileStructure
    path: str
    language: str
    total_loc: int
    functions: list[FunctionInfo]
    function_count: int
    imports: list[str] = []
    imported_by: list[str] = []
```

### 5.2 新增模型（structure_service.py）

```python
# src/vibe3/models/snapshot.py

class ModuleMetrics(BaseModel):
    """模块级度量（目录聚合）."""
    files: int
    loc: int
    functions: int


class ModuleInfo(BaseModel):
    """模块信息（一个目录）."""
    name: str  # 相对路径，如 "services/user"
    path: str  # 文件系统路径
    metrics: ModuleMetrics
    dependencies: list[str]  # 依赖的其他模块
    function_hashes: list[str]  # 模块内所有函数的 hash


class Snapshot(BaseModel):
    """项目级结构快照."""
    version: str = "1.0"
    timestamp: str  # ISO 8601
    branch: str
    commit: str

    # 全局统计
    global_metrics: ModuleMetrics

    # 模块列表
    modules: list[ModuleInfo]

    # 重复代码检测
    duplications: list[DuplicationInfo]


class DuplicationInfo(BaseModel):
    """重复代码信息."""
    hash: str  # Function hash
    count: int  # 出现次数
    modules: list[str]  # 在哪些模块中出现


class SnapshotDiff(BaseModel):
    """快照差异."""
    # 全局变化
    loc_change: int
    files_change: int
    modules_change: int

    # 模块级变化
    module_changes: dict[str, ModuleChange]

    # 重复代码变化
    duplication_changes: dict[str, DuplicationChange]

    # 依赖关系变化
    dependency_changes: list[DependencyChange]


class ModuleChange(BaseModel):
    """模块变化."""
    loc_change: int
    functions_change: int
    dependencies_added: list[str]
    dependencies_removed: list[str]


class DuplicationChange(BaseModel):
    """重复代码变化."""
    before: int
    after: int


class DependencyChange(BaseModel):
    """依赖关系变化."""
    module: str
    added: list[str]
    removed: list[str]
```

---

## 6. 服务层设计

### 6.1 文件分析服务（file_analyzer.py）

```python
# src/vibe3/services/file_analyzer.py

def analyze_file(file_path: str) -> FileAnalysisResult
def analyze_python_file(file_path: str) -> FileAnalysisResult
def analyze_shell_file(file_path: str) -> FileAnalysisResult
```

### 6.2 结构快照服务（structure_service.py）

```python
# src/vibe3/services/structure_service.py

class StructureService:
    """结构快照服务（项目级）."""

    def build_snapshot(self, root: Path = Path("src/vibe3")) -> Snapshot:
        """构建项目快照."""
        # 1. 扫描所有文件
        # 2. 按模块聚合
        # 3. 提取依赖关系（复用 dag_service）
        # 4. 计算函数 hash
        # 5. 构建重复代码映射
        # 6. 生成 snapshot.json

    def load_snapshot(self, path: Path = Path(".structure/snapshot.json")) -> Snapshot:
        """加载快照."""
        # 从文件加载 JSON

    def save_snapshot(self, snapshot: Snapshot, path: Path) -> None:
        """保存快照."""
        # 写入 JSON（保证稳定 key 顺序）

    def diff_snapshots(self, baseline: str, current: str) -> SnapshotDiff:
        """对比两个快照."""
        # 1. 加载 baseline snapshot
        # 2. 加载 current snapshot
        # 3. 对比差异
```

### 6.3 Function Hash 实现（简化版）

```python
# src/vibe3/services/function_hash.py

import ast
import hashlib

def compute_function_hash(node: ast.FunctionDef) -> str:
    """计算函数 hash（简化版：不 normalize）."""
    # MVP 阶段：直接 hash AST
    source = ast.unparse(node)
    return hashlib.sha256(source.encode()).hexdigest()[:8]

    # 完整版需要：
    # 1. Normalize AST（去变量名、常量值）
    # 2. 保留结构
    # 3. 计算 hash
```

---

## 7. 实施路径

### 7.1 MVP 第一阶段（最小可交付）

**目标**：基本快照能力

**任务**：
- [ ] 定义 Snapshot 模型
- [ ] 实现 `build_snapshot()` 基础版
- [ ] 实现模块聚合（目录级统计）
- [ ] 复用 `dag_service` 提取依赖关系
- [ ] 实现 `vibe3 inspect structure --build`

**产出**：
- 生成 `.structure/snapshot.json`
- 包含：全局统计 + 模块列表 + 依赖关系

### 7.2 MVP 第二阶段

**目标**：可视化与对比

**任务**：
- [ ] 实现 `vibe3 inspect structure --show`
- [ ] 实现 `vibe3 inspect structure --diff A B`
- [ ] 实现文本化输出（表格 + ASCII）
- [ ] 实现 JSON 输出（给 agent）

**产出**：
- `structure show` 输出结构摘要
- `structure diff` 输出变更摘要

### 7.3 完整版

**目标**：重复检测

**任务**：
- [ ] 实现函数 hash（简化版）
- [ ] 构建重复代码映射
- [ ] 在 snapshot 中包含 duplication 信息
- [ ] 在 diff 中输出重复代码变化

**产出**：
- 自动检测重复代码
- 跨模块重复警告

---

## 8. 现有代码复用

### 8.1 直接复用

| 能力 | 服务 | 说明 |
|------|------|------|
| 文件分析 | `file_analyzer.analyze_file()` | 已有（重构后）|
| 依赖图 | `dag_service.build_module_graph()` | 已有 |
| 项目度量 | `metrics_service.collect_metrics()` | 已有 |

### 8.2 扩展点

| 能力 | 现有 | 需要新增 |
|------|------|---------|
| 模块定义 | 无 | `ModuleInfo` 模型 |
| 模块聚合 | 无 | 按目录聚合文件级数据 |
| 快照持久化 | 无 | `SnapshotService` |
| 变更对比 | 无 | `diff_snapshots()` |
| 函数 hash | 无 | `compute_function_hash()` |

---

## 9. 与 Agent 集成

### 9.1 输入给 Agent

```json
{
  "snapshot": ".structure/snapshot.json",
  "diff": ".structure/diff.json"  // 可选
}
```

### 9.2 Agent 职责

- 是否需要重构
- 是否重复实现
- 是否结构异常
- 是否依赖过重

### 9.3 示例场景

**场景1：Code Review**
```bash
# 生成当前分支快照
vibe3 inspect structure --build

# 对比 main 分支
vibe3 inspect structure --diff main HEAD

# Agent 消费 diff.json
vibe3 review base --use-structure-diff
```

**场景2：重复代码检测**
```bash
# 构建快照（包含 duplication）
vibe3 inspect structure --build

# 查看重复代码
vibe3 inspect structure --show | grep Duplication

# Agent 分析
vibe3 review structure --focus-duplication
```

---

## 10. 开放问题

### 10.1 模块定义

**问题**：什么算一个"模块"？

**选项**：
- A. 所有有代码的目录
- B. 忽略 `__tests__`、`test`、`tests` 目录
- C. 只统计 `src/vibe3` 下的目录

**建议**：选项 B（与 OpenAI 建议稿一致）

### 10.2 快照存储位置

**问题**：`.structure/snapshot.json` 是否提交到 git？

**选项**：
- A. 提交（作为项目元数据）
- B. 不提交（临时文件，`.gitignore`）
- C. 用户选择

**建议**：选项 B（不提交），理由：
- 快照是派生数据，可以从代码重新生成
- 避免合并冲突
- CI/CD 中按需生成

### 10.3 Function Hash 复杂度

**问题**：MVP 阶段要不要 normalize AST？

**选项**：
- A. 直接 hash AST（简化版）
- B. Normalize 后 hash（完整版）

**建议**：选项 A（简化版），理由：
- 快速上线
- 后续迭代优化
- 即使不 normalize 也有价值（检测完全相同的代码）

---

## 11. 参考文档

- [OpenAI 建议稿](../../prds/structure-snapshow.md)
- [现有 structure_service.py](../../../src/vibe3/services/structure_service.py)
- [现有 dag_service.py](../../../src/vibe3/services/dag_service.py)
- [现有 metrics_service.py](../../../src/vibe3/services/metrics_service.py)