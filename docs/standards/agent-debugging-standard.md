# Agent 调试标准

> **文档定位**：Vibe3 agent 编排调试的统一入口。涵盖日志规范、链路调试方法、观测手段和项目理解。
> **适用范围**：所有使用 `vibe3 serve`、`vibe3 run`、`vibe3 plan`、`vibe3 review`、heartbeat、orchestra、manager 的 agent 编排调试。
> **权威性**：本标准是 agent 调试流程与日志规范的权威依据。业务语义以 `skills/`、`supervisor/`、`.agent/policies/` 为准；编排状态语义与 authoritative ref 定义以 [vibe3-state-sync-standard.md](vibe3-state-sync-standard.md) 为准；运行时架构以 [vibe3-orchestra-runtime-standard.md](vibe3-orchestra-runtime-standard.md) 为准。

---

## 一、目标

调试 agent 链路时，目标不是"尽快跑通一次"，而是：

- 确认 prompt 材料是否正确装配
- 确认底层触发是否只做最小能力提供
- 确认业务逻辑是否仍留在上层 skill / supervisor
- 确认执行结果是否能被稳定观察、复盘与复现

本标准要求先把一条链路调通，再迁移到下一条链路。当前推荐顺序：

1. 先调通 supervisor / orchestra 治理链
2. 再用同样方法调试 manager 单 issue 执行链

---

## 二、总原则

### 2.1 上层负责业务，底层只负责触发

- Python 底层能力只提供：
  - prompt 装配
  - issue/plan/instruction 注入
  - async/tmux 启动
  - session/log 暴露
- Python 底层**不应**硬编码：
  - findings 类型路由
  - 治理动作判断
  - comment / close 决策
  - 是否查询 `vibe3 task status` / `vibe3 flow show`

业务逻辑必须留在：

- `skills/`：人机协作入口
- `supervisor/`：自动化治理与角色材料
- `.agent/policies/`：plan/run/review mode policy

### 2.2 先 dry-run，再单步 apply

每一条新链路都按下面顺序调试：

1. 先看 prompt 是否正确装配
2. 再跑 dry-run，确认建议或执行计划是否合理
3. 再做一次最小真实执行
4. 每执行一步都停下来检查结果

禁止一开始就把 heartbeat、批量执行、自动回收一起打开。

### 2.3 默认 async/tmux，观察优先

agent 调试默认使用 async/tmux：

- 默认使用 async 执行，避免前台阻塞
- 通过 tmux session 和 session log 观察运行过程
- 通过 `vibe3 flow show` 或 GitHub issue 查看外部结果

调试时必须优先保证"能看见发生了什么"，而不是追求链路一步到位自动化。

### 2.4 角色默认模型必须显式配置

- `plan`、`run`、`review`、`manager`、`supervisor` 是不同角色，不应因为实现方便而隐式共用同一个默认 agent preset
- 尤其是 `manager`，它承担 scene 判断、状态迁移、后续 agent 派发，不应默认继承 `run.agent_config.agent`
- 如果某个角色长期表现出"执行型过强、治理型过弱"或"过度自由探索"，优先检查该角色是否错误继承了别的默认 agent/model
- 调试时要同时核查两层真源：
  - 仓库配置真源：`config/settings.yaml`
  - codeagent preset 真源：`~/.codeagent/models.json`
- 原则上：
  - 仓库只决定"这个角色默认用哪个 agent/backend/model"
  - `models.json` 决定该 preset 的具体底层映射
  - prompt 不负责偷偷补偿模型选择错误

---

## 三、日志规范

### 3.1 日志分层

Vibe3 的日志体系分三层，各有明确用途：

| 层 | 路径 | 用途 | 持久性 |
|---|---|---|---|
| Orchestra 运行时日志 | `temp/logs/orchestra/` | server 生命周期、service 调度、governance 事件 | 跨 serve 运行 |
| Agent 会话日志 | `temp/logs/*.async.log` | 单次 agent 执行的完整输出 | 60s keep-alive 后回收 |
| 控制台日志 | stderr (loguru) | 开发者实时观察 | 不持久化 |

