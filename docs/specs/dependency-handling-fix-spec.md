# Spec: 依赖处理机制修复与自动唤醒设计

## 问题背景

### 当前问题

**核心缺陷：依赖方向错乱**
- **现状**：被依赖的 issue（如 #301）被标记为 `blocked`
- **正确做法**：依赖方（如 #300）应该等待被依赖项完成

**缺失能力**：
1. 没有自动依赖解析（scheduler 不查询 `flow_issue_links`）
2. 没有 waiting 状态/队列机制
3. 没有依赖满足后的自动唤醒逻辑
4. Blocked flow 必须人工 resume

### Issue #301 案例分析

```
Issue #300 → depends on → Issue #301
当前状态：
  - #301 GitHub: state/blocked（错误）
  - #300 GitHub: state/failed
  - #301 本地：无 flow_state 记录（未开始开发）
  - flow_issue_links: task/issue-300 → dependency #301

期望状态：
  - #301: state/ready（或执行中）
  - #300: state/waiting (blocked_by_issue=301)
  - #301 完成 PR create 后 → 自动唤醒 #300
```

## 设计目标

### 核心原则

1. **依赖方向正确化**
   - 有依赖的 flow 进入 `waiting` 状态
   - 被依赖的 flow 正常执行（不被阻塞）

2. **自动唤醒机制**
   - 被依赖 flow 完成（PR create）时触发事件
   - 检查所有依赖方，满足条件后自动 `waiting → ready`

3. **分支策略**
   - **关键点**：完成标志是 PR create（不一定已合并）
   - 有依赖的 issue 应从**被依赖的 PR 分支**创建开发分支
   - 不是从 `origin/main` 创建

4. **利用已有基础设施**
   - `flow_issue_links` 表（dependency 关系）
   - `blocked_by_issue` 字段（已有）
   - `get_flow_dependents()` helper（已存在）
   - `flow_state.blocked_reason` 字段（已有）

## 实现方案

### Phase 1: Waiting 状态机制

#### 1.1 新增 flow_status 值

**修改文件**：`src/vibe3/models/flow.py`

```python
flow_status: Literal[
    "active", "blocked", "failed", "done", "stale", "aborted", "merged",
    "waiting"  # NEW: waiting for dependencies
] = "active"
```

#### 1.2 Dispatcher 筛选逻辑调整

**修改文件**：`src/vibe3/orchestra/services/state_label_dispatch.py`

**`collect_ready_issues()` 改造**：

```python
def collect_ready_issues(self) -> list[IssueInfo]:
    """Collect ready issues, excluding those waiting for dependencies."""
    candidates = self._github.list_issues(
        state="open",
        labels=["state/ready"],
        repo=self.config.repo,
    )

    ready_issues = []
    for issue in candidates:
        # Check if this issue has unresolved dependencies
        dependencies = self._get_issue_dependencies(issue.number)

        if dependencies:
            # Has dependencies → check if all are satisfied
            unresolved = [d for d in dependencies if not self._is_dependency_satisfied(d)]

            if unresolved:
                # Move to waiting state (not ready)
                self._mark_issue_waiting(issue.number, unresolved)
                logger.info(
                    f"Issue #{issue.number} has unresolved dependencies: {unresolved}"
                )
                continue

        # No dependencies OR all satisfied → ready
        ready_issues.append(issue)

    return ready_issues

def _get_issue_dependencies(self, issue_number: int) -> list[int]:
    """Get dependency issue numbers from flow_issue_links."""
    store = SQLiteClient()
    # Query flows where this issue is task role
    flows = store.get_flows_by_issue(issue_number, role="task")
    if not flows:
        return []

    branch = flows[0].get("branch")
    if not branch:
        return []

    # Query dependency links for this branch
    with sqlite3.connect(store.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT issue_number FROM flow_issue_links "
            "WHERE branch = ? AND issue_role = 'dependency'",
            (branch,),
        )
        return [row[0] for row in cursor.fetchall()]

def _is_dependency_satisfied(self, dep_issue_number: int) -> bool:
    """Check if dependency issue has completed (PR created)."""
    gh = GitHubClient()
    payload = gh.view_issue(dep_issue_number, repo=self.config.repo)

    if not isinstance(payload, dict):
        return False

    # Check issue state
    state = payload.get("state")
    if state == "closed":
        return True  # Issue closed → dependency satisfied

    # Check for PR reference (completion marker)
    labels = [lb.get("name", "") for lb in payload.get("labels", []) if isinstance(lb, dict)]
    if "state/done" in labels or "state/merged" in labels:
        return True  # Task completed with PR

    # Check for PR in issue body or comments
    body = payload.get("body", "")
    if "pull request" in body.lower() or "pr #" in body.lower():
        return True  # PR mentioned → likely completed

    return False  # Dependency not yet satisfied

def _mark_issue_waiting(self, issue_number: int, unresolved_deps: list[int]) -> None:
    """Mark issue as waiting for dependencies."""
    store = SQLiteClient()
    flows = store.get_flows_by_issue(issue_number, role="task")
    if not flows:
        return

    branch = flows[0].get("branch")
    if not branch:
        return

    # Update flow_status to waiting
    store.update_flow_state(
        branch,
        flow_status="waiting",
        blocked_by_issue=unresolved_deps[0],  # Primary dependency
        blocked_reason=f"Waiting for dependencies: #{unresolved_deps}",
    )

    # Add event
    store.add_event(
        branch,
        "dependency_waiting",
        "orchestra:dispatcher",
        detail=f"Waiting for dependencies: {unresolved_deps}",
        refs={"dependencies": [str(d) for d in unresolved_deps]},
    )

    # Sync GitHub label (optional: create state/waiting label or use existing blocked)
    gh = GitHubClient()
    # For now, use state/blocked label (waiting is subset of blocked)
    gh.add_labels(issue_number, ["state/blocked"], repo=self.config.repo)
```

