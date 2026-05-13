---
name: vibe-review-pr
description: |
  Use only in Claude Code environments with Agent Teams enabled when the user wants
  a comprehensive PR review using the multi-agent team workflow.
---

# Vibe PR Review

`vibe-review-pr` 是 Claude Code Agent Teams 专用 PR 审查入口。Phase 0 完成环境和 Team 准备，Phase 1-5 各是一个 Backlog Task。下游 agent 通过 prompt 注入获取前序报告。

## When to Use

仅在以下条件**全部**满足时使用：

- host 为 Claude Code
- `TMUX` 已设置
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- 工具面提供 TeamCreate / Agent / SendMessage

任一缺失 -> 立即停止，按文件范围回退到单 agent 审查。

## Must Read

需要消息样例或恢复路径时读 `references/execution-reference.md` / `references/recovery-playbook.md`。

## File Map

| 文件 | 职责 |
|------|------|
| `SKILL.md` | 生命周期、phase 契约、握手协议、硬边界 |
| `references/execution-reference.md` | 消息样例与等待策略 |
| `references/recovery-playbook.md` | 故障恢复路径 |
| `references/debug-guide.md` | pane 可见性、agent 执行过程查看、model 参数核查、PR 编号路由诊断 |
| `runtime/agents.sh` | Agent 注册表（名称 + 类型映射） |
| `.claude/agents/pr-*.md` | Teammate 项目特定职责定义 |

脚本使用见 [附录 A] Shell 脚本速查。

## Agent 定义

| agent | agent_type | Phase | 需要读取 |
|-------|-----------|-------|---------|
| context-researcher | pr-context-researcher | 1 | (无) — 独立调研 |
| code-analyst | pr-code-analyst | 2 | `scripts/agent-report.sh context-researcher` |
| architect-reviewer | pr-architect-reviewer | 2 | `scripts/agent-report.sh context-researcher` |
| security-reviewer | pr-security-reviewer | 2 | `scripts/agent-report.sh context-researcher` |
| fix-executor | pr-fix-executor | 5 | Phase 4 结论中提取的修复指令（lead 直接写入 prompt） |

> **codex 是外部 plugin**，通过 `codex:rescue` skill 调用，不是 teammate。不在 agents.sh 中。能跑脚本读 inbox，但不能收 SendMessage。输出由 skill 调用直接返回给 lead。

真源文件：`skills/vibe-review-pr/runtime/agents.sh`

## Shell 脚本

| 脚本 | 用途 |
|------|------|
| `scripts/agent-exist.sh` | 检查 agent 存在性（definition/inbox/pane/alive） |
| `scripts/agent-event.sh` | 列出 agent 事件（标题+时间） |
| `scripts/agent-report.sh` | 提取 agent 报告全文 |

## 握手协议（简化版）

> **核心原则**：所有 agent 必须先完成握手，才能接收正式任务。握手是**有方向、有时序**的，不是双方同时各说一次"已就绪"。

### 握手流程

1. **Phase 0**: team-lead 先执行 `ToolSearch(query="select:SendMessage")` 加载 SendMessage
2. **spawn agent**: prompt 只包含握手准备，不包含具体任务
3. **team-lead 发送握手**: `SendMessage(to=<agent>, summary="握手信号", message="【lead_ready】")`
4. **agent 回复**: 等待 `【lead_ready】` → 执行 ToolSearch → 发送 `【agent_ready】已就绪`
5. **team-lead 下发任务**: 收到 `【agent_ready】` 后，立即发送正式任务（含 PR 编号、具体指令）

### 握手约束

**team-lead 必须**：
- spawn 后立即发送 `【lead_ready】`
- 收到 `【agent_ready】` 后，**立即**发送正式任务（fresh spawn 不得先进入 idle）
- 超时未收到 → 重试（最多 3 次，每次 30s）→ 标记 blocked

