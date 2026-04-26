w# IssueTitleCacheService 使用指南

## 概述

`IssueTitleCacheService` 提供统一的 issue 标题缓存服务，解决以下问题：

1. **缓存逻辑分散**：整合 `FlowProjectionService` 和 `StatusQueryService` 的标题获取逻辑
2. **缓存 key 不统一**：统一使用 `branch` 作为标准参数和缓存主键
3. **缓存更新时机不一致**：提供统一的更新接口

## 核心设计原则

### Branch 作为标准参数

**重要**：所有缓存接口都使用 `branch` 作为参数，不提供 `issue_number` 参数的接口。

```python
# ✅ 正确：使用 branch 参数
title = cache_service.get_title("task/issue-123")

# ❌ 错误：缓存服务不提供 issue_number 接口
title = cache_service.get_title_by_issue(123)  # 不存在此方法
```

### Issue Number 转换在命令层

`issue_number` 只在命令层用于转换为 `branch`，转换完成后丢弃：

```python
# 命令层示例
def show_flow(issue_or_branch: str):
    # 如果是纯数字，尝试转换为 branch
    if issue_or_branch.isdigit():
        issue_number = int(issue_or_branch)
        branch = issue_flow_service.canonical_branch_name(issue_number)
    else:
        branch = issue_or_branch

    # 后续操作都使用 branch
    title = cache_service.get_title(branch)
```

## 接口说明

### 读取操作

#### `get_title(branch: str) -> str | None`

获取单个 branch 的缓存标题（不触发 API 调用）。

```python
title = cache_service.get_title("task/issue-123")
if title:
    print(f"Cached title: {title}")
```

#### `get_titles(branches: list[str]) -> dict[str, str]`

批量获取多个 branch 的缓存标题。

```python
titles = cache_service.get_titles(["task/issue-123", "task/issue-456"])
# 返回: {"task/issue-123": "Title 1", "task/issue-456": "Title 2"}
```

#### `get_title_with_fallback(branch: str) -> tuple[str | None, bool]`

获取标题，如果缓存不存在则从 GitHub API 获取并更新缓存。

```python
title, had_network_error = cache_service.get_title_with_fallback("task/issue-123")
if had_network_error:
    logger.warning("Network error occurred")
elif title:
    print(f"Title: {title}")
```

#### `get_titles_with_fallback(branches: list[str]) -> tuple[dict[str, str], bool]`

批量获取标题，缓存缺失时从 GitHub API 获取。

```python
titles, net_err = cache_service.get_titles_with_fallback(
    ["task/issue-123", "task/issue-456"]
)
```

### 写入操作

#### `update_title(branch: str, title: str) -> None`

更新指定 branch 的标题缓存。

```python
cache_service.update_title("task/issue-123", "New Title")
```

#### `update_pr(branch: str, pr_number: int, pr_title: str) -> None`

更新指定 branch 的 PR 信息缓存。

```python
cache_service.update_pr("task/issue-123", 456, "PR Title")
```

#### `invalidate(branch: str) -> None`

清除指定 branch 的标题缓存（设置 `issue_title` 为 `NULL`）。

```python
cache_service.invalidate("task/issue-123")
```

## 集成示例

### StatusQueryService

```python
class StatusQueryService:
    def __init__(self, title_cache: IssueTitleCacheService | None = None):
        self._title_cache = title_cache

    @property
    def title_cache(self) -> IssueTitleCacheService:
        if self._title_cache is None:
            self._title_cache = IssueTitleCacheService(self.store, self.github)
        return self._title_cache

    def fetch_orchestrated_issues(self, flows: list[FlowStatusResponse]):
        # 收集所有 branch
        branches = [flow.branch for flow in flows if flow.branch]

        # 使用缓存服务获取标题（cache-first）
        branch_titles, _ = self.title_cache.get_titles_with_fallback(branches)

        # 后续使用 branch_titles
        for issue in issues:
            flow = issue_to_flow.get(issue["number"])
            if flow:
                title = branch_titles.get(flow.branch) or issue["title"]
```

### FlowProjectionService

