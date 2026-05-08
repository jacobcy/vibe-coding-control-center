# Flow Context Cache Standard

状态：Active

## 1. 目的

本标准定义 Vibe3 flow context cache 的设计、使用和治理规范。

它回答四个核心问题：

- 缓存存储什么数据
- 缓存何时被更新
- 缓存与真源的关系
- 缓存失效时如何降级

本标准适用于：

- 使用 `flow_context_cache` 表的所有代码
- 调用 `FlowProjectionService.get_issue_titles()` 的代码
- 需要理解缓存层架构的开发者

## 2. 架构原则

### 2.1 Truth vs Cache 分离

**真源（Authoritative Truth）**：

- `flow_state` 表：flow 状态真源
- `flow_issue_links` 表：issue 关系真源
- GitHub API：issue/PR 元数据真源

**缓存（Optimization Layer）**：

- `flow_context_cache` 表：issue/PR 元数据本地缓存
- 目的：减少 GitHub API 调用、提升展示速度
- 非真源：缓存可能与真源不一致，允许降级

**核心原则**：

```
Cache 是优化层，不是真源
系统在 cache 完全不可用时仍可正常工作
```

### 2.2 Lazy Initialization

缓存采用懒初始化策略：

- Flow 创建时不立即填充缓存
- 首次访问时检查并初始化
- 对于 issue 分支（`task/issue-N` 或 `dev/issue-N`），自动从 GitHub 拉取 issue title 并缓存

示例流程：

```
1. vibe3 flow start task/issue-436
   → flow_state 创建
   → 缓存为空

2. vibe3 flow show task/issue-436
   → FlowProjectionService.get_issue_titles([436])
   → 检查缓存：未命中
   → 调用 GitHub API 获取 issue title
   → 更新缓存：{task_issue_number: 436, issue_title: "..."}

3. 后续 vibe3 flow show
   → 缓存命中
   → 跳过 GitHub API 调用
```

### 2.3 Graceful Degradation

系统在缓存缺失或 GitHub API 失败时继续运行：

- GitHub API 失败 → `issue_title` 为 `None`，缓存记录存在
- 缓存完全不可用 → 降级为每次调用 GitHub API
- 不因缓存问题阻塞业务流程

示例：

```python
# 在 FlowProjectionService.get_issue_titles() 中
try:
    issue = self.github_client.view_issue(n)
    if isinstance(issue, dict):
        fetched_title = issue.get("title", f"Issue #{n}")
        titles[n] = fetched_title
        # 尝试更新缓存（失败不影响返回结果）
        self.store.upsert_flow_context_cache(...)
except Exception as e:
    # GitHub 失败，记录日志但不抛异常
    network_error = True
    logger.warning(f"Failed to fetch issue #{n} from GitHub: {e}")
```

## 3. 缓存数据模型

### 3.1 Schema

```sql
CREATE TABLE flow_context_cache (
    branch TEXT PRIMARY KEY,           -- 分支名（外键关联 flow_state）
    task_issue_number INTEGER,         -- 关联的 task issue 编号
    issue_title TEXT,                  -- Issue 标题
    pr_number INTEGER,                 -- 关联的 PR 编号
    pr_title TEXT,                     -- PR 标题
    updated_at TEXT NOT NULL           -- 最后更新时间（ISO 8601）
)
```

### 3.2 字段语义

| 字段 | 真源 | 缓存时机 | 可为空 | 说明 |
|------|------|----------|--------|------|
| `branch` | `flow_state.branch` | Flow 创建时 | 否 | 主键，关联真源 |
| `task_issue_number` | `flow_issue_links` | Issue link 绑定时 | 是 | 从真源初始化 |
| `issue_title` | GitHub issue API | 首次访问时 | 是 | 从 GitHub 拉取 |
| `pr_number` | GitHub PR API | PR 创建时 | 是 | 从 GitHub 拉取 |
| `pr_title` | GitHub PR API | PR 创建/更新时 | 是 | 从 GitHub 拉取 |
| `updated_at` | 本地时钟 | 每次更新时 | 否 | 审计字段 |

