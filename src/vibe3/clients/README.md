# Clients

外部系统客户端层，为 Git, GitHub, AI, Serena, SQLite 提供最小包装。

## 职责

- Git 操作（branch, diff, status, worktree）
- GitHub API（PR, issue, review, comment）
- AI 文本生成（LiteLLM 多模型支持）
- Serena 符号查询
- SQLite 本地状态持久化

## 关键组件

| 文件 | 职责 |
|------|------|
| git_client.py | Git 操作主入口 |
| git_branch_ops.py | 分支操作 |
| git_diff_hunks.py | Diff 解析 |
| git_status_ops.py | Status 查询 |
| git_worktree_ops.py | Worktree 操作 |
| github_client.py | GitHub API 主入口 |
| github_client_base.py | GitHub 基础客户端 |
| github_pr_ops.py | PR 操作 |
| github_issues_ops.py | Issue 操作 |
| github_review_ops.py | Review 操作 |
| ai_client.py | AI 调用（LiteLLM） |
| serena_client.py | Serena 符号分析 |
| sqlite_client.py | SQLite 持久化 |
| protocols.py | 客户端接口协议 |

## 依赖关系

- 依赖: models, config, exceptions
- 被依赖: services, analysis, agents, commands, manager, orchestra
