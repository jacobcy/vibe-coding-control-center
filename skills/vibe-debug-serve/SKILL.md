---
name: vibe-debug-serve
description: Use when checking whether a new vibe3 serve debugging round is ready, debugging vibe3 serve (orchestra server), inspecting agent execution logs in temp/logs/, diagnosing governance or manager chain failures, or identifying bugs in the heartbeat/dispatch pipeline. Do not use for flow/task metadata repair (use vibe-check) or issue pool governance (use vibe-orchestra).
---

# /vibe-debug-serve - vibe3 serve 自动化调试

调试 `vibe3 serve` 的标准化流程，涵盖日志读取、链路验证、问题识别与修复。

**调试原则**：先看日志，再做判断；先 dry-run，再最小执行；每步执行后停下来确认结果。

**开调前先分流目标**：先判断这轮要调的是全局 `serve/heartbeat/dispatch`，还是当前分支承载的单 issue / flow 链路。两者前置条件不同，不要混成一次“总调试”。

**分支隔离原则**：调试 `serve` 链路时，默认使用临时 `debug/*` 分支承载新的调试动作；不要在已经承载自动化 PR 的 `task/issue-*` 分支上继续引入新的调试目标。

> 调试规范、日志分层与反模式定义以 `docs/standards/agent-debugging-standard.md` 为权威来源。

---

## 语义边界

- 本 skill 负责：`vibe3 serve` 相关的日志读取、链路调试、bug 识别、修复验证。
- 本 skill **不负责**：flow/task runtime 绑定修复（用 `vibe-check`）、issue pool 治理建议（用 `vibe-orchestra`）、roadmap 规划（用 `vibe-roadmap`）。
- 所有状态写入只通过真实 `vibe3` 命令完成，不直接改 `.git/vibe3/` 底层文件。
- `debug/*` 只是临时调试分支，不是 canonical flow 分支，不替代 `dev/issue-*` 或 `task/issue-*` 的正式语义。

## 调试分支规则

当当前工作树已经是 `task/issue-*` 自动化分支，且该分支上已有活跃 PR 时：

- 不要继续在这个分支上引入新的调试目标。
- 当前分支只允许处理该 PR 的 review follow-up、CI 修复和 handoff 收口。
- 若本轮目的是开启新的 `serve` / heartbeat / dispatch 调试，请先合并当前 PR，再从干净基线新开 `debug/*` 分支。

推荐流程：

```bash
# 先合并当前 PR

# 回到最新主线（或约定基线）后创建临时调试分支
git checkout main
git pull
git checkout -b debug/serve-<topic>
```

使用约束：

- `debug/*` 只用于隔离调试，不默认注册为 flow。
- 如果调试结果沉淀成新的正式开发任务，再按仓库正式语义新开 `dev/issue-<id>` 或 `task/issue-<id>` 分支处理。
- 不要把一次性的 `debug/*` 分支长期保留成正式交付分支。

## 调试前置条件

在进入日志调试前，先运行：

```bash
uv run python src/vibe3/cli.py task status
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py check
uv run python src/vibe3/cli.py serve status
```

然后按目标分流：

- **全局 serve 调试**：要调的是 heartbeat、dispatch、governance、manager child session 链路。此时当前 branch 不一定需要是已注册 flow，但 `serve status` 必须能说明 server 当前是 running、stopped，还是启动失败。
- **当前 flow / issue 调试**：要调的是“当前分支为什么没有按预期进入 manager/run/review”这类问题。此时当前 branch 应该是有效 flow；若 `flow show` 提示当前分支尚未注册为 flow，则这轮条件不完整，应先补 `vibe3 flow update` 或转交 `vibe-check` / `vibe-new`。

关于分支选择：

- 若当前分支是带活跃 PR 的 `task/issue-*` 自动化分支，这通常**不满足新调试目标的分支隔离条件**。
- 若本轮只是为现有 PR 收集调试证据或做最小 follow-up，可留在当前分支。
- 若本轮是新的 `serve` 调试主题，建议在当前 PR 合并后改到新的 `debug/*` 分支继续。

判断规则：

