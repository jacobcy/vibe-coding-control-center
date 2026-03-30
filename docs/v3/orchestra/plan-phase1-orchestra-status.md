---
document_type: plan
title: "Phase 1: OrchestraStatusService — 系统可观测性"
phase: 1
status: draft
author: "Claude"
created: "2026-03-30"
depends_on:
  - src/vibe3/orchestra/heartbeat.py
  - src/vibe3/orchestra/event_bus.py
  - src/vibe3/orchestra/flow_orchestrator.py
  - src/vibe3/services/label_service.py
  - src/vibe3/models/orchestration.py
---

# Phase 1: OrchestraStatusService — 系统可观测性

## 目标

为 Orchestra 提供聚合状态视图，使 governance skill（vibe-orchestra、vibe-roadmap）
和运维人员能看到系统全貌。类似 reviewer 拿到 structure 信息后才能做决策，
orchestrator 也需要一个整合的"眼睛"。

## 当前实现状态（2026-03-30）

**已完成（核心功能全部就位）：**

- `src/vibe3/orchestra/services/status_service.py` — OrchestraStatusService + IssueStatusEntry + OrchestraSnapshot
- `src/vibe3/commands/orchestra.py` — `vibe3 orchestra status` CLI（含 `--json` 模式）
- `src/vibe3/ui/orchestra_ui.py` — 文本/JSON 渲染
- `serve.py:91-94` — `GET /status` HTTP endpoint，集成在 `_build_server()` 中
- `tests/vibe3/orchestra/test_status_service.py` — 7 个用例，全部通过

**与本计划的差距（待补齐）：**

1. `IssueStatusEntry` 缺少 `blocked_by: list[int]`（来自 DependencyChecker）
2. `OrchestraSnapshot` 缺少 `services_registered` 和 `queue_size`（来自 HeartbeatServer）
3. `server_running` 硬编码 `True`，不反映真实 server 状态
4. `snapshot()` 缺少 TTL 缓存，频繁调用会消耗 API quota
5. `protocols.py:91` 中 `list_issues` 签名缺少 `assignee` 参数（与实现不一致）

## 核心原则

- **只读聚合**：不引入新真源，从现有数据源（GitHub Labels、FlowService、GitClient）
  拉取并组装
- **复用优先**：LabelService.get_state()、FlowOrchestrator.get_flow_for_issue()、
  GitClient.list_worktrees() 已有能力，不重新实现
- **最小新增**：一个 service + 一个 CLI 子命令 + 一个 HTTP endpoint

## 数据源与聚合

```
GitHub Issues (labels) --> LabelService.get_state()
                           |
Flow State (.git/vibe3/) --> FlowService --> active flows, branches
                           |
Git Worktrees ----------> GitClient.list_worktrees()
                           |
HeartbeatServer ----------> running, queue_size, service_names
                           |
                           v
                   OrchestraStatusService
                           |
                           v
             OrchestraSnapshot (frozen dataclass)
```

## 数据模型（目标）

```python
@dataclass(frozen=True)
class IssueStatusEntry:
    """单个 issue 的聚合状态。"""
    number: int
    title: str
    state: IssueState | None      # 来自 label
    assignee: str | None
    has_flow: bool
    flow_branch: str | None
    has_worktree: bool
    worktree_path: str | None
    has_pr: bool
    pr_number: int | None
    blocked_by: list[int]         # 待补齐：来自 DependencyChecker

@dataclass(frozen=True)
class OrchestraSnapshot:
    """Orchestra 全局状态快照。"""
    timestamp: float
    server_running: bool          # 待改进：应反映真实状态
    services_registered: list[str]  # 待补齐：来自 HeartbeatServer
    queue_size: int               # 待补齐：来自 HeartbeatServer
    active_issues: tuple[IssueStatusEntry, ...]
    active_flows: int
    active_worktrees: int
    circuit_breaker_state: str    # Phase 2 占位，默认 "closed"
```

## 待补齐实现

### 1. blocked_by 字段

```python
# 在 OrchestraStatusService.__init__ 中
from vibe3.orchestra.dependency_checker import DependencyChecker
self._dep_checker = DependencyChecker(config.repo)

# 在 snapshot() 的 issue 遍历中
blocked_by = self._dep_checker.get_blockers(number)  # 返回 list[int]
```

DependencyChecker 已有 TTL 缓存（5 分钟），可直接复用。

### 2. HeartbeatServer 运行时信息

需要在 `_build_server()` 中将 heartbeat 引用传入 status_service：

```python
status_service = OrchestraStatusService(
    config,
    github=shared_github,
    orchestrator=shared_orchestrator,
    heartbeat=heartbeat,          # 新增：传入 heartbeat 实例
)
```

OrchestraStatusService 从 heartbeat 读取 `service_names`、`queue_size`、`running`。

### 3. TTL 缓存

```python
_CACHE_TTL_SECONDS = 60  # 1 分钟内重复调用直接返回缓存

def snapshot(self) -> OrchestraSnapshot:
    now = time.time()
    if self._cached and now - self._cache_time < _CACHE_TTL_SECONDS:
        return self._cached
    result = self._build_snapshot()
    self._cached = result
    self._cache_time = now
    return result
```

### 4. protocols.py 同步

```python
# protocols.py
def list_issues(
    self,
    limit: int = 30,
    state: str = "open",
    assignee: str | None = None,  # 补齐此参数
) -> list[dict[str, Any]]:
```

## 为 Governance Skill 提供上下文

OrchestraSnapshot 设计为可序列化输出，供 skill 消费：

```python
# 在 skill context builder 中（Phase 2 实现）
snapshot = status_service.snapshot()
context = format_snapshot_for_skill(snapshot)
```

## 验收标准

1. `vibe3 orchestra status` 可输出当前系统状态 ✅（已完成）
2. `GET /status` 返回 JSON 格式的 OrchestraSnapshot ✅（已完成）
3. OrchestraSnapshot 包含 issues + flows + worktrees 聚合 ✅（已完成）
4. `blocked_by` 字段纳入 IssueStatusEntry（待补齐）
5. `services_registered` + `queue_size` 纳入 OrchestraSnapshot（待补齐）
6. `snapshot()` 有 TTL 缓存（待补齐）
7. 不引入新的持久化存储 ✅

## 风险

- **API 调用频率**：snapshot() 每次调用可能触发 GitHub API。
  缓解：加 TTL 缓存（参见上方实现方案）
- **大量 issue 时性能**：只查询已分配给 manager_usernames 的 open issues，
  而非全量 issue 列表
