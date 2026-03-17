# 调用链路追踪 vs DAG 模块依赖

> **关键区别**: 一个是运行时调用链，一个是静态依赖图

---

## 1. 调用链路追踪 (Call Tracing)

### 1.1 定义

**运行时**的方法调用链路，记录程序执行过程中调用了哪些方法。

### 1.2 示例

```bash
vibe inspect pr 42 --debug
```

**输出**:
```
vibe inspect pr 42
└─ commands/inspect.py::pr()
   └─ services/serena_service.py::analyze_changes()
      └─ clients/git_client.py::get_changed_files()
         └─ subprocess.run("gh pr diff 42 --name-only")
      └─ services/serena_service.py::analyze_files()
         └─ clients/serena_client.py::get_symbols_overview()
```

### 1.3 用途

- **调试**: 看清楚命令执行了哪些代码
- **错误排查**: 定位哪个文件、哪个方法出错
- **性能分析**: 看到每个步骤的耗时

### 1.4 时效性

- **运行时**: 每次执行命令时生成
- **动态**: 不同的输入可能有不同的调用链

---

## 2. DAG 模块依赖 (Module Dependency Graph)

### 2.1 定义

**静态**的模块依赖关系，分析代码文件之间的 import 关系。

### 2.2 示例

**场景**: PR 改动了 `lib/flow.sh`

**DAG 分析**:
```python
# dag.json
{
  "changed_files": ["lib/flow.sh"],
  "impacted_modules": [
    "bin/",           # bin/vibe 依赖 lib/flow.sh
    "lib/flow/",      # 其他 flow 模块依赖 flow.sh
    "lib/github/",    # github 模块调用 flow
    "lib/git/"        # git 模块调用 flow
  ],
  "dependency_graph": {
    "bin/": ["lib/flow"],
    "lib/flow/": ["lib/flow"],
    "lib/github/": ["lib/flow"],
    "lib/git/": ["lib/flow"]
  }
}
```

### 2.3 用途

- **影响范围分析**: 改动 `flow.sh` 会影响哪些模块
- **风险评分**: 改动影响了多少模块（影响越大风险越高）
- **上下文收窄**: 只审核受影响的模块，不审核全仓库

### 2.4 时效性

- **静态**: 分析代码文件的 import 语句
- **相对稳定**: 只要代码不变，依赖关系就不变

---

## 3. 核心区别对比

| 维度 | 调用链路追踪 | DAG 模块依赖 |
|------|------------|-------------|
| **类型** | 运行时调用链 | 静态依赖图 |
| **分析对象** | 方法调用（函数级别） | 模块依赖（文件级别） |
| **时效性** | 动态（每次执行生成） | 静态（代码结构决定） |
| **用途** | 调试、错误排查 | 影响范围分析、风险评分 |
| **输出** | 调用栈日志 | 模块依赖图 JSON |
| **示例** | `inspect.py::pr()` 调用 `serena.analyze_changes()` | `bin/` 依赖 `lib/flow` |
| **Phase** | Phase 1（调试支持） | Phase 1（风险评分基础） |

---

## 4. 实际应用场景对比

### 4.1 调用链路追踪场景

**场景**: `vibe inspect pr 42` 报错

**用户执行**:
```bash
vibe inspect pr 42 --debug
```

**日志输出**:
```
2026-03-17 08:00:00.003 | ERROR | vibe3.clients.git_client:get_changed_files:48 - Git 操作失败
    domain: git
    action: get_changed_files
    error_type: CalledProcessError
    command: gh pr diff 42 --name-only
    exit_code: 1

Traceback (most recent call last):
  File "src/vibe3/clients/git_client.py", line 45, in get_changed_files
    ...
```

**作用**: 清楚看到 `git_client.py` 的 `get_changed_files()` 方法出错了。

---

### 4.2 DAG 模块依赖场景

**场景**: PR 改动了 `lib/flow.sh`，需要评估风险

**DAG 分析流程**:
```
1. 改动文件: lib/flow.sh
   ↓
2. 分析 import/依赖关系
   - bin/vibe imports lib/flow.sh
   - lib/github/ calls lib/flow functions
   - lib/git/ calls lib/flow functions
   ↓
3. 构建影响模块列表
   impacted_modules = ["bin/", "lib/flow/", "lib/github/", "lib/git/"]
   ↓
4. 风险评分
   - 影响了 4 个模块 → MEDIUM 风险
   - 触及关键路径 → +2 分
   - 总分 5 → MEDIUM 风险
```

**作用**: 知道改动影响了哪些模块，风险多大。

---

## 5. Phase 2 中的协作关系

**完整流程**:
```bash
vibe review pr 42
  ↓
1. vibe inspect pr 42  # 调用链路追踪可调试这一步
  ↓
2. serena_service → impact.json  # 改动了哪些符号
  ↓
3. dag_service → dag.json  # 模块依赖分析
  ↓
4. pr_scoring_service → score.json  # 风险评分
  ↓
5. codex review  # 只审核受影响的模块
```

**两者作用**:
- **调用链路追踪**: 帮助调试步骤 1-5 的执行过程
- **DAG 模块依赖**: 步骤 3 的核心，用于影响范围分析和风险评分

---

## 6. 具体实现对比

### 6.1 调用链路追踪实现

**位置**: Phase 1 每个 Client/Service 方法中

```python
# clients/git_client.py
def get_changed_files(self, source: ChangeSource) -> list[str]:
    """获取改动文件列表"""
    logger.bind(
        domain="git",
        action="get_changed_files"
    ).info("获取改动文件")

    # 执行 git 命令
    result = subprocess.run(...)
    return result.stdout.split("\n")
```

**特点**: 通过日志记录方法调用。

---

### 6.2 DAG 模块依赖实现

**位置**: `services/dag_service.py`（Phase 1 新增）

```python
# services/dag_service.py
import ast
from pathlib import Path

def build_module_graph() -> dict[str, set[str]]:
    """构建模块依赖图"""
    graph = {}

    for py_file in Path(".").rglob("*.py"):
        # 解析 import 语句
        tree = ast.parse(py_file.read_text())
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.append(node.names[0].name)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)

        graph[py_file.stem] = imports

    return graph

def expand_impacted_modules(seed_files: list[str], graph: dict) -> list[str]:
    """扩展影响模块"""
    # 从种子文件出发，找出所有依赖它们的上游模块
    impacted = set()
    for seed in seed_files:
        for module, deps in graph.items():
            if seed in deps:
                impacted.add(module)
    return list(impacted)
```

**特点**: 通过 AST 解析分析静态依赖关系。

---

## 7. 总结

| 概念 | 问题 | 答案 |
|------|------|------|
| **调用链路追踪** | "我的命令执行了哪些代码？" | 运行时方法调用链 |
| **DAG 模块依赖** | "我的改动影响了哪些模块？" | 静态依赖关系图 |

**关系**:
- 调用链路追踪 = 调试工具（我刚才补充的）
- DAG 模块依赖 = 影响分析工具（Phase 1 原计划）

**Phase 1 都需要实现**，但用途完全不同。