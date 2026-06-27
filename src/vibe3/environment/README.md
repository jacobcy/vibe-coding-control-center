# Environment

环境资源管理，提供 worktree 和 session 隔离。

## 职责

- Worktree 生命周期管理：创建、切换、回收 worktree
- Tmux session 管理：创建、销毁、查询 session
- Session 注册表：维护 session 与 worktree 的映射关系
- 环境隔离：确保不同任务在不同 worktree 和 session 中执行

## 文件列表

统计时间：2026-06-27

### Worktree 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| worktree.py | 364 | Worktree 管理主入口（acquire/release） |
| worktree_context.py | 17 | Worktree 上下文管理器 |
| worktree_lifecycle.py | 500 | Worktree 生命周期编排（创建、验证、回收） |
| worktree_pr_mixin.py | 283 | Worktree PR 相关操作 mixin |
| worktree_support.py | 302 | Worktree 辅助函数（查找、初始化、回收） |

### Session 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| session.py | 217 | Session 创建与销毁（tmux/codeagent） |
| session_naming.py | 15 | Session 命名规则 |
| session_registry.py | 481 | Session 注册表，维护 session 与 worktree 映射 |

### 其他文件

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 56 | 模块导出（延迟加载） |

**总计**：8 文件，约 2235 行

## 公共 API

从 `__init__.py` 的 `__all__` 导出的 9 个符号，按功能分组：

### Session 管理

- `SessionManager` — Session 创建与销毁主入口
- `TmuxSessionContext` — Tmux session 上下文
- `CodeagentSessionContext` — Codeagent session 上下文
- `get_manager_session_name` — 获取 manager session 名称

### Session 注册表

- `SessionRegistryService` — Session 注册表服务（持久化 session 与 worktree 映射）

### Worktree 管理

- `WorktreeManager` — Worktree 管理主入口（acquire/release）
- `WorktreeContext` — Worktree 上下文（路径、分支、issue）

### Worktree 辅助

- `find_worktree_by_path` — 按路径查找 worktree
- `find_worktree_for_branch` — 按分支查找 worktree

## 依赖关系

### 依赖

- `clients`：Git 客户端（worktree 操作）、SQLite 客户端（注册表持久化）
- `exceptions`：环境相关异常（WorktreeExists, SessionNotFound 等）
- `config`：编排配置（worktree 根路径、session 命名规则）
- `execution`：Flow 分发（worktree 与 flow 绑定）

### 被依赖

- `execution`：执行协调器需要 worktree 和 session
- `roles`：各角色执行时需要 worktree 隔离
- `commands`：命令层需要查询和管理 worktree

## 架构说明

### L3 Issue Worktree vs L2 Temporary Worktree

Environment 模块实现了两层 worktree 分离设计：

- **L3 Issue Worktree**：
  - 绑定到特定 issue，生命周期与 issue 一致
  - 路径命名：`{worktree_root}/issue-{number}-{hash}/`
  - 支持恢复：issue 重新激活时可复用已有 worktree
  - 用途：长期任务开发、跨 session 持久化

- **L2 Temporary Worktree**：
  - 临时创建，任务完成后立即回收
  - 路径命名：`{worktree_root}/temp-{hash}/`
  - 不支持恢复：每次执行都是全新环境
  - 用途：短期任务（如 governance 扫描、supervisor 检查）

### Session 与 Worktree 关系

```
Session Registry
├─ session_id → worktree_path
├─ session_id → tmux_session_name
└─ session_id → flow_id

Worktree Manager
├─ acquire_issue_worktree() → L3 worktree
└─ acquire_temporary_worktree() → L2 worktree
```

### Worktree 生命周期

Worktree 完整生命周期分为四个阶段：

1. **创建阶段**
   - `WorktreeLifecycle.create_issue_worktree()` — 创建 issue-bound worktree
   - `WorktreeLifecycle.create_temporary_worktree()` — 创建 temporary worktree
   - 路径生成规则：`issue-{number}-{hash}` (L3) 或 `temp-{hash}` (L2)
   - 前置清理：`git worktree prune` 清理 stale references

