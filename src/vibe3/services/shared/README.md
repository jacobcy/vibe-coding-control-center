# Services/Shared

跨领域公共能力模块，为 services 子模块及外部消费方提供基础工具和服务。

## 职责

- Label 状态编排与查询
- Git 路径解析与操作辅助
- 错误记录与查询工具
- 分支命名与解析
- Actor 格式化与角色提取
- Artifact 解析
- Binding guard（任务绑定验证、事件发射、角色辅助）
- Context caching（Flow 上下文缓存）
- Dependency resolution（依赖解析）
- File loader（配置/material/policy 加载）
- LOC 分析
- Queue dirty flag（队列脏标记）
- Signature service（签名管理）
- Spec ref service（规格引用管理）
- Status query service（状态查询）
- Timeline parsing（时间线解析）
- Version service（版本管理）

## 文件列表

统计时间：2026-06-27

### Label 体系

| 文件 | 行数 | 职责 |
|------|------|------|
| labels.py | 244 | 状态标签常量与编排逻辑 |
| label_service.py | 211 | Label CRUD 服务（GitHub API） |

### 路径与 Git

| 文件 | 行数 | 职责 |
|------|------|------|
| paths.py | 392 | Git 路径协议与辅助函数 |
| branch_resolver.py | 164 | 分支输入解析与验证 |
| branches.py | 76 | 分支命名常量与解析工具 |

### 错误与事件

| 文件 | 行数 | 职责 |
|------|------|------|
| errors.py | 75 | 错误记录与查询工具 |

### Actor 与角色

| 文件 | 行数 | 职责 |
|------|------|------|
| actors.py | 102 | Actor 格式化与角色提取 |

### 其他服务

| 文件 | 行数 | 职责 |
|------|------|------|
| artifacts.py | 82 | Artifact 解析器 |
| binding_guard.py | 92 | 任务绑定验证、事件发射、角色辅助 |
| comment.py | 86 | Comment 类型检测 |
| context_cache.py | 96 | Flow 上下文缓存服务 |
| dependency_resolution.py | 117 | 依赖解析服务 |
| file_loader.py | 134 | Material/Policy 文件加载器 |
| loc.py | 154 | LOC 分析服务 |
| queue_dirty.py | 72 | Queue dirty flag 管理 |
| signatures.py | 127 | 签名管理服务 |
| spec_ref.py | 271 | Spec 引用管理服务 |
| status_query.py | 452 | 状态查询服务 |
| timeline.py | 89 | Timeline 解析工具 |
| versions.py | 121 | 版本管理服务 |

**总计**：20 文件，3334 行

## 公共 API

从 `__init__.py` 导出的 54 个符号：

### Label 体系（13 个）

- `LabelService` - Label CRUD 服务
- `classify_dispatch_eligibility` - 分发资格分类
- `clean_old_state_labels` - 清理旧状态标签
- `get_state_labels` - 获取状态标签集合
- `has_manager_assignee` - 检查 manager assignee
- `has_orchestra_governed` - 检查 orchestra governed 标签
- `has_roadmap_label` - 检查 roadmap 标签
- `normalize_assignees` - 规范化 assignees
- `normalize_labels` - 规范化 labels
- `should_skip_from_queue` - 是否应从队列跳过
- `ORCHESTRA_GOVERNED_LABEL` - Orchestra governed 标签常量

### 路径与 Git（8 个）

- `GitPathProtocol` - Git 路径协议
- `check_ref_exists` - 检查 ref 是否存在
- `get_git_common_dir` - 获取 git common directory
- `get_worktree_root` - 获取 worktree 根路径
- `ref_to_handoff_cmd` - ref 到 handoff 命令转换
- `resolve_ref_path` - 解析 ref 路径
- `sanitize_event_detail_paths` - 规范化事件详情路径
- `resolve_issue_branch_input` - 解析 issue branch 输入

### 错误与事件（4 个）

- `log_dispatch_error` - 记录分发错误
- `has_recent_specific_error` - 检查最近特定错误
- `emit_issue_failed` - 发射 issue 失败事件

### Actor 与角色（4 个）

- `format_agent_actor` - 格式化 agent actor
- `format_dry_run_header` - 格式化 dry run header
- `extract_role_from_actor` - 从 actor 提取角色
- `get_role_block_function` - 获取角色 block 函数

### 其他服务（26 个）

- `ArtifactParser` - Artifact 解析器
- `MissingTaskIssueError` - 任务绑定缺失异常
- `build_bind_task_hint` - 构建绑定提示
- `ensure_task_issue_bound` - 确保任务绑定
- `is_human_comment` - 检查是否人类评论
- `FlowContextCacheService` - Flow 上下文缓存服务
- `DependencyResolution` - 依赖解析模型
- `DependencyResolutionService` - 依赖解析服务
- `material_loader` - Material 加载器
- `policy_loader` - Policy 加载器
- `LocService` - LOC 分析服务
- `LOCStats` - LOC 统计模型
- `is_queue_dirty` - 检查队列是否脏
- `mark_queue_dirty` - 标记队列脏
- `clear_queue_dirty` - 清除队列脏标记
- `SignatureService` - 签名管理服务
- `SpecRefService` - Spec 引用服务
- `StatusQueryService` - 状态查询服务
- `is_auto_task_branch` - 检查是否 auto task 分支
- `is_dev_collab_branch` - 检查是否 dev collab 分支
- `TIMELINE_DISPLAY_MAP` - Timeline 显示映射
- `parse_timeline_from_comments` - 从评论解析 timeline
- `VersionService` - 版本管理服务

## 内部依赖

### 模块间依赖

- `status_query.py` → `labels.py`（状态标签查询）
- `label_service.py` → `clients/github_labels.py`（GitHub Label API）
- `branch_resolver.py` → `branches.py`（分支命名规则）
- `dependency_resolution.py` → `status_query.py`（状态查询）
- `loc.py` → `clients/git_client.py`（Git diff 操作）

## 外部依赖

- `clients` - Git 客户端、GitHub 客户端、SQLite 客户端
- `models` - 领域模型定义
- `exceptions` - 业务异常
- `config` - 配置加载

## 被依赖

约 100+ 文件引用，主要消费方：

- `services/flow` - Flow 生命周期管理
- `services/pr` - PR 服务
- `services/task` - Task 服务
- `services/orchestra` - 编排服务
- `services/check` - Pre-push 检查
- `commands` - 命令层
- `domain` - 事件处理器
- `execution` - 执行器
- `server` - Server 状态展示

## 设计原则

### Lazy Import 避免循环依赖

使用 `__getattr__` 实现延迟导入，避免模块加载时的循环依赖：

```python
def __getattr__(name: str) -> Any:
    if name in _SYMBOL_MODULES:
        import importlib
        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        globals()[name] = symbol
        return symbol
    raise AttributeError(...)
```

### `_SYMBOL_MODULES` 映射表

每个导出符号映射到其源模块，确保 `from vibe3.services.shared import X` 能正确路由。

### `__all__` 与映射一致性断言

通过 `assert set(__all__) == set(_SYMBOL_MODULES.keys())` 确保公共 API 契约一致性。

### 职责拆分

- Label 体系：`labels.py`（常量与逻辑）+ `label_service.py`（API 服务）
- 路径工具：`paths.py`（路径协议）+ `branch_resolver.py`（输入解析）
- 错误工具：统一错误记录接口，支持错误追踪服务