所有日志统一写入仓库 `temp/logs/`，不写入 `.git/vibe3/` 或其他共享状态目录。`temp/` 在 `.gitignore` 中排除。

### 3.2 Orchestra 运行时日志

**主事件日志**：

```text
temp/logs/orchestra/events.log
```

记录内容：

- server 启停（含 tick_interval、polling_enabled、max_concurrent、services 列表）
- service 注册
- heartbeat tick 开始/完成
- governance dispatch / skip / fail
- state trigger dispatch / skip
- runtime 错误

格式：

```text
[2026-04-04T14:23:31] [server] start tick_interval=60s polling_enabled=True max_concurrent=3
[2026-04-04T14:23:31] [server] registered service: GovernanceService
[2026-04-04T14:24:35] [governance] tick #1 dispatched: tmux=vibe3-governance-scan-... log=temp/logs/...
[2026-04-04T14:25:35] [server] heartbeat tick #1 completed in 0.12s
```

启用条件：`VIBE3_ORCHESTRA_EVENT_LOG=1`（`vibe3 serve start` 自动设置）。

每次 `serve start` 会覆盖 `events.log`（写入 run separator），不会跨运行追加。

**Governance 日志**：

```text
temp/logs/orchestra/governance/governance.log
```

记录 governance service 的所有事件，同时写入 `events.log`。格式同上。

**Governance dry-run 输出**：

```text
temp/logs/orchestra/governance/dry-run/governance_dry_run_*.md
```

`serve start --dry-run` 时 governance prompt 组装结果写入此目录，用于检查 prompt 是否正确装配。

### 3.3 Agent 会话日志

每次 agent 异步执行都会产生一个会话日志：

```text
temp/logs/vibe3-{role}-{target}.async.log
```

角色与命名规则：

| 角色 | 文件名模式 | 示例 |
|---|---|---|
| manager | `temp/logs/issues/issue-{n}/manager.async.log` | `temp/logs/issues/issue-372/manager.async.log` |
| plan | `temp/logs/issues/issue-{n}/plan.async.log` | `temp/logs/issues/issue-420/plan.async.log` |
| run | `temp/logs/issues/issue-{n}/run.async.log` | `temp/logs/issues/issue-420/run.async.log` |
| review | `temp/logs/issues/issue-{n}/review.async.log` | `temp/logs/issues/issue-420/review.async.log` |
| governance | `vibe3-governance-scan-{ts}-t{n}.async.log` | `vibe3-governance-scan-20260404-142351-t3.async.log` |
| supervisor | `temp/logs/issues/issue-{n}/supervisor.async.log` | `temp/logs/issues/issue-435/supervisor.async.log` |

会话日志特性：

- 通过 tmux `tee` 捕获完整 stdout/stderr
- 内置 awk 过滤器：自动抑制 Codex runtime noise（state-db warning、shell-snapshot cleanup、analytics 403）
- 执行结束后 tmux session 保持 60s（keep-alive），方便检查尾部输出
- CLI 输出会直接显示 `Session log: temp/logs/...` 路径

### 3.4 控制台日志

基于 loguru 的结构化控制台输出（stderr），不写入文件。

配置：

- `vibe3 serve start` — 默认 INFO 级别
- `vibe3 serve start -v` — DEBUG 级别，含 file:line:function
- `vibe3 serve start -vv` — TRACE 级别

代码中使用语义化 context binding：

```python
logger.bind(domain="orchestra", action="governance").info("Governance scan dispatched")
```

### 3.5 日志读取方法

**查看 orchestra 运行状态**：

```bash
# 实时跟踪主事件日志
tail -f temp/logs/orchestra/events.log

# 查看 governance 事件
cat temp/logs/orchestra/governance/governance.log

# 查看 dry-run prompt 组装结果
cat temp/logs/orchestra/governance/dry-run/governance_dry_run_*.md
```

**查看 agent 执行日志**：

```bash
# 查看最新 manager 执行
ls -lt temp/logs/vibe3-manager-*.async.log | head -1
tail -100 temp/logs/issues/issue-XXX/manager.async.log

# 实时跟踪正在运行的 agent
tail -f temp/logs/vibe3-plan-issue-XXX.async.log

# 列出所有活跃 tmux session
tmux ls | grep vibe3

# 查看特定 tmux session
tmux capture-pane -t vibe3-manager-issue-XXX -p
```

