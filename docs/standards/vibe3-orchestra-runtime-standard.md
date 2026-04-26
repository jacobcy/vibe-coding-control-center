# Vibe3 Orchestra Runtime Standard

状态：Active

## 1. 目的

本标准定义 `vibe3 serve` 运行时的统一语义，避免混淆以下概念：

- `orchestra service`
- `server process`
- `heartbeat tick`
- `governance`
- `manager / plan / run / review` 状态触发
- `tmux session`

本标准回答的问题：

- 什么是长期运行的 driver
- 什么是每轮 tick
- 什么是 tick 派发出来的异步子任务
- 哪些组件负责“决定进入 ready”
- 哪些组件负责“消费已有 state”

本标准不定义：

- `state/*` 业务含义细节（见 `docs/standards/vibe3-state-sync-standard.md`）
- handoff 正文格式
- skill / supervisor 具体 prompt 文案
- 日志读取与调试方法（见 `docs/standards/agent-debugging-standard.md`）

## 2. 核心对象

### 2.1 Orchestra Driver

`vibe3 serve start` 启动的是一个**长期运行的 driver 进程**。

它负责：

- 启动 HTTP server（webhook / health / status）
- 启动 heartbeat loop
- 注册 runtime services
- 在每轮 heartbeat 时调用 service `on_tick()`
- 在 webhook 到达时调用 service `handle_event()`

它不是：

- governance agent
- manager agent
- plan / run / review agent

它只是**驱动程序 / 调度器**。

### 2.2 Heartbeat Tick

heartbeat tick 是 driver 进程内部的一次轮询循环。

它的语义是：

- 每隔固定秒数运行一次
- 遍历所有已注册 service
- 依次调用各 service 的 `on_tick()`

它不是：

- 一个新的独立 tmux 进程
- 一个独立的治理任务
- 一个长期保活的 worker

### 2.3 Async Child Session

某些 service 在 `on_tick()` 中不会直接做完全部工作，而是会**异步派发一个 tmux child session**。

例如：

- governance scan
- manager issue run
- supervisor handoff apply
- state-driven `plan / run / review`

这些 child session 才是实际调用 codeagent 的执行壳。

它们的语义是：

- 一次性任务执行
- 执行结束后短时间保活，方便检查日志
- 保活结束后退出

它们不是 driver。

## 3. 运行层级

运行时应分成三层：

### 3.1 第一层：长期 driver

只有一个主进程：

- `uv run python src/vibe3/cli.py serve start`

它常驻运行，负责：

- webhook
- heartbeat
- runtime service 调度

### 3.2 第二层：tick 内 service 判定

每一轮 tick，driver 调用各 service 的 `on_tick()`。

service 在这一层只负责：

- 读取真源
- 判断当前是否应该 dispatch
- 如果应该，则启动异步 child
- 如果已有 child 在运行，则 skip

这一层要求：

- 幂等
- 快速返回
- 不长时间阻塞 heartbeat

### 3.3 第三层：异步 child 执行

真正耗时的 agent 任务必须放到异步 child session 中执行。

包括：

- governance supervisor task
- manager task
- plan
- run
- review

这层可以耗时，但不能阻塞 heartbeat driver。

### 3.4 Dispatch 入口形式

异步 child session 有两种 dispatch 入口：

| 入口形式 | 适用场景 | 示例 | 实现 |
|---------|---------|------|------|
| CLI 命令 (`vibe3 internal`) | 需要 issue 参数、手动/脚本触发 | manager, supervisor/apply | `commands/internal.py` → `run_issue_role_async/sync()` |
| 事件 handler | 全局周期性、无特定参数 | governance scan, supervisor scan | `domain/handlers/` → `handle_*_started()` |

两种入口最终都通过 `ExecutionRequest` + `dispatch_request()` 走相同的执行管道，区别仅在于触发方式：

- **CLI 入口**：orchestra tick 判定某个 issue 需要处理后，构造 `vibe3 internal <role> <issue>` 命令，在 tmux 中启动独立 session
- **事件入口**：tick 直接在进程内发布 DomainEvent（如 `GovernanceScanStarted`），由对应 handler 构造 `ExecutionRequest` 并 dispatch