```python
class FlowProjectionService:
    def get_issue_titles(self, issue_numbers: list[int]):
        # 命令层：issue_number -> branch 转换
        # 优先使用实际 flow 的 branch（可能是 dev/issue-N）
        # 如果没有 flow，则 fallback 到 canonical branch
        issue_flow = IssueFlowService()
        issue_to_branch = {}
        for n in issue_numbers:
            # 优先从 flow store 取真实 branch
            flow_state = issue_flow.find_active_flow(n)
            if flow_state and flow_state.get("branch"):
                branch = str(flow_state["branch"])
            else:
                # Fallback to canonical branch name
                branch = issue_flow.canonical_branch_name(n)
            issue_to_branch[n] = branch

        branches = list(issue_to_branch.values())

        # 使用缓存服务（branch 接口）
        branch_titles, net_err = self.title_cache.get_titles_with_fallback(branches)

        # 转换回 issue_number 映射
        issue_titles = {
            n: branch_titles[branch]
            for n, branch in issue_to_branch.items()
            if branch in branch_titles
        }

        return issue_titles, net_err
```

**重要**：`get_issue_titles()` 方法现在会：
1. 优先查找实际的 flow branch（可能是 `dev/issue-N`）
2. 如果没有 flow，才 fallback 到 canonical branch（`task/issue-N`）
3. 这确保了 `dev/issue-N` 分支也能正确命中缓存

### Flow Status Dashboard 优化

`flow_status.py` dashboard 路径现在直接使用已有的 `flows` 列表（包含真实 branch）：

```python
# 直接从 flows 收集真实 branches
branches = [flow.branch for flow in flows if flow.branch]

# 直接使用缓存服务，绕过 get_issue_titles 的转换逻辑
from vibe3.services.issue_title_cache_service import IssueTitleCacheService

title_cache = IssueTitleCacheService(store, github_client)
branch_titles, net_err = title_cache.get_titles_with_fallback(branches)

# 构建 issue_number -> title 映射
for flow in flows:
    if flow.task_issue_number and flow.branch in branch_titles:
        titles[flow.task_issue_number] = branch_titles[flow.branch]
```

这避免了通过 `canonical_branch_name` 猜测 branch，提高了缓存命中率。

## 缓存更新时机

| 事件 | 触发位置 | 更新方法 |
|------|---------|---------|
| Flow 初始化 | `flow_transition.init_issue_context()` | `title_cache.update_title()` |
| PR 创建/更新 | `pr_service.create_pr()` | `title_cache.update_pr()` |
| 标题获取（缓存缺失） | `IssueTitleCacheService._fetch_and_cache_title()` | `self.update_title()` |
| Issue 标题变更 | GitHub webhook | `title_cache.invalidate()` + 重新获取 |

## 数据库结构

```sql
CREATE TABLE IF NOT EXISTS flow_context_cache (
    branch TEXT PRIMARY KEY,           -- 主键：branch
    task_issue_number INTEGER,         -- 关联的 issue number（只读）
    issue_title TEXT,                  -- 缓存的 issue 标题
    pr_number INTEGER,                 -- 关联的 PR number
    pr_title TEXT,                     -- PR 标题
    updated_at TEXT NOT NULL           -- 更新时间戳
)
```

**设计要点**：
- `branch` 是主键，所有查询都通过 `branch` 进行
- `task_issue_number` 用于关联 issue，但不用于查询
- 无需为 `task_issue_number` 添加索引（查询不使用该字段）

## 常见问题

### Q: 为什么不提供 `get_title_by_issue(issue_number)` 接口？

**A**: 这是为了保持接口语义清晰：
- `branch` 是标准参数和缓存主键
- `issue_number` 只在命令层用于转换
- 提供多种接口会模糊设计边界，增加维护成本

### Q: 如果一个 issue 对应多个 branch 怎么办？

**A**: 每条 branch 记录独立缓存：
- `task/issue-123` 有独立的缓存记录
- `dev/issue-123` 也有独立的缓存记录
- 两者可以有不同的标题（虽然通常是相同的）

### Q: 如何处理网络错误？

**A**: 所有带 fallback 的方法都返回 `had_network_error` 标志：

```python
title, had_error = cache_service.get_title_with_fallback(branch)
if had_error:
    # 处理网络错误（例如：使用降级数据）
    pass
```

### Q: 缓存何时失效？

**A**:
1. 手动调用 `invalidate()` 清除
2. GitHub webhook 触发（需配置）
3. 下次调用 `get_title_with_fallback()` 时重新获取

## 测试覆盖

- **单元测试**: `tests/vibe3/services/test_issue_title_cache_service.py`
- **集成测试**: `tests/vibe3/services/test_issue_title_cache_integration.py`

运行测试：
```bash
uv run pytest tests/vibe3/services/test_issue_title_cache_service.py -v
uv run pytest tests/vibe3/services/test_issue_title_cache_integration.py -v
```