**查看完整执行现场**：

```bash
# 真源三件套
uv run python src/vibe3/cli.py task show <target-branch> --comments
uv run python src/vibe3/cli.py handoff show <target-branch>
gh issue view <issue-number> --json labels,state

# 验证 flow lifecycle integrity（状态变更事件记录）
uv run python src/vibe3/cli.py flow show <target-branch>
```

### 3.6 日志标准要求

- agent 执行必须通过 async/tmux，CLI 输出必须显示 `Session log: temp/logs/...`
- 新增 service 必须在 `on_tick()` 中调用 `append_orchestra_event()` 记录关键事件
- 日志文件不进入 git（`temp/` 在 `.gitignore` 中）
- 不要在 `events.log` 中混入 unit test 的假 server run
- 会话日志不挂在上层 handoff 语义里；handoff 是交接材料，日志是调试材料

---

## 四、标准调试循环

每条 agent 链路都应遵循同一套调试循环：

1. **确定真源**
   - 开发链：issue + branch + flow + worktree
   - 治理链：issue + labels + comments
2. **确认 prompt 材料**
   - 先确认 `skills/`、`supervisor/`、`.agent/policies/` 是否在正确层级
3. **dry-run 验证**
   - 确认建议、计划或目标 issue 是否正确
   - 查看 `temp/logs/orchestra/governance/dry-run/` 输出
4. **最小真实执行**
   - 只放开最小动作，不一次启用所有副作用
5. **观察执行现场**
   - 记录 tmux session、session log（`temp/logs/*.async.log`）、CLI 输出、issue/flow 变化
6. **停下来读结果**
   - 先确认结果与 comment / issue 线程一致，再进入下一步
7. **只收当前尾巴**
   - 清掉重复 comment、错误提示、无效中间文件、旧 help 文案等残留

---

## 五、Orchestra 治理链调试

### 5.1 链路语义

治理链涉及两条运行时路径：

**路径 A — Governance 周期扫描**：

```text
GovernanceService.on_tick() -> PromptRecipe 组装 -> codeagent dispatch -> 治理 issue 创建/处理
```

- 由 `GovernanceService` 按配置的 `interval_ticks` 周期性触发
- 通过 `PromptRecipe` / `PromptAssembler` 组装 prompt，使用 `supervisor/governance/assignee-pool.md` 作为角色材料

> **概念区别**：
> - `governance`（无临时 worktree）：scan agent，只观察和建议，读取 `supervisor/governance/assignee-pool.md`
> - `supervisor/apply`（有临时 worktree）：治理执行 agent，负责 label/comment/close/recreate 等 issue 治理动作；**禁止代码修改**
> - `supervisor/governance/assignee-pool.md`：governance supervisor material，不是 runtime orchestra 本体
> - runtime orchestra（heartbeat/event-bus）是系统基础设施层，三者独立，不可混淆
- 日志：`temp/logs/orchestra/governance/governance.log`

**路径 B — Supervisor Handoff 消费**：

```text
SupervisorHandoffService.on_tick() -> 查找 supervisor+state/handoff issue -> dispatch -> apply -> comment -> close
```

- 消费带有 `supervisor` + `state/handoff` labels 的 issue
- 使用 `supervisor/apply.md` 作为角色材料
- 日志：`temp/logs/vibe3-supervisor-issue-{n}.async.log`

### 5.2 治理 issue 约定

治理 issue 的最小约定：

- labels：
  - `supervisor`
  - `state/handoff`
- 标题前缀表达 findings 类型，例如：
  - `cleanup: ...`
- body 中写清：
  - findings
  - 建议动作
  - 禁止动作
  - 核查方式

### 5.3 调试步骤

#### 第一步：检查 governance prompt 装配

```bash
# 启动 dry-run 模式，prompt 写入文件但不实际执行
uv run python src/vibe3/cli.py serve start --dry-run
# 检查输出
cat temp/logs/orchestra/governance/dry-run/governance_dry_run_*.md
```

