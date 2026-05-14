---
name: vibe-review-pr
description: |
  Use only in Claude Code environments with Agent Teams enabled when the user wants
  a comprehensive PR review using the multi-agent team workflow.
---

# Vibe PR Review

`vibe-review-pr` 是 Claude Code Agent Teams 专用 PR 审查入口。Phase 0 完成环境和 Team 准备，Phase 1-5 各是一个 Backlog Task。下游 agent 通过 prompt 注入获取前序报告。

## When to Use

仅以下条件**全部**满足时使用，任一缺失 → 立即停止，按文件范围回退到单 agent 审查：

- host 为 Claude Code
- `TMUX` 已设置（Agent 会由运行时自动在 tmux session 中创建新 pane，team-lead 不需要手动管理 pane）
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- 工具面提供 TeamCreate / Agent / SendMessage

## File Map

| 文件 | 职责 |
|------|------|
| `SKILL.md` | 生命周期、phase 契约、握手协议、硬边界（本文件） |
| `references/execution-reference.md` | 消息样例与等待策略 |
| `references/recovery-playbook.md` | 故障恢复路径 |
| `references/debug-guide.md` | pane 可见性、agent 执行过程查看、model 参数核查、PR 编号路由诊断 |
| `scripts/agent-exist.sh` | 检查 agent 存在性（definition/inbox/pane/alive） |
| `scripts/agent-event.sh` | 列出 agent 事件（标题+时间） |
| `scripts/agent-report.sh` | 提取 agent 报告全文 |
| `.claude/agents/pr-*.md` | Teammate 项目特定职责定义 |

## Agent 定义

| agent | agent_type | Phase | 需要读取 |
|-------|-----------|-------|---------|
| context-researcher | pr-context-researcher | 1 | (无) — 独立调研 |
| code-analyst | pr-code-analyst | 2 | `agent-report.sh context-researcher` |
| architect-reviewer | pr-architect-reviewer | 2 | `agent-report.sh context-researcher` |
| security-reviewer | pr-security-reviewer | 2 | `agent-report.sh context-researcher` |
| fix-executor | pr-fix-executor | 5 | Phase 4 修复指令（lead 直接写入 prompt） |

> codex 是外部 plugin，通过 `codex:rescue` skill 调用，不是 teammate。能跑脚本读 inbox，但不能收 SendMessage。输出由 skill 调用直接返回给 lead。

---

# Pseudocode Convention

本文件使用特殊符号约定来区分**伪代码（执行描述）**与**真实命令/工具调用**。

## 视觉区分系统

| 写法 | 含义 | 示例 |
|------|------|------|
| `@function(args)` | 伪代码函数，定义在 Common Protocols 中 | `@handshake(agent_name)` |
| `ToolName(param=value)` | 真实的 Claude Code Tool 调用 | `TeamCreate(team_name="pr-review-team")` |
| `$ script.sh <arg>` | 真实的 Shell 命令（在终端执行） | `$ agent-exist.sh context-researcher` |
| `` ```bash `` 代码块 | 真实 Shell 脚本，可直接执行 | `skills/vibe-review-pr/scripts/agent-exist.sh` |
| `{variable}` | 占位符，agent 替换为实际值 | `{PR_NUMBER}`, `{agent_name}` |
| `→` | 状态转换方向 | `spawn → 握手 → 分配任务` |
| `// comment` | 伪代码注释（解释 WHY，不是 WHAT） | `// 禁止在此步执行 gh pr view` |

## 伪代码函数 `@` 约定

以 `@` 开头的函数名是**本文件定义的元指令**（Common Protocols 或 Phase 步骤），不是 Claude Code Tool：

```
@handshake(agent_name):        // Common Protocols 中定义
@wait_for_report(agent_name):  // Common Protocols 中定义
@spawn_with_handshake(...):    // Common Protocols 中定义
@stop("原因"):                 // 硬阻塞，立即停止所有操作
```

`@` 函数返回流程级状态：`OK` / `TIMEOUT` / `BLOCKED` / `RETRY`（不是 shell exit code）。

## 真实 Tool 调用（无前缀）

首字母大写的标识符是 Claude Code 的真实 Tool：

```
TeamCreate(team_name="...")    // → 调用 TeamCreate tool
SendMessage(to=..., message=...)// → 调用 SendMessage tool
TaskCreate(subject=..., ...)   // → 调用 TaskCreate tool
Agent(name=..., subagent_type=...) // → 调用 Agent tool
```

## Shell 命令 `$` 约定

伪代码块内用 `$` 前缀的行是真实 Shell 命令：

```
Phase_1():
  $ agent-exist.sh context-researcher    // 检查 agent 状态
  $ agent-report.sh code-analyst         // 提取报告
  result = 上一条命令的 stdout            // 伪代码变量接收输出
```

