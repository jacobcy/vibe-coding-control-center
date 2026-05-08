# Orchestra 模块

`vibe3 serve` 的核心是一个长期运行的 driver / 调度器。

统一 runtime 语义以
[docs/standards/vibe3-orchestra-runtime-standard.md](docs/standards/vibe3-orchestra-runtime-standard.md)
为准。

## 架构

```
vibe3 serve start --port 8080
  |
  +-- FastAPI (0.0.0.0:8080)
  |     POST /webhook/github    GitHub 实时推送
  |     GET  /health / /status
  |
  +-- HeartbeatServer (asyncio)
        Semaphore(3)            最多 3 个并发任务
        |
        +-- 事件路径 (实时, 主路径)
        |     接收 webhook -> 匹配 service -> handle_event()
        |
        +-- 心跳路径 (每 900s, 兜底)
              遍历已注册 service -> on_tick()
```

## 触发机制

当前应按两层理解：

### 1. Governance / Supervisor 决定 ready

以下角色负责把 issue 推进到 `state/ready`：

- governance
- supervisor / triage agent
- 人工治理

### 2. State Trigger 消费已有状态

driver 在 heartbeat tick 中消费已有 `state/*`：

- `state/ready` -> manager
- `state/claimed` -> plan
- `state/in-progress` -> run
- `state/review` -> review

补充：

- `state/blocked` 表示无法继续推进（包括业务阻塞和执行失败）
  - blocked_reason 字段记录具体原因
  - 人工 resume 恢复执行

## 内置 Service

| Service | event_types | 功能 |
|---------|-------------|------|
| `AssigneeDispatchService` | `issues` | assignee 变化的兼容入口 |
| `CommentReplyService` | `issue_comment` | `@vibe-manager` 提及 → 自动 ACK 回复 |
| `StateLabelDispatchService(manager)` | heartbeat tick | `state/ready` -> manager |
| `StateLabelDispatchService(plan)` | heartbeat tick | `state/claimed` → plan |
| `StateLabelDispatchService(run)` | heartbeat tick | `state/in-progress` → run |
| `StateLabelDispatchService(review)` | heartbeat tick | `state/review` → review |
| `GovernanceService` | heartbeat tick | 周期性治理扫描；可决定 ready 候选 |
| `SupervisorHandoffService` | heartbeat tick | 消费治理 handoff issue |

## 注册自定义 Service

```python
from vibe3.runtime.service_protocol import GitHubEvent, ServiceBase
from vibe3.runtime.heartbeat import HeartbeatServer

class MyService(ServiceBase):
    event_types = ["pull_request"]

    async def handle_event(self, event: GitHubEvent) -> None:
        if event.action == "opened":
            ...  # 处理 PR 开启事件

    async def on_tick(self) -> None:
        ...  # 每 900s 轮询兜底

heartbeat = HeartbeatServer(config)
heartbeat.register(MyService())
```

## 部署（开发服务器）

```bash
# 启动
vibe3 serve start --port 8080

# 后台运行
tmux new -d -s orchestra 'vibe3 serve start --port 8080'

# GitHub Webhook 配置：
#   URL: http://<server>:8080/webhook/github
#   Events: Issues, Issue comments
#   Secret: 设置 ORCHESTRA__WEBHOOK_SECRET 环境变量
```

## 配置

`config/v3/settings.yaml` 中的 `orchestra` 节：

```yaml
orchestra:
  enabled: true
  polling_interval: 900        # 正常模式默认 15 分钟
  debug_polling_interval: 60   # debug 模式默认 1 分钟
  port: 8080
  repo: owner/repo             # 留空则用当前 repo
  max_concurrent_flows: 3
  webhook_secret: ""           # 强烈建议生产环境配置
  manager_usernames:
    - vibe-manager
  comment_reply:
    enabled: true
```

## 文件结构

```
orchestra/
  runtime/service_protocol.py   GitHubEvent 模型 + ServiceBase 协议
  heartbeat.py                  HeartbeatServer：事件循环 + 服务注册表
  webhook_handler.py     FastAPI router：HMAC 验签 + 事件解析
  serve.py               CLI 入口（start / stop / status）
  config.py              OrchestraConfig
  dependency_checker.py  解析 blocked-by + 检查依赖是否 closed
  dispatcher.py          Dispatcher：执行具体命令（plan / run / review / manager）
  flow_orchestrator.py   FlowOrchestrator：flow 创建 + 分支切换
  router.py              Router：label 状态变化 → 命令（legacy）
  poller.py              Poller：旧版轮询器（已废弃，保留向后兼容）
  master.py              TriageDecision：新 issue 分类逻辑
  master_handler.py      MasterAgentHandler：调用 master agent
  models.py              IssueInfo, Trigger
  services/
    assignee_dispatch.py  AssigneeDispatchService
    comment_reply.py      CommentReplyService
```

---

## 已知问题：与基础设施的集成缺口

当前 orchestra 模块与 vibe3 其他层处于**半分离状态**：独立实现了一批能力，
但又无法真正独立，因为核心流程（flow 生命周期、状态机）还是要依赖共享层。

### 重复实现清单

| 操作 | 现有基础设施 | Orchestra 的做法 | 文件 |
|------|-------------|-----------------|------|
| 列出 issues | `GitHubClient.list_issues()` | `subprocess(gh issue list)` | `poller.py`, `assignee_dispatch.py` |
| 查看 issue | `GitHubClient.view_issue()` | `subprocess(gh issue view)` | `master_handler.py`, `dependency_checker.py` |
| 关闭 issue | 缺失（应加入 GitHubClient） | `subprocess(gh issue close)` | `master_handler.py` |
| 发评论 | 缺失（应加入 GitHubClient） | `subprocess(gh issue comment)` | `master_handler.py`, `comment_reply.py` |
| PR ↔ issue 关联 | 缺失（应加入 GitHubClient） | `subprocess(gh pr list)` 手动过滤 | `flow_orchestrator.py` |
| 创建 flow | `FlowService.create_flow_with_branch()` | 直接写 SQLite，绕过 FlowService | `flow_orchestrator.py` |
| 记录 flow 事件 | `FlowLifecycleMixin` | 未使用，无事件记录 | `flow_orchestrator.py` |

### 根本问题

`FlowOrchestrator` 绕过了 `FlowService`，直接操作 SQLiteClient。
这导致：
- orchestra 创建的 flow 不触发生命周期事件
- 无法通过 `vibe3 flow show` 正常看到 orchestra 启动的任务状态
- 两套 flow 创建路径，维护成本加倍

### 建议修复路径

**高优先级**：
1. 在 `GitHubClient` 补充缺失方法：`close_issue()`, `add_comment()`, `get_pr_for_issue()`
2. `FlowOrchestrator.create_flow_for_issue()` 改为调用 `FlowService.create_flow_with_branch()`

**中优先级**：
3. `poller.py` / `assignee_dispatch.py` 的 `gh issue list` 替换为 `GitHubClient.list_issues()`
4. `dependency_checker.py` 的 `gh issue view` 替换为 `GitHubClient.view_issue()`