- `check` 不干净：先走 `vibe-check` 做 runtime 审计与修复，不要先怪 `serve`。
- `serve status` 显示 stopped：说明当前**不满足 live heartbeat 调试条件**；除非你要调的是“为什么启动不起来”，否则先补启动现场。
- 当前 branch 不是 flow：说明当前**不满足单分支 execution 调试条件**；但仍可继续做全局 serve 调试。
- 当前 branch 是带 PR 的 `task/issue-*`：说明当前**不满足新调试主题的隔离分支条件**；优先等当前 PR 合并后切到新的 `debug/*` 分支。

---

## 日志结构速查

```
temp/logs/
  orchestra/
    events.log                          # 主事件日志（serve 生命周期、tick、dispatch）
    governance/
      governance.log                    # Governance service 详细事件
      dry-run/governance_dry_run_*.md   # dry-run prompt 组装结果
  vibe3-manager-issue-{n}.async.log     # Manager 执行日志
  vibe3-plan-issue-{n}.async.log        # Plan 执行日志
  vibe3-run-issue-{n}.async.log         # Run 执行日志
  vibe3-review-issue-{n}.async.log      # Review 执行日志
  vibe3-governance-scan-{ts}-t{n}.async.log  # Governance 执行日志
  vibe3-supervisor-issue-{n}.async.log  # Supervisor apply 执行日志
```

`temp/` 在 `.gitignore` 中排除，日志不进入 git。

---

## 执行流程

### Step 1: 先判断这轮调试是否具备条件

先读取：

```bash
uv run python src/vibe3/cli.py task status
uv run python src/vibe3/cli.py flow show
uv run python src/vibe3/cli.py check
uv run python src/vibe3/cli.py serve status
```

这一层回答四个问题：

- 当前 server 是 running、stopped，还是启动失败
- 当前 runtime sync 是否干净
- 当前 branch 是否已注册 flow
- 当前问题更像全局 serve 链路问题，还是当前 flow / issue 现场问题

若结论是“不是 serve 调试问题而是 runtime / binding 问题”，立即转交 `vibe-check`，不要继续在本 skill 内盲读日志。

### Step 2: 确认 serve 运行状态

```bash
uv run python src/vibe3/cli.py serve status
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/status
```

- serve 未启动时无法观察 heartbeat 与 dispatch 事件
- `serve status` 输出 `running` 才进入后续步骤
- 如果 `serve status` 是 `stopped`，但当前目标是“启动路径调试”，则继续读取启动日志或最小启动证据；如果目标不是启动问题，先恢复 live serve 现场再继续

### Step 3: 读取主事件日志

```bash
# 实时跟踪（serve 正在运行时）
tail -f temp/logs/orchestra/events.log

# 事后复盘
cat temp/logs/orchestra/events.log
```

事件日志记录：server 启停、tick 开始/完成、dispatch 触发/跳过/失败、runtime 错误。

识别关键信号：

- `[governance] tick #N dispatched` — governance 已触发，正常
- `[governance] tick #N skip` — governance 本轮跳过，检查 interval_ticks 配置
- `[server] heartbeat tick #N completed` — 心跳正常
- 包含 `ERROR` / `exception` 的行 — 立即定位

### Step 4: 读取 agent 执行日志

```bash
# 查看最近的 manager 日志
ls -lt temp/logs/vibe3-manager-*.async.log | head -5

# 实时跟踪正在运行的 agent
tail -f temp/logs/vibe3-manager-issue-{n}.async.log

# 查看特定 issue 的所有执行日志
ls temp/logs/*issue-{n}*.async.log

# 查看 tmux session（如仍存活）
tmux ls | grep vibe3
tmux capture-pane -t vibe3-manager-issue-{n} -p
```

agent 日志包含完整的 stdout/stderr，内置 awk 过滤器已抑制 Codex runtime noise。执行结束后 session 保持 60s keep-alive。

### Step 5: 定位问题类型

根据日志判断问题归属：

**A. Prompt 材料问题**（governance / supervisor 链路）

现象：agent 的行为不符合治理预期，决策逻辑错误。

```bash
# 检查 dry-run prompt 组装输出
uv run python src/vibe3/cli.py serve start --dry-run
cat temp/logs/orchestra/governance/dry-run/governance_dry_run_*.md
```