### 3.3 UPSERT 语义

使用 `INSERT OR REPLACE` 实现原子更新：

```python
def upsert_flow_context_cache(
    self,
    branch: str,
    task_issue_number: int | None,
    issue_title: str | None,
    pr_number: int | None,
    pr_title: str | None,
) -> None:
    """Upsert cache entry atomically."""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO flow_context_cache
            (branch, task_issue_number, issue_title, pr_number, pr_title, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (branch, task_issue_number, issue_title, pr_number, pr_title, now_iso8601),
        )
        conn.commit()
```

**重要**：调用方必须提供所有字段值，UPSERT 会完全替换旧行：

```python
# ❌ 错误：只更新部分字段会丢失其他字段
self.store.upsert_flow_context_cache(
    branch="task/issue-436",
    task_issue_number=436,
    issue_title="New title",
    pr_number=None,  # 会覆盖已有的 pr_number！
    pr_title=None,
)

# ✅ 正确：读取现有值，更新后完整写入
existing = self.store.get_flow_context_cache(branch)
self.store.upsert_flow_context_cache(
    branch=branch,
    task_issue_number=existing.get("task_issue_number") if existing else None,
    issue_title="New title",
    pr_number=existing.get("pr_number") if existing else None,
    pr_title=existing.get("pr_title") if existing else None,
)
```

## 4. 缓存更新时机

### 4.1 初始化时机

| 场景 | 触发点 | 初始化内容 |
|------|--------|-----------|
| Issue 分支 flow 创建 | `FlowService.ensure_flow_for_branch()` | `task_issue_number`, `issue_title` (从 GitHub 拉取) |
| 非issue 分支 flow 创建 | 不初始化 | 留空 |
| 首次 flow show | `FlowProjectionService.get_issue_titles()` | `issue_title` (缓存未命中时从 GitHub 拉取) |

### 4.2 更新时机

| 场景 | 触发点 | 更新字段 |
|------|--------|---------|
| PR 创建 | `PRService._sync_pr_flow_state()` | `pr_number`, `pr_title` |
| PR 标记 ready | `PRService._sync_pr_flow_state()` | `pr_title` |
| Issue title 变更 | GitHub Webhook (未实现) | `issue_title` |
| 手动刷新 | `vibe3 cache refresh` (未实现) | 所有字段 |

### 4.3 失效时机

| 场景 | 触发点 | 操作 |
|------|--------|------|
| Flow reactivate | `FlowService.reactivate_flow()` | `DELETE FROM flow_context_cache` |
| Flow delete | `SQLiteClient.delete_flow()` | `DELETE FROM flow_context_cache` (级联删除) |

**为什么 reactivate 时清缓存**：

- `reactivate_flow()` 用于 "canonical task flow 被重用于新的 issue iteration"
- 新 iteration 可能关联不同 issue 或 PR
- 清缓存确保下次访问时重新初始化，避免残留旧数据

## 5. 使用规范

### 5.1 读取缓存

```python
# ✅ 推荐：通过 FlowProjectionService 读取（带降级）
projection_service = FlowProjectionService(store=store)
titles, net_err = projection_service.get_issue_titles([436])
# 自动处理缓存命中/未命中/GitHub 失败

# ⚠️ 允许但需谨慎：直接读取缓存（无降级）
cache = store.get_flow_context_cache(branch)
if cache:
    issue_title = cache.get("issue_title")  # 可能为 None
# 注意：直接读取不触发 GitHub 拉取，需自行处理缺失情况
```

### 5.2 写入缓存

```python
# ✅ 正确：读取现有值，完整写入
existing_cache = store.get_flow_context_cache(branch)
store.upsert_flow_context_cache(
    branch=branch,
    task_issue_number=existing_cache.get("task_issue_number") if existing_cache else 436,
    issue_title=new_title,
    pr_number=existing_cache.get("pr_number") if existing_cache else None,
    pr_title=existing_cache.get("pr_title") if existing_cache else None,
)

# ❌ 错误：部分更新会丢失其他字段
store.upsert_flow_context_cache(
    branch=branch,
    issue_title=new_title,
    pr_number=None,  # 会覆盖已有值
    pr_title=None,
)
```

