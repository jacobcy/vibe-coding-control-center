# Clients

外部系统客户端层，为 Git, GitHub, AI, Serena, SQLite 提供最小包装。

## 职责

- Git 操作（branch, diff, status, worktree）
- GitHub API（PR, issue, review, comment）
- AI 文本生成（LiteLLM 多模型支持）
- Serena 符号查询
- SQLite 本地状态持久化

## 文件列表

统计时间：2026-05-02

### Git 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| git_client.py | 415 | Git 操作主入口 |
| git_branch_ops.py | 188 | 分支操作（创建、删除、切换） |
| git_diff_hunks.py | - | Diff 解析（已迁移到 analysis） |
| git_status_ops.py | 178 | Status 查询（文件状态、修改列表） |
| git_worktree_ops.py | 258 | Worktree 操作（创建、删除、列表） |

### GitHub 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| github_client.py | 29 | GitHub API 主入口（门面） |
| github_client_base.py | 95 | GitHub 基础客户端（认证、请求） |
| github_pr_ops.py | 520 | PR 操作（创建、更新、合并、查询） |
| github_issues_ops.py | 272 | Issue 操作（创建、更新、查询、关闭） |
| github_issue_admin_ops.py | 292 | Issue 管理操作（关闭、reopen） |
| github_review_ops.py | 155 | Review 操作（创建、查询、提交） |
| github_comment_ops.py | 161 | Comment 操作（创建、查询） |
| github_labels.py | 152 | GitHub issue label CRUD |
| merged_pr_cache.py | 242 | 已合并 PR 缓存 |

### AI 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| ai_client.py | 97 | AI 调用（LiteLLM） |
| ai_suggestion_client.py | 114 | 面向 PR/文案建议的高层 AI 客户端 |

### Serena 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| serena_client.py | 195 | Serena 符号分析（AST 查询） |

### SQLite 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| sqlite_client.py | 19 | SQLite 门面客户端（兼容现有调用） |
| sqlite_base.py | 40 | SQLite 连接管理与 schema 初始化 |
| sqlite_schema.py | 354 | Schema 定义（表结构、索引） |
| sqlite_flow_state_repo.py | 396 | flow_state / flow_issue_links 持久化 |
| sqlite_event_repo.py | 86 | flow_events 持久化 |
| sqlite_session_repo.py | 208 | runtime_session 持久化 |
| sqlite_context_cache_repo.py | 75 | flow_context_cache 持久化 |

### 协议定义文件

| 文件 | 行数 | 职责 |
|------|------|------|
| protocols.py | 212 | 客户端接口协议（Protocol 定义） |

### 其他文件

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 15 | 模块导出 |

**总计**：24 文件，4768 行

## 依赖关系

### 依赖

- `models`：领域模型定义
- `config`：配置加载（GitHub token、数据库路径）
- `exceptions`：客户端异常

### 被依赖

- `services`：业务逻辑层调用客户端
- `analysis`：代码分析服务调用 Git 客户端
- `agents`：Agent 后端调用 AI 客户端
- `commands`：命令层调用客户端
- `execution`：执行器调用客户端
- `orchestra`：全局编排调用客户端

## 架构说明

### Git 操作拆分设计

Git 客户端按职责拆分为多个文件：

- `git_client.py`：门面，聚合所有 Git 操作
- `git_branch_ops.py`：分支管理（创建、删除、切换、查询）
- `git_worktree_ops.py`：Worktree 管理（创建、删除、列表、查询）
- `git_status_ops.py`：状态查询（修改文件、分支状态）

### SQLite Repo 拆分设计

SQLite 按数据类型拆分为多个 repo：

- `sqlite_flow_state_repo.py`：Flow 状态持久化（flow_state、flow_issue_links）
- `sqlite_event_repo.py`：事件持久化（flow_events）
- `sqlite_session_repo.py`：Session 持久化（runtime_session）
- `sqlite_context_cache_repo.py`：上下文缓存（flow_context_cache）

### GitHub API 设计

GitHub 客户端采用门面 + mixin 设计：

- `github_client.py`：门面，聚合所有 GitHub 操作
- `github_client_base.py`：基础功能（认证、请求）
- `github_pr_ops.py`、`github_issues_ops.py` 等：按资源类型拆分

### 关键设计

1. **接口隔离**：通过 Protocol 定义客户端接口，便于测试和替换
2. **职责拆分**：大型客户端按职责拆分为多个文件
3. **错误封装**：统一异常处理，屏蔽底层实现细节
4. **缓存设计**：对频繁查询的数据（如 merged PR）提供缓存
5. **异步支持**：AI 客户端支持异步调用，避免阻塞