**team-lead 禁止**：
- spawn 后不发 `【lead_ready】`，假设 agent 会自动执行
- 未收到 `【agent_ready】` 就给该 agent 分配工作
- 对 fresh spawn 且刚回复"【agent_ready】已就绪"的 agent 发送"保持空闲 / 等待新 PR"

### 握手失败处理

- 超时 3 次 → 标记 agent 为 blocked
- 使用 `scripts/agent-exist.sh <agent>` 诊断状态
- 使用 `scripts/agent-event.sh <agent>` 查看事件
- 详细恢复路径见 `references/recovery-playbook.md`
- 常见诊断问题见 `references/debug-guide.md`

## 阻塞处理

### Team-lead 遇到错误

**调试阶段硬规则（强制）**：

Team-lead 执行过程中遇到**任何错误或异常**，必须立即 `stop()`：

- 工具调用返回错误（不管原因）
- 收到下游 agent 的【agent_blocked】标记
- 脚本执行返回非零退出码
- 任何未预期的行为

**核心原则**：调试阶段宁可过度谨慎，不可遗漏异常。

**stop() 定义**：
1. **立即停止所有操作**：不再执行任何后续工具调用
2. **停止创建**：不再创建 backlog task、不再 spawn agent、不再激活 phase
3. **说明阻塞原因**：输出明确的错误信息和当前状态
4. **等待反馈**：等待用户明确指示才能继续

**禁止**：
- ❌ 修复错误后立即继续执行
- ❌ 自行判断"理解了应该继续"
- ❌ 只发送警告而不停止
- ❌ 假设用户只是想暂停思考一下

**恢复条件**：
- ✅ 用户明确指示："继续" / "resume" / "go ahead"
- ❌ 不得自行恢复

**示例**：
```
错误: TaskCreate 参数缺失 subject
↓
stop() → 输出错误原因 → 等待用户指示
↓
用户: "继续修复"
↓
修复参数 → 重新执行
```

### 下游 Agent 遇到错误

Agent 执行过程中遇到**任何错误**，必须立即发送 `【agent_blocked】` 并停止当前任务：

- 工具调用返回错误（不管原因）
- 脚本执行返回非零退出码
- 任何未预期的行为

```
【agent_blocked】脚本 agent-report.sh 执行失败：agent xxx not defined
```

**Lead 收到 `【agent_blocked】` 后**：
1. 立即 `stop()` 停止当前 Phase 流程
2. `agent-event.sh <agent>` 查看事件上下文
3. `agent-exist.sh <agent>` 诊断状态
4. 输出阻塞原因，等待用户指示

**禁止**: lead 不得跳过 `agent_blocked` 继续推进 Phase。

---

# Phase 0: 准备

> Phase 0 是 team-lead 内联操作，不需要 Backlog Task。

## Steps

### Step 1: 环境检查

检查 tmux / Agent Teams / TeamCreate / ToolSearch / SendMessage 可用性。任一缺失 -> 立即停止。

### Step 2: Team 创建或复用

1. `TeamCreate(team_name="pr-review-team")` — 若 already exists 则跳过创建
2. 对已有 members（除 team-lead）逐个握手存活检测：
   - `SendMessage(to=member, summary="握手检测", message="【lead_ready】")`
   - 收到 `【agent_ready】` -> 存活，可复用
   - 超时 3 次（各 30s）-> 标记 dead
3. 全死 -> TeamDelete -> TeamCreate 重建
4. 部分存活 -> 复用存活者，缺失的在对应 Phase 用 `Agent(name="agent_name")` spawn

> TeamCreate 后才能 TaskCreate，否则 task 不关联 team

### Step 3: team-lead 自身 ToolSearch

`ToolSearch(query="select:SendMessage")` -> 失败则停止。

### Step 4: 创建完整 Backlog

一次性创建 Phase 1-5 全部 Backlog Task。只设置 phase_order 和 depends_on_phase，不设 handshake metadata。

