# Engineering Review Report

**Plan**: `docs/plans/2026-04-09-issue-pr-cache-unification-plan.md`
**Reviewer**: plan-eng-review
**Date**: 2026-04-09
**Score**: 6/10

---

## Executive Summary

该计划旨在通过引入本地 cache 减少 GitHub API 调用，采用 lazy initialization + on-demand sync 架构。评审发现 **3 个严重架构问题**、**1 个性能问题** 和 **若干代码质量问题**。

**关键风险**：
1. Schema-code 不一致：代码假设 `flow_state.pr_number` 存在，但 schema 中没有定义
2. N+1 性能问题：`get_issue_titles()` 循环调用 GitHub API
3. 同步触发点缺失：未明确定义何时调用 `cache_service.maybe_sync()`

---

## Section 1: Architecture Review

### Issue #1: pr_number Storage Inconsistency ❌ CRITICAL

**严重程度**：CRITICAL
**影响范围**：4 个文件，PR hint 机制完全失效

**现状**：
- Schema `flow_state` 表（14-40行）中没有 `pr_number` 字段
- 但代码在多处尝试读取：
  - `flow_service.py:413` - `pr_number_hint = flow_data.get("pr_number")`
  - `pr_service.py:398` - `resolved_pr = flow_data.get("pr_number")`
  - `pr_lifecycle.py:45` - `flow_data.get("pr_number")`
  - `check_service.py:284` - `flow_data.get("pr_number")`

**问题本质**：
- Schema 定义与代码假设不一致
- 读取不存在的字段，永远返回 `None`
- PR hint 优化完全失效

**解决方案**：
- ✅ **已决策**：pr_number 只存在 cache 表（见 `architecture-decisions.md`）
- 移除所有 `flow_data.get("pr_number")` 读取
- 替换为 `cache_service.get_pr_number(branch)` 或直接 GitHub 查询

**修复步骤**：
1. 在 `FlowContextCacheService` 中实现 `get_pr_number(branch)` 方法
2. 替换所有 `flow_data.get("pr_number")` 调用
3. 添加测试验证 PR number 从 cache 正确读取

---

### Issue #2: Issue Title Fetch Duplication ❌ HIGH

**严重程度**：HIGH
**影响范围**：2 个服务，重复 API 调用

**现状**：
- `FlowProjectionService.get_issue_titles()` - 批量获取 issue titles
- `SpecRefService._fetch_issue_data()` - 单个 issue title/body 获取
- 两者都直接调用 `gh` API，没有 cache

**问题本质**：
- 重复的 API 调用逻辑
- 没有统一的 cache 层
- 同一 issue 在不同命令中多次请求

**解决方案**：
- ✅ **已决策**：统一迁移到 `FlowContextCacheService`
- `FlowProjectionService` → 使用 `cache_service.get_issue_titles()`
- `SpecRefService` → 使用 `cache_service.get_issue_title()`
- Cache service 负责 UPSERT + TTL 管理

**修复步骤**：
1. 实现 `FlowContextCacheService.get_issue_titles(issue_numbers)`
2. 实现 `FlowContextCacheService.get_issue_title(issue_number)`
3. 迁移 `FlowProjectionService` 使用 cache
4. 迁移 `SpecRefService` 使用 cache
5. 添加测试验证 cache 命中与 miss 逻辑

---

### Issue #3: Missing Sync Trigger Points ❌ HIGH

**严重程度**：HIGH
**影响范围**：Cache 同步策略无法生效

**现状**：
- Design doc 提出"每 N commands 同步一次"
- 但没有明确哪些命令应该触发 `cache_service.maybe_sync()`

**分析命令集成点**：
1. **Flow commands**：
   - `flow update` (119-163行) - 创建/更新 flow
   - `flow bind` (166-220行) - 绑定 issue
   - `flow show` (35-198行) - 展示 flow

2. **PR commands**：
   - `pr create` - 创建 PR
   - `pr ready` (62-138行) - PR lifecycle 事件