## 4. Governance 语义

### 4.1 Governance 是什么

governance 是一个**周期性治理扫描任务**。

它负责：

- 查看全局 issue / flow / scene 事实
- 判定哪些 issue 可以进入 `state/ready`
- 创建治理 issue
- 或对治理 issue 做进一步处理

它不负责：

- 充当 heartbeat driver
- 直接替代 manager
- 长时间阻塞主 server

### 4.2 Governance 在 runtime 中的位置

governance 是一个 registered service。

它在 `on_tick()` 中只做：

- 如果已有 governance child session 在运行：skip
- 如果没有：dispatch 一个 governance async child

因此：

- `tick` 不是 governance 本身
- `governance child session` 才是真正的治理任务

### 4.3 Governance child 的保活

governance child 执行结束后只需短保活，用于检查尾部输出。

当前约定：

- governance child 使用短保活（例如 10s）
- 不应像长期 driver 一样保活 60s 以上

否则会造成：

- 下一个 tick 误判“仍在运行”
- heartbeat 视角下的重复 skip 噪音

## 5. State Trigger 语义

### 5.1 State Trigger 是什么

state trigger 是消费已有 `state/*` labels 的 service 集合。

当前主链：

- `state/ready` -> manager
- `state/claimed` -> plan
- `state/in-progress` -> run
- `state/review` -> review

这些 service 负责**消费状态**，不是决定 ready。

### 5.2 谁决定 issue 进入 ready

决定哪些 issue 进入 `state/ready`，不属于 state trigger。

这应由：

- governance
- supervisor / triage agent
- 或人工治理

来完成。

因此：

- `orchestra driver` = 调度器
- `governance` = ready 候选判定器
- `state trigger` = 已有状态的消费者

## 6. Debug vs Normal 模式

### 6.1 Normal

正常模式应更接近生产语义：

- scene base: `origin/main`
- heartbeat interval: 900s（15 分钟）

### 6.2 Debug

调试模式应更接近当前开发现场：

- scene base: 当前 branch
- heartbeat interval: 60s（1 分钟）

因此：

- `serve start`：长期运行、低频、安全
- `serve start --debug`：短周期、高可观测、用于调试

## 7. 日志语义

> 完整的日志规范、目录结构和读取方法见 [agent-debugging-standard.md](agent-debugging-standard.md) §三。

### 7.1 主事件日志

主日志：

- `temp/logs/orchestra/events.log`

它记录：

- server run start
- registered services
- heartbeat tick
- governance dispatch / skip / fail
- 其他 runtime 关键事件

它不应混入：

- 测试 helper 的注册日志
- 普通 unit test 的假 server run

### 7.2 如何理解“重复日志”

看到重复时先区分两种情况：

1. **重复打印**
- 同一个主日志文件记录了多次 server 启停
- 或多个 service 的正常注册日志

2. **重复启动**
- 同一 issue / 同一 governance task 在已有 live tmux session 时又被重复 dispatch

判定原则：

- 如果只是跨多个 `server run start` 分隔块出现，不算重复启动
- 如果同一 run 中出现同一 execution name 的多次 dispatch，才算重复启动

## 8. 幂等要求

以下 `on_tick()` 必须幂等：

- governance
- supervisor handoff
- state triggers

幂等的最小要求：

- 若已有对应 live tmux session，则本轮 skip
- 不得在每轮 tick 中重复创建同一任务

## 9. 标准结论

统一语义如下：

- `orchestra service` = 长期运行的 driver / 调度器
- `heartbeat tick` = driver 内部一次轮询，不是独立进程
- `governance` = 由 tick 派发的治理任务，不是 driver
- `manager / plan / run / review` = 由 state trigger 派发的异步 child
- `领域事件 (Domain Events)` = Agent 执行生命周期的真源，负责驱动状态转换与副作用
- `ready` 的判定来源于 governance / supervisor / 人工治理
- `state trigger` 只消费已有状态

如果实现偏离上述定义，应先修 runtime 语义，再讨论 prompt 行为。