检查点：

- prompt 是否使用了正确的 supervisor 文件（`supervisor/governance/assignee-pool.md`，即 governance supervisor material）
- runtime vars 是否正确注入（active_count、issue_list 等）
- 是否避免把过多业务判断下沉到底层

#### 第二步：手动触发 supervisor suggest

```bash
uv run python src/vibe3/cli.py run --supervisor supervisor/issue-cleanup.md
```

检查点：

- 是否真的创建了治理 issue，而不是只停留在 findings preview
- 创建前是否先查重，避免重复发布重叠 issue
- 是否只创建当前轮次需要的最小 issue 集

#### 第三步：观察 apply 自动触发

> **注意**：apply 由 `SupervisorHandoffService.on_tick()` 自动触发，无需手动命令。
> 当检测到带有 `supervisor` + `state/handoff` labels 的 issue 时，服务会自动 dispatch apply agent。
> 手动执行 `run --issue <n>` **不是**正确的触发方式，会绕过 on_tick 状态机，可能导致重复执行或状态不一致。

观察方式：

```bash
# 方式一：观察 serve 运行时日志（推荐）
tail -f temp/logs/vibe3-serve.log | grep supervisor

# 方式二：确认 issue 已被识别并进入队列
uv run python src/vibe3/cli.py flow status

# 方式三：查看 apply session log（由 on_tick 生成）
ls -lt temp/logs/vibe3-supervisor-issue-*.async.log | head -5
```

检查点：

- `on_tick` 是否检测到了正确的 `supervisor+state/handoff` issue
- apply agent 是否已进入 async/tmux session
- Session log 路径是否显示：`temp/logs/vibe3-supervisor-issue-{n}.async.log`

> **调试用途**（仅限本地单步验证）：若需要隔离测试 apply 逻辑而不依赖 on_tick，
> 可直接调用服务层，但不要通过 CLI `run --issue` 命令，该命令路径与 supervisor apply 逻辑不匹配。

#### 第四步：观察结果

观察顺序：

1. `temp/logs/vibe3-supervisor-issue-{n}.async.log` — 执行日志
2. tmux session（如仍存活）
3. GitHub issue comment
4. GitHub issue close 状态

成功标准：

- issue 中只有一条正式结果 comment
- comment 与实际执行结果一致
- issue 被关闭

### 5.4 治理链调试结论

- 治理链通过 issue 交接，不通过 branch handoff 交接
- apply 由 `SupervisorHandoffService.on_tick()` **自动触发**，检测 `supervisor+state/handoff` issue 后 dispatch；`run --issue` 不是 apply 的触发入口
- async/tmux 与 session log 属于底层 codeagent 适配层，不属于上层 orchestration
- 底层只负责触发；是否检查 `vibe3 task status`、是否创建 issue、是否 comment / close，全部由 supervisor prompt 决定

---

## 六、Manager 链调试标准

manager 链不复用治理 issue 交接模型，而是保留 scene 模型：

```text
issue -> branch/worktree -> flow -> manager -> plan -> run -> review
```

调试 manager 时，沿用本标准中的三条不变原则：

1. 先确认 prompt / policy / scene 装配是否正确
2. 默认 async/tmux，确保执行过程可观测
3. 每跑一步就停下来检查结果，不连续堆叠多个阶段

manager 链与治理链的差异只在真源：

- 治理链以 GitHub issue 为交接真源
- manager 链以 issue + branch + worktree + flow 为交接真源

因此，调试 manager 时必须重点检查：

- 当前 branch / worktree / flow 是否一致
- manager 是否只负责 scene 推进，而没有吞掉上层业务编排
- plan/run/review 的 mode policy 是否正确注入
- manager 使用的默认 agent/model 是否来自独立配置（`config/settings.yaml` 的 `orchestra.assignee_dispatch`），而不是隐式继承 `run.agent_config`

### 6.1 Manager 角色与模型

