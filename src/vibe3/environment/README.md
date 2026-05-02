# Environment

环境资源管理，提供 worktree 和 session 隔离。

## 职责

- Worktree 生命周期管理：创建、切换、回收 worktree
- Tmux session 管理：创建、销毁、查询 session
- Session 注册表：维护 session 与 worktree 的映射关系
- 环境隔离：确保不同任务在不同 worktree 和 session 中执行

## 文件列表

统计时间：2026-05-02

### Worktree 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| worktree.py | 421 | Worktree 生命周期管理主入口 |
| worktree_context.py | 17 | Worktree 上下文管理器 |
| worktree_pr_mixin.py | 287 | Worktree PR 相关操作 mixin |
| worktree_support.py | 266 | Worktree 辅助函数（查找、初始化、回收） |

### Session 管理文件

| 文件 | 行数 | 职责 |
|------|------|------|
| session.py | 216 | Tmux session 创建与销毁 |
| session_naming.py | 15 | Session 命名规则 |
| session_registry.py | 465 | Session 注册表，维护 session 与 worktree 映射 |

### 其他文件

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 17 | 模块导出 |

**总计**：8 文件，1704 行

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

### 关键设计

1. **资源隔离**：每个 flow 在独立 worktree 和 session 中执行
2. **生命周期管理**：worktree 自动回收，避免资源泄漏
3. **并发安全**：session 注册表确保同一 worktree 不会被并发访问
4. **路径对齐**：支持 auto-scene 对齐到 base 分支