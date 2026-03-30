---
document_type: plan
title: "Phase 3: Feedback Loop + MCP 对外接口"
phase: 3
status: draft
author: "Claude"
created: "2026-03-30"
depends_on:
  - docs/v3/orchestra/plan-phase1-orchestra-status.md
  - docs/v3/orchestra/plan-phase2-governance-circuit-breaker.md
  - src/vibe3/orchestra/heartbeat.py
  - src/vibe3/orchestra/services/assignee_dispatch.py
---

# Phase 3: Feedback Loop + MCP 对外接口

## 目标

1. **Feedback Loop**：Manager 执行结果（成功/失败/blocked）反馈到 issue label，
   形成完整的 `issue -> dispatch -> execute -> feedback` 闭环
2. **MCP Server**：对外暴露 Orchestra 状态，让其他系统（Claude Code、外部 AI agent、
   监控工具）可以观测和查询系统运行状况

## Part A: Feedback Loop — 执行结果收敛

### 当前缺口

现有链路：`webhook -> dispatch -> _run_command()` 完成后，只有 stdout/stderr
日志记录，没有结构化反馈。Issue 的 state label 停留在 `state/in-progress`，
不会根据执行结果前进或回退。

### 目标状态

```
dispatch_manager()
    |
    +-- success + PR exists --> state/review
    |
    +-- success + no PR    --> state/in-progress (保持，agent 未完成工作)
    |
    +-- api_error/timeout  --> circuit breaker + state/blocked
    |                          + issue comment 说明原因
    |
    +-- business_error     --> state/in-progress (保持，不自动回退)
```

### 实现

在 `Dispatcher.dispatch_manager()` 返回路径上增加反馈：

```python
def dispatch_manager(self, issue: IssueInfo) -> bool:
    ...
    success = self._run_command(cmd, manager_cwd, "Manager execution")

    # Feedback: update state based on result
    if success:
        self._on_dispatch_success(issue, flow_branch)
    else:
        self._on_dispatch_failure(issue, self._last_error_category)

    return success

def _on_dispatch_success(self, issue: IssueInfo, flow_branch: str) -> None:
    """执行成功后检查 PR 状态，推进 issue state。"""
    pr_number = self.orchestrator.get_pr_for_issue(issue.number)
    if pr_number:
        self._update_state_label(issue.number, IssueState.REVIEW)
        logger.bind(domain="orchestra").info(
            f"Issue #{issue.number}: dispatch success, PR #{pr_number} exists, "
            f"advancing to state/review"
        )
    # 无 PR 则保持 in-progress，不做操作

def _on_dispatch_failure(self, issue: IssueInfo, category: str) -> None:
    """执行失败后根据错误类型设置状态。"""
    if category in ("api_error", "timeout"):
        self._update_state_label(issue.number, IssueState.BLOCKED)
        self._post_failure_comment(
            issue.number,
            f"Orchestra dispatch 失败（{category}），已暂停调度，等待恢复"
        )

def _post_failure_comment(self, issue_number: int, reason: str) -> None:
    """在 issue 上留下失败原因 comment。"""
    try:
        from vibe3.clients.github_client import GitHubClient
        GitHubClient().create_comment(
            issue_number,
            f"[Orchestra] {reason}",
            repo=self.config.repo,
        )
    except Exception as exc:
        logger.bind(domain="orchestra").warning(
            f"Failed to post failure comment for #{issue_number}: {exc}"
        )
```

### 事件日志

引入轻量事件日志，记录 dispatch 结果，复用 FlowService 的 event 机制：

```python
# 成功时
self.orchestrator.flow_service.record_event(
    branch=flow_branch,
    event_type="dispatch_result",
    data={"success": True, "issue": issue.number, "pr": pr_number},
    actor="orchestra:dispatcher",
)

# 失败时
self.orchestrator.flow_service.record_event(
    branch=flow_branch,
    event_type="dispatch_result",
    data={"success": False, "issue": issue.number, "category": category},
    actor="orchestra:dispatcher",
)
```