### 5.3 避免的模式

```python
# ❌ 错误：假设缓存一定存在
cache = store.get_flow_context_cache(branch)
title = cache["issue_title"]  # KeyError if cache is None

# ✅ 正确：处理缓存缺失
cache = store.get_flow_context_cache(branch)
title = cache.get("issue_title") if cache else None

# ❌ 错误：在真源操作前检查缓存
cache = store.get_flow_context_cache(branch)
if cache and cache["pr_number"]:
    pr = github.get_pr(cache["pr_number"])
# 缓存可能过期，导致读取错误的 PR

# ✅ 正确：真源操作不依赖缓存
pr = github.get_pr(None, branch)  # 直接查询 GitHub
```

## 6. 性能优化

### 6.1 批量查询优化

`FlowProjectionService.get_issue_titles()` 支持批量查询：

```python
# ✅ 推荐：批量查询，减少 GitHub API 调用
issue_numbers = [436, 437, 438]
titles, net_err = projection_service.get_issue_titles(issue_numbers)

# 实现：先查缓存，只对 cache misses 调用 GitHub API
# - Cache hit: 0 次 GitHub API 调用
# - Cache miss (N 个): N 次 GitHub API 调用
```

### 6.2 并发安全

使用 `INSERT OR REPLACE` 保证原子性：

```python
# 并发安全：多个 agent 同时更新同一 branch
# SQLite 的 INSERT OR REPLACE 保证最终一致性
store.upsert_flow_context_cache(
    branch="task/issue-436",
    task_issue_number=436,
    issue_title="Concurrent update",
    pr_number=None,
    pr_title=None,
)
```

## 7. 故障处理

### 7.1 GitHub API 失败

```python
# 在 FlowProjectionService.get_issue_titles() 中
try:
    issue = self.github_client.view_issue(n)
except Exception as e:
    # 记录网络错误标志
    network_error = True
    logger.warning(f"Failed to fetch issue #{n}: {e}")
    # 不抛异常，继续处理其他 issue
# 返回 (titles, network_error) 让调用方决定是否重试
```

### 7.2 SQLite 错误

```python
# 在 SQLiteClient.upsert_flow_context_cache() 中
try:
    cursor.execute(...)
    conn.commit()
except sqlite3.Error as e:
    # 记录错误但不阻塞业务
    logger.error(f"Failed to update cache: {e}")
    # 降级：缓存不可用，但 flow show 仍可工作
```

### 7.3 缓存不一致

当发现缓存与真源不一致时：

```python
# 手动清空缓存，下次访问时重新拉取
store.delete_flow_context_cache(branch)

# 或等待自动失效：
# - reactivate_flow() 时自动清空
# - delete_flow() 时级联删除
```

## 8. 未来改进

当前缓存设计采用懒初始化 + 手动失效，未来可考虑：

### 8.1 GitHub Webhook 自动更新

```
GitHub issue.updated webhook
  → POST /webhook/github
  → update_flow_context_cache(branch, issue_title=...)
```

### 8.2 定期同步任务

```
vibe3 cache sync --stale-max-hours=24
  → 查找 updated_at > 24h 的缓存
  → 批量从 GitHub 拉取最新数据
  → 更新缓存
```

### 8.3 TTL 自动过期

```sql
ALTER TABLE flow_context_cache ADD COLUMN expires_at TEXT;
-- 查询时过滤过期缓存
SELECT * FROM flow_context_cache
WHERE branch = ? AND expires_at > datetime('now');
```

## 9. 参考

- [glossary.md](glossary.md) — 术语定义
- [v3/command-standard.md](v3/command-standard.md) — 命令与状态同步标准
- [agent-debugging-standard.md](agent-debugging-standard.md) — 调试方法

## 10. 变更历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-04-09 | 初始版本，定义 flow context cache 标准 |

---

**维护者**：Vibe Team
**最后更新**：2026-04-09