检查点：

- prompt 是否使用了 `supervisor/orchestra.md`（governance 链）或 `supervisor/manager.md`（manager 链）
- runtime vars 是否正确注入（active_count、issue_list 等）
- 业务判断是否错误下沉到底层（见标准 §2.1）

**B. 配置问题**（角色模型 / 间隔 / 并发）

现象：某个角色行为明显偏差（过度执行或过于保守）。

```bash
cat config/settings.yaml
```

检查点：

- `orchestra.assignee_dispatch` 中 manager 的 agent preset 是否独立配置（不得隐式继承 `run.agent_config`）
- `interval_ticks` 是否合理
- `max_concurrent` 是否限制了并发

**C. 状态迁移问题**（state labels / flow 不一致）

```bash
uv run python src/vibe3/cli.py task status --all
uv run python src/vibe3/cli.py flow show
gh issue view {n} --json labels,state
```

状态迁移语义以 `docs/standards/vibe3-state-sync-standard.md` 为准。

如果这里发现的根因其实是：

- 当前 branch 不是有效 flow
- task <-> flow 绑定脏掉
- auto task scene 需要恢复

则应停止 `vibe-debug-serve`，转交 `vibe-check` 处理。

**D. Agent 执行崩溃**（tmux / session 异常退出）

```bash
# 查看日志尾部
tail -50 temp/logs/vibe3-manager-issue-{n}.async.log

# 检查 tmux session 是否异常退出
tmux ls 2>&1
```

### Step 6: 最小真实执行验证

问题定位后按链路选择最小入口验证：

**Governance 治理链**：

```bash
# 手动触发 governance suggest（创建治理 issue）
uv run python src/vibe3/cli.py run --supervisor supervisor/issue-cleanup.md

# 手动 apply 特定治理 issue
uv run python src/vibe3/cli.py run --issue {governance_issue_number}
```

**Manager / 开发执行链**：

Manager 由 `StateLabelDispatchService` 自动调度（`state/ready` 或 `state/handoff` labels），不需要手动命令触发。验证方法：

```bash
# 观察 manager 是否被自动 dispatch
tail -f temp/logs/orchestra/events.log

# 查看 manager 执行日志
tail -f temp/logs/vibe3-manager-issue-{n}.async.log
```

禁止同时打开 heartbeat + dry-run + 自动 apply + 自动回收，每步执行后必须停下来确认结果。

### Step 7: 验证修复结果

修复后按以下顺序确认：

1. `temp/logs/orchestra/events.log` — 确认无新的 ERROR
2. `temp/logs/vibe3-{role}-issue-{n}.async.log` — 确认执行日志正常
3. GitHub issue comment + labels — 确认外部状态与预期一致
4. `uv run python src/vibe3/cli.py flow show` — 确认 flow 状态正确

成功标准（governance 链）：

- issue 中只有一条正式结果 comment
- comment 与实际执行结果一致
- issue 被关闭

### Step 8: 报告

最终报告包含：

- 这轮是否满足调试前置条件
- 调的是全局 serve 链路还是当前 flow / issue 链路
- 是否满足调试分支隔离条件
- 问题类型（Prompt / 配置 / 状态迁移 / 执行崩溃）
- 关键日志证据（文件路径 + 关键行）
- 执行的修复命令
- 验证结果

---

## 常见反模式

详细列表见 `docs/standards/agent-debugging-standard.md` §八。核心禁止项：

- 看不到 tmux/session log 就继续盲跑下一轮
- 只看 GitHub issue 不看 session log（或反过来）
- 把 session log 路径硬编码到 handoff 内容中
- 一次调试同时打开多个副作用

---

## 相关标准

- `docs/standards/agent-debugging-standard.md` — 调试规范权威来源（日志分层、调试循环、反模式）
- `docs/standards/vibe3-orchestra-runtime-standard.md` — Orchestra 运行时架构
- `docs/standards/vibe3-state-sync-standard.md` — state labels 与状态迁移语义
- `docs/standards/v3/command-standard.md` — Shell 命令边界与共享状态规范
