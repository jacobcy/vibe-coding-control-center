# Orchestra 拆分方案

**状态**: Ready
**背景**: 研究现有代码后得出，已与产品方向确认
**原则**: 不破坏现有行为，边界清晰优先于代码量减少

---

## 前提确认

### V2 / V3 关系（完全独立，不动 V2）

V2 Shell (`bin/vibe`, `lib/`) 和 V3 Python (`src/vibe3/`) 没有双向调用：
- V3 不调用 V2 Shell
- V2 只提供 `lib/alias/vibe3.sh` 别名指向 `uv run python -m vibe3`

**结论**：V2 保持不动（alias/worktree 基础功能），V3 完全独立演进。

---

## 架构概念定义

三层职责，边界清晰：

```
Server 层
  职责：启动并监听，接受服务注册，驱动心跳
  包含：HTTP webhook 监听、MCP 服务器、服务注册工厂、HeartbeatServer
  心跳程序组成：由 settings.yaml 配置，注册哪些 Service 就运行哪些

Dispatcher 层
  职责：接受"执行 issue"的请求，调度 agent 运行，观测执行结果
  包含：worktree 解析、命令构造、subprocess 执行、成功/失败处理
  不包含：决策（谁应该被执行）、状态判断（issue 是否就绪）

Orchestra 层（编排依据）
  职责：提供决策——哪些 issue 应该推进，推进到什么状态
  包含：flow_orchestrator（issue→flow 映射）、governance prompt、状态转换规则
  执行者：orchestra agent（AI），由心跳每 15 分钟触发
  输出：状态标签变更（不是直接调用 dispatcher）
```

---

## 完整触发流程

### 流程一：外部事件触发（实时）

```
GitHub 事件
  issues/assigned → webhook → Server.app.py
                             → AssigneeDispatchService.on_event()
                             → Dispatcher.dispatch_manager(issue)
                             → agent 执行

  issues/labeled (label=state/ready)
                           → webhook → Server.app.py
                                      → StateLabelDispatchService.handle_event()
                                      → Dispatcher.dispatch_manager(issue)
                                      → dispatcher 先将标签改为 state/in-progress
                                      → agent 执行

  pull_request/review_requested → webhook → Server.app.py
                                           → PRReviewDispatchService.on_event()
                                           → Dispatcher.dispatch_pr_review(pr)
                                           → review agent 执行
```

### 流程二：心跳触发（每 15 分钟）

```
HeartbeatServer tick（每 15 分钟）
  - GovernanceService.on_tick()
      运行 orchestra agent（AI 分析所有 issue）
      orchestra agent 做决策，输出：
        - issue #42 依赖解除 → 设置 state/ready 标签
        - issue #17 卡住了   → 设置 state/blocked 标签
        - issue #8 已完成    → 设置 state/done 标签
      （orchestra agent 只改标签，不直接调用 dispatcher）

  - [新增] StateLabelDispatchService.on_tick()
      作为 webhook 漏接时的 fallback，扫描所有
      state/ready 且未在执行中（非 state/in-progress）的 issue
      → Dispatcher.dispatch_manager(issue)
      → dispatcher 先将标签改为 state/in-progress（声明占用，防重入）
      → agent 执行任务
      → 成功：state/in-progress → state/review
      → 失败：state/in-progress → state/blocked
```

### 为什么用 state 标签触发，不用 assignee

| | 改 assignee 触发 | 改 state 标签触发（本方案）|
|--|---------|---------|
| 语义 | 归属关系（谁负责） | 系统状态（处于哪个阶段） |
| 现有设施 | 无状态机 | 已有 IssueState 枚举 + VALID_TRANSITIONS |
| 可读性 | AI 频繁改 assignee，人类看不懂 | state/ready → state/in-progress，清晰 |
| 解耦 | orchestra 和 dispatcher 通过 assignee 耦合 | orchestra 只改标签，dispatcher 独立检测 |
| 防重入 | 需要额外机制 | state/in-progress 本身即占用标志 |

**assignee 的正确语义**：人工指派或 dispatcher 接手时设置，表示"谁在执行"，不作为触发信号。

---

## 当前 Orchestra 各组件职责

