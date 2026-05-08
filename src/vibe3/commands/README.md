# Commands

CLI 子命令实现层，每个文件对应一个 `vibe3 <cmd>` 子命令。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| status.py | 464 | 全局状态面板、系统健康检查 |
| task.py | 425 | Task 绑定、查询、comments 展示 |
| pr_query.py | 403 | PR 查询、列表、状态展示 |
| snapshot.py | 364 | 代码结构快照、baseline 管理、diff 对比 |
| flow.py | 356 | Flow 命令入口、子命令注册 |
| flow_status.py | 338 | Flow 状态展示、transition 查询 |
| inspect.py | 318 | Inspect 命令入口、子命令注册 |
| handoff_write.py | 298 | Handoff 写入、append/report |
| review.py | 289 | Review 命令、review 执行入口 |
| handoff_render.py | 269 | Handoff 渲染、模板处理 |
| run.py | 247 | Run 命令、agent 执行入口 |
| plan.py | 237 | Plan 命令、plan 生成入口 |
| pr_create.py | 223 | PR 创建、标题/模板处理 |
| check_support.py | 218 | Check 支持、mode 实现 |
| handoff_read.py | 213 | Handoff 读取、show/status |
| inspect_base_helpers.py | 196 | Inspect base 辅助函数 |
| check.py | 155 | Check 命令、环境检查 |
| inspect_symbols.py | 150 | Inspect symbols 子命令 |
| inspect_base.py | 150 | Inspect base 子命令 |
| inspect_change.py | 147 | Inspect change 子命令 |
| pr_lifecycle.py | 136 | PR 生命周期、状态管理 |
| output_format.py | 129 | 输出格式化、JSON/文本转换 |
| pr_quality_gates.py | 115 | PR 质量门控、检查逻辑 |
| internal.py | 111 | Internal 命令、内部工具 |
| flow_lifecycle.py | 109 | Flow 生命周期、状态切换 |
| inspect_helpers.py | 73 | Inspect 辅助函数 |
| command_options.py | 65 | 命令选项定义、公共参数 |
| common.py | 56 | 公共辅助函数、trace_scope |
| handoff.py | 31 | Handoff 命令入口 |
| pr.py | 29 | PR 命令入口 |
| __init__.py | 25 | 空文件（无公共导出） |
| pr_helpers.py | 17 | PR 辅助函数 |
| inspect_pr_helpers.py | 16 | Inspect PR 辅助函数 |

**总计**: 33 文件，6372 行代码

## 命令分组

### Flow 管理（3 文件，803 行）
- **flow.py**: Flow 命令入口，注册子命令
- **flow_lifecycle.py**: Flow 生命周期管理（claim、start、complete、archive）
- **flow_status.py**: Flow 状态展示、transition 查询

### Task 管理（1 文件，425 行）
- **task.py**: Task 绑定、查询、issue comments 展示

### PR 管理（6 文件，923 行）
- **pr.py**: PR 命令入口
- **pr_create.py**: PR 创建、标题/模板处理
- **pr_lifecycle.py**: PR 生命周期、状态管理
- **pr_query.py**: PR 查询、列表、状态展示
- **pr_quality_gates.py**: PR 质量门控、检查逻辑
- **pr_helpers.py**: PR 辅助函数

### Review 管理（1 文件，289 行）
- **review.py**: Review 命令入口、review 执行

### Inspect 分析（6 文件，977 行）
- **inspect.py**: Inspect 命令入口，注册子命令
- **inspect_base.py**: Inspect base 子命令（分支对比）
- **inspect_symbols.py**: Inspect symbols 子命令（符号分析）
- **inspect_change.py**: Inspect change 子命令（变更分析）
- **inspect_base_helpers.py**: Base 分析辅助函数
- **inspect_pr_helpers.py**: PR 分析辅助函数

### Handoff 管理（4 文件，811 行）
- **handoff.py**: Handoff 命令入口
- **handoff_read.py**: Handoff 读取（show、status）
- **handoff_write.py**: Handoff 写入（append、report）
- **handoff_render.py**: Handoff 渲染、模板处理

### Plan/Run 执行（2 文件，484 行）
- **plan.py**: Plan 命令入口
- **run.py**: Run 命令入口