Phase 1:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 1: 背景调研"
    description: "spawn context-researcher -> 等待报告 -> 标记完成"
    metadata:
      phase_order: 1
      depends_on_phase: 0
```

Phase 2:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 2: 专家评审"
    description: "spawn code-analyst / architect-reviewer / security-reviewer -> 等待报告 -> 标记完成"
    metadata:
      phase_order: 2
      depends_on_phase: 1
```

Phase 3:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 3: Codex 复查"
    description: "调用 codex:rescue skill -> 等待复查结果 -> 标记完成"
    metadata:
      phase_order: 3
      depends_on_phase: 2
```

Phase 4:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 4: 综合判断"
    description: "汇总 Phase 1-3 报告 -> 输出审查结论"
    metadata:
      phase_order: 4
      depends_on_phase: 3
```

Phase 5:

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 5: 写回 + 修复"
    description: "spawn fix-executor -> 等待报告 -> 标记完成"
    metadata:
      phase_order: 5
      depends_on_phase: 4
```

### Step 5: 激活 Phase 1

`TaskUpdate(taskId=<phase-1>, status="in_progress")`

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | 无（独立执行） |
| 输出 | Team 就绪 + 全部 Phase 1-5 backlog 已创建 + Phase 1 已激活 |
| 失败处理 | 立即停止，不创建任何 backlog |

## Hard Rules

- TeamCreate 必须先于 TaskCreate
- 复用判断 = 握手结果
- 全部 Phase 1-5 task 在 Phase 0 一次性创建
- 不使用 meta-task 模式

---

# Phase 1: 背景调研

> 产出：context-researcher 结构化 PR 背景报告

## Steps

### Step 1: spawn context-researcher

spawn 时 prompt **只包含握手准备，不包含具体任务**：

```text
你是 context-researcher。

等待 team-lead 的握手信号和正式调研任务。

不要自行开始调研工作。
```

spawn:

```yaml
- tool: Agent
  params:
    description: "PR 背景调研"
    prompt: "<上述 prompt>"
    name: "context-researcher"
    subagent_type: "pr-context-researcher"
    team_name: "pr-review-team"
```

### Step 2: 验证 spawn 成功

执行脚本确认 agent 已正确注册到 team：

```bash
skills/vibe-review-pr/scripts/agent-exist.sh context-researcher
```

**期望输出**：
```
def=ok, inbox=ok, pane=ok, alive=yes
```

**失败处理**：
- `def=missing` → agent 定义文件不存在，检查 `.claude/agents/`
- `inbox=missing` → agent 未注册到 team，检查 `name` 参数
- `alive=never` → agent 进程未启动，等待几秒后重试
- 任意字段异常 → 停止流程，诊断修复后重新 spawn

**禁止跳过验证直接握手**。

### Step 3: 握手 → 分配任务

1. 发送握手信号：`SendMessage(to="context-researcher", summary="握手信号", message="【lead_ready】")`
2. 等待 `【agent_ready】已就绪` 回复（最多 3 次，每次 30s 超时）
3. 收到 `【agent_ready】` 后，立即发送正式调研任务：

```yaml
- tool: SendMessage
  params:
    to: "context-researcher"
    summary: "PR #843 背景调研任务"
    message: |
      分析 PR #843 并产出一份结构化背景报告。

      职责：
      1. 阅读 CLAUDE.md、AGENTS.md、glossary.md、PR description、PR diff
      2. 不要修改任何文件
      3. 完成后用 SendMessage(to="team-lead", message="【agent_report】\n\n## PR #843 背景报告\n...")

      报告将保存在 team-lead.json inbox 中，后续 agent 通过 scripts/agent-report.sh context-researcher 读取。

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

**未握手成功前，不得给该 agent 分配任何工作。**

### Step 4: 等待报告

收到 context-researcher 的 idle 通知后:

