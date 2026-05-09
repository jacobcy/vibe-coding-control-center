# UI

CLI 输出格式化层，使用 Rich 渲染 flow/task/PR 等状态展示。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| console.py | 11 | 共享 Rich Console 实例 |
| handoff_ui.py | 13 | Handoff 记录展示 |
| flow_ui_primitives.py | 69 | Flow UI 基础组件（status, actor, ref 解析） |
| pr_ui.py | 151 | PR 状态展示 |
| task_ui.py | 193 | Task 状态展示 |
| flow_ui.py | 303 | Flow 状态展示（表格模式） |
| flow_ui_timeline.py | 337 | Flow 时间线可视化 |

截至 2026-05，总计约 1077 行。

**注意**: ui 模块缺失 `__init__.py` 文件。

## 职责

- Rich Console 实例管理（agent-friendly，highlight=False）
- Flow 状态渲染（表格、时间线）
- PR 状态渲染
- Task 状态渲染
- Handoff 记录展示
- Orchestra 状态展示

## 关键组件

### console.py
提供共享 Rich Console 实例：
- `console`: 全局 Console 实例
- 配置为 agent-friendly（highlight=False）
- 被 UI 模块所有组件使用

### flow_ui_primitives.py
基础 UI 组件库：
- `status_text()`: 状态徽章渲染
- `display_actor()`: actor 名称格式化
- `kv()`: key-value 对渲染
- `resolve_ref_path()`: 引用路径解析

### flow_ui.py
Flow 状态表格展示：
- `display_flow_status()`: 渲染 flow 状态表格
- 显示 flow 元数据、步骤、状态
- 支持引用路径展示

### flow_ui_timeline.py
Flow 时间线可视化：
- `render_flow_timeline()`: 渲染 flow 事件时间线
- 显示事件序列、actor、时间戳
- 支持事件过滤

### task_ui.py
Task 状态展示：
- `display_task_status()`: 渲染 task 状态
- 显示 task 元数据、分支、issue
- 支持 comment 渲染

### pr_ui.py
PR 状态展示：
- `display_pr_status()`: 渲染 PR 状态
- 显示 PR 元数据、review 状态、检查结果

### handoff_ui.py
Handoff 记录展示：
- `display_handoff()`: 渲染 handoff 记录
- 支持文件内容展示

## 分层架构

```
ui/
├── console.py          # 基础层：共享 Console 实例
├── flow_ui_primitives.py  # 组件层：基础 UI 组件
└── 业务层：具体业务 UI
    ├── flow_ui.py
    ├── flow_ui_timeline.py
    ├── task_ui.py
    ├── pr_ui.py
    └── handoff_ui.py
```

依赖流向：业务层 → 组件层 → 基础层

## 依赖关系

```
ui/
├── console.py → （无内部依赖）
├── flow_ui_primitives.py → console
├── flow_ui.py → console, flow_ui_primitives, flow_ui_timeline, utils/path_helpers
├── flow_ui_timeline.py → console, flow_ui_primitives, models/flow, utils/path_helpers
├── task_ui.py → console, flow_ui_primitives, utils/constants, utils/path_helpers
├── pr_ui.py → console, models/pr
└── handoff_ui.py → console
```

**外部依赖**:
- rich: Rich 库
- vibe3.models: 数据模型（flow, pr）
- vibe3.utils.constants: 自动化标记常量
- vibe3.utils.path_helpers: 引用路径工具
- vibe3.services: 服务模块（signature_service, flow_classifier, spec_ref_service, task_service；部分为条件导入）
- vibe3.clients: 客户端模块（git_client，条件导入）
- vibe3.analysis: 分析模块（local_review_report，条件导入）

**被依赖**:
- commands/: 输出格式化

## 架构问题说明

### 缺失 __init__.py

**发现**: ui 模块没有 `__init__.py` 文件

**影响**: 不影响功能，但不符合 Python 模块规范

**处理**: 通过 handoff 记录此发现，不阻塞文档更新任务

**记录**: 已通过 handoff 记录此发现。