```
orchestra/ 模块（3675 行，14 个文件）

serve.py              231  CLI 命令入口（start/stop/status）
serve_utils.py        291  服务器装配工厂（组合所有组件）
heartbeat.py          143  事件循环引擎（tick_loop + event_loop）
config.py             257  配置模型（从 settings.yaml 加载）
dispatcher.py         357  执行调度（职责过载，见下文）
dispatcher_worktree.py 230  worktree 路径解析
circuit_breaker.py    228  故障保护
flow_orchestrator.py  118  issue → flow branch 映射
master.py             156  Issue 分诊 AI Agent（orchestra agent 模式）
master_handler.py      80  master 结果处理
prompts.py             65  manager prompt 渲染
mcp_server.py         225  只读 MCP 观察接口
webhook_handler.py     99  HTTP webhook 路由

services/
  assignee_dispatch.py   190  监听 assigned 事件 → 触发 dispatch
  pr_review_dispatch.py   91  监听 review_requested → 触发 dispatch
  governance_service.py  382  周期性运行 orchestra agent
  comment_reply.py        74  回复 @mention
  status_service.py      223  只读状态聚合
```

**Dispatcher 职责超载分析**（357 行中约 220 行不属于核心）：

```
dispatch_manager() 实际做了：
  1. flow 创建（flow_orchestrator）           ← OK，协调调用
  2. worktree 路径解析（dispatcher_worktree） ← OK，基础设施
  3. prompt + command 构造（prompts.py）      ← 应提取到 command_builder
  4. 命令执行（executor.run_command）         ← 核心职责
  5. state label 更新                         ← 应提取到 result_handler
  6. 成功/失败评论、事件记录                  ← 应提取到 result_handler
```

---

## 目标架构

```
src/vibe3/
  server/              <- 新建：服务器层
    __init__.py
    app.py             <- HTTP + webhook 监听（原 serve.py + webhook_handler.py）
    mcp.py             <- MCP 只读接口（原 mcp_server.py）
    registry.py        <- 服务注册工厂（原 serve_utils.py）

  orchestra/           <- 保留：编排层（精简后）
    heartbeat.py       <- 不动（事件循环引擎）
    config.py          <- 不动（配置模型）
    flow_orchestrator.py <- 不动（issue → flow 映射）
    dispatcher.py      <- 精简至 ~130 行（纯调度）
    command_builder.py <- 新增（从 dispatcher 提取：命令构造）
    result_handler.py  <- 新增（从 dispatcher 提取：成功/失败处理）
    dispatcher_worktree.py <- 不动
    circuit_breaker.py <- 不动
    executor.py        <- 不动
    prompts.py         <- 不动
    master.py          <- 不动（orchestra agent）
    master_handler.py  <- 不动

  orchestra/services/  <- 保留，新增一个
    assignee_dispatch.py   <- 不动
    pr_review_dispatch.py  <- 不动
    governance_service.py  <- 不动
    comment_reply.py       <- 不动
    status_service.py      <- 不动
    state_label_dispatch.py <- 新增：检测 state/ready → 触发 dispatch
```

---

## 分步实施方案

每步独立 PR，可单步 revert。

---

### Step 1: 提取 `server/` 模块

**变动**：

```
新建 src/vibe3/server/
  __init__.py
  app.py       ← serve.py（CLI start/stop/status）+ webhook_handler.py（HTTP 路由）
  mcp.py       ← mcp_server.py（整体迁移，无逻辑改动）
  registry.py  ← serve_utils.py（装配工厂 + 服务注册逻辑）

orchestra/ 保留：
  heartbeat.py    不动
  config.py       不动
  dispatcher.py   暂不动（Step 2）
  services/       不动
```

**验收**：`vibe3 serve start/stop/status` 行为不变，mypy 零错误

---

### Step 2: 精简 `dispatcher.py`

从 dispatcher 提取两个新文件：

```python
# orchestra/command_builder.py（约 60 行）
class CommandBuilder:
    def build_manager_command(flow, issue, config) -> AgentCommand: ...
    def build_pr_review_command(pr, flow, config) -> AgentCommand: ...

# orchestra/result_handler.py（约 90 行）
class DispatchResultHandler:
    def on_success(flow, result) -> None: ...   # 更新标签、检查 PR
    def on_failure(flow, error, issue) -> None: ... # 评论、记录事件
```

精简后的 dispatcher.py（目标 ~130 行）：