1. `scripts/agent-report.sh context-researcher` 检查报告是否到达
2. 无报告 -> `scripts/agent-exist.sh context-researcher` 诊断
3. 有报告 -> 标记 Phase 1 完成

```yaml
- tool: TaskUpdate
  params:
    taskId: "<phase-1-task-id>"
    status: "completed"
```

### Step 5: 激活 Phase 2

`TaskUpdate(taskId=<phase-2>, status="in_progress")`

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | PR 编号 |
| 输出 | context-researcher 报告（team-lead.json 中可查） |
| 门禁 | `agent-report.sh context-researcher` 返回成功 |

## Hard Rules

- team-lead 不得自行收集上下文（gh pr view、git diff 等）
- 不得在未收到报告前激活 Phase 2

---

# Phase 2: 专家评审

> Phase 2 的三个 agent 可并行 spawn，各自独立审查

## Steps

### Step 1: 并行 spawn 三个 agent

spawn 时 prompt **只包含握手准备，不包含具体任务**：

```text
你是 code-analyst。等待 team-lead 的握手信号和正式审查任务。不要自行开始工作。
```

```text
你是 architect-reviewer。等待 team-lead 的握手信号和正式审查任务。不要自行开始工作。
```

```text
你是 security-reviewer。等待 team-lead 的握手信号和正式审查任务。不要自行开始工作。
```

spawn:

```yaml
- tool: Agent
  params:
    description: "代码质量分析"
    name: "code-analyst"
    subagent_type: "pr-code-analyst"
    team_name: "pr-review-team"
    prompt: "<code-analyst 握手 prompt>"
- tool: Agent
  params:
    description: "架构审查"
    name: "architect-reviewer"
    subagent_type: "pr-architect-reviewer"
    team_name: "pr-review-team"
    prompt: "<architect-reviewer 握手 prompt>"
- tool: Agent
  params:
    description: "安全审查"
    name: "security-reviewer"
    subagent_type: "pr-security-reviewer"
    team_name: "pr-review-team"
    prompt: "<security-reviewer 握手 prompt>"
```

### Step 2: 验证 spawn 成功

执行脚本确认所有 agent 已正确注册到 team：

```bash
skills/vibe-review-pr/scripts/agent-exist.sh
```

**期望输出**（检查以下三行）：
```
code-analyst          pr-code-analyst              ok         ok         ok         yes
architect-reviewer    pr-architect-reviewer        ok         ok         ok         yes
security-reviewer     pr-security-reviewer         ok         ok         ok         yes
```

**失败处理**：
- 任意 agent 的 `def/inbox/pane/alive` 字段异常 → 停止流程
- `def=missing` → agent 定义文件不存在，检查 `.claude/agents/`
- `inbox=missing` → agent 未注册到 team，检查 `name` 参数
- `alive=never` → agent 进程未启动，等待几秒后重试

**禁止跳过验证直接握手**。

### Step 3: 并行握手 → 分配任务

对每个 agent 执行握手（可并行）：

1. 发送握手信号：`SendMessage(to=<agent>, summary="握手信号", message="【lead_ready】")`
2. 等待 `【agent_ready】已就绪` 回复（最多 3 次，每次 30s 超时）
3. 收到 `【agent_ready】` 后，立即发送正式审查任务：

code-analyst 任务：

```yaml
- tool: SendMessage
  params:
    to: "code-analyst"
    summary: "PR #843 代码质量分析任务"
    message: |
      分析 PR #843 的代码质量和技术债。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      完成分析后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 代码质量分析报告\n...")

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

architect-reviewer 任务：

```yaml
- tool: SendMessage
  params:
    to: "architect-reviewer"
    summary: "PR #843 架构审查任务"
    message: |
      审查 PR #843 的架构影响。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      完成审查后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 架构审查报告\n...")

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

security-reviewer 任务：