### Phase 2: 依赖满足唤醒机制

#### 2.1 PR Create 触发唤醒事件

**新增事件类型**：`DependencySatisfied`

**触发时机**：`vibe3 pr create` 成功后

**修改文件**：`src/vibe3/services/pr_service.py`

```python
def create_pr(...) -> PR:
    """Create PR and trigger dependency wake-up."""
    pr = self._github_client.create_pr(...)

    if pr and pr.number:
        # Trigger dependency wake-up
        self._trigger_dependency_wake_up(branch, pr.number)

    return pr

def _trigger_dependency_wake_up(self, branch: str, pr_number: int) -> None:
    """Wake up flows waiting on this branch's completion."""
    from vibe3.orchestra.events import publish_event
    from vibe3.domain.events import DependencySatisfied

    store = SQLiteClient()

    # Get task issue for this branch
    links = store.get_issue_links(branch)
    task_issue = next((l for l in links if l.get("issue_role") == "task"), None)

    if not task_issue:
        return

    issue_number = task_issue.get("issue_number")

    # Publish dependency satisfied event
    publish_event(
        DependencySatisfied(
            issue_number=issue_number,
            branch=branch,
            pr_number=pr_number,
        )
    )
```

#### 2.2 Domain Handler 处理唤醒

**新增 Handler**：`src/vibe3/domain/handlers/dependency_wake_up.py`

