---
document_type: prd
title: "Orchestra 调度器设计 PRD"
version: v1
author: "Kiro"
created: "2026-03-16"
last_updated: "2026-03-17"
related_docs:
  - docs/v3/orchestra/README.md
  - CLAUDE.md
  - src/vibe3/flow/
  - src/vibe3/task/
---

# Orchestra 调度器设计 PRD

## 0. 背景与定位

**Orchestra** 是 Vibe Center v3 的调度器子系统，负责从任务板（GitHub Issues）拉取任务并自动分发给 Agent 执行。

设计参考了 [openai/symphony](https://github.com/openai/symphony) 的调度工程理念（发布于 2026 年 3 月）。Symphony 是 OpenAI 的任务板编排框架，其 [SPEC.md](https://github.com/openai/symphony/blob/main/SPEC.md) 提供了语言无关的调度规范。

### 0.1 两个系统的根本差异

**Symphony（OpenAI）的 agent 模型**（单 agent per issue，简单）：
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

`handoff.db` 里的 `planner_actor`、`executor_actor`、`reviewer_actor` 字段，正是为这个多 agent 编排设计的。**v3 的设计比 Symphony 更完整**，Symphony 的 `session_id` 只是单个 agent 会话 ID，而 v3 区分了 flow 内部的完整责任链与交接协议。

两个系统的终点相同：**issue 进，PR 出，人类只做最终 review**。但中间过程的工程复杂度不同。

### 0.2 值得借鉴的部分

Symphony 解决的是**调度工程问题**：如何让 daemon 安全地并发管理多个 agent 执行，保证不重复 dispatch、能从崩溃恢复、能在 issue 状态变化时及时停止 agent。

| Symphony 工程逻辑 | 价值 | Vibe Center 现状 |
|-----------------|------|----------------|
| Orchestrator 状态机（claimed/running/retry set） | ⭐⭐⭐ | 无，并发时会重复 dispatch |
| Reconciliation loop（issue 变 terminal → 停 agent） | ⭐⭐⭐ | 无，孤儿进程风险 |
| WORKFLOW.md 规范（标准化 prompt 模板格式） | ⭐⭐ | 无等价物 |
| Workspace hook 体系（after_create/before_run/after_run） | ⭐⭐ | vibe3 flow new 部分覆盖 |
| Agent Runner JSON-RPC 协议（codex app-server） | ⭐ | 用 `claude -p` headless 替代，不需要 |
| Phoenix 监控面板 | ⭐ | vibe3 flow status 替代，不需要 |

**Orchestra 设计策略：借鉴 Symphony 的调度工程逻辑（状态机 + reconciliation），叠加在 v3 更完整的多 agent 编排体系（handoff 责任链）之上，用 Python 实现。**

### 0.3 v3 技术栈对齐

**Orchestra 调度器面向 v3 设计，使用 Python 实现。**

v3 的数据模型已为自动化编排预留接口：

| v3 字段 | Symphony 对应概念 | 实际用途 |
|--------|-----------------|--------------|
| `flow_state.planner_actor` | — | 记录 planner agent（`claude/sonnet-4.5`） |
| `flow_state.executor_actor` | `session_id` 的 actor 部分 | 记录 executor agent |
| `flow_state.reviewer_actor` | — | 记录 reviewer agent |
| `flow_state.session_id` | `<thread_id>-<turn_id>` | 记录当前活跃 agent 的会话 ID |
| `flow_state.latest_actor` | — | 记录当前持有 flow 的 agent |
| `flow_state.flow_status` | claimed/running/released | flow 在 Orchestra 中的调度状态 |

Orchestra 调度器的状态直接写入 `handoff.db`，无中间文件。

## 1. 架构对比

Symphony 的五层抽象与 v3 架构的映射：

```
Symphony 层级                    Vibe Center v3 对应
─────────────────────────────────────────────────────────────
Policy Layer (WORKFLOW.md)   ↔  AGENTS.md + CLAUDE.md + .agent/rules/
  └─ 团队规则、prompt 模板          └─ 已有，格式待对齐

Coordination Layer           ↔  Orchestra 调度器（待实现）
  └─ 轮询、并发、重试、调度          └─ 借鉴 Symphony 状态机设计

Execution Layer              ↔  vibe3 flow + claude headless
  └─ workspace 生命周期、agent 启动  └─ 已有 flow，agent 用 claude -p

Integration Layer            ↔  GitHub Issues 适配器（待实现）
  └─ GitHub Issues 适配             └─ 复用现有 GitHub API 集成

Observability Layer          ↔  vibe3 flow status（扩展 Agent 行）
  └─ 运行状态可见                    └─ session_id 非空时显示 running
```

## 2. 设计策略

### 策略选择：借鉴调度理念，使用 Python 实现

v3 的多 agent 编排体系（planner → executor → reviewer handoff 责任链）比 Symphony 的单 agent 模型更完整。Orchestra 不是"学习 Symphony 怎么做 agent"，而是**借鉴 Symphony 解决的调度工程问题**：如何让 daemon 安全地并发管理多个 agent 执行，保证不重复 dispatch、能从崩溃恢复。

**设计决策**：
- 使用 Python 实现 Orchestra 调度器，遵循 v3 技术栈
- 状态机和 reconciliation loop 借鉴 Symphony 的设计理念
- 与现有 `vibe3` CLI 无缝集成，不引入独立命令
- 借鉴 Symphony 的 WORKFLOW.md 规范作为 prompt 模板格式

## 3. 运作机制详解

### 3.0 端到端流程

理解 Orchestra 的关键是理解 Agent 的两种运行模式：

```
交互模式（日常使用）          Headless 模式（Orchestra 使用）
─────────────────────────────────────────────────────────
claude "fix the bug"          claude -p "fix the bug" --output-format json
↓                            ↓
终端 UI，等待人确认           无 UI，stdout 返回 JSON 结果
人在旁边监督                  Orchestra daemon 发 prompt，Agent 自主执行
```

**完整端到端流程**（后台 daemon 24/7 运行）：

```
[Orchestra daemon]

每 60 秒 tick：
  ① gh issue list --label orchestra:ready
     → 发现 issue #42 "fix login redirect"

  ② 查 handoff.db：#42 有没有对应 flow？
     → 没有 → dispatch

  ③ vibe3 flow new fix-login-redirect
     → 创建 branch task/fix-login-redirect

  ④ vibe3 flow bind task 42
     → #42 成为这条 flow 的 task issue

  ⑤ 写 handoff.db：
     flow_state.latest_actor = "claude/sonnet-4.5"
     flow_state.flow_status  = "active"

  ⑥ 启动 Claude headless（在 branch workspace 里）：
     claude -p "$rendered_prompt" --output-format json
     → Agent 自主执行，返回结果

  ⑦ 写 handoff.db：
     flow_state.session_id = "<session-uuid>"
     （此时 vibe3 flow status 显示 "Agent: claude/sonnet-4.5 · running"）

  ⑧ Claude 自主工作：
     读代码 → 写代码 → git commit → gh pr create

  ⑨ Agent 完成：
     → 清空 flow_state.session_id
     → gh issue edit 42 --add-label orchestra:done
     → vibe3 flow status 里 Agent 行消失

  ⑩ 人类收到 PR 通知，review & merge
```

### 3.0.1 Agent 选择：Claude Code Headless

Orchestra 使用 Claude Code headless 模式启动 Agent，无需实现复杂的 JSON-RPC 协议：

```
优势：
  claude -p "..." --output-format json
  → 直接 CLI 调用，stdout 返回 JSON 结果
  → 无需额外协议层
  → 使用现有 Anthropic 账号
  → 实现简单，~10 行 Python 代码
```

`src/vibe3/orchestra/agent_runner.py` 的核心逻辑：

```python
def run_agent(workspace: str, prompt: str, actor: str = "claude"):
    """启动 Agent 并返回结果"""
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json"],
        cwd=workspace,
        capture_output=True,
        text=True
    )
    return json.loads(result.stdout)
```

`WORKFLOW.md` 里的 `agent.command` 字段对应 `claude -p`。

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
  Agent:      claude/sonnet-4.5 · running 12m   ← session_id 非空时显示
  PR:         none
  Next:       (由 Agent 自主决定)

# agent 完成后（session_id 被清空）
Flow: fix-login-redirect
  Branch:     task/fix-login-redirect
  Status:     active
  Task Issue: #42 fix login redirect
  PR:         #201 (draft)                   ← Agent 创建的 PR
  Next:       human review
```

数据来源全部在 `flow_state` 表，v3 已预留字段，零 schema 变更。

## 4. 具体实现（分层）

### 4.1 Policy Layer：WORKFLOW.md 规范引入

**目标**：让 Vibe Center 的 repo 对外部 agent（Claude 等）可读，符合 Symphony 的 Policy Layer 规范。

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
    git fetch origin main --quiet
  before_run: |
    # 加载 vibe 环境
    source ~/.vibe/loader 2>/dev/null || true
  after_run: |
    # 触发 vibe check
    vibe3 check 2>/dev/null || true

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

### 4.2 Coordination Layer：Orchestra 调度器实现

**目标**：实现 Orchestra 的核心调度逻辑，作为 v3 的后台服务。

**实现位置**：`src/vibe3/orchestra/` 模块

**核心逻辑**（借鉴 Symphony SPEC §7-8）：

```
Orchestra Scheduler
  ├── 读取 WORKFLOW.md（tracker 配置、polling 间隔）
  ├── 启动轮询 daemon（后台进程）
  │   └── 每 interval_ms 执行一次 tick：
  │       ├── 1. reconcile_running：检查运行中任务的 tracker 状态
  │       ├── 2. fetch_candidates：从 tracker 拉取 active issues
  │       ├── 3. dispatch_eligible：对符合条件的 issue 执行：
  │       │       ├── vibe3 flow new <issue-slug>（创建 worktree）
  │       │       ├── vibe3 flow bind task <id>（注册任务）
  │       │       └── 启动 agent in workspace
  │       └── 4. 更新 handoff.db 状态
  └── 写入 PID 到 .git/vibe/orchestra.pid
```

**状态机**（借鉴 Symphony SPEC §7.1）：

```
Unclaimed → Claimed → Running → [RetryQueued | Released]
```

映射到 v3：
- `Unclaimed` = `vibe3 task` status: `todo`
- `Claimed` = `vibe3 task` status: `in_progress`（已 bind worktree）
- `Running` = worktree 存在 + agent 进程活跃
- `RetryQueued` = `vibe3 task` status: `blocked`（等待重试）
- `Released` = `vibe3 task` status: `completed` 或 `archived`

### 4.3 Integration Layer：Issue Tracker 适配器

**目标**：实现 Symphony SPEC §11 的 Issue Tracker Integration Contract。

**实现位置**：`src/vibe3/orchestra/tracker.py`

支持 GitHub Issues 作为 tracker：

```python
class GitHubTracker:
    """GitHub Issues tracker adapter"""

    def fetch_candidates(self, project_slug: str) -> List[Issue]:
        """拉取 active issues"""
        result = subprocess.run(
            ["gh", "issue", "list",
             "--repo", project_slug,
             "--state", "open",
             "--label", "orchestra:ready",
             "--json", "id,title,body,labels,state"],
            capture_output=True,
            text=True
        )
        return self._parse_issues(result.stdout)

    def fetch_states_by_ids(self, issue_ids: List[str]) -> Dict[str, str]:
        """批量状态刷新（reconcile 用）"""
        # ...
```

**触发标签约定**：`orchestra:ready` → 触发 dispatch；`orchestra:done` → terminal state。

## 5. 实现优先级

### Phase 1（最小可用）

1. **WORKFLOW.md** — 零风险，纯文档，立即让 repo 对 Orchestra 兼容
2. **`src/vibe3/orchestra/tracker.py`** — GitHub Issues 适配器
3. **`src/vibe3/orchestra/scheduler.py`** — 核心调度逻辑

### Phase 2（完整功能）

4. **`src/vibe3/orchestra/agent_runner.py`** — Agent 启动管理
5. **Linear 适配器** — 如果团队使用 Linear

### Phase 3（可选增强）

6. **HTTP 状态接口** — 对应 Symphony SPEC §13.7，状态查询 API
7. **多机扩展** — 对应 Symphony SPEC Appendix A，多机并发

## 6. 不实现的部分

| Symphony 功能 | 不实现原因 |
|--------------|-----------|
| Elixir 参考实现 | 技术栈不符，使用 Python 实现 |
| Codex app-server 协议 | 与 claude CLI 直接调用等价，不需要 JSON-RPC 层 |
| 视频 walkthrough | 超出当前项目范围 |
| 多租户控制面板 | Symphony 自身也列为 Non-Goal |

## 7. 风险与约束

- **并发安全**：使用数据库锁保护 `handoff.db` 写入
- **Daemon 管理**：后台轮询进程需要可靠的 PID 管理和信号处理
- **Tracker API 限流**：GitHub API 有速率限制，polling interval 不应低于 30s
- **Agent 与 worktree 一对一**：Orchestra dispatch 不得自行新建物理 worktree，必须通过 `vibe3 flow new`

## 8. 完整工作循环

整合后，人类只在两个点介入，其余全自动：

```
① 你写 GitHub Issue（描述清楚需求）
   ↓ 加标签 orchestra:ready

② [自动] Orchestra daemon 发现 issue
   ↓ vibe3 flow new + flow bind task
   ↓ 启动 Claude headless（无交互，沙箱隔离）
   ↓ 发送渲染后的 WORKFLOW.md prompt

③ [自动] Claude Agent 自主执行
   ↓ 读代码 → 写代码 → git commit
   ↓ gh pr create（PR 自动关联 issue）
   ↓ vibe3 flow status 显示 "Agent: claude/sonnet-4.5 · running Xm"

④ [可选自动] vibe3 pr review --agent claude
   ↓ 另一个 Claude 实例读 diff
   ↓ 生成结构化 review 结论，回贴到 PR comment

⑤ 你收到 PR 通知
   ↓ 看 review 结论（可能已由 Claude 预审）
   ↓ Approve & Merge（或 Request Changes）

⑥ [自动] PR merge 后
   ↓ flow_state.flow_status = "done"
   ↓ issue 自动关闭（GitHub close keyword）
   ↓ vibe3 flow status 该条目消失
```

**人类角色转变**：需求定义者 + 最终决策者，不再是执行者。

**Agent 为什么不需要交互确认**：
- 只能写当前 issue 的 workspace，不能碰系统或其他 branch
- 出了沙箱范围的操作直接报错给 daemon，daemon 记录并重试，不会静默失败

**需求质量决定结果质量**：
- Issue 描述越清楚（当前行为、期望行为、相关文件），Agent 实现越准确
- `AGENTS.md` + `CLAUDE.md` + `WORKFLOW.md` 是 Agent 的"项目规则书"，维护好这三个文件是 harness engineering 的核心工作

## 9. 与现有体系的关系

```
现有体系（人工触发）          Orchestra 整合后（自动触发）
─────────────────────────────────────────────────────
人工: vibe3 flow new <feat>  →  自动: Orchestra 轮询 → dispatch
人工: vibe3 flow bind task   →  自动: Orchestra 注册 task
人工: /vibe-done              →  自动: Agent 完成后创建 PR
人工: vibe3 flow pr           →  自动: PR 自动创建
```

两种模式共存，不冲突。人工模式保持不变，Orchestra 模式作为可选的自动化层叠加。
