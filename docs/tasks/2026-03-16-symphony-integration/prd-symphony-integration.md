---
document_type: prd
title: "Symphony 整合方案 PRD"
version: v1
author: "Kiro"
created: "2026-03-16"
last_updated: "2026-03-16"
related_docs:
  - docs/tasks/2026-03-16-symphony-integration/README.md
  - CLAUDE.md
  - lib/flow.sh
  - lib/task.sh
---

# Symphony 整合方案 PRD

## 0. 背景与定位

[openai/symphony](https://github.com/openai/symphony) 于 2026 年 3 月发布，是一个将任务板（Linear/GitHub Issues）与自主 coding agent 连接的编排框架。参考实现基于 Elixir/BEAM，[SPEC.md](https://github.com/openai/symphony/blob/main/SPEC.md) 是语言无关规范。

### 0.1 两个系统的根本差异

**Symphony 的 agent 模型**（单 agent per issue，简单）：
```
issue → 一个 agent 从头做到尾 → PR
```

**Vibe Center v3 的 agent 模型**（多 agent per flow，有流程控制）：
```
issue
  → planner agent  ──handoff──→  executor agent  ──handoff──→  reviewer agent
       写 plan/spec                  实现代码                      audit
                                                                      ↓
                                                               主控汇总 → PR
```

`handoff.db` 里的 `planner_actor`、`executor_actor`、`reviewer_actor` 字段，正是为这个多 agent 编排设计的。**我们的设计比 Symphony 更完整**，Symphony 的 `session_id` 只是单个 agent 会话 ID，而我们区分了 flow 内部的完整责任链与交接协议。

两个系统的终点相同：**issue 进，PR 出，人类只做最终 review**。但中间过程的工程复杂度不同。

### 0.2 Symphony 真正值得借鉴的部分

Symphony 不是 agent 框架，它解决的是**调度工程问题**：如何让 daemon 安全地并发管理多个 agent 执行，保证不重复 dispatch、能从崩溃恢复、能在 issue 状态变化时及时停止 agent。

| Symphony 工程逻辑 | 价值 | Vibe Center 现状 |
|-----------------|------|----------------|
| Orchestrator 状态机（claimed/running/retry set） | ⭐⭐⭐ | 无，并发时会重复 dispatch |
| Reconciliation loop（issue 变 terminal → 停 agent） | ⭐⭐⭐ | 无，孤儿进程风险 |
| WORKFLOW.md 规范（标准化 prompt 模板格式） | ⭐⭐ | 无等价物 |
| Workspace hook 体系（after_create/before_run/after_run） | ⭐⭐ | vibe3 flow new 部分覆盖 |
| Agent Runner JSON-RPC 协议（codex app-server） | ⭐ | 用 `claude -p` headless 替代，不需要 |
| Phoenix 监控面板 | ⭐ | vibe3 flow status 替代，不需要 |

**整合策略：借鉴 Symphony 的调度工程逻辑（状态机 + reconciliation），叠加在 Vibe Center 更完整的多 agent 编排体系（handoff 责任链）之上。**

### 0.3 V3 对齐说明

**本 PRD 面向 Vibe Center v3，不面向 v2。**

v3 的数据模型已为自动化编排预留接口：

| v3 字段 | Symphony 对应概念 | 我们的实际用途 |
|--------|-----------------|--------------|
| `flow_state.planner_actor` | — | 记录 planner agent（`claude/sonnet-4.5`） |
| `flow_state.executor_actor` | `session_id` 的 actor 部分 | 记录 executor agent |
| `flow_state.reviewer_actor` | — | 记录 reviewer agent |
| `flow_state.session_id` | `<thread_id>-<turn_id>` | 记录当前活跃 agent 的会话 ID |
| `flow_state.latest_actor` | — | 记录当前持有 flow 的 agent |
| `flow_state.flow_status` | claimed/running/released | flow 在 Orchestrator 中的调度状态 |

v3 不再有 `worktrees.json` / `registry.json`，Symphony Orchestrator 的状态直接写入 `handoff.db`。

## 1. 架构对比

Symphony 的五层抽象与 Vibe Center 三层架构的映射：

```
Symphony 层级                    Vibe Center v3 对应
─────────────────────────────────────────────────────────────
Policy Layer (WORKFLOW.md)   ↔  AGENTS.md + CLAUDE.md + .agent/rules/
  └─ 团队规则、prompt 模板          └─ 已有，格式待对齐

Coordination Layer           ↔  vibe symphony daemon（待新增）
  └─ 轮询、并发、重试、调度          └─ 借鉴 Symphony 状态机实现

Execution Layer              ↔  vibe3 flow new/bind + claude headless
  └─ workspace 生命周期、agent 启动  └─ 已有 flow，agent 用 claude -p

Integration Layer            ↔  lib/symphony_tracker.sh（待新增）
  └─ GitHub Issues 适配             └─ 复用现有 roadmap_github_api.sh

Observability Layer          ↔  vibe3 flow status（扩展 Agent 行）
  └─ 运行状态可见                    └─ session_id 非空时显示 running
```

## 2. 整合策略

### 策略选择：借鉴调度工程逻辑，不引入运行时

Vibe Center v3 的多 agent 编排体系（planner → executor → reviewer handoff 责任链）比 Symphony 的单 agent 模型更完整。我们不是"学习 Symphony 怎么做 agent"，而是**借鉴 Symphony 解决的调度工程问题**：如何让 daemon 安全地并发管理多个 agent 执行，保证不重复 dispatch、能从崩溃恢复。

直接使用 Symphony Elixir 实现的问题：
- 引入 Elixir/BEAM 运行时，违背 Zsh 技术栈原则
- 与现有 `vibe flow` / `vibe task` 体系产生重复和冲突
- Symphony 目前是 "low-key engineering preview"，不适合生产依赖

**结论**：将 Symphony 的 Orchestrator 状态机和 Reconciliation loop 移植进 Vibe Center，用 Zsh 实现，叠加在已有的 handoff 责任链之上。

## 3. 运作机制详解

### 3.0 端到端流程

理解整合方案的关键是理解 Codex 的两种运行模式：

```
交互模式（日常使用）          app-server 模式（Symphony 使用）
─────────────────────────────────────────────────────────
codex "fix the bug"          codex app-server
↓                            ↓
终端 UI，等待人确认           无 UI，通过 stdin/stdout 收发 JSON-RPC
人在旁边监督                  daemon 发 prompt，Codex 自主执行
```

**完整端到端流程**（Mac Mini 上 24/7 运行）：

```
[Mac Mini daemon: vibe symphony start]

每 60 秒 tick：
  ① gh issue list --label symphony:ready
     → 发现 issue #42 "fix login redirect"

  ② 查 handoff.db：#42 有没有对应 flow？
     → 没有 → dispatch

  ③ vibe3 flow new fix-login-redirect
     → 创建 branch task/fix-login-redirect

  ④ vibe3 flow bind task 42
     → #42 成为这条 flow 的 task issue

  ⑤ 写 handoff.db：
     flow_state.latest_actor = "codex/gpt-5.4"
     flow_state.flow_status  = "active"

  ⑥ 启动 Codex app-server（在 branch workspace 里）：
     codex app-server
     ↓ JSON-RPC over stdio
     → initialize（握手）
     → thread/start（创建会话，得到 thread_id）
     → turn/start（发送 WORKFLOW.md 渲染后的 prompt）

  ⑦ 写 handoff.db：
     flow_state.session_id = "<thread_id>-<turn_id>"
     （此时 vibe3 flow status 显示 "Agent: codex/gpt-5.4 · running"）

  ⑧ Codex 自主工作：
     读代码 → 写代码 → git commit → gh pr create
     每个动作以 JSON-RPC 事件流回 daemon

  ⑨ 收到 turn/completed 事件：
     → 清空 flow_state.session_id
     → gh issue edit 42 --add-label symphony:done
     → vibe3 flow status 里 Agent 行消失

  ⑩ 人类收到 PR 通知，review & merge
```

### 3.0.1 Agent 选择：Codex vs Claude Code

Symphony SPEC §10 定义的 Agent Runner 协议是专门为 `codex app-server` 设计的 JSON-RPC 层。
**你们应该用 Claude Code headless 模式，可以完全绕过这层协议。**

```
Codex app-server（Symphony 原生）    Claude Code headless（推荐）
──────────────────────────────────────────────────────────────
codex app-server                     claude -p "..." --output-format json
JSON-RPC over stdio，需实现协议层     直接 CLI 调用，stdout 返回结果
需要 OpenAI Codex 订阅               Anthropic 账号（已有）
Symphony Agent Runner §10 全部实现   daemon 直接 exec，~10 行代码
```

`lib/symphony.sh` 里的 agent 启动逻辑因此大幅简化：

```bash
_symphony_run_agent() {
  local workspace="$1" issue_prompt="$2" actor="${3:-claude}"
  cd "$workspace"
  case "$actor" in
    claude)
      claude -p "$issue_prompt" \
        --output-format json \
        --allowedTools "Bash,Read,Write,Edit,Glob,Grep"
      ;;
    codex)
      # 若将来需要 Codex，再实现 JSON-RPC 层
      codex "$issue_prompt"
      ;;
  esac
}
```

`WORKFLOW.md` 里的 `codex.command` 字段对应改为 `agent.command: claude -p`。

### 3.1 WORKFLOW.md prompt 模板示例

Codex 收到的 prompt 由 WORKFLOW.md 模板 + issue 数据渲染而成：

```markdown
你正在处理 GitHub issue #{{ issue.identifier }}: {{ issue.title }}

Issue 描述：
{{ issue.description }}

执行前必须阅读：
- AGENTS.md（项目规则入口）
- CLAUDE.md（硬规则）

完成后：
1. 提交所有改动（git commit）
2. 创建 PR（gh pr create），PR 描述中关联 issue #{{ issue.identifier }}
3. 不要自行 merge，等待人类 review
```

### 3.2 `flow status` 可见性

整合后 `vibe3 flow status` 的输出变化：

```
# 有 agent 运行时
Flow: fix-login-redirect
  Branch:     task/fix-login-redirect
  Status:     active
  Task Issue: #42 fix login redirect
  Agent:      codex/gpt-5.4 · running 12m   ← session_id 非空时显示
  PR:         none
  Next:       (由 Codex 自主决定)

# agent 完成后（session_id 被清空）
Flow: fix-login-redirect
  Branch:     task/fix-login-redirect
  Status:     active
  Task Issue: #42 fix login redirect
  PR:         #201 (draft)                   ← Codex 创建的 PR
  Next:       human review
```

数据来源全部在 `flow_state` 表，v3 已预留字段，零 schema 变更。

## 4. 具体整合点（分层）

### 3.1 Tier 3 整合：WORKFLOW.md 规范引入

**目标**：让 Vibe Center 的 repo 对外部 agent（Codex、Claude 等）可读，符合 Symphony 的 Policy Layer 规范。

**方案**：在项目根目录新增 `WORKFLOW.md`，格式兼容 Symphony SPEC §5：

```yaml
---
tracker:
  kind: github          # 或 linear
  active_states: ["todo", "in_progress"]
  terminal_states: ["done", "archived", "cancelled"]

polling:
  interval_ms: 60000

workspace:
  root: .worktrees      # 复用现有 worktree 目录

hooks:
  after_create: |
    # 复用 vibe flow new 的 worktree 初始化逻辑
    git fetch origin main --quiet
  before_run: |
    # 加载 vibe 环境
    source ~/.vibe/loader 2>/dev/null || true
  after_run: |
    # 触发 vibe check
    bin/vibe check 2>/dev/null || true

agent:
  max_concurrent_agents: 3
  max_turns: 20
---

# Vibe Center Workflow

你是 Vibe Center 项目的 coding agent。

执行前必须阅读：
- AGENTS.md（入口导航）
- CLAUDE.md（硬规则）
- .agent/context/task.md（当前任务状态）

...（完整 prompt template）
```

**影响**：零破坏性变更，纯新增文件。

---

### 3.2 Tier 1 整合：`vibe symphony` 子命令

**目标**：实现 Symphony Orchestrator 的核心调度逻辑，作为 `vibe` 的新子命令。

**新增命令**：`vibe symphony <start|stop|status>`

**核心逻辑**（移植自 Symphony SPEC §7-8）：

```
vibe symphony start
  ├── 读取 WORKFLOW.md（tracker 配置、polling 间隔）
  ├── 启动轮询 daemon（后台进程）
  │   └── 每 interval_ms 执行一次 tick：
  │       ├── 1. reconcile_running：检查运行中任务的 tracker 状态
  │       ├── 2. fetch_candidates：从 tracker 拉取 active issues
  │       ├── 3. dispatch_eligible：对符合条件的 issue 执行：
  │       │       ├── vibe flow new <issue-slug>（创建 worktree）
  │       │       ├── vibe task add <id> --title "<title>"（注册任务）
  │       │       └── 启动 agent（codex/claude）in workspace
  │       └── 4. 更新 registry.json 状态
  └── 写入 PID 到 .git/vibe/symphony.pid
```

**状态机**（移植自 Symphony SPEC §7.1）：

```
Unclaimed → Claimed → Running → [RetryQueued | Released]
```

映射到 Vibe Center：
- `Unclaimed` = `vibe task` status: `todo`
- `Claimed` = `vibe task` status: `in_progress`（已 bind worktree）
- `Running` = worktree 存在 + agent 进程活跃
- `RetryQueued` = `vibe task` status: `blocked`（等待重试）
- `Released` = `vibe task` status: `completed` 或 `archived`

**实现文件**：`lib/symphony.sh`（预估 ~250 行，符合单文件 ≤300 行约束）

---

### 3.3 `flow status` 扩展：agent 运行状态可见

**目标**：不新增命令，直接在 `vibe3 flow status` 里展示哪条线有 agent 在跑。

**现有 v3 `flow status` 输出**（来自 `handoff.db`）：
```
Flow: fix-login
  Branch: task/fix-login
  Status: active
  Task Issue: #42
  PR: #201 (draft)
  Next: implement redirect logic
```

**整合后新增一行**：
```
Flow: fix-login
  Branch: task/fix-login
  Status: active
  Task Issue: #42
  PR: #201 (draft)
  Agent: codex/gpt-5.4 · running 12m    ← 新增，来自 flow_state.session_id + latest_actor
  Next: implement redirect logic
```

**数据来源**：v3 `flow_state` 表已有的字段：
- `latest_actor` → 显示 `codex/gpt-5.4`
- `session_id`（预留字段）→ 存 Symphony 的 `<thread_id>-<turn_id>`
- `updated_at` → 计算 running 时长

Symphony Orchestrator dispatch 一个 issue 时，只需要往 `handoff.db` 写：
```python
flow_state.latest_actor = "codex/gpt-5.4"
flow_state.session_id   = "<thread_id>-<turn_id>"
flow_state.flow_status  = "active"
```

`flow status` 读取时，若 `session_id` 非空且 `flow_status == active`，就显示 Agent 行。agent 完成后清空 `session_id`，该行自动消失。

**无 agent 运行时**：不显示 Agent 行，输出与现在完全一致，零干扰。

---

### 3.5 Tier 2 整合：`vibe-symphony` Skill

**目标**：为 agent 提供 Symphony 模式下的交互入口，处理 proof-of-work 输出。

**新增 Skill**：`skills/vibe-symphony/SKILL.md`

核心职责：
- 解析当前 issue 上下文（从 WORKFLOW.md prompt template 渲染）
- 执行完成后生成标准化 proof-of-work bundle：
  - CI 状态（`vibe flow review` 输出）
  - 复杂度分析（diff stats）
  - 变更摘要（用于 PR body）
- 调用 `vibe flow pr` 提交 PR，状态回写 tracker

---

### 3.6 Issue Tracker 适配器（新增）

**目标**：实现 Symphony SPEC §11 的 Issue Tracker Integration Contract。

**方案**：新增 `lib/symphony_tracker.sh`，支持两种 tracker：

```bash
# GitHub Issues 适配（优先，因为项目本身在 GitHub）
_symphony_tracker_fetch_candidates()   # 拉取 active issues
_symphony_tracker_fetch_by_states()    # 按状态过滤
_symphony_tracker_fetch_states_by_ids() # 批量状态刷新（reconcile 用）
```

**GitHub Issues 实现**（使用 `gh` CLI，已在 vibe check 中验证存在）：

```bash
_symphony_tracker_fetch_candidates() {
  local project_slug="$1"
  gh issue list \
    --repo "$project_slug" \
    --state open \
    --label "symphony:ready" \
    --json id,title,body,labels,state \
    --jq '.[] | {id: (.number|tostring), identifier: ("GH-"+(.number|tostring)), title, description: .body, state: .state, labels: [.labels[].name]}'
}
```

**触发标签约定**：`symphony:ready` → 触发 dispatch；`symphony:done` → terminal state。

## 4. 实现优先级

### Phase 1（最小可用，建议先做）

1. **WORKFLOW.md** — 零风险，纯文档，立即让 repo 对 Symphony 兼容
2. **`lib/symphony_tracker.sh`** — GitHub Issues 适配器，~100 行
3. **`lib/symphony.sh`** 核心轮询逻辑 — `vibe symphony start/stop/status`

### Phase 2（完整整合）

4. **`skills/vibe-symphony/SKILL.md`** — proof-of-work bundle 生成
5. **Linear 适配器** — 如果团队使用 Linear

### Phase 3（可选增强）

6. **HTTP 状态接口** — 对应 Symphony SPEC §13.7，`vibe symphony status --json`
7. **SSH worker 扩展** — 对应 Symphony SPEC Appendix A，多机并发

## 5. 不整合的部分

| Symphony 功能 | 不整合原因 |
|--------------|-----------|
| Elixir 参考实现 | 技术栈不符，用 Zsh 移植核心逻辑 |
| Codex app-server 协议 | 与 claude/codex CLI 直接调用等价，不需要 JSON-RPC 层 |
| 视频 walkthrough | 超出当前项目范围 |
| 多租户控制面板 | Symphony 自身也列为 Non-Goal |

## 6. 风险与约束

- **并发安全**：Zsh 没有 Elixir 的 BEAM 并发原语，需用文件锁（`flock`）保护 registry.json 写入
- **Daemon 管理**：后台轮询进程需要可靠的 PID 管理和信号处理
- **Tracker API 限流**：GitHub API 有速率限制，polling interval 不应低于 30s
- **HARD RULE §8**：agent 与 worktree 一对一，symphony dispatch 不得自行新建物理 worktree，必须通过 `vibe flow new`

## 7. 完整工作循环

整合后，人类只在两个点介入，其余全自动：

```
① 你写 GitHub Issue（描述清楚需求）
   ↓ 加标签 symphony:ready

② [自动] Symphony daemon 发现 issue
   ↓ vibe3 flow new + flow bind task
   ↓ 启动 Codex app-server（无交互，沙箱隔离）
   ↓ 发送渲染后的 WORKFLOW.md prompt

③ [自动] Codex 自主执行
   ↓ 读代码 → 写代码 → git commit
   ↓ gh pr create（PR 自动关联 issue）
   ↓ vibe3 flow status 显示 "Agent: codex/gpt-5.4 · running Xm"

④ [可选自动] vibe3 pr review --agent codex
   ↓ 另一个 Codex 实例读 diff
   ↓ 生成结构化 review 结论，回贴到 PR comment

⑤ 你收到 PR 通知
   ↓ 看 review 结论（可能已由 Codex 预审）
   ↓ Approve & Merge（或 Request Changes）

⑥ [自动] PR merge 后
   ↓ flow_state.flow_status = "done"
   ↓ issue 自动关闭（GitHub close keyword）
   ↓ vibe3 flow status 该条目消失
```

**人类角色转变**：需求定义者 + 最终决策者，不再是执行者。

**Codex 为什么不需要交互确认**：
- `approval_policy: never` — 在沙箱范围内完全自主
- `thread_sandbox: workspace-write` — 只能写当前 issue 的 workspace，不能碰系统或其他 branch
- 出了沙箱范围的操作直接报错给 daemon，daemon 记录并重试，不会静默失败

**需求质量决定结果质量**：
- Issue 描述越清楚（当前行为、期望行为、相关文件），Codex 实现越准确
- `AGENTS.md` + `CLAUDE.md` + `WORKFLOW.md` 是 Codex 的"项目规则书"，维护好这三个文件是 harness engineering 的核心工作

## 8. 与现有体系的关系

```
现有体系（人工触发）          Symphony 整合后（自动触发）
─────────────────────────────────────────────────────
人工: vibe flow new <feat>  →  自动: symphony 轮询 → dispatch
人工: vibe task add ...     →  自动: symphony 注册 task
人工: /vibe-done            →  自动: vibe-symphony skill → PR
人工: vibe flow pr          →  自动: proof-of-work bundle → PR
```

两种模式共存，不冲突。人工模式保持不变，symphony 模式作为可选的自动化层叠加。