```python
from vibe3.domain.events import DependencySatisfied
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from loguru import logger

def handle_dependency_satisfied(event: DependencySatisfied) -> None:
    """Wake up flows waiting on this dependency."""
    logger.bind(
        domain="dependency_handler",
        satisfied_issue=event.issue_number,
        pr_number=event.pr_number,
    ).info("Dependency satisfied, checking dependents")

    store = SQLiteClient()
    gh = GitHubClient()

    # Find all flows waiting on this issue
    waiting_flows = _find_waiting_flows(store, event.issue_number)

    for flow in waiting_flows:
        branch = flow.get("branch")
        blocked_by = flow.get("blocked_by_issue")

        if blocked_by != event.issue_number:
            continue  # Not blocked by this specific issue

        # Check if ALL dependencies are now satisfied
        all_deps = _get_all_dependencies(store, branch)
        all_satisfied = all(
            _is_issue_satisfied(gh, dep) for dep in all_deps
        )

        if all_satisfied:
            # Wake up this flow
            _wake_up_flow(store, gh, branch, event.pr_number)

def _find_waiting_flows(store: SQLiteClient, dep_issue_number: int) -> list[dict]:
    """Find flows blocked by this specific issue."""
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM flow_state "
            "WHERE flow_status = 'waiting' AND blocked_by_issue = ?",
            (dep_issue_number,),
        )
        return [dict(row) for row in cursor.fetchall()]

def _get_all_dependencies(store: SQLiteClient, branch: str) -> list[int]:
    """Get all dependency issue numbers for this branch."""
    with sqlite3.connect(store.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT issue_number FROM flow_issue_links "
            "WHERE branch = ? AND issue_role = 'dependency'",
            (branch,),
        )
        return [row[0] for row in cursor.fetchall()]

def _is_issue_satisfied(gh: GitHubClient, issue_number: int) -> bool:
    """Check if issue is completed (PR created/closed)."""
    # Same as Phase 1.2 _is_dependency_satisfied()
    # ...

def _wake_up_flow(
    store: SQLiteClient,
    gh: GitHubClient,
    branch: str,
    source_pr_number: int,
) -> None:
    """Wake up waiting flow and create branch from dependency PR."""
    # 1. Update flow status
    store.update_flow_state(
        branch,
        flow_status="active",
        blocked_by_issue=None,
        blocked_reason=None,
    )

    # 2. Add wake-up event
    store.add_event(
        branch,
        "dependency_wake_up",
        "orchestra:dependency_handler",
        detail=f"Dependencies satisfied, ready to proceed",
        refs={"source_pr": str(source_pr_number)},
    )

    # 3. Sync GitHub labels
    links = store.get_issue_links(branch)
    task_issue = next((l for l in links if l.get("issue_role") == "task"), None)

    if task_issue:
        issue_number = task_issue.get("issue_number")
        gh.remove_labels(issue_number, ["state/blocked"], repo=...)
        gh.add_labels(issue_number, ["state/ready"], repo=...)

    # 4. CRITICAL: Create development branch from dependency PR branch
    _create_branch_from_pr(store, branch, source_pr_number)

def _create_branch_from_pr(
    store: SQLiteClient,
    branch: str,
    source_pr_number: int,
) -> None:
    """Create development branch from dependency PR head branch.

    This ensures the dependent work builds on the dependency's work,
    not on origin/main (which may not have merged changes yet).
    """
    from vibe3.clients.git_client import GitClient

    gh = GitHubClient()
    git = GitClient()

    # Get PR info
    pr = gh.get_pr(source_pr_number, repo=...)
    if not isinstance(pr, dict):
        logger.error(f"Cannot fetch PR #{source_pr_number}")
        return

    source_branch = pr.get("head", {}).get("ref")
    if not source_branch:
        logger.error(f"PR #{source_pr_number} has no head branch")
        return

    # Create dependent branch from source PR branch
    try:
        # Fetch source branch
        git.fetch_branch(source_branch)

        # Create new branch from source branch
        # Note: This happens in worktree manager later, here we just record intent
        logger.info(
            f"Will create {branch} from {source_branch} "
            f"(PR #{source_pr_number}) when manager starts"
        )

        # Store branch creation intent in flow metadata
        store.update_flow_state(
            branch,
            # Add custom field for branch source
            # Or rely on handoff instructions
        )
    except Exception as e:
        logger.error(f"Failed to prepare branch from PR: {e}")
```

### Phase 3: Worktree 分支创建策略

#### 3.1 Manager 分支选择逻辑

**修改文件**：`src/vibe3/environment/worktree_manager.py`

```python
def resolve_manager_cwd(
    self,
    issue_number: int,
    branch: str,
) -> tuple[Path | None, str | None]:
    """Resolve worktree cwd, considering dependency branch source."""
    store = SQLiteClient()
    flow = store.get_flow_state(branch)

    if not flow:
        # Default: create from main
        return self._create_from_main(branch), None

    # Check if this flow was woken up from waiting
    events = store.get_events(branch, event_type="dependency_wake_up")
    if events:
        # Get source PR from wake-up event
        source_pr_ref = events[0].get("refs", {}).get("source_pr")
        if source_pr_ref:
            source_pr_number = int(source_pr_ref)
            # Create from dependency PR branch
            return self._create_from_pr_branch(branch, source_pr_number), None

    # Default: create from main
    return self._create_from_main(branch), None

def _create_from_pr_branch(self, branch: str, pr_number: int) -> Path:
    """Create worktree from PR head branch."""
    gh = GitHubClient()
    pr = gh.get_pr(pr_number, repo=self.config.repo)

    if not isinstance(pr, dict):
        raise ValueError(f"Cannot fetch PR #{pr_number}")

    source_branch = pr.get("head", {}).get("ref")
    if not source_branch:
        raise ValueError(f"PR #{pr_number} has no head branch")

    # Ensure source branch is fetched
    self._git_client.fetch_branch(source_branch)

    # Create worktree from source branch
    worktree_path = self._create_worktree(branch, base_branch=source_branch)

    logger.info(
        f"Created worktree for {branch} from {source_branch} "
        f"(PR #{pr_number})"
    )

    return worktree_path
```