3. **Service methods**：
   - `FlowService.create_flow()` - flow 创建后
   - `FlowService.ensure_flow_for_branch()` - flow 注册后

**解决方案**：
- ✅ **已决策**：在命令 handler 结尾添加 `cache_service.maybe_sync()`
- 在核心 service 方法后添加同步调用

**修复步骤**：
1. 定义 trigger points 清单（见 `architecture-decisions.md` Decision #3）
2. 在每个 trigger point 添加：
   ```python
   cache_service = FlowContextCacheService()
   cache_service.maybe_sync()
   ```
3. 测试验证同步计数器与 TTL 逻辑

---

## Section 2: Code Quality Review

### ✅ 符合规范

**文件大小**：
- 所有超限文件已在 `config/settings.yaml` 中注册例外
- `flow_service.py` (519/600), `pr_service.py` (467/600), `check_service.py` (507/600)

**类型注解**：
- 所有公共函数有完整类型注解
- 使用 Python 3.10+ 语法

**函数大小**：
- Service 层函数均 < 100 行
- Command 层函数均 < 50 行

**日志规范**：
- 使用 `loguru` logger
- 结构化日志（`logger.bind(domain="pr", action="create_draft")`）

### ⚠️ 需要改进

**代码复杂度**：
- `FlowProjectionService.get_milestone_data()` - 4层嵌套（超出限制3层）
  ```python
  # 当前：try → if → if → if → if (4层)
  # 重构为：early returns
  ```

**错误处理**：
- `PRService.get_pr()` - 缺少错误处理，`github_client.get_pr()` 可能失败
- `TaskService.fetch_issue_with_comments()` - 缺少错误处理
- `FlowProjectionService.get_issue_titles()` - 错误处理过于宽泛（`except Exception`）

**文档缺失**：
- `TaskService.fetch_issue_with_comments()` 缺少 docstring
- 部分私有函数缺少注释

---

## Section 3: Test Review

### ✅ 现有测试覆盖

**服务层测试**：43个测试文件，覆盖核心服务：
- `test_flow_service.py` - FlowService 核心逻辑
- `test_pr_service.py` - PR 生命周期
- `test_task_service_fresh_db.py` - Task 绑定与查询
- `test_spec_ref_service.py` - Spec 解析与 issue 获取
- `test_flow_projection_service.py` - Flow 投影与数据组装

**测试组织**：
- 按服务拆分测试文件（一对一映射）
- 测试命名规范：`test_<service_name>.py`

### ⚠️ 缺失的测试

**新服务**：
- `FlowContextCacheService` - 计划新增，需要测试覆盖：
  - Lazy initialization 逻辑
  - On-demand sync 触发
  - TTL 过期与 refresh
  - Rate limiting 处理
  - UPSERT 并发安全

**建议测试用例**：
```python
# test_flow_context_cache_service.py

def test_lazy_initialization():
    """Cache starts empty, populated on first access"""

def test_cache_hit_returns_cached_title():
    """Subsequent calls return cached title"""

def test_cache_miss_fetches_from_github():
    """First call fetches from GitHub API"""

def test_ttl_expiration_triggers_refresh():
    """Stale entries (>1 hour) are refreshed"""

def test_rate_limiting_pauses_sync():
    """Sync pauses when X-RateLimit-Remaining < 100"""

def test_upsert_concurrency_safety():
    """Concurrent updates use INSERT OR REPLACE"""
```

---

## Section 4: Performance Review

### ❌ N+1 Query Pattern

**位置**：`FlowProjectionService.get_issue_titles()` (94-111行)

**问题**：
```python
def get_issue_titles(self, issue_numbers: list[int]) -> tuple[dict[int, str], bool]:
    titles: dict[int, str] = {}
    for n in issue_numbers:  # N+1 问题
        try:
            issue = self.github_client.view_issue(n)  # 每个 issue 调用一次 API
            ...
```