这样 `vibe3 flow show` 可以看到 dispatch 历史，与现有 flow 生命周期一致。

## Part B: MCP Server — 对外可观测性

### 设计思路

MCP (Model Context Protocol) 让外部 AI agent 可以通过标准接口查询 Orchestra 状态。
适合的场景：

- Claude Code 用户想知道"当前 orchestra 在处理什么 issue"
- 外部监控 agent 想聚合多个项目的 orchestra 状态
- 开发团队的 AI 助手想了解自动化执行进度

### MCP Resource 设计

```json
{
  "resources": [
    {
      "uri": "orchestra://status",
      "name": "Orchestra Status",
      "description": "当前 Orchestra 系统全局状态快照",
      "mimeType": "application/json"
    },
    {
      "uri": "orchestra://issues",
      "name": "Managed Issues",
      "description": "Orchestra 管理的 issue 列表及其状态",
      "mimeType": "application/json"
    },
    {
      "uri": "orchestra://circuit-breaker",
      "name": "Circuit Breaker State",
      "description": "Dispatch circuit breaker 当前状态",
      "mimeType": "application/json"
    }
  ]
}
```

### MCP Tool 设计

```json
{
  "tools": [
    {
      "name": "orchestra_status",
      "description": "获取 Orchestra 系统状态快照",
      "inputSchema": {}
    },
    {
      "name": "orchestra_issue_detail",
      "description": "获取单个 issue 的 orchestra 管理详情",
      "inputSchema": {
        "type": "object",
        "properties": {
          "issue_number": {"type": "integer"}
        },
        "required": ["issue_number"]
      }
    },
    {
      "name": "orchestra_dispatch_history",
      "description": "查看最近的 dispatch 执行记录（来自 flow events）",
      "inputSchema": {
        "type": "object",
        "properties": {
          "limit": {"type": "integer", "default": 10}
        }
      }
    }
  ]
}
```

### 实现方案

#### 方案选择：SSE-based MCP over HTTP

Orchestra 已有 FastAPI HTTP 服务（serve.py），MCP server 可以直接挂载为
FastAPI 的子路由，复用同一端口，零额外基础设施：

```python
# src/vibe3/orchestra/mcp_server.py
from mcp.server.fastmcp import FastMCP

def create_mcp_server(status_service: OrchestraStatusService) -> FastMCP:
    mcp = FastMCP("orchestra")

    @mcp.resource("orchestra://status")
    def get_status_resource() -> str:
        snapshot = status_service.snapshot()
        return json.dumps(_serialize_snapshot(snapshot), indent=2)

    @mcp.tool()
    def orchestra_status() -> str:
        """获取 Orchestra 系统当前状态。"""
        snapshot = status_service.snapshot()
        return format_snapshot_for_mcp(snapshot)

    @mcp.tool()
    def orchestra_issue_detail(issue_number: int) -> str:
        """获取指定 issue 的 Orchestra 管理详情。"""
        snapshot = status_service.snapshot()
        for entry in snapshot.active_issues:
            if entry.number == issue_number:
                return json.dumps(asdict(entry), indent=2)
        return json.dumps({"error": f"Issue #{issue_number} not in active issues"})

    return mcp
```

在 `serve.py` 的 `_build_server()` 中挂载：

```python
# 仅在依赖可用时启用 MCP
try:
    from vibe3.orchestra.mcp_server import create_mcp_server
    mcp = create_mcp_server(status_service)
    fastapi_app.mount("/mcp", mcp.sse_app())
    logger.bind(domain="orchestra").info("MCP server mounted at /mcp")
except ImportError:
    logger.bind(domain="orchestra").debug("mcp package not available, skipping MCP server")
```

外部系统连接：

```json
{
  "mcpServers": {
    "orchestra": {
      "url": "http://localhost:8080/mcp/sse"
    }
  }
}
```

### 依赖