完整 Shell 脚本用 ` ```bash ` 代码块。

## 显式停止条件

`@stop()` 是硬阻塞。所有 stop 条件使用显式模式：

```
if <条件缺失>: @stop("具体原因")
if <脚本失败>: @stop("哪个脚本、什么错误")
收到【agent_blocked】: @stop("agent 名称 + 阻塞原因")
```

禁止的模式：
- `handle errors appropriately` → 改为 `if exit ≠ 0: @stop("脚本名失败: 错误信息")`
- `wait for completion` → 改为 `@wait_for_report(agent_name)` 或 `if timeout: @stop("agent 未响应")`

## 执行意图标注

涉及文件时，明确标注**执行**还是**读取参考**：

- **执行**：`$ agent-report.sh code-analyst`（运行脚本，只消费 stdout）
- **读取参考**：`Read reference: references/execution-reference.md`（读取文件内容进 context）

禁止模糊写法：`use agent-report.sh` / `check execution-reference.md`


---

# Common Protocols

以下函数在整个审查流程中复用，定义一次，各 Phase 引用。

## @handshake(agent_name) → OK | TIMEOUT

```
@handshake(agent_name):
  """有方向、有时序的握手。team-lead 发起，agent 回复。"""
  SendMessage(to=agent_name, summary="握手信号", message="【lead_ready】")
  for attempt in 1..3:
    sleep(30)
    $ agent-exist.sh {agent_name} | grep -q "ready_event=found"
    if found: return OK
  return TIMEOUT
```

> **State Semantics**:
> - `ready_event=found` — Agent 已发送 `【agent_ready】` 事件，可进入下一步任务分配
> - `ready_event=missing` — Agent 未发送过 ready 事件（可能未启动、已关闭、或 inbox 为空）
> - `ready_event=waiting` — Lead inbox 不存在（team 结构未初始化），需要先执行 team 创建流程
>
> **Detection Strategy**:
> - 握手检测应区分 `found`（成功）和 `missing/waiting`（需要等待或重试）
> - `waiting` 状态表示基础设施未就绪，应等待 team 初始化完成
> - `missing` 状态表示 agent 未响应，应等待或重新 spawn

`agent-exist.sh <agent>` 输出最后一行包含 `ready_event=found|missing|waiting`，grep `ready_event=found` 确认 agent 已回复 `【agent_ready】`。

**约束**：
- spawn 后必须先握手，不得跳过
- 收到 `【agent_ready】` 后，下一条消息必须是正式任务（fresh spawn 不得先进入 idle）
- 超时 3 次 → 标记 agent 为 blocked，继续处理下一个 agent
- team-lead 自身必须先 `ToolSearch("select:SendMessage")` 再 spawn 任何 agent

## @wait_for_report(agent_name, timeout=180, max_attempts=3) → report | TIMEOUT

```
@wait_for_report(agent_name):
  """主动轮询等待 agent 报告。禁止被动 idle。
  
  注意：stale 状态只表示长时间无消息，不代表 agent 失联。
  如果 agent-exist.sh 显示 stale/inactive，应先捕获 tmux pane 内容确认是否有输出。
  如果 pane 有输出（agent 正在工作），继续等待，不要重新握手。
  只有 pane 无输出时才重新握手。"""
  
  for attempt in 1..max_attempts:
    sleep(timeout)
    $ agent-report.sh {agent_name}
    if exit code == 0:        // 报告已送达
      return stdout            // 完整报告文本（agent= / timestamp= / body_start / 正文）
    // exit 3 = 暂无报告, exit 2 = 未定义 agent, exit 1 = inbox 不存在
  return TIMEOUT
```

> `agent-report.sh` 输出格式：`agent=<name>` / `timestamp=<ts>` / `body_start` / 完整消息正文。`body_start` 之后的内容即为 agent 通过 SendMessage 发送的原始报告。

## @handle_idle(agent_name) → report | RETRY | BLOCKED

```
@handle_idle(agent_name):
  """收到 idle 通知后的统一处理。idle_notification 是触发信号，不是完成确认。"""
  // 1. 检查是否有报告（agent-report.sh 直接判断，exit 0 = 有报告）
  $ agent-report.sh {agent_name} > /dev/null 2>&1
  if exit == 0:
    return $(agent-report.sh {agent_name})   // exit 0, stdout = 完整报告

  // 2. 无报告 → 检查 agent 状态诊断
  status = $(agent-exist.sh {agent_name})     // 看 alive 字段: active/idle/stale/inactive/never
  events = $(agent-event.sh {agent_name})     // 看最新事件类型: agent_ready/agent_report/message

  // 3. 根据状态行动
  case status.alive:
    "active" or "idle"  → continue waiting（agent 可能仍在执行）
    "stale" or "inactive" or "never" → 
      // 捕获 tmux pane 内容（确认是否有输出）
      pane_content = tmux capture-pane -t <pane_id> -p -S -50
      if pane_content has recent output:
        continue waiting  // agent 正在工作，不要握手
      else:
        // 重新握手
        for attempt in 1..3:
          SendMessage(to=agent_name, message="【lead_ready】")
          sleep(180)  // fix-executor 等待 180s
          $ agent-exist.sh {agent_name} | grep -q "ready_event=found"
          if found: return RETRY  // 重新分配任务
        return BLOCKED