```python
class Dispatcher:
    def dispatch_manager(issue) -> DispatchResult:
        flow = self.orchestrator.ensure_flow(issue)
        cwd  = self.worktree_resolver.resolve(flow)
        cmd  = self.command_builder.build_manager_command(...)
        result = self.executor.run_command(cmd, cwd)
        self.result_handler.handle(flow, result)
        return result
```

**验收**：现有测试全部通过，dispatcher 行为不变

---

### Step 3: 新增 `StateLabelDispatchService`

新增 `orchestra/services/state_label_dispatch.py`（约 80 行）：

```python
class StateLabelDispatchService(ServiceBase):
    """检测 state/ready 标签，触发 dispatcher 执行。"""

    event_types = ["issues"]  # 订阅 issues/labeled，实时触发

    async def handle_event(self, event: GitHubEvent) -> None:
        if event.action == "labeled" and event.payload["label"]["name"] == "state/ready":
            await self._dispatch_if_needed(issue)

    async def on_tick(self) -> None:
        issues = await self._get_ready_issues()  # polling fallback
        for issue in issues:
            await self._dispatch_if_needed(issue)

    async def _get_ready_issues(self) -> list[Issue]:
        # 查询有 state/ready 标签、无 state/in-progress 标签的 issue
        ...
```

同步更新 `registry.py`（原 serve_utils.py）：在 settings.yaml 中新增
`state_label_dispatch.enabled` 配置项，默认开启。

**验收**：
- 手动给 issue 打 state/ready 标签，可通过 webhook 实时触发 dispatch
- webhook 不可用或漏接时，下个 tick 内可由 polling fallback 触发 dispatch
- webhook 与 polling 重叠时，同一 issue 只会 dispatch 一次

---

### Step 4: 明确 governance prompt 的输出规范

更新 governance_service 的 prompt 模板，明确告知 orchestra agent：

```
决策输出格式：
- 推进 issue → 在 GitHub issue 上设置 state/ready 标签
- 标记阻塞   → 设置 state/blocked 标签（附评论说明原因）
- 标记完成   → 设置 state/done 标签
- 无需操作   → 不改动标签

注意：不要直接 assign，不要直接调用执行命令。
```

**验收**：governance agent 的输出只通过标签变更表达决策。

---

## 现有 Gap 汇总

| Gap | 当前状态 | Step |
|-----|---------|------|
| StateLabelDispatchService 不存在 | AssigneeDispatch 是唯一调度触发 | Step 3 |
| dispatcher 改 state/in-progress 不一致 | 部分有，部分无 | Step 2 |
| governance agent 没有明确的"只改标签"规范 | prompt 无约束 | Step 4 |
| server/ 和 orchestra/ 边界模糊 | serve_utils 混杂装配和业务 | Step 1 |

---

## 不做的事

| 项目 | 原因 |
|------|------|
| V2 重构 | 暂不动，alias/worktree 保持现状 |
| services/ 其他重构 | 职责清晰，不动 |
| heartbeat.py 迁移出 orchestra | 事件循环归属 orchestra 合理 |
| MCP 增加写能力 | 范围外，单独讨论 |
| circuit_breaker 分类细化 | 独立 issue |
| flow_orchestrator.py 重命名 | 代价不值得 |

---

## 实施后的模块规模

| 模块 | 当前 | 拆分后 |
|------|------|--------|
| orchestra/ | 3675 行，14 文件 | ~2200 行，12 文件 |
| server/ | 不存在 | ~800 行，3 文件 |
| dispatcher.py | 357 行 | ~130 行 |
| services/ | 5 个文件 | 6 个文件（+StateLabelDispatch） |

---

## 风险评估

| 步骤 | 风险 | 缓解 |
|------|------|------|
| Step 1 server/ 提取 | 低（纯文件移动） | shim 过渡 + mypy |
| Step 2 dispatcher 精简 | 中（逻辑提取） | 现有测试覆盖 |
| Step 3 StateLabelDispatch 新增 | 低（纯新增，不改现有路径） | 集成测试验证 |
| Step 4 governance prompt 更新 | 低（prompt 文本改动） | 沙盒调试 |

---

## 验收标准

- `vibe3 serve start` 行为不变
- `vibe3 run/plan/review` 行为不变
- MCP 接口不变
- mypy 零错误，现有测试全部通过
- `dispatcher.py` < 150 行
- state/ready 标签可触发自动 dispatch
- orchestra agent 通过标签表达决策，不直接调用 dispatcher
