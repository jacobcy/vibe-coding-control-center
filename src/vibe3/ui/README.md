# UI

CLI 输出格式化层，使用 Rich 渲染 flow/task/PR 等状态展示。

## 职责

- Rich Console 实例管理（agent-friendly，highlight=False）
- Flow 状态渲染（表格、时间线）
- PR 状态渲染
- Task 状态渲染
- Handoff 记录展示
- Orchestra 状态展示

## 关键组件

| 文件 | 职责 |
|------|------|
| console.py | 共享 Rich Console 实例 |
| flow_ui.py | Flow 状态展示 |
| flow_ui_timeline.py | Flow 时间线可视化 |
| pr_ui.py | PR 状态展示 |
| task_ui.py | Task 状态展示 |
| handoff_ui.py | Handoff 记录展示 |
| orchestra_ui.py | Orchestra 状态展示 |

## 依赖关系

- 依赖: models (渲染数据结构)
- 被依赖: commands (输出格式化)