```

> idle_notification 语义：agent 空闲了，**可能**完成了工作。teammate-message 系统不转发工作报告（工作报告写入 inbox），只转发 idle_notification / permission_request / plan_approval_request。收到 idle 后必须主动检查 inbox/pane，不能假设工作已完成。

## @stop(reason)

```
@stop(reason):
  """调试阶段硬规则：遇到任何错误立即停止。"""
  halt_all_operations()
  output("BLOCKED: " + reason)
  wait_for_user_instruction()
  // 禁止：修复后自行继续、自行判断"理解了应该继续"、只发警告不停止
  // 恢复：仅用户明确指示 "继续" / "resume" / "go ahead"
```

**触发条件**：工具调用返回错误 / 收到 `【agent_blocked】` / 脚本非零退出码 / 任何未预期行为

**Lead 收到 `【agent_blocked】` 后**：
1. `@stop()` 停止当前 Phase
2. `$ agent-event.sh {agent}` 查看事件上下文
3. `$ agent-exist.sh {agent}` 诊断状态
4. 输出阻塞原因，等待用户指示

## @spawn_with_handshake(agent_name, agent_type, model="sonnet") → OK | TIMEOUT

```
@spawn_with_handshake(agent_name, agent_type):
  Agent(
    name=agent_name,
    subagent_type=agent_type,
    team_name="pr-review-team",
    model=model,
    prompt="【第一步只能握手】
      你现在不得开始工作，也不得抢先自报 ready。
      等待 team-lead 发送 `【lead_ready】`。
      收到后执行 ToolSearch(query='select:SendMessage', max_results=1)，
      然后立刻 SendMessage(to='team-lead', message='【agent_ready】已就绪')。
      在收到正式任务前，不得开始任何工作。"
  )
  return @handshake(agent_name)
```

---

# Phase 0: Preparation

> Phase 0 是 team-lead 内联操作，不创建 Backlog Task。失败 → 立即停止，不创建任何 Backlog。

```
Phase_0():
  // Step 1: 环境检查
  assert tmux is set
  assert AGENT_TEAMS=1
  assert TeamCreate, TaskCreate, ToolSearch, SendMessage available
  // 禁止在此步执行 gh pr view / gh pr diff / git diff

  // Step 2: 选择执行模式
  mode = user_specified or "ask-each"
  // 选项: auto-fix / comment-only / auto-decide / ask-each

  // Step 3: Team 创建或复用
  result = TeamCreate(team_name="pr-review-team")
  if result == "already_exists":
    for member in existing_members (except team-lead):
      if @handshake(member) == OK: mark alive, reuse
      else: mark dead
    if all_dead: TeamDelete() → TeamCreate(team_name="pr-review-team")
    // 部分存活 → 复用存活者，缺失的在对应 Phase spawn
  // Team 名称固定为 pr-review-team（不用 pr-review-<number>）
  // 复用判断 = 握手结果（不检查 isActive/config.json）

  // Step 4: team-lead 自身 ToolSearch
  ToolSearch(query="select:SendMessage")
  if failed: @stop("team-lead ToolSearch 失败")
  // SendMessage 是 deferred tool，必须先加载 schema

  // Step 5: 一次性创建全部 5 个 Backlog Task
  // 验证清单（提交前必须输出）:
  //   Phase 1: subject="Phase 1: 背景调研", metadata={phase_order:1, depends_on_phase:0}
  //   Phase 2: subject="Phase 2: 专家评审", metadata={phase_order:2, depends_on_phase:1}
  //   Phase 3: subject="Phase 3: Codex 复查", metadata={phase_order:3, depends_on_phase:2}
  //   Phase 4: subject="Phase 4: 综合判断", metadata={phase_order:4, depends_on_phase:3}
  //   Phase 5: subject="Phase 5: 写回 + 修复", metadata={phase_order:5, depends_on_phase:4}
  //
  // 每个 TaskCreate 必须包含 subject + description + metadata
  // 禁止空调用、禁止批量参数（一次调用只创建一个 task）
  // InputValidationError → @stop()

  TaskCreate(subject="Phase 1: 背景调研",
    description="spawn context-researcher → 握手 → 分配任务 → 等待报告 → PR 分类",
    metadata={phase_order:1, depends_on_phase:0})
  TaskCreate(subject="Phase 2: 专家评审",
    description="并行 spawn code-analyst/architect-reviewer/security-reviewer → 握手 → 分配任务 → 等待全部报告",
    metadata={phase_order:2, depends_on_phase:1})
  TaskCreate(subject="Phase 3: Codex 复查",
    description="校验 Phase 2 报告质量 → 决定是否启用 codex → 如启用则调用 codex:rescue",
    metadata={phase_order:3, depends_on_phase:2})
  TaskCreate(subject="Phase 4: 综合判断",
    description="收集全部报告 → 仲裁冲突 → 出具最终决策（APPROVE/NEEDS_CHANGES/REJECT）",
    metadata={phase_order:4, depends_on_phase:3})
  TaskCreate(subject="Phase 5: 写回 + 修复",
    description="写 PR comment → 可选 spawn fix-executor 修复 → 创建 follow-up issues",
    metadata={phase_order:5, depends_on_phase:4})

  // Step 6: 激活 Phase 1
  TaskUpdate(phase_1_task_id, status="in_progress")