```yaml
- tool: SendMessage
  params:
    to: "security-reviewer"
    summary: "PR #843 安全审查任务"
    message: |
      审查 PR #843 的安全问题。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      完成审查后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 安全审查报告\n...")

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

**未握手成功前，不得给该 agent 分配任何工作。**

### Step 4: 等待全部报告

对每个 agent:
1. 收到 idle 通知 -> `scripts/agent-report.sh <agent>` 检查报告
2. 全部就绪 -> 标记 Phase 2 完成

```yaml
- tool: TaskUpdate
  params:
    taskId: "<phase-2-task-id>"
    status: "completed"
```

### Step 4: 激活 Phase 3

`TaskUpdate(taskId=<phase-3>, status="in_progress")`

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 1 报告 |
| 输出 | code-analyst / architect-reviewer / security-reviewer 报告 |
| 门禁 | 三个 agent 的 `agent-report.sh` 均返回成功 |

---

# Phase 3: Codex 复查

## Steps

### Step 1: 调用 codex:rescue

codex 自己通过脚本读取前序报告（和 Phase 2 agent 一样），输出由 skill 调用直接返回给 lead：

```yaml
- tool: Skill
  params:
    skill: codex:rescue
    args: |
      复查 PR #<number> 的全部审查报告，给出第三方独立评估。

      读取 Phase 1 背景报告：
        skills/vibe-review-pr/scripts/agent-report.sh context-researcher

      读取 Phase 2 专家评审：
        skills/vibe-review-pr/scripts/agent-report.sh code-analyst
        skills/vibe-review-pr/scripts/agent-report.sh architect-reviewer
        skills/vibe-review-pr/scripts/agent-report.sh security-reviewer

      重点关注：是否有遗漏、结论是否一致、建议是否可行。
      给出综合评估意见。
```

> codex 是外部 plugin，不是 teammate。能跑脚本读 inbox，但不能收 SendMessage。输出由 skill 调用直接返回给 lead。

### Step 2: 收到 codex 复查结果 -> 激活 Phase 4

标记 Phase 3 完成，激活 Phase 4。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 1 + Phase 2 报告 |
| 输出 | codex 复查报告 |

---

# Phase 4: 综合判断

> team-lead 内联操作，汇总所有报告做最终决策

## Steps

### Step 1: 提取所有报告

```bash
for agent in context-researcher code-analyst architect-reviewer security-reviewer; do
  skills/vibe-review-pr/scripts/agent-report.sh "$agent"
done
```

> codex 复查结果已在 Phase 3 由 skill 调用直接返回，不在 inbox 中。

### Step 2: 输出审查结论

基于所有报告 + 执行模式（auto-fix / ask-each / comment-only），决定：

- 批准: 无阻塞问题
- 修复: 有阻塞问题 + auto-fix -> 激活 Phase 5
- 评论: 有问题但不可自动修复 -> 输出评论，不激活 Phase 5

### Step 3: 按决策行动

auto-fix 且有阻塞问题 — 先提取可修复项，再激活 Phase 5:

```yaml
# 从 Phase 1/2/3 报告中提取具体修复点，整理为修复指令
- tool: TaskUpdate
  params:
    taskId: "<phase-4-task-id>"
    status: "completed"

- tool: TaskUpdate
  params:
    taskId: "<phase-5-task-id>"
    status: "in_progress"
```

**修复指令格式**（Phase 4 产出，写入 Phase 5 prompt）：

```text
## 修复指令

基于 Phase 1-3 审查结论，以下问题可在当前 PR 范围内修复：

1. [具体问题] — 来源: [agent 名] — 修复方式: [具体操作]
2. ...