- `manager` 是开发链 owner，不是普通执行 agent
- `manager` 的默认 agent/model 应单独配置在 orchestra/manager 侧（`config/settings.yaml` 的 `orchestra.assignee_dispatch`），而不是沿用 `run.agent_config`
- `manager` 当前主线语义是：**能推进就推进，不能推进且本轮没有任何可观察进展时，进入 `state/blocked`**
- `state/blocked` 之后的 follow-up（例如 doctor 修复、人工恢复、或 aborted 收尾）明确不属于当前 manager 主线，而是后续链路
- 调试 manager 异常时，优先区分三类问题：
  - prompt 材料不对
  - scene/worktree/session 不对
  - manager 角色模型不对

如果 manager 的行为明显更像"直接实现代码"而不是"检查现场、迁移状态、决定下一步"，优先检查 manager 的默认 agent preset 是否选错

### 6.2 Manager 链运行时架构

manager 链在 `vibe3 serve` 中的调度路径：

```text
HeartbeatServer._tick_loop()
  -> StateLabelDispatchService.on_tick()  (trigger_state=READY, trigger_name="manager")
    -> ManagerExecutor.dispatch_manager(issue)
      -> CodeagentBackend.start_async_command()
        -> tmux session: vibe3-manager-issue-{n}
        -> log: temp/logs/issues/issue-{n}/manager.async.log
```

状态迁移由 `StateLabelDispatchService` 按 `state/*` labels 触发：

| 触发状态 | 触发角色 | 调度方式 | 调试方法 |
|---|---|---|---|
| `state/ready` | manager | Orchestra 自动调度 | `vibe3 serve start` 后观察 `temp/logs/issues/issue-{n}/manager.async.log` |
| `state/handoff` | manager (resume) | Orchestra 自动调度 | `vibe3 serve start` 后观察 `temp/logs/issues/issue-{n}/manager.async.log` |
| `state/claimed` | plan | 手动触发 | `vibe3 plan --issue {n}` |
| `state/in-progress` | run | 手动触发 | `vibe3 run` |
| `state/review` | review | 手动触发 | `vibe3 review base` |

**注意**：Manager 的调度是自动的，由 `StateLabelDispatchService.on_tick()` 周期性扫描 `state/ready` 和 `state/handoff` labels 的 issue 并自动 dispatch。不需要手动 CLI 命令触发。调试时应通过观察日志和 tmux session 来监控执行过程。

**Manager Handoff Resume**：

当 issue 处于 `state/handoff` 且满足以下条件时，manager 会自动恢复执行：

1. Issue 有 canonical task flow（`task/issue-*` 分支）
2. 没有活动的 manager session

这里不要把 auto-saved artifact 或 async log 误认成 authoritative ref：

- `.git/vibe3/handoff/...` 下的自动产物，只是共享 artifact
- `temp/logs/*.async.log` 只是调试日志
- authoritative ref 是否成立，以 [vibe3-state-sync-standard.md](vibe3-state-sync-standard.md) 中定义的 handoff write + flow state 为准

这个 resume 路径使用与 `state/ready` 相同的去重机制：
- 如果已有 live session，不会重复 dispatch
- 如果 session 结束且无进展，会 auto-block

详细的状态迁移语义见 [vibe3-state-sync-standard.md](vibe3-state-sync-standard.md)。

### 6.3 Manager 主线结束条件

当前 manager 主线只关心两类结果：

- 本轮推进成功，产生明确状态变化或交接产物
- 本轮无法推进，且 manager session 结束后没有任何可观察进展，此时进入 `state/blocked`

对 manager 的 `state/ready` / `state/handoff` 路径，最关键的“可观察进展”是状态迁移本身。

调试时应按下面顺序读：

1. `state/*` label 是否离开当前状态
2. 是否发生显式 abandon / close
3. 其余 comment、handoff、refs 仅作为辅助现场，不单独构成 manager 路径成功

如果你看到新的 handoff 文件或 auto-saved artifact，但 issue 仍停在 `state/handoff`，不要把它误判成 manager 已完成推进。

**Progress Detection Parity**：

Manager 的 progress 判断在 async runtime 和 sync CLI 执行中保持一致，使用共享的 progress snapshot contract。无论通过哪种路径执行，progress 判断都基于相同的观察维度。