2. **分配阶段**
   - `WorktreeManager.acquire_issue_worktree()` — 分配 L3 worktree（支持复用）
   - `WorktreeManager.acquire_temporary_worktree()` — 分配 L2 worktree（不复用）
   - Flow 绑定：调用 `FlowStatePort.update_flow_metadata()` 记录 worktree 路径

3. **使用阶段**
   - `WorktreeContext` — 描述当前 worktree 状态（路径、分支、issue）
   - 环境隔离：不同 worktree 独立 git state，支持并发开发
   - Session 绑定：`SessionRegistryService` 维护 session → worktree 映射

4. **回收阶段**
   - `WorktreeManager.release_issue_worktree()` — 回收 L3 worktree（可选，保留用于恢复）
   - `WorktreeManager.release_temporary_worktree()` — 回收 L2 worktree（强制清理）
   - 清理操作：`git worktree remove --force` + `shutil.rmtree()`

**L2 vs L3 生命周期对比**：

| 特性 | L3 Issue Worktree | L2 Temporary Worktree |
|------|-------------------|----------------------|
| 绑定对象 | GitHub issue | 无绑定（临时任务） |
| 路径规则 | `issue-{number}-{hash}` | `temp-{hash}` |
| 支持复用 | ✅ Issue 重新激活时可复用 | ❌ 每次全新创建 |
| 回收策略 | 可选（保留供恢复） | 强制（立即清理） |
| 适用场景 | 长期开发、跨 session 持久化 | 短期任务（governance、supervisor） |

### Session 生命周期

Session 完整生命周期分为四个阶段：

1. **创建阶段**
   - `SessionManager.create_tmux_session()` — 创建纯 tmux session（L3 manager）
   - `SessionManager.create_codeagent_session()` — 创建 codeagent session（可选 tmux wrapper）
   - 命名规则：`vibe3_{prefix}_{timestamp}`（如 `vibe3_manager_20260627101234`）
   - 日志路径：`.git/vibe3/logs/{session_id}.log`

2. **绑定阶段**
   - `SessionRegistryService.register_session()` — 注册 session 与 worktree 映射
   - 持久化：写入 `runtime_session` 表（session_id、worktree_path、flow_id）
   - 并发安全：同一 worktree 不会被多个 session 同时占用

3. **执行阶段**
   - `SessionManager.attach_session()` — Attach 到运行中的 session
   - `TmuxSessionContext.keep_alive_seconds` — Session 保活时间（异步执行）
   - `CodeagentSessionContext.sync_mode` — 区分同步/异步执行模式

4. **销毁阶段**
   - `SessionManager.destroy_tmux_session()` — 销毁 tmux session
   - `SessionManager.destroy_codeagent_session()` — 销毁 codeagent session
   - `SessionRegistryService.unregister_session()` — 从注册表移除
   - 日志保留：session log 保留供事后排查

**Session naming 规则**（`session_naming.py`）：

- 格式：`vibe3_{prefix}_{timestamp}`
- Prefix：角色标识（如 `manager`、`plan`、`run`）
- Timestamp：YYYYMMDDHHMMSS（避免冲突）
- 示例：`vibe3_manager_20260627101234`

**Session 注册表持久化**（`session_registry.py`）：

- 表：`runtime_session`
- 字段：session_id、worktree_path、flow_id、created_at
- 查询：`get_session_for_worktree()`、`get_session_for_flow()`
- 清理：自动清理超过 keep_alive 时间的 session

### 关键设计

1. **资源隔离**：每个 flow 在独立 worktree 和 session 中执行
2. **生命周期管理**：worktree 自动回收，避免资源泄漏
3. **并发安全**：session 注册表确保同一 worktree 不会被并发访问
4. **路径对齐**：支持 auto-scene 对齐到 base 分支

### Bootstrap 资源解析

`WorktreeManager.resolve_bootstrap_worktree_context()` 提供最小资源接口，
供 `vibe-new` bootstrap 阶段调用：

**职责边界**：
- ✅ 解析物理执行环境（worktree 或当前仓库）
- ✅ 返回 WorktreeContext 描述
- ❌ 不执行 issue intake、flow bind、snapshot 等业务逻辑
- ❌ 不编排 workflow 选择

**调用方**：
- `BootstrapContextService` 通过 action plan 引用此接口
- Skill 层负责编排，environment 层只提供资源描述