### Snapshot 管理（1 文件，364 行）
- **snapshot.py**: 代码结构快照、baseline 管理、diff 对比

### 状态与检查（3 文件，837 行）
- **status.py**: 全局状态面板、系统健康检查
- **check.py**: Check 命令入口
- **check_support.py**: Check mode 实现

### 辅助模块（5 文件，434 行）
- **common.py**: 公共辅助函数（trace_scope、run_full_check_shortcut）
- **command_options.py**: 命令选项定义、公共参数
- **output_format.py**: 输出格式化（JSON、文本转换）
- **inspect_helpers.py**: Inspect 辅助函数
- **internal.py**: Internal 命令、内部工具

## 架构说明

### Typer 命令注册模式

Commands 模块采用 Typer 框架的命令注册模式：

```python
# 主入口（cli.py）
app = typer.Typer()
app.add_typer(flow_app, name="flow")
app.add_typer(inspect_app, name="inspect")

# 子命令入口（flow.py）
flow_app = typer.Typer()

@flow_app.command("claim")
def claim_command(...):
    ...
```

**设计特点**:
- 每个命令组有独立的 Typer app 实例
- 入口文件（flow.py、inspect.py）负责子命令注册
- 实现文件（flow_lifecycle.py、inspect_base.py）提供具体功能

### Helper 层次结构

Commands 模块有清晰的 helper 层次：

```
命令实现 → 辅助函数 → 共享工具
│          │          │
│          └─► inspect_base_helpers.py
│          └─► pr_helpers.py
│          └─► common.py
│
└─► command_options.py (参数定义)
└─► output_format.py (格式化)
```

**依赖模式**:
- `check.py` → `check_support.py`
- `flow.py`, `flow_lifecycle.py`, `flow_status.py` → `common.py`
- `inspect_base.py` → `inspect_base_helpers.py`
- `inspect_helpers.py` → `inspect_pr_helpers.py`
- `pr_create.py`, `pr_lifecycle.py` → `pr_helpers.py`

## 内部依赖

```
commands/
├── 命令入口层（无内部依赖）
│   ├── task.py
│   ├── review.py
│   ├── plan.py
│   ├── run.py
│   ├── snapshot.py
│   ├── status.py
│   └── internal.py
├── 命令组入口（注册子命令）
│   ├── flow.py → flow_lifecycle.py, flow_status.py
│   ├── handoff.py → handoff_read.py, handoff_write.py
│   ├── inspect.py → inspect_base.py, inspect_symbols.py, inspect_change.py
│   └── pr.py → pr_create.py, pr_lifecycle.py, pr_query.py
├── 实现层（依赖 helpers）
│   ├── check.py → check_support.py
│   ├── flow_lifecycle.py → common.py
│   ├── flow_status.py → common.py
│   ├── handoff_read.py → common.py
│   ├── handoff_write.py → common.py
│   ├── inspect_base.py → inspect_base_helpers.py
│   ├── inspect_helpers.py → inspect_pr_helpers.py
│   ├── pr_create.py → pr_helpers.py
│   ├── pr_lifecycle.py → pr_helpers.py
│   ├── pr_query.py → output_format.py
│   ├── plan.py → command_options.py
│   ├── review.py → command_options.py
│   └── run.py → command_options.py
└── 辅助层（无依赖）
    ├── command_options.py
    ├── output_format.py
    ├── check_support.py
    ├── inspect_base_helpers.py
    ├── inspect_pr_helpers.py
    ├── pr_helpers.py
    ├── pr_quality_gates.py
    ├── handoff_render.py
    └── common.py (trace_scope)
```

**循环依赖检查**: ✅ 无循环依赖

**设计原则**: Commands 模块只负责参数解析和输出格式化，业务逻辑在 services 层实现。

## 外部依赖

- **services/**: FlowService, PRService, ReviewService, SnapshotService 等
- **models/**: FlowState, PR, ReviewRequest 等
- **analysis/**: 代码分析服务
- **agents/**: AgentOptions, AgentResult
- **ui/**: 输出格式化、终端渲染
- **config/**: VibeConfig

## 被依赖

- **cli.py**: 命令注册入口