```toml
# pyproject.toml 可选依赖
[project.optional-dependencies]
mcp = ["mcp>=1.0.0"]
```

MCP server 为可选功能，不安装 `mcp` 包时自动降级跳过，不影响核心功能。

### 安全考虑

- MCP 端点与 webhook 共享同一 HTTP 服务，但不需要 webhook secret 认证
- MCP 只暴露只读信息（status、history），不提供写操作
- 敏感信息（token、secret、完整 stderr）不出现在 MCP 响应中
- 如需限制访问，可在 FastAPI 层添加 API key 中间件（可选）

## Part C: 完整闭环验证

Phase 1-3 完成后的完整链路：

```
1. GovernanceService (on_tick, 每 ~1 小时)
   |-- 获取 OrchestraSnapshot (Phase 1)
   |-- 构建 context plan
   |-- 调用 vibe3 run --plan (governance skill)
   |
2. Governance Skill 决策
   |-- 调整 issue label (priority, state)
   |-- 分配 issue 给 vibe-manager-agent
   |
3. GitHub 发送 webhook (issues/assigned)
   |
4. AssigneeDispatchService 处理
   |-- DependencyChecker 检查依赖
   |-- FlowOrchestrator 创建/复用 flow
   |-- Dispatcher 在 worktree 中执行
   |-- Circuit Breaker 检查（Phase 2）
   |
5. Dispatcher 执行结果反馈（Phase 3）
   |-- success + PR: 推进 state -> review
   |-- api_error: circuit breaker + state/blocked + comment
   |-- event 写入 flow history
   |
6. MCP Server 全程暴露状态（Phase 3）
   |-- 外部系统可查询进度
   |-- Claude Code 用户可通过 MCP tool 了解情况
```

## 验收标准

### Feedback Loop

1. Manager dispatch 成功且有 PR 时，issue state 自动推进到 `state/review`
2. API 错误导致的失败触发 circuit breaker + `state/blocked` + issue comment
3. 执行结果通过 FlowService event 可追溯（`vibe3 flow show` 可见）
4. business_error 不自动回退 state（保留人工判断空间）

### MCP Server

1. MCP server 在 `vibe3 serve start` 时自动挂载（依赖可用时）
2. 外部 AI agent 可通过 SSE 连接获取 orchestra 状态
3. MCP resource `orchestra://status` 返回 OrchestraSnapshot JSON
4. MCP tool 可查询单个 issue 详情
5. 未安装 `mcp` 包时优雅降级，不影响核心功能

## 风险

- **MCP 协议稳定性**：MCP 仍在演进中，API 可能变化。
  缓解：使用官方 `mcp` Python SDK，标注最低版本要求；以可选依赖形式引入
- **Feedback 误判**：dispatch 进程成功退出不等于 agent 完成了工作。
  缓解：成功只意味着进程正常退出 + PR 已创建，不自动跳到 `state/done`
- **循环触发**：feedback 修改 label -> webhook -> 重复 dispatch。
  缓解：AssigneeDispatchService 已有 `_dispatched_issues` 去重；
  状态推进到 `state/review` 后不会再触发 assignee dispatch

## 工作量估算

### Feedback Loop
- `Dispatcher` 反馈逻辑（`_on_dispatch_success/failure`）：~80 行
- `_post_failure_comment` + FlowService event 集成：~40 行
- 测试：~100 行

### MCP Server
- `src/vibe3/orchestra/mcp_server.py`：~100 行
- `serve.py` 集成（可选挂载）：~20 行
- 测试（mock MCP）：~50 行

### 总计：~390 行

## 未来方向

- **MCP 写操作**：允许外部 agent 通过 MCP 触发 governance 扫描或手动分配 issue
- **Webhook 转发**：将 GitHub webhook 事件作为 MCP notification 推送给订阅者
- **多项目聚合**：MCP server 支持多个 repo 的 orchestra 状态聚合
- **Dashboard**：基于 MCP 数据构建简单的 web dashboard