**影响**：
- `flow status` 命令：10 个 active flows → 10 次 API 调用
- `flow show --snapshot` 命令：5 个 issue links → 5 次 API 调用
- 累计效应：用户频繁运行命令导致大量 API 调用

**解决方案**：

**短期方案**（在 `FlowContextCacheService` 中）：
```python
def get_issue_titles(self, issue_numbers: list[int]) -> dict[int, str]:
    """Batch fetch issue titles using gh CLI."""
    if not issue_numbers:
        return {}

    # 使用 gh issue view 配合 xargs 批量查询
    # gh issue view 1 2 3 --json number,title
    cmd = [
        "gh", "issue", "view",
        *map(str, issue_numbers),
        "--json", "number,title"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {}

    issues = json.loads(result.stdout)
    return {issue["number"]: issue["title"] for issue in issues}
```

**长期方案**：
- 使用 GitHub GraphQL API 批量查询
- 一次查询获取多个 issue 的 title/body/labels

**修复步骤**：
1. 在 `FlowContextCacheService` 实现批量获取方法
2. 迁移 `FlowProjectionService` 使用批量方法
3. 添加性能测试验证 API 调用次数

---

## Critical Path & Risk Assessment

### 高风险改动

**Schema-code inconsistency** - 风险：HIGH
- 现有代码依赖不存在的字段
- 修复时可能影响 PR 查询逻辑
- 建议：分阶段修复，先添加日志追踪 `flow_data.get("pr_number")` 的调用

**N+1 performance** - 风险：MEDIUM
- 影响用户体验（命令响应时间）
- 可能触发 GitHub rate limiting
- 建议：优先实现 cache service 批量获取

**Cache sync triggers** - 风险：LOW
- 主要是集成遗漏，不影响现有功能
- 建议：逐个命令添加同步点，测试验证

---

## Recommendations

### 立即修复（P0）

1. **修复 schema-code 不一致**
   - 移除所有 `flow_data.get("pr_number")` 读取
   - 替换为 cache 查询或 GitHub 查询
   - 添加测试验证修复正确性

2. **实现 FlowContextCacheService**
   - Lazy initialization
   - Batch issue title fetch
   - UPSERT cache updates
   - TTL management

### 短期优化（P1）

3. **添加 sync trigger points**
   - 在 flow/pr commands 后添加 `maybe_sync()`
   - 在核心 service 方法后添加同步调用
   - 测试验证同步逻辑

4. **优化错误处理**
   - 添加 `PRService.get_pr()` 错误处理
   - 细化 `FlowProjectionService.get_issue_titles()` 异常捕获
   - 添加网络错误重试逻辑

### 长期改进（P2）

5. **重构代码复杂度**
   - `FlowProjectionService.get_milestone_data()` early returns
   - 减少嵌套层级至 ≤3

6. **完善测试覆盖**
   - `FlowContextCacheService` 完整测试套件
   - 性能测试验证批量查询收益

7. **实现 GraphQL batch query**
   - 研究 GitHub GraphQL API
   - 实现批量 issue/PR 查询
   - 减少 API 调用次数 50%+

---

## Architecture Decisions Record

见 `.agent/reviews/architecture-decisions.md`，包含：
- Decision #1: pr_number storage location (cache table only)
- Decision #2: issue title fetch unification (FlowContextCacheService)
- Decision #3: sync trigger points (command handlers + service methods)
- Decision #4: cache vs truth boundaries (strict separation)

---

## Next Steps

1. **更新 design doc**：将 architecture decisions 同步到 design doc
2. **实现 P0 修复**：schema-code inconsistency + cache service
3. **添加测试**：FlowContextCacheService 完整测试套件
4. **验证性能**：性能测试验证批量查询收益

---

## Verdict

**VERDICT: MAJOR**

计划整体方向正确，但存在 3 个严重架构问题需要立即修复：
1. Schema-code inconsistency 导致 PR hint 机制失效
2. N+1 性能问题影响用户体验
3. Sync trigger points 缺失导致 cache 策略无法生效

建议：修复 P0 问题后再进入实现阶段。