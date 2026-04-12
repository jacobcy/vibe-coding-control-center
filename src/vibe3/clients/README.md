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
| github_labels.py | GitHub issue label CRUD |
| github_issue_admin_ops.py | 关闭 issue 等管理操作 |
| ai_client.py | AI 调用（LiteLLM） |
| ai_suggestion_client.py | 面向 PR/文案建议的高层 AI 客户端 |
| serena_client.py | Serena 符号分析 |
| sqlite_client.py | SQLite 门面客户端（兼容现有调用） |
| sqlite_base.py | SQLite 连接管理与 schema 初始化 |
| sqlite_flow_state_repo.py | flow_state / flow_issue_links 持久化 |
| sqlite_event_repo.py | flow_events 持久化 |
| sqlite_session_repo.py | runtime_session 持久化 |
| sqlite_context_cache_repo.py | flow_context_cache 持久化 |
| protocols.py | 客户端接口协议 |

## 依赖关系

- 依赖: models, config, exceptions
- 被依赖: services, analysis, agents, commands, manager, orchestra
