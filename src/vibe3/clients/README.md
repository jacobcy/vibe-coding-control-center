# Clients

外部系统客户端层，为 Git, GitHub, AI, Serena, SQLite 提供最小包装。

## 职责

- Git 操作（branch, diff, status, worktree）
- GitHub API（PR, issue, review, comment）
- AI 文本生成（LiteLLM 多模型支持）
- Serena 符号查询
- SQLite 本地状态持久化

## 文件列表

统计时间：2026-06-27

### Git 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| git_client.py | 635 | Git 操作主入口 |
| git_branch_ops.py | 188 | 分支操作（创建、删除、切换） |
| git_branch_listing.py | 44 | 分支列表查询 |
| git_status_ops.py | 448 | Status 查询（文件状态、修改列表） |
| git_worktree_ops.py | 291 | Worktree 操作（创建、删除、列表） |

### GitHub 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| github_client.py | 29 | GitHub API 主入口（门面） |
| github_client_base.py | 161 | GitHub 基础客户端（认证、请求） |
| github_pr_ops.py | 21 | PR 操作门面 |
| github_pr_read_ops.py | 479 | PR 读操作（查询、列表） |
| github_pr_write_ops.py | 282 | PR 写操作（创建、更新、合并） |
| github_issues_ops.py | 502 | Issue 操作（创建、更新、查询、关闭） |
| github_issue_admin_ops.py | 372 | Issue 管理操作（关闭、reopen） |
| github_review_ops.py | 158 | Review 操作（创建、查询、提交） |
| github_comment_ops.py | 166 | Comment 操作（创建、查询） |
| github_labels.py | 147 | GitHub issue label CRUD |
| github_field_constants.py | 141 | GitHub field 常量定义 |
| label_utils.py | 227 | 标签工具函数（规范化、异常检测） |
| merged_pr_cache.py | 345 | 已合并 PR 缓存 |
| recent_pr_cache.py | 152 | 最近 PR 缓存 |
| pr_status_checker.py | 120 | PR 状态检查器 |

### AI 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| ai_client.py | 99 | AI 调用（LiteLLM） |
| ai_suggestion_client.py | 119 | 面向 PR/文案建议的高层 AI 客户端 |

### Serena 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| serena_client.py | 349 | Serena 符号分析（AST 查询） |

### SQLite 客户端文件

| 文件 | 行数 | 职责 |
|------|------|------|
| sqlite_client.py | 25 | SQLite 门面客户端（兼容现有调用） |
| sqlite_base.py | 193 | SQLite 连接管理与 schema 初始化 |
| sqlite_schema.py | 593 | Schema 定义（表结构、索引） |
| sqlite_flow_state_repo.py | 591 | flow_state / flow_issue_links 持久化 |
| sqlite_event_repo.py | 87 | flow_events 持久化 |
| sqlite_session_repo.py | 278 | runtime_session 持久化 |
| sqlite_context_cache_repo.py | 137 | flow_context_cache 持久化 |
| sqlite_queue_repo.py | 59 | flow_queue 持久化 |
| sqlite_snapshot_repo.py | 94 | flow_snapshot 持久化 |
| sqlite_transition_history_repo.py | 137 | flow_transition_history 持久化 |

### 运行时资源文件

| 文件 | 行数 | 职责 |
|------|------|------|
| runtime_assets.py | 132 | 运行时资源路径解析 |
| store_context.py | 28 | Store context 上下文管理 |
| sync_rules.py | 177 | 同步规则加载 |

### 协议定义文件

| 文件 | 行数 | 职责 |
|------|------|------|
| protocols/__init__.py | 13 | 协议模块导出 |
| protocols/backend.py | 90 | Backend 协议定义 |
| protocols/flow.py | 57 | Flow 协议定义 |
| protocols/git.py | 24 | Git 路径协议定义 |
| protocols/github.py | 265 | GitHub 客户端协议定义 |
| protocols/pr.py | 21 | PR 解析协议定义 |
| protocols/role.py | 31 | Role 定义协议 |

### 其他文件

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 183 | 模块导出（延迟加载） |

**总计**：44 文件（37 主目录文件 + 7 protocols 子目录文件），约 8690 行

## 公共 API

从 `__init__.py` 的 `__all__` 导出的 48 个符号，按功能分组：

### Git 客户端

- `GitClient` — Git 操作主入口
- `GitClientProtocol` — Git 客户端协议
- `find_repo_root` — 查找仓库根路径
- `prune_worktrees` — 清理无效 worktree
- `remove_worktree` — 删除指定 worktree

### GitHub 客户端

- `GitHubClient` — GitHub API 主入口
- `GitHubClientProtocol` — GitHub 客户端协议
- `get_merged_pr_for_issue` — 获取 issue 的已合并 PR
- `has_merged_pr_for_issue` — 检查 issue 是否有已合并 PR

### GitHub 标签

- `GhIssueLabelPort` — GitHub label 操作接口
- `IssueLabelPort` — Issue label 操作接口
- `GITHUB_DEFAULT_VIEW_FIELDS` — GitHub 默认视图字段
- `GITHUB_FIELDS_BODY_COMMENTS` — GitHub body/comments 字段

### GitHub 工具

- `parse_blocked_by` — 解析 blocked-by 关系
- `parse_linked_issues` — 解析 linked issues

### 标签工具

- `LabelAnomaly` — 标签异常类型
- `collect_label_anomalies` — 收集标签异常
- `has_manager_assignee` — 检查是否有 manager assignee
- `normalize_assignees` — 规范化 assignees
- `normalize_labels` — 规范化 labels

### PR 缓存

- `MergedPRCache` — 已合并 PR 缓存
- `RecentPRCache` — 最近 PR 缓存

### AI 客户端

- `AIClient` — AI 调用客户端
- `AISuggestionClient` — AI 建议（文案/PR）客户端

### Serena 客户端

- `SerenaClient` — Serena 符号分析客户端
- `count_references` — 统计符号引用数
- `extract_class_locations` — 提取类位置
- `extract_class_names` — 提取类名
- `extract_function_locations` — 提取函数位置
- `extract_function_names` — 提取函数名

### SQLite 客户端

- `SQLiteClient` — SQLite 客户端
- `init_schema` — 初始化 schema
- `get_store` — 获取 store context

### 运行时资源

- `bundled_project_root` — Bundled 项目根路径
- `resolve_prompt_config` — 解析 prompt config
- `resolve_runtime_asset` — 解析运行时资源路径
- `runtime_assets_root` — 运行时资源根路径

### 同步规则

- `LocalSyncRules` — 本地同步规则
- `RemoteSyncRules` — 远程同步规则
- `SyncRule` — 同步规则定义
- `SyncRulesConfig` — 同步规则配置
- `load_sync_rules` — 加载同步规则

### 协议

- `BackendProtocol` — Backend 协议
- `FlowReader` — Flow 读接口
- `FlowStatePort` — Flow 状态接口
- `GitPathProtocol` — Git 路径协议
- `BaseResolver` — PR 解析基类
- `TriggerableRoleDefinitionProtocol` — 可触发角色定义协议

## 依赖关系

### 依赖

- `models`：领域模型定义（AdapterManifest、FlowState 等）
- `config`：配置加载（GitHub token、数据库路径、运行时资源路径）
- `exceptions`：客户端异常（GitHubAPIError、WorktreeError 等）

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