**Session ID Re-entry**：

当 planner/executor/reviewer 执行到达 terminal state（completed/aborted）时，其 session_id 会被清除，允许后续合法的 re-entry。这确保：

- Actor 和 event history 保留，维持 observability
- Stale session_id 不会阻止正常的 re-plan/re-run/re-review

因此，调试 manager 时不要把”no-progress -> blocked”当作异常补丁；在当前架构里，这是刻意保留的主线收口规则，用来让 manager 聚焦推进 flow，而把 blocked 后的处置留给后续链路。

---

## 七、观测标准

### 7.1 默认观测入口

CLI 输出必须直接给出：

- `Tmux session: ...`
- `Session log: temp/logs/...`

调试者优先看：

1. `temp/logs/*.async.log` — agent 执行日志
2. `temp/logs/orchestra/events.log` — 运行时事件
3. tmux session（如仍存活）
4. `vibe3 flow show` / `vibe3 task show`
5. GitHub issue / PR / comment

### 7.2 运行时观测

**serve 运行中**：

```bash
# 跟踪主事件
tail -f temp/logs/orchestra/events.log

# 跟踪 governance
tail -f temp/logs/orchestra/governance/governance.log

# HTTP 状态端点
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/status
```

**agent 执行中**：

```bash
# 实时跟踪 agent 日志
tail -f temp/logs/issues/issue-372/manager.async.log

# 查看 tmux session
tmux attach -t vibe3-manager-issue-372  # 或 tmux capture-pane
```

### 7.3 事后复盘

```bash
# 查看 serve 运行记录
cat temp/logs/orchestra/events.log

# 查看最近 agent 执行
ls -lt temp/logs/*.async.log | head -10

# 查看特定 issue 的所有执行日志
ls temp/logs/*issue-420*.async.log
```

---

## 八、反模式

以下做法属于反模式：

- 在 Python 底层按 findings 类型硬编码 supervisor 路由
- 为每个新 supervisor 增加一套专用 runtime context 适配
- 让底层帮上层预判是否 comment / close
- 治理链依赖 branch/worktree handoff
- 一次调试同时打开 dry-run、heartbeat、自动 apply、自动回收
- 看不到 tmux/session log 就继续盲跑下一轮
- 在 `events.log` 中混入 unit test 的假 server run
- 把 session log 路径硬编码到 handoff 内容中
- 只看 GitHub issue 不看 session log（或反过来）

---

## 九、相关标准索引

调试 agent 时，以下文档可能需要交叉引用：

| 文档 | 用途 |
|---|---|
| [vibe3-orchestra-runtime-standard.md](vibe3-orchestra-runtime-standard.md) | Orchestra 运行时架构：driver、heartbeat、service 分层、governance 语义 |
| [vibe3-state-sync-standard.md](vibe3-state-sync-standard.md) | `state/*` labels 语义、状态迁移规则、manager 判定规则、真源分层 |
| `supervisor/manager.md` | Manager 角色材料：Permission Contract、Pseudo Functions、Stop Conditions |
| `supervisor/governance/assignee-pool.md` | Governance supervisor material（原 orchestra.md）；governance agent 的角色材料，不是 runtime orchestra 本体 |
| `supervisor/apply.md` | Governance issue apply 角色材料 |
| `.agent/policies/plan.md` | Plan mode policy |
| `.agent/policies/run.md` | Run mode policy |
| `.agent/policies/review.md` | Review mode policy |
| `config/settings.yaml` | 运行时配置：agent preset、interval、governance、state_label_dispatch |

---

## 十、落地检查清单

开始调试一条新链路前，先检查：

- 是否已经明确这条链的真源是什么
- 是否已经明确业务逻辑留在 skill/supervisor，而不是底层
- 是否已经有 dry-run 入口
- 是否默认 async/tmux
- 是否能直接看到 session log 路径（`temp/logs/*.async.log`）
- 是否知道去哪里看运行时事件（`temp/logs/orchestra/events.log`）
- 是否有最小真实执行入口
- 是否规定了执行后停下来检查结果

如果以上任一项不满足，应先补调试能力，再继续扩展业务逻辑。