不可自动修复的问题（已转 follow-up issue / PR comment）：
- [问题] — 原因: [为何不可自动修复]
```

否则标记 Phase 5 为 skipped。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 1/2/3 全部报告 |
| 输出 | 审查结论 + 修复行动 |

---

# Phase 5: 写回 + 修复

> 仅 auto-fix 模式且存在阻塞问题时进入

## Steps

### Step 1: spawn fix-executor

spawn 时 prompt **只包含握手准备，不包含具体任务**：

```text
你是 fix-executor。等待 team-lead 的握手信号和正式修复任务。不要自行开始工作。
```

spawn:

```yaml
- tool: Agent
  params:
    description: "修复执行"
    name: "fix-executor"
    subagent_type: "pr-fix-executor"
    team_name: "pr-review-team"
    prompt: "<上述握手 prompt>"
```

### Step 2: 验证 spawn 成功

执行脚本确认 agent 已正确注册到 team：

```bash
skills/vibe-review-pr/scripts/agent-exist.sh fix-executor
```

**期望输出**：
```
def=ok, inbox=ok, pane=ok, alive=yes
```

**失败处理**：
- 验证失败 → 停止流程，诊断修复后重新 spawn

**禁止跳过验证直接握手**。

### Step 3: 握手 → 分配任务

1. 发送握手信号：`SendMessage(to="fix-executor", summary="握手信号", message="【lead_ready】")`
2. 等待 `【agent_ready】已就绪` 回复（最多 3 次，每次 30s 超时）
3. 收到 `【agent_ready】` 后，立即发送正式修复任务：

```yaml
- tool: SendMessage
  params:
    to: "fix-executor"
    summary: "PR #843 修复任务"
    message: |
      根据 team-lead 提供的修复指令修复 PR #843。

      修复指令：
      <Phase 4 产出的具体修复点列表，逐条包含问题描述、来源 agent、修复方式>

      职责：
      1. 按修复指令逐条执行修复
      2. 不要自行扩大修复范围
      3. 完成后用 SendMessage(to="team-lead", message="【agent_report】\n\n## 修复报告\n...")

      **脚本错误处理**：如脚本执行失败，立即发送【agent_blocked】+ 错误详情，停止执行。
```

**未握手成功前，不得给该 agent 分配任何工作。**

### Step 4: 等待修复报告

### Step 5: 修复完成

标记 Phase 5 完成 -> 清理。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 4 结论中的修复指令（lead 直接写入 prompt） |
| 输出 | 修复提交 + 修复报告 |

---

# 清理

审查流程完成后:

1. `TaskUpdate` 标记所有未完成 task 为 skipped
2. `TeamDelete(team_name="pr-review-team")` 清理 team

---

# [附录 A] Shell 脚本速查

```bash
# Agent 存在性
scripts/agent-exist.sh                 # 全部状态
scripts/agent-exist.sh code-analyst    # 单个状态

# Agent 事件
scripts/agent-event.sh                  # 全部最新事件
scripts/agent-event.sh code-analyst     # 单个事件列表

# 报告提取
scripts/agent-report.sh                 # 全部报告状态
scripts/agent-report.sh code-analyst    # 完整报告正文
```

# [附录 B] idle 处理

收到 idle 通知后:

1. `scripts/agent-event.sh <agent>` 查看该 agent 的最新事件
2. 若有 `agent_report` -> `scripts/agent-report.sh <agent>` 提取报告
3. 若仅有 `agent_ready` -> 检查报告是否未发送，是则 SendMessage 提醒
4. 若 `event_status=missing` -> `scripts/agent-exist.sh <agent>` 诊断

详细消息样例见 `references/execution-reference.md`。

# [附录 C] 恢复

Agent 失联:

1. `scripts/agent-exist.sh <agent>` 诊断
2. `SendMessage(to=<agent>, summary="握手测试", message="【lead_ready】")` 测试握手
3. 3 次超时 -> 重新 `Agent(name=<agent>, subagent_type=pr-<agent>, team_name="pr-review-team")` spawn

详细恢复流程见 `references/recovery-playbook.md`。
常见诊断问题见 `references/debug-guide.md`。