## 实施步骤

### Step 1: 添加 waiting 状态（低风险）
1. 修改 `flow_status` Literal 类型
2. 更新 UI 显示逻辑
3. 无破坏性，向后兼容

### Step 2: Dispatcher 筛选逻辑（中风险）
1. 修改 `collect_ready_issues()`
2. 添加依赖检查和 waiting 标记
3. 测试：确保不影响现有 ready flows

### Step 3: 唤醒机制（中风险）
1. 定义 `DependencySatisfied` 事件
2. 在 PR create 时触发
3. 实现 domain handler

### Step 4: 分支创建策略（高风险）
1. 修改 worktree manager
2. 确保 PR branch 可访问
3. 测试：从 PR branch 创建 worktree 的完整性

## 验证标准

### 功能验证

1. **依赖方向测试**
   - 创建 flow A → depends on → flow B
   - 确认：A 进入 waiting，B 保持 ready

2. **唤醒测试**
   - B 完成 PR create
   - 确认：A 自动从 waiting → ready
   - 确认：A 的开发分支从 B 的 PR branch 创建

3. **多依赖测试**
   - flow A → depends on → B, C
   - B 完成 → A 仍 waiting
   - C 完成 → A wake up（所有依赖满足）

### 边界情况

1. **循环依赖检测**
   - A → B → A（应拒绝或报错）

2. **PR 未合并**
   - B PR create 但未合并
   - A 仍可从 B 的 branch 开发（这是正确行为）

3. **依赖 PR 关闭/放弃**
   - B 的 PR closed without merge
   - A 应如何处理？（需要人工决策）

## 关键文件清单

### 需修改的文件

1. `src/vibe3/models/flow.py` - flow_status 类型扩展
2. `src/vibe3/orchestra/services/state_label_dispatch.py` - dispatcher 筛选逻辑
3. `src/vibe3/services/pr_service.py` - PR create 触发唤醒
4. `src/vibe3/domain/handlers/dependency_wake_up.py` - 新增唤醒 handler
5. `src/vibe3/environment/worktree_manager.py` - 分支创建策略
6. `src/vibe3/domain/events.py` - 新增 DependencySatisfied 事件定义

### 利用已有基础设施

1. `flow_issue_links` 表 - dependency 关系存储
2. `blocked_by_issue` 字段 - 依赖真源字段
3. `get_flow_dependents()` - 查询依赖方 helper
4. `flow_state.blocked_reason` - 阻塞原因字段
5. Event bus infrastructure - 事件发布机制

## 风险评估

### 低风险
- waiting 状态定义（纯类型扩展）
- UI 显示调整

### 中风险
- Dispatcher 逻辑改造（影响调度流程）
- 唤醒事件触发（需要事件 bus 稳定）

### 高风险
- Worktree 分支创建策略（git 操作，需要充分测试）
- 多依赖场景（复杂度增加）

## 替代方案

### 方案 A：最小侵入（仅修复方向）
- 只修改 `vibe3 flow blocked --by` 的语义
- 不实现自动唤醒
- Blocked flow 需人工 resume
- **优点**：最小改动
- **缺点**：无自动化，用户体验差

### 方案 B：完整方案（推荐）
- 实现 waiting 状态
- 实现自动唤醒
- 实现 PR branch 创建策略
- **优点**：完整的依赖处理闭环
- **缺点**：改动较大，需要充分测试

### 方案 C：混合方案
- Phase 1-2 实施（waiting + 唤醒）
- Phase 3-4 暂缓（分支策略需更多讨论）
- **优点**：渐进式，风险可控
- **缺点**：开发分支仍从 main 创建，可能冲突

## 推荐方案

**采用方案 B（完整方案）**，理由：

1. **核心需求明确**：依赖处理是 orchestra 的关键能力
2. **已有基础设施充分**：大部分 helper 和字段已存在
3. **一次性解决**：避免后续补丁式修复
4. **测试可控**：可通过集成测试验证闭环

建议分阶段实施，每阶段完成后验证，逐步推进至完整方案。

---

**维护者**：Vibe Team
**创建日期**：2026-04-20
**版本**：1.0