```

## Hard Rules

- TeamCreate 必须先于 TaskCreate（否则 task 不关联 team）
- agent 复用判断依赖于握手结果
- 全部 Phase 1-5 task 在 Phase 0 一次性创建

---

# Phase 1: Context Research

> 产出：context-researcher 结构化 PR 背景报告
> 依赖：Phase 0 完成

```
Phase_1():
  // Step 1: spawn + 握手
  if context-researcher not already alive:
    @spawn_with_handshake("context-researcher", "pr-context-researcher")
  if result == TIMEOUT: @stop("context-researcher 握手超时")

  // Step 2: 分配任务
  SendMessage(to="context-researcher", summary="PR #N 背景调研任务", message="""
    分析 PR #N 并产出一份结构化背景报告。

    职责：
    1. 阅读 CLAUDE.md、AGENTS.md、glossary.md、PR description、PR diff
    2. 不要修改任何文件
    3. 完成后用 SendMessage(to="team-lead", message="【agent_report】\n\n## PR #N 背景报告\n...")

    脚本错误处理：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
  """)
  // 禁止：team-lead 自行执行 gh pr view / git diff / git log 收集上下文
  // 禁止：显式 PR 编号入口下 lead 预调查（确认状态/标题/标签/变更范围）

  // Step 3: 等待报告
  report = @wait_for_report("context-researcher")
  if report == TIMEOUT:
    @stop("context-researcher 报告超时，回退单 agent 审查")

  // Step 4: PR 分类
  pr_type = @classify_pr(report)
  TaskUpdate(phase_1_task_id, status="completed",
    metadata={phase_1_output: report})

  // Step 5: 激活下一 Phase
  if pr_type == "simple":
    TaskUpdate(phase_3_task_id, status="in_progress")  // 跳过 Phase 2
  else:
    TaskUpdate(phase_2_task_id, status="in_progress")
