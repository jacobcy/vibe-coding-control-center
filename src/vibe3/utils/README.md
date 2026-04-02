# Utils

通用工具函数，提供 branch 解析、issue 引用解析、git 路径计算等基础能力。

## 关键组件

| 文件 | 职责 |
|------|------|
| branch_utils.py | Branch 名称解析与验证 |
| git_helpers.py | Git 目录和 handoff 路径计算 |
| issue_ref.py | Issue 引用解析（#123, owner/repo#123） |
| trace.py | Trace 工具函数 |

## 依赖关系

- 依赖: (无内部依赖)
- 被依赖: services, commands, clients