```

## PR Classification

```
@classify_pr(report):
  """基于 phase_1_output 判断 PR 类型。"""

  // simple 必须同时满足全部 4 项：
  if (单文件改动 AND < 30 行 AND 仅文档/注释/字符串/重命名 AND 无 security/* 标签):
    return "simple"

  if 涉及认证/授权/数据/凭据/输入验证: return "security"
  if ≥ 5 文件或大规模重构:                   return "refactor"
  return "standard"
```

| 类型 | 条件 | 路由 |
|------|------|------|
| `simple` | 4 项全满足 | Phase 1 → Phase 3（跳过 Phase 2） |
| `security` | 涉及认证/授权/数据/凭据/输入验证 | Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 |
| `refactor` | ≥ 5 文件或大规模重构 | 同上 |
| `standard` | 不属于上述 | 同上 |

> 反例（issue #742）：PR #713 改 6 文件、+11/-10、含 `manager.py` 代码改动 → 错误归类 simple → 实际应按 standard 处理。只要包含代码改动或多文件，就不是 simple。

## idle 自动处理

收到 context-researcher 的 idle 通知后，立即执行 `@handle_idle("context-researcher")`：
- 有报告 → 提取并继续 Phase 1 Step 4
- 需重新握手 → SendMessage(【lead_ready】)，最多 3 次
- 标记 blocked → @stop("context-researcher blocked，回退单 agent 审查")

## Hard Rules

- team-lead 不得自行收集上下文（这是 context-researcher 的工作）
- 不得在未收到报告前激活 Phase 2/3
- 保持空闲 / 等待新 PR 只适用于复用 teammate；不适用于 fresh spawn 且刚完成握手的 agent
- 收到 idle 通知后必须使用 `@handle_idle`，不得直接轮询

---

# Phase 2: Expert Review

> 产出：code-analyst / architect-reviewer / security-reviewer 的独立审查报告
> 依赖：Phase 1 完成（phase_1_output 非空）
> 启动前：从 Phase 1 task metadata 提取 phase_1_output；未 ready → @stop()

```
Phase_2():
  // Step 1: 提取 Phase 1 报告
  phase_1_output = TaskGet(phase_1_task_id).metadata.phase_1_output
  if not phase_1_output: @stop("Phase 1 报告未就绪")

  // Step 2: 并行 spawn 三个 agent（同一响应内）
  parallel:
    Agent(name="code-analyst", subagent_type="pr-code-analyst",
      team_name="pr-review-team", model="sonnet",
      prompt="【第一步只能握手】等待 team-lead 发送【lead_ready】...")
    Agent(name="architect-reviewer", subagent_type="pr-architect-reviewer",
      team_name="pr-review-team", model="sonnet",
      prompt="【第一步只能握手】等待 team-lead 发送【lead_ready】...")
    Agent(name="security-reviewer", subagent_type="pr-security-reviewer",
      team_name="pr-review-team", model="sonnet",
      prompt="【第一步只能握手】等待 team-lead 发送【lead_ready】...")

  // Step 3: 逐个握手 + 分配任务（非批量，逐个处理）
  for agent in ["code-analyst", "architect-reviewer", "security-reviewer"]:
    if @handshake(agent) == TIMEOUT:
      @mark_blocked(agent)
      continue  // 跳过该 agent，继续下一个

    // 立即分配正式任务（含 phase_1_output）
    SendMessage(to=agent, summary="PR #N 审查任务", message="""
      分析 PR #N。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      完成审查后用 SendMessage(to="team-lead", message="【agent_report】\n\n## <角色>报告\n...")

      脚本错误处理：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
    """)
    // 派发完一个后不得进入 idle，必须继续处理下一个

  // Step 4: 等待全部报告
  reports = {}
  for agent in active_agents:
    report = @wait_for_report(agent)
    if report == TIMEOUT:
      @mark_blocked(agent)
    else:
      reports[agent] = report

  if len(reports) == 0: @stop("Phase 2 无可用报告，回退单 agent 审查")

  TaskUpdate(phase_2_task_id, status="completed",
    metadata={phase_2_reports: reports, blocked_agents: blocked})

  // Step 5: 激活 Phase 3
  TaskUpdate(phase_3_task_id, status="in_progress")
```

## idle 自动处理

收到任何 Phase 2 agent 的 idle 通知后，立即执行 `@handle_idle(agent_name)`：
- 有报告 → 提取并继续
- 需重新握手 → SendMessage(【lead_ready】)，最多 3 次
- 标记 blocked 后仍继续等待其他 agent

## Hard Rules

- Phase 1 / Phase 2 严格串行，禁止并行启动
- fresh spawn 的初始 prompt 只允许握手，不得内嵌 phase_1_output 或正式任务
- 收到 `【agent_ready】` 后的下一条有效动作必须是正式任务；不得插入"保持空闲 / 等待新 PR"
- 至少 1 个 agent 握手成功 + 返回有效报告即可推进

---

# Phase 3: Codex Review

> 目标：校验 Phase 2 报告质量，决定是否启用 codex 复查
> 依赖：Phase 2 完成
> 此阶段不涉及 agent 握手

```
Phase_3():
  // Step 1: 校验 Phase 2 报告基础数据
  for report in phase_2_reports:
    // 检查文件数/行数/涉及模块是否与 PR 实际 diff 一致
    if report has 严重幻觉（数据与 diff 明显矛盾）:
      @mark_invalid(report)  // 标注"报告作废"

  // Step 2: 决定是否启用 codex
  valid_reports = phase_2_reports - invalid_reports
  trigger_codex = (
    is_security_pr OR
    diff > 500 lines OR
    @reports_conflict(valid_reports) OR  // 多份报告对同一问题结论矛盾
    len(valid_reports) < len(expected_agents)  // 报告缺失
  )

  // Step 2.1: 输出决策依据（让决策过程透明可见）
  output("Codex 触发决策依据：")
  output(f"  - is_security_pr: {is_security_pr}")
  output(f"  - diff > 500 lines: {diff > 500} (实际 diff: {diff} lines)")
  output(f"  - reports_conflict: {reports_conflict(valid_reports)}")
  output(f"  - 报告缺失: {len(valid_reports)} < {len(expected_agents)}")
  output(f"  - 任一报告有严重幻觉: {any_report_invalid}")
  output(f"  → trigger_codex = {trigger_codex}")

  if any_report_invalid:  // 任一报告有严重幻觉 → 跳过 codex
    trigger_codex = false

  if trigger_codex and codex:rescue available:
    Skill(skill="codex:rescue", args="""
      复查 PR #N 的全部审查报告，给出第三方独立评估。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      读取 Phase 2 专家评审：
        skills/vibe-review-pr/scripts/agent-report.sh code-analyst
        skills/vibe-review-pr/scripts/agent-report.sh architect-reviewer
        skills/vibe-review-pr/scripts/agent-report.sh security-reviewer

      重点关注：是否有遗漏、结论是否一致、建议是否可行。
    """)
  else if trigger_codex and codex:rescue not available:
    // Fallback: team-lead 自行执行复查逻辑
    // 读取 Phase 1 + Phase 2 报告，基于自身推理进行第三方独立评估

  TaskUpdate(phase_3_task_id, status="completed",
    metadata={codex_result: result, invalid_reports: invalid})

  // Step 3: 激活 Phase 4
  TaskUpdate(phase_4_task_id, status="in_progress")
```

## Hard Rules

- 绝对禁止传 diff/代码片段给 codex：只传 Phase 2 结构化报告（文件列表、行数、安全声明等）
- 任一报告存在严重幻觉 → 跳过 codex，直接进入 Phase 4
- 不得在 Phase 2 完成前启动 codex（严格串行）

---

# Phase 4: Final Judgment

> 目标：收集全部可用报告，仲裁冲突，出具最终决策
> 依赖：Phase 3 完成
> team-lead 内联操作

```
Phase_4():
  // Step 1: 收集全部可用报告
  all_reports = []
  for agent in ["context-researcher", "code-analyst", "architect-reviewer", "security-reviewer"]:
    report = $(agent-report.sh {agent})
    if report valid: all_reports.append(report)
  if codex_result: all_reports.append(codex_result)
  // 剔除 Phase 3 标记为作废的报告

  // Step 1.5: 复验测试脚本（如果 PR 包含新增测试脚本）
  if PR contains new test files:
    output("检测到新增测试脚本，team-lead 执行复验...")
    for test_file in new_test_files:
      $ uv run pytest {test_file} -v
      if exit ≠ 0:
        @stop("测试脚本复验失败：{test_file}")
    output("✅ 所有新增测试脚本通过复验")

  // Step 2: 仲裁冲突 + 出具最终决策
  decision = @arbitrate(all_reports, mode)
  // decision ∈ {APPROVE, NEEDS_CHANGES, REJECT}

  // Step 3: 质量自查（写回前强制执行，不得在生成 Phase 5 产出后再自查，见 Appendix A）
  // ⚠️ 禁止延迟自查：不得在生成 PR comment 后才执行质量自查，必须在 Step 4 之前严格执行
  for rule in QUALITY_STANDARDS:
    if not @pass(rule): @fix_before_proceeding()

  // Step 4: 按决策行动
  if decision == NEEDS_CHANGES and mode == "auto-fix":
    // 提取可修复项（从 Phase 1/2/3 报告中），整理为修复指令
    fix_instructions = @extract_fixable_items(all_reports)
    // 格式：每条 = 具体问题 + 来源 agent + 修复方式
    // 不可自动修复的问题 → 转 follow-up issue / PR comment

    TaskUpdate(phase_4_task_id, status="completed",
      metadata={decision: decision, fix_instructions: fix_instructions})
    TaskUpdate(phase_5_task_id, status="in_progress")
  else:
    TaskUpdate(phase_4_task_id, status="completed",
      metadata={decision: decision})
    // Phase 5 仅写 comment，不 spawn fix-executor
    TaskUpdate(phase_5_task_id, status="in_progress")
```

## Hard Rules

- 禁止使用已作废报告做结论
- 替缺失 agent 脑补结论 → 标注"审查不完整"
- teammate-message PR 编号不匹配时必须如实标注
- 拒绝"已合并 / CI 通过 / 无漏洞"这类无证据声明
- 必须通过全部 8 条质量自查（见 Appendix A）

---

# Phase 5: Writeback + Fix

> 目标：PR comment + follow-up issues + 可选修复 commit
> 依赖：Phase 4 完成
> 执行路径由 execution_mode 决定

## Execution Modes

| 模式 | 行为 | 适用场景 |
|------|------|---------|
| `ask-each`（默认） | 每步操作前询问用户 | 标准 PR、安全 PR |
| `auto-decide` | team-lead 根据复杂度自动决策 | 简单 PR（< 50 行，无安全相关） |
| `auto-fix` | 自动修复阻塞问题 | 阻塞项 < 3 个，修改面 < 3 文件 |
| `comment-only` | 只写 comment，不修复 | 大型 PR、高风险改动 |

```
Phase_5():
  // Step 1: 写 PR comment
  // 格式要求见 Appendix A 第 8 条
  // 必须包含：决策一行 / 已解决技术债（带 diff 引用） / 遗留问题（带规则引用） /
  //          follow-up issue 链接 / 审查依据
  // 禁止包含：百分制/字母评分 / Phase 1/2/3 内部流程标题作叙事结构 /
  //          已解决与未解决问题混在一起
  gh pr comment PR#N --body "<formatted_review>"

  // Step 2: 修复（仅 auto-fix 模式且存在阻塞问题）
  if mode == "auto-fix" and decision == NEEDS_CHANGES:
    // spawn + 握手
    @spawn_with_handshake("fix-executor", "pr-fix-executor")
    if result == TIMEOUT: @stop("fix-executor 握手超时")

    // 分配修复任务
    SendMessage(to="fix-executor", summary="PR #N 修复任务", message="""
      根据 team-lead 提供的修复指令修复 PR #N。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      修复指令：
      <Phase 4 产出的具体修复点列表，逐条包含问题描述、来源 agent、修复方式>

      职责：
      1. 按修复指令逐条执行修复
      2. 不要自行扩大修复范围
      3. 完成后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 修复报告\n...")

      脚本错误处理：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
    """)

    // 等待修复报告
    report = @wait_for_report("fix-executor")
    if report == TIMEOUT: @stop("fix-executor 报告超时")

  // Step 3: 创建 follow-up issues（范围外问题）
  for issue in out_of_scope_issues:
    // 先搜索去重，禁止重复创建
    gh issue create --title "..." --body "..."
  // 禁止：把当前 PR 阻塞问题转为 follow-up
  // 禁止：把范围外技术债塞进当前 PR comment

  TaskUpdate(phase_5_task_id, status="completed")

  // Step 4: 会话收尾
  @ask_user("继续审查下一个 PR？(continue / end)")
  if continue:
    goto Phase_0_Step_3  // 复用 Team，不重建
  else:
    for teammate in all_agents:
      SendMessage(to=teammate, summary="会话结束", message="shutdown_request")
    TeamDelete()
    // 若 TeamDelete 返回 "no team found" → rm -rf ~/.claude/teams/pr-review-team
```

## Hard Rules

- 模式决定路径；仅 `auto-fix` 可 spawn `pr-fix-executor`
- 范围外问题转 follow-up issue；禁止把范围外技术债塞进当前 PR comment
- 禁止把当前 PR 阻塞问题转为 follow-up
- 仅限 `gh pr comment` 和 `gh issue create`（禁止其他 gh/git 命令）
- 会话中途不得发送 shutdown 指令
- **会话收尾必须询问用户**：完成 Phase 5 后必须执行 `@ask_user("继续审查下一个 PR？")`，不得直接发送 shutdown 或清理 Team

---

# Session Lifecycle

> Team 是会话级对象，不是 PR 级。一个会话一个 Team，多个 PR 复用。

```
环境检查 → 检查已有 Team → 握手确认存活 → PR #A → continue → PR #B → ... → end → TeamDelete
```

- 复用判断 = 握手结果（alive=复用，dead=清理后 TeamCreate），不检查 isActive/config.json
- TeamDelete 默认仅在用户 end：用户没说结束就保留状态
- 切换 PR 用 SendMessage（握手成功的复用 agent），禁止盲目重新 spawn
- 每个 PR 开始前：检查 TaskList，上一轮未完成 task 标记 completed

---

# Appendix A: Review Quality Standards

> 写回前强制自查全部 8 条。任一条不满足必须先修正再写回 comment。

### 1. 禁虚假精度评分

LLM 拟合不出小数点评分，强行打分就是幻觉。
- ❌ "代码质量评分：89.75 / 100 (A-)"
- ✅ "APPROVE（已解决 3 项技术债，遗留 2 项次要问题转 follow-up）"

### 2. 强制规则引用

判定为"违规 / 技术债 / 应修复"的条目，必须引用具体规则来源。
- ❌ "异常类型不一致（ValueError 应改为 SystemError）"
- ✅ "`ValueError` 不在 `CLAUDE.md` HARD RULE 13 规定的 `SystemError / UserError / BatchError` 体系内"

**引用格式示例**：
- **文件级别引用**：`CLAUDE.md` HARD RULE 13
- **章节级别引用**：`.claude/rules/coding-standards.md §Size And Complexity §文件大小`
- **段落级别引用**：`docs/standards/error-handling.md §错误处理分类 §SystemError 定义`

合法引用源：`CLAUDE.md` 第 N 条 / `.claude/rules/coding-standards.md § X` / `.claude/rules/python-standards.md` / `docs/standards/error-handling.md` 等。

### 3. 验证再断言（数字基于本 PR 实际 diff）

- ❌ 在不修改 PRService 的 PR 中报告 "PRService at 394/400 maintained"
- ❌ "函数大小超标（68 行，接近 100 行上限）"——project 标准是 < 100 建议，68 行未超标
- ✅ "`get_numstat()` 函数体 65 行（含 docstring），Client/Utils 层建议上限 100，未超标"

### 4. 禁滑动靶点（论证只针对本 PR 改动）

- ❌ 本 PR 函数不直接调用 subprocess，却写"无 shell 注入风险：使用 subprocess.run 列表形式"
- ✅ "本 PR 新增的 `get_numstat()` 不直接调用 subprocess，通过注入的 `run` callable 委托；底层 `_run` 安全性属于既有代码"

### 5. 禁无关指标

不要把与本 PR 无关的项目级指标作为"verification result"列出。
- ❌ 本 PR 不改 PRService，却列 "PRService at 394/400 maintained"
- ✅ 仅列本 PR 改动文件的真实数据（行数、覆盖率、增删比）

### 6. 强制识别真实重构机会

必须做结构性扫描，不能只跑样板检查。重点找：重复代码段、冗余防御（discriminated union 之后又做 isinstance）、已有规则在新代码中的违反点。
- ❌ 遗漏 BRANCH 与 PR 分支的 `merge_base + 三点 diff` 重复
- ✅ 明确指出"BRANCH 和 PR 两条分支共享同一模式，可提取私有 helper 减少 6 行重复"

### 7. 测试评估看性质而非数量

- ❌ "9 个测试 → 测试覆盖 A (95)"
- ✅ "9 个 MagicMock 单元测试，覆盖 4 种 ChangeSource + 4 种错误分支，但缺乏与真实 GitClient._run 的集成契约测试"

必须区分：单元（mock）/ 集成（真实依赖）、happy path / 错误分支。

### 8. Comment 格式（写回前最后一道关）

**必须包含**：
- 决策一行（APPROVE / NEEDS_CHANGES / REJECT）
- 已解决技术债（带 diff 引用）
- 遗留问题（每条带规则引用）
- follow-up issue 链接
- 审查依据（引用了哪些规则文档）

**禁止包含**：
- ❌ 百分制 / 字母评分（除非用户明确要求）
- ❌ "Phase 1 / Phase 2 / Phase 3" 内部流程标题作叙事结构
- ❌ 已解决与未解决问题混在一起

---

# Appendix B: Shell Scripts Interface Reference

> 所有脚本位于 `skills/vibe-review-pr/scripts/`，需从仓库根目录调用。
> 脚本从 `runtime/agents.sh` 读取 agent 注册表，team group 默认为 `pr-review-team`。

## agent-exist.sh

```
agent-exist.sh                        # 列表模式：全部 agent 的 def/inbox/pane/alive/suggestion 表格
agent-exist.sh <agent_name>           # 单 agent 模式：表格行 + ready_event=found|missing|waiting
agent-exist.sh <agent_name> --group <name>  # 指定 team group
```

**握手检测**：单 agent 模式输出最后一行 `ready_event=found` 表示该 agent 已发送 `【agent_ready】`。
**alive 字段**：`active (<10s)` / `idle (<60s)` / `stale (<5min)` / `inactive (>5min)` / `never`。
**suggestion 字段**：`spawn agent` / `send handshake to verify` / `available for task` / `working on task`。

## agent-event.sh

```
agent-event.sh                        # 列表模式：全部 agent 的最新事件概览
agent-event.sh <agent_name>           # 单 agent 模式：该 agent 全部非 idle 事件列表
agent-event.sh <agent_name> --group <name>
```

**输出格式**（单 agent）：TSV — `event_type` `timestamp` `title`
**event_type 值**：`agent_ready` / `agent_report` / `agent_blocked` / `message`
**检查报告事件**：`agent-event.sh <agent> | grep -q "agent_report"`
**检查握手事件**：`agent-event.sh <agent> | grep -q "agent_ready"`

## agent-report.sh

```
agent-report.sh                       # 列表模式：全部 agent 的报告状态 (ok/missing + timestamp)
agent-report.sh <agent_name>          # 提取模式：输出完整报告正文
agent-report.sh <agent_name> --group <name>
```

**退出码**：
| 退出码 | 含义 |
|--------|------|
| 0 | 报告已找到并输出 |
| 1 | team-lead inbox 不存在 |
| 2 | 未定义的 agent 名称 |
| 3 | 该 agent 无报告 (stderr: `report_event=missing`) |

**输出格式**（提取模式）：
```
agent=<name>
timestamp=<iso8601>
body_start
<完整报告正文 — agent 通过 SendMessage 发送的原始内容>
```

**报告检测逻辑**：优先匹配 `【agent_report】` 前缀，fallback 匹配 `## PR #` / `# PR #` 或包含 `审查报告`/`背景报告` 的消息。

---

# Appendix C: Recovery

按 `references/recovery-playbook.md` 处理，不在主流程临场发明 workaround：

- Agent 失联：`agent-exist.sh <agent>` 诊断 alive 状态 → `SendMessage` 测试握手 → 3 次超时 → 重新 `Agent()` spawn
- 报告未送达：`agent-report.sh <agent>` (exit 3 = 无报告) → `agent-event.sh <agent>` 查看事件历史 → `agent-exist.sh <agent>` 检查 alive → 如 inactive 则重新握手
- TeamCreate 与 Agent spawn 状态不一致 → 见 recovery-playbook.md
- teammate-message PR 编号路由错误（已知 bug #40166 / #39651）→ 见 debug-guide.md

执行过程看不到 / model 不对 / PR 编号错位 → `references/debug-guide.md`。

---

# Appendix D: Phase Contracts Cheat Sheet

| Phase | 强制要求 | 易错点 |
|-------|---------|-------|
| 0 | 环境检查 → TeamCreate → ToolSearch（内联操作）；已有 Team 则握手确认存活 | 跳过 Phase 0 直接开始 Phase 1；不复用也不清理直接 TeamCreate；team-lead 未 ToolSearch |
| 1 | 必须先于 Phase 2 完成；产出 phase_1_output；team-lead 不得自行收集上下文；收到 idle 必须使用 @handle_idle | 只打印到终端未保存；team-lead 自己跑 gh pr view；收到 idle 不使用 @handle_idle 直接轮询 |
| 2 | 多 agent 同一响应内并行 spawn；fresh spawn 先握手再分配任务；收到 idle 必须使用 @handle_idle | 与 Phase 1 并行启动；把正式任务写进 spawn prompt；收到 idle 不使用 @handle_idle |
| 3 | 校验报告基础数据；失真报告标注作废；决定是否启用 codex；只传结构化报告给 codex | 与 Phase 2 并行；报告不合格仍调用 codex；给 codex 传 diff |
| 4 | 收集可用报告（剔除作废）；仲裁冲突；通过 8 条质量自查 | 使用已作废报告；替缺失 agent 脑补结论 |
| 5 | 模式决定路径；仅 auto-fix 可 spawn fix-executor；范围外问题转 follow-up；**会话收尾必须询问用户** | 把范围外技术债塞进 PR comment；把阻塞问题转 follow-up；**直接发送 shutdown 不询问用户** |

> 没有 Phase 6。完成 Phase 5 后流程结束。
