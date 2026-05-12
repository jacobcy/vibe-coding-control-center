---
name: vibe-review-pr
description: |
  Use only in Claude Code environments with Agent Teams enabled when the user wants
  a comprehensive PR review using the multi-agent team workflow.
---

# Vibe PR Review Skill

## 版本历史

- **v2026-05-12**: 修复 Phase 0 Backlog 约束、Phase 2 agent idle 处理、Phase 5 执行模式说明
- **v2026-04-27**: 基于 PR #842 稳定版本重组（执行顺序组织）

---

## 改进摘要

**本次改进解决的核心问题**：

1. **Phase 0 Backlog 约束缺失** → 现在强制创建所有 Phase 1-5 的 Backlog task，防止流程跳过
2. **agent idle 处理缺失** → 现在收到 idle 通知后自动检查并重新握手，无需用户干预
3. **Phase 5 执行模式说明缺失** → 现在明确说明 ask-each / auto-decide / auto-fix / comment-only 四种模式的区别和适用场景

**关键设计决策**：

- **混合 Backlog 创建策略**：Phase 0 创建骨架 task，各 Phase 结束时补充详细 metadata
- **全自动化 agent idle 处理**：无需用户干预，自动检测、诊断、重新握手
- **渐进式执行模式**：从最安全的 ask-each 到高效的 auto-fix，用户可根据风险偏好选择

---

`vibe-review-pr` 是 **Claude Code Agent Teams 专用入口**。Phase 0 是前置条件（内联操作），Phase 1-5 各是一个 Backlog Task。每个 Phase 按 Steps / Contracts / Hard Rules 组织。附录保留握手协议伪代码、质量标准、契约速查表。

非 Claude team 环境（含 Codex）一律分流：docs-only PR → `vibe-review-docs`；其他 → `vibe-review-code`。

## When to Use

仅在以下条件**全部**满足时使用：

- host 为 Claude Code
- `TMUX` 已设置
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- 工具面提供 TeamCreate / Agent / SendMessage / teammate-message

任一缺失 → 立即停止，按文件范围回退到单 agent 审查。

> **tmux 机制说明**：`TMUX` 已设置是前置条件，因为 `Agent(team_name=...)` 会由 Claude Code 运行时**自动**在当前 tmux session 中创建新 pane 来运行 teammate。team-lead **不需要**手动执行 tmux 命令管理 pane——pane 的创建、复用、销毁全部由运行时处理。team-lead 只通过 `SendMessage` 和接收 teammate-message 与 teammates 通信。

## Must Read

需要消息样例或恢复路径时读 `references/execution-reference.md` / `references/recovery-playbook.md`。

---

# Phase 0: 准备与握手

> Phase 0 不是 Backlog Task。所有 Step 是 team-lead 内联操作，无需 TaskCreate 追踪。
> Phase 0 失败 → 立即停止，不创建任何 Backlog task。

## Steps

### Step 1: 环境检查

只检查 tmux / Agent Teams / TeamCreate / TaskCreate / ToolSearch / SendMessage 可用性。
**禁止在这一步执行 `gh pr view` / `gh pr diff` / `git diff`**。

任一缺失 → 立即停止。

### Step 2: 选择执行模式

`auto-fix / comment-only / auto-decide / ask-each`。
用户指定 → 使用用户指定；未指定 → `ask-each`。

### Step 3: 加载 template

读 `.claude/team-templates/pr-review-team.yaml`，确认配置完整。

### Step 4: 创建或复用 Team

1. 检查 Team 是否已存在（TeamCreate 若报 already exists）
2. 不存在 → `TeamCreate(team_name="pr-review-team")`
3. 已存在 → 对已有 members（除 team-lead）逐个握手检测存活：
   - `SendMessage(to=member, lead_ready)`
   - 收到 `agent_ready` → 存活，可复用
   - 超时 3 次（各 30s）→ 标记 dead
4. 全死 → `TeamDelete` → `TeamCreate` 重建
5. 部分存活 → 复用存活者，缺失的 agent type 在对应 Phase spawn

> **复用判断 = 握手结果**。不检查 `isActive`（不可靠，Issue #29271），不读 `config.json` 推断状态（Issue #44701）。
>
> **踩坑记录**：TeamCreate 之前创建的 TaskCreate 不会关联到 team 的 task list。必须先 TeamCreate 再 TaskCreate。

Team 名称固定为 `pr-review-team`（**不要**用 `pr-review-713` 这种 PR-编号命名）。

### Step 5: team-lead 自身 ToolSearch

执行 `ToolSearch(query="select:SendMessage")`，确认 lead 自己可发送消息。

> **⚠️ 最高优先级**：`SendMessage` 是 deferred tool，声明在 agent 定义中不等于 schema 已加载。调用前必须先 `ToolSearch` 加载，否则报 `InputValidationError`。即使会话开始时 hook 自动触发了其他 ToolSearch，team-lead 也必须重新执行此步骤作为 Phase 0 的正式握手。

失败 → 立即停止，禁止 spawn 任何 agent。

**诊断**（如 agent 未发送报告）：
```bash
tmux capture-pane -t <pane-id> -p -S -1000 | grep -E "ToolSearch|SendMessage|InputValidationError"
```

### Step 6: 创建 Phase 1-5 Backlog 骨架 Task（强制）

一次性批量创建所有后续 Phase 的 Backlog task，作为执行约束检查点。

**执行流程**：使用 `references/backlog-task-templates.yaml` 中的 Phase 1-5 模板批量创建骨架 task。

**关键约束**：
- Phase 0 必须创建所有后续 Phase 的 Backlog task（硬规则）
- 每个 Backlog task 的 `metadata` 必须包含强制字段（见 §Hard Rules）
- Backlog task 的 `blockedBy` 设置依赖关系，确保 Phase 串行执行
- Backlog task 的 `owner` 默认为空，Phase 开始时设置为 "team-lead"

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | 无（独立执行） |
| 输出 | Team 就绪 + team-lead ToolSearch 完成 + **Phase 1-5 Backlog task 已创建** |
| 门禁 | Team 已创建、team-lead 已完成 ToolSearch、**所有 Backlog task 已创建**、复用场景下需复用的 agent 已握手存活 |
| 失败处理 | 立即停止，不创建任何 Backlog task |

## Hard Rules

- **Phase 0 必须先于任何 subagent 执行**
- **复用判断 = 握手结果**（alive=复用，dead=清理后 TeamCreate），禁止跳过握手直接 TeamCreate
- **切换 PR 用 SendMessage**（握手成功的复用 agent），禁止盲目重新 spawn
- **清理与恢复规则**：见 `references/recovery-playbook.md`
- **Phase 0 必须创建 Phase 1-5 的骨架 Backlog task**（硬规则，不可跳过）
- **Backlog 约束详细说明**：见 `references/execution-reference.md`

---

# Phase 1: 背景调研

> 目标：产出 `phase_1_output` — 结构化 PR 背景报告（概述、改动范围、关联 issue、风险评估）。
> 依赖：Phase 0 完成。

## Steps

### Step 1: 创建 Phase 1 Backlog Task

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 1: 背景调研"
    description: |
      【输入】PR 编号
      【输出】phase_1_output（结构化背景报告）
      【步骤】
      1. spawn context-researcher → 握手 → 分配调研任务
      2. 等待报告 → 保存 phase_1_output 到 Task metadata
      【门禁】
      - handshake_status.context-researcher == "ready"
      - phase_1_output 非空
      - team-lead 不得自行执行 gh pr view/diff
- tool: TaskUpdate
  params:
    taskId: "<phase-1-task-id>"
    status: "in_progress"
    owner: "team-lead"
    metadata:
      handshake_protocol: "ordered_v1"
      handshake_required: true
      lead_handshake_status: "ready"
      lead_ready_sent: false
      task_activation_allowed: false
      expected_next_action: "send_context_lead_ready"
      activation_state: "awaiting_lead_ready"
      handshake_agents: ["context-researcher"]
      handshake_status:
        context-researcher: "pending"
      on_handshake_failure: "skip_phase_and_fallback_to_single_agent"
```

### Step 2: spawn → 握手 → 分配任务

1. spawn context-researcher，prompt 仅含握手指令
2. 按 `handshake_agent("context-researcher")` 执行握手（最多 3 次唤醒，30s 超时，见 §握手与唤醒协议规范）
3. 收到 `【agent_ready】已就绪` 后，立即 SendMessage 下发正式调研任务（含 PR 编号）
4. **未握手成功前，不得给该 agent 分配任何工作**

backlog gate：发送 lead_ready 后写入 `lead_ready_sent=true, expected_next_action=verify_context_handshake, activation_state=awaiting_agent_ready`
backlog gate：收到 agent_ready 后写入 `task_activation_allowed=true, expected_next_action=send_context_task, activation_state=awaiting_task_dispatch`

### Step 3: 等待报告 → 保存 output

收到 context-researcher 报告后：

```yaml
- tool: TaskUpdate
  params:
    taskId: "<phase-1-task-id>"
    status: "completed"
    metadata:
      phase_1_output: |
        ## PR #<number> 背景报告
        [完整的 context-researcher 报告内容，包括所有章节]
```

### Step 4: PR 分类 + 补建后续 Backlog

基于 `phase_1_output` 判断 PR 类型。

> **常见错误**：看到"文档改动"就归类 `simple`。这是错的。

`simple` 必须**同时**满足全部 4 项：
- ✅ **单文件**改动
- ✅ 改动 **< 30 行**
- ✅ 仅文档 / 注释 / 字符串 / 重命名
- ✅ 无 `security/*` 标签

任一不满足 → 不是 simple。

| 类型 | 条件 |
|------|------|
| `simple` | 4 项全满足 |
| `security` | 涉及认证/授权/数据/凭据/输入验证 |
| `refactor` | ≥ 5 文件或大规模重构 |
| `standard` | 不属于上述 |

**反例**（issue #742 真实踩坑）：PR #713 改 6 文件、+11/-10、含 `manager.py` 代码改动 + 文档 → 错误归类 `simple` → 实际应按 `standard` 处理。**只要包含代码改动或多文件，就不是 simple。**

按 PR 类型补建后续 Backlog Task：

| 类型 | 需创建的 Task | 说明 |
|------|-------------|------|
| `simple` | Phase 3, 4, 5 | 跳过 Phase 2（不 spawn agent），Phase 1 报告直接交给 Phase 3 |
| `security` | Phase 2, 3, 4, 5 | Phase 2 必须含 `security-reviewer` |
| `refactor` | Phase 2, 3, 4, 5 | Phase 2 spawn code-analyst + architect-reviewer |
| `standard` | Phase 2, 3, 4, 5 | Phase 2 spawn code-analyst + architect-reviewer |

**Phase 1 是入口统一创建的**（Phase 0 完成后立即 TaskCreate），不在补建之列。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | PR 编号、Phase 0 完成 |
| 输出 | `phase_1_output`（结构化背景报告） |
| 门禁 | `handshake_status.context-researcher == "ready"`、`phase_1_output` 非空 |
| 失败处理 | context-researcher 失联 → 标记 blocked，回退单 agent review |
| 下游依赖 | Phase 2 / Phase 3 需要 `phase_1_output` |

## Hard Rules

- **team-lead 不得自行收集上下文**（gh pr view、git diff、git log 等），这是 context-researcher 的工作
- **显式 PR 编号入口禁止 lead 预调查**：`/vibe-review-pr 821` 这类入口下，team-lead 不得为"确认状态/标题/标签/变更范围"执行 `gh pr view` / `gh pr diff`；这些事实必须由 Phase 1 背景报告提供
- **禁止 team-lead 执行其他 shell 命令**：gh pr diff、git show、git commit、git push 等调研或修改操作
- team-lead 职责：spawn agent、管理 task 生命周期；唯一的 context 传递是从 Phase 1 报告通过 SendMessage **转发**到 Phase 2 agents
- `保持空闲 / 等待新 PR` 只适用于**上一轮任务已完成的复用 teammate**；不适用于本轮 fresh spawn 且刚完成握手的 agent

---

# Phase 2: 专家评审

> 目标：code-analyst / architect-reviewer / security-reviewer 的独立审查报告。
> 依赖：Phase 1 完成（`handshake_status.context-researcher == "ready"` + `phase_1_output` 非空）。
> 启动前：`TaskGet Phase 1` → 提取 `phase_1_output`；未 ready → 停止，回退单 agent。

## Steps

### Step 1: 创建 Phase 2 Backlog Task

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 2: 专家评审"
    description: |
      【输入】phase_1_output（从 Phase 1 task metadata 获取）
      【输出】code-analyst / architect-reviewer / security-reviewer 的审查报告
      【步骤】
      1. TaskGet Phase 1 → 提取 phase_1_output
      2. 确认 context-researcher handshake_status == "ready"（未 ready → 停止）
      3. 依次对 code-analyst → architect-reviewer → security-reviewer：
         a. spawn agent，prompt 仅含握手指令，run_in_background=true
         b. 按 handshake_agent(agent_name) 执行握手（最多 3 次唤醒，30s 超时，见 §握手与唤醒协议规范）
         c. 收到 agent_ready 后，SendMessage 下发正式任务（含 phase_1_output）
         d. 派发后不得 idle，立即继续下一个 agent
      4. 等待所有已握手 agent 的 task-notification
      5. 收集全部报告
      【门禁】
      - 至少 1 个 agent handshake_status == "ready" 且返回了有效报告
      - 未握手 agent 的报告标记为无效
- tool: TaskUpdate
  params:
    taskId: "<phase-2-task-id>"
    addBlockedBy: ["<phase-1-task-id>"]
    metadata:
      handshake_protocol: "ordered_v1"
      requires_phase_1_output: true
      handshake_required: true
      task_activation_allowed: false
      expected_next_action: "send_code_analyst_lead_ready"
      activation_state: "awaiting_first_lead_ready"
      handshake_agents: ["code-analyst", "architect-reviewer", "security-reviewer"]
      lead_ready_sent:
        code-analyst: false
        architect-reviewer: false
        security-reviewer: false
      handshake_status:
        code-analyst: "pending"
        architect-reviewer: "pending"
        security-reviewer: "pending"
      on_handshake_failure: "skip_unready_agent_and_mark_review_incomplete"
      wakeup_policy:
        max_attempts: 3
        timeout: 30s
```

### Step 2: spawn → 逐个握手 → 分配任务

多 agent **同一响应**内并行 spawn，但握手逐个进行（非批量）：

1. 每 spawn 一个立即发送 `【lead_ready】`
2. 收到该 agent `【agent_ready】已就绪` → 通过第二条 SendMessage 发送 `phase_1_output` 和正式审查任务
3. 派发完一个后 team-lead 不得进入 idle；必须继续处理下一个 agent，直到全部完成
4. 超时未收到 → 按 `handshake_agent()` 重试/blocked 逻辑处理

**约束**：
- fresh spawn 先只做握手，收到"已就绪"后才分配工作
- 握手阶段不得内嵌 `phase_1_output` 或正式审查任务
- 复用 teammate 或补发上下文时也用 SendMessage

### Step 3: 收集报告

等待所有已握手 agent 的 task-notification（status=completed），收集全部审查报告。

### Step 4: agent idle 自动检测与重新握手（自动化流程）

收到任何 Phase 2 agent 的 idle 通知后，team-lead 立即执行自动化处理（无需用户干预）。

**自动化流程**：
1. 检查 inbox → 是否收到 task-notification？是则提取报告，否则继续
2. 检查 pane（tmux capture-pane）→ 诊断 agent 状态（InputValidationError/执行中/idle）
3. 如需重新握手 → SendMessage(lead_ready)，等待 agent_ready，最多 3 次
4. 循环检测直到收到 notification 或标记 blocked

**约束**：
- 全自动化，无需用户干预
- 重新握手间隔 >= 10s，最多 3 次
- 标记 blocked 后仍继续等待其他 agent
- 通过 TaskUpdate 同步状态（handshake_status/blocked_agents/incomplete_reason）

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 1 的 `phase_1_output` |
| 输出 | code-analyst / architect-reviewer / security-reviewer 的审查报告 |
| 门禁 | 至少 1 个 agent 握手成功 + 返回有效报告；未握手 agent 报告标记无效 |
| 失败处理 | 握手失败 → 标记 blocked，跳过该 agent，继续下一个 |
| 下游依赖 | Phase 3 需要全部 Phase 2 报告 |

## Hard Rules

- Phase 1 / Phase 2 严格**串行**，禁止并行启动
- fresh spawn 的初始 prompt 只允许握手
- fresh spawn 的 agent 一旦回复"【agent_ready】已就绪"，team-lead 的**下一条有效动作**必须是正式任务激活（`send_code_analyst_task` 等）；不得插入"保持空闲 / 等待新 PR"之类待命消息
- backlog metadata 必须同时记录 `expected_next_action` 与 `task_activation_allowed`；若元数据仍处于 `awaiting_lead_ready` / `awaiting_agent_ready`，则任何正式任务下发都视为协议违规
- 切换到下一 PR、复用 teammate 或补发额外上下文时，才使用 SendMessage
- 仅 `refactor / security / standard` 走双阶段；`simple` 只做 Phase 1

---

# Phase 3: Codex 复查

> 目标：校验 Phase 2 报告质量，决定是否启用 codex 复查。
> 依赖：Phase 2 完成（全部 agent 报告已送达或已标记 blocked）。
> 此阶段不涉及 agent 握手。

## Steps

### Step 1: 创建 Phase 3 Backlog Task

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 3: Codex 复查"
    description: |
      【输入】Phase 2 全部审查报告
      【输出】codex 验证报告（或 skip 标记及原因）
      【步骤】
      1. 收集 Phase 2 全部报告
      2. 校验各报告基础数据（文件数/行数/涉及模块）是否与 PR 实际 diff 一致
      3. 失真报告标注"报告作废"，不作为 codex 输入
      4. 判断触发条件（安全PR / diff>500行 / 报告冲突 / 报告缺失）
      5. 满足且报告质量合格 → 调用 codex:rescue（仅传结构化报告，禁止传 diff/代码片段）
      6. 不满足或全部报告不合格 → 记录 skip 原因，直接进入 Phase 4
      【门禁】
      - 已做出"启用 codex"或"跳过 codex"的明确决定（不可跳过此判断）
      - 如启用 codex：codex 报告已收到并保存
- tool: TaskUpdate
  params:
    taskId: "<phase-3-task-id>"
    addBlockedBy: ["<phase-2-task-id>"]
    metadata:
      requires_phase_2_reports: true
```

### Step 2: 校验报告数据

按 Step 1 yaml 模板步骤 2-3 执行：校验基础数据 → 失真报告标注作废。

### Step 3: 决定是否启用 codex

**触发条件**（满足任一项）：
- 安全 PR（涉及认证/授权/路径解析/输入验证）
- 大型 PR（diff > 500 行）
- 报告冲突（Phase 2 多份报告对同一问题结论矛盾）
- 报告缺失（Phase 2 应有报告未送达）

**调用约束**：
- **绝对禁止传 diff 给 codex**：codex 的输入只能是 Phase 2 的结构化报告（文件列表、行数、安全声明、红队测试结果等），不得包含 git diff、代码片段、代码变更内容
- 不得在 Phase 2 完成前启动（严格串行）
- 不得用幻觉报告喂 codex（失效数据无法被 codex 验证）
- 任一报告存在严重幻觉 → 跳过 codex 直接进入 Phase 4

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 2 全部审查报告 |
| 输出 | codex 验证报告（或 skip 标记及原因） |
| 门禁 | 已做出"启用 codex"或"跳过 codex"的明确决定 |
| 失败处理 | 全部报告不合格 → 记录 skip 原因，直接进入 Phase 4 |
| 下游依赖 | Phase 4 需要 Phase 3 决策结果 |

## Hard Rules

- **绝对禁止传 diff 给 codex**：只传 Phase 2 结构化报告（文件列表、行数、安全声明等）
- 任一报告存在严重幻觉 → 跳过 codex，直接进入 Phase 4
- 不得在 Phase 2 完成前启动 codex（严格串行）

---

# Phase 4: 综合判断

> 目标：收集全部可用报告，仲裁冲突，出具最终决策。
> 依赖：Phase 3 完成。

## Steps

### Step 1: 创建 Phase 4 Backlog Task

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 4: 综合判断"
    description: |
      【输入】Phase 2 可用报告（剔除作废） + Phase 3 codex 报告（如有）
      【输出】最终决策（APPROVE / NEEDS_CHANGES / REJECT）+ 结构化审查报告
      【步骤】
      1. 收集 Phase 2 可用报告，剔除 Phase 3 标记为作废的
      2. 收集 Phase 3 codex 报告（如有）
      3. 仲裁不同报告间的冲突，记录仲裁理由
      4. 生成最终决策
      5. 按 Review Quality Standards 自审查报告（禁虚假评分、禁无关指标、强制规则引用，见 §Review Quality Standards）
      6. 缺失 agent 报告标注"审查不完整"，不脑补结论
      【门禁】
      - 最终决策已做出
      - 审查报告已通过 Review Quality Standards 全部 8 条自查
      - 未使用已作废的报告做结论
- tool: TaskUpdate
  params:
    taskId: "<phase-4-task-id>"
    addBlockedBy: ["<phase-3-task-id>"]
    metadata:
      requires_phase_2_and_3_output: true
```

### Step 2: 收集可用报告 + 冲突仲裁

按 Step 1 yaml 模板步骤 1-3 执行：收集 Phase 2 可用报告 + Phase 3 codex 报告 → 仲裁冲突。

### Step 3: 出具最终决策 + 质量自查

按 Step 1 yaml 模板步骤 4-6 执行：生成最终决策 → 质量自查 → 标注缺失报告。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 2 可用报告（剔除作废） + Phase 3 codex 报告（如有） |
| 输出 | 最终决策（APPROVE / NEEDS_CHANGES / REJECT）+ 结构化审查报告 |
| 门禁 | 最终决策已做出、审查报告已通过 §Review Quality Standards 全部 8 条自查、未使用已作废报告 |
| 下游依赖 | Phase 5 需要最终决策和审查报告 |

## Hard Rules

- 禁止使用已作废报告做结论
- 替缺失 agent 脑补结论 → 标记"审查不完整"
- teammate-message PR 编号不匹配时必须如实标注
- 拒绝"已合并 / CI 通过 / 无漏洞"这类无证据声明
- 必须通过 §Review Quality Standards 全部 8 条自查（写回前）

---

# Phase 5: 写回 + 修复

> 目标：PR comment + follow-up issues + 可选修复 commit。
> 依赖：Phase 4 完成。

**执行模式**：Phase 5 根据 `execution_mode` 参数选择执行路径。详细说明见 `references/execution-modes.md`：
- **ask-each**（默认）：用户决策，最安全
- **auto-decide**：team-lead 根据复杂度自动决策
- **auto-fix**：自动修复（高风险，有约束）
- **comment-only**：只写 comment（最安全）

**执行模式选择建议**：简单 PR（< 50 行，无安全相关）→ auto-decide；标准 PR（50-200 行）→ ask-each；安全 PR → ask-each；大型 PR → comment-only。

## Steps

### Step 1: 创建 Phase 5 Backlog Task

```yaml
- tool: TaskCreate
  params:
    subject: "Phase 5: 写回 + 修复"
    description: |
      【输入】Phase 4 最终决策和审查报告
      【输出】PR comment + follow-up issues + 可选修复 commit
      【步骤】
      1. 判断执行模式（auto-fix / comment-only / auto-decide / ask-each）
      2. 写 PR comment（含：决策/已解决技术债/遗留问题/规则引用/follow-up 链接）
      3. 如 auto-fix 模式：
         a. spawn fix-executor，prompt 仅含握手指令
         b. 按 handshake_agent("fix-executor") 执行握手（最多 3 次唤醒，30s 超时，见 §握手与唤醒协议规范）
         c. 收到 agent_ready 后，SendMessage 下发修复任务（含审查报告）
         d. 等待修复完成并验证
      4. 范围外问题创建 follow-up issues（先搜索去重，禁止重复创建）
      【门禁】
      - PR comment 已通过 gh pr comment 发布
      - 范围外问题已创建 follow-up issue 或确认无需创建
      - 禁止把当前 PR 阻塞问题转为 follow-up
- tool: TaskUpdate
  params:
    taskId: "<phase-5-task-id>"
    addBlockedBy: ["<phase-4-task-id>"]
```

### Step 2: 写 PR comment

PR comment 格式要求见 §Review Quality Standards 第 8 条。

### Step 3: spawn fix-executor + 修复（仅 auto-fix）

按 Step 1 yaml 模板步骤 3 执行：spawn → 握手 → 分配修复任务 → 等待验证。

### Step 4: 创建 follow-up issues

范围外问题创建 follow-up issues（先搜索去重，禁止重复创建）。

## 会话收尾

1. 询问继续：continue → 回 Phase 0 Step 4（复用 Team）；end → 下一步
2. 向所有 teammates 发 `shutdown_request`
3. 等待 idle 通知后 `TeamDelete()`
4. 若 TeamDelete 返回 "no team found" → 手动清理：`rm -rf ~/.claude/teams/pr-review-team ~/.claude/tasks/pr-review-team`

**会话中途**不得发送 shutdown 指令（Phase 5 完成前的 idle 通知是正常现象，不是关闭信号）。

## Contracts

| 项目 | 内容 |
|------|------|
| 输入 | Phase 4 最终决策和审查报告 |
| 输出 | PR comment + follow-up issues + 可选修复 commit |
| 门禁 | PR comment 已发布、follow-up issue 已创建或确认无需创建、禁止把阻塞问题转 follow-up |
| 写回后 | 询问继续 → 复用 Team 审下一个 PR → end → TeamDelete |

## Hard Rules

- 模式决定路径；仅 `auto-fix` 可 spawn `pr-fix-executor`
- 范围外问题转 follow-up issue；禁止把范围外技术债塞进当前 PR comment
- 禁止把当前 PR 阻塞问题转为 follow-up
- 仅限 `gh pr comment` 和 `gh issue create`（禁止其他 gh/git 命令）
- 会话中途不得发送 shutdown 指令
- comment 格式必须符合 §Review Quality Standards 第 8 条

---

## 跨 PR 管理

`TaskList` 可随时用于确认进度，避免重复创建。

**每个 PR 开始审查前**：
1. 检查 `TaskList`，如有上一轮 PR 的未完成 task，标记为 `completed`（附带说明：上一 PR 遗留）
2. 如有上一轮 PR 已完成但未标记的 task，标记为 `completed`
3. 为当前 PR 创建 Phase 1 task（Phase 0 是前置条件，不创建 task）

**每个 Phase 执行时**：
- 开始 Phase → `TaskUpdate(status="in_progress")`
- 完成 Phase → `TaskUpdate(status="completed")`

**会话结束时**：所有 task 由 TeamDelete 自动清理，无需手动删除。

---

## Session Lifecycle（强制理解，issue #742 反复踩坑）

> **核心误解**：把 Team 当成"PR-级"对象。事实上 Team 是"会话级"对象。

```
环境检查 → 检查已有 Team → 握手确认存活 → PR #A → continue → PR #B → ... → end → TeamDelete
```

要点：
- Team 是会话级对象，不是 PR 级。一个会话一个 Team，多个 PR 复用
- 复用判断见 Phase 0 Step 4（握手 = 存活检测，不检查 isActive/config.json）
- TeamDelete 默认仅在用户 end：用户没说结束就保留状态

---

# 附录

## Phase Contracts 速查表

| Phase | 强制要求 | 易错点 |
|-------|---------|-------|
| 0 准备与握手 | 环境检查 → TeamCreate → team-lead ToolSearch（内联操作，不是 Backlog Task）；已有 Team 则握手确认 agent 存活（alive=复用，dead=清理重建） | 跳过 Phase 0 直接开始 Phase 1；不复用也不清理，直接 TeamCreate 重复创建；team-lead 自身未 ToolSearch |
| 1 背景调研 | 必须**先于** Phase 2 完成；产出 `phase_1_output` 并回传 team-lead；**team-lead 不得自行收集上下文**，必须 spawn context-researcher | 只打印到终端、未保存为变量、未通过 SendMessage 回传；team-lead 自己跑 gh pr view / git diff 而不是 spawn context-researcher |
| 2 专项审查 | 多 agent **同一响应**内并行 spawn；fresh spawn 先只做握手，收到"已就绪"后再通过 SendMessage 下发 `phase_1_output` 和正式任务；复用 teammate 或补发上下文时也用 SendMessage | **与 Phase 1 并行启动**；把正式任务直接写进 spawn prompt；让复用语义和首轮语义混在一起 |
| 3 Codex决策（必选） | **必选动作**：校验各报告的基础数据（文件数/行数/涉及模块）是否与 PR 实际 diff 一致，失真报告标注"报告作废"；**决定是否启用 codex**——报告质量合格且满足触发条件（安全PR、大型PR>500行、冲突仲裁）时调用 `codex:rescue`；**调用时只传 Phase 2 结构化报告（禁止传 diff/代码片段）**；任一报告存在严重幻觉 → 跳过 codex 直接进入 Phase 4 | 与 Phase 2 并行执行；未收集完整 Phase 2 报告就做决策；**在报告质量不合格时仍调用 codex（幻觉数据无法被 codex 验证）**；**给 codex 传 diff 而不是报告**；**未将 Phase 2 报告发给 codex** |
| 4 综合判断 | 收集 Phase 2 可用报告（剔除 Phase 3 标记为作废的）和 Phase 3 codex 报告（如有）；仲裁不同报告间的冲突；做出最终判断 | 使用已作废的报告做结论；替缺失 agent 脑补结论 |
| 5 写回 + 修复 | 模式决定路径；仅 `auto-fix` 可 spawn `pr-fix-executor`；范围外问题转 follow-up issue | 把范围外技术债塞进当前 PR comment |

> **没有 Phase 6**。完成 Phase 5 后流程结束。teammates 的 idle / pane / inbox 由运行时管理，**skill 不感知不操作**。如果你正在思考"清理 inbox"或"保留状态"，停下——这不是你的工作。

详细消息样例见 `references/execution-reference.md`。

---

## 握手与唤醒协议规范

参数定义见 Backlog metadata `wakeup_policy`（`max_attempts`、`timeout`）。以下流程是**单源真源**，修改参数只需改 metadata 一处。

### handshake_agent(agent_name)

```
1. SendMessage(to=agent_name, lead_ready)
2. 等待 agent_ready 回复（timeout=wakeup_policy.timeout）
3. 超时 & 重试次数 < wakeup_policy.max_attempts → 重试（告知第 N 次唤醒）
4. 超时 & 重试次数 >= wakeup_policy.max_attempts → 标记 blocked，继续处理下一个 agent
5. 收到 agent_ready → 该 agent ready，重置计数器，立即分配正式任务
```

**约束**：派发完一个 agent 后 team-lead 不得进入 idle；必须继续处理下一个 agent，直到全部完成。

### handle_agent_idle_after_task(agent_name)

```
收到 agent 的 idle 通知后（仅用于排查交付问题，不用于常规状态检查）：

1. 检查 inbox：任务结果是否已送达
2. check pane: InputValidationError → 该 agent 可能未加载 SendMessage，重新握手
3. check pane: Bash/Read 输出 → agent 正在执行中，正常等待
4. check pane: ❯ 等待输入 → 正常 idle，任务尚未完成，继续等待
```

### 握手强制规则

**这是有方向、有时序的握手，不是双方同时各说一次"已就绪"。**

**team-lead 必须**：
1. Phase 0 中自身先执行 `ToolSearch(query="select:SendMessage")`
2. 每 spawn 一个 agent，立即发送 `【lead_ready】`
3. 收到 `【agent_ready】已就绪` 后，必须立即发送该 phase 的正式任务；fresh spawn 不得先进入 idle / 待命态
4. 超时未收到 → 按 `handshake_agent()` 重试/blocked 逻辑处理

**team-lead 禁止**：
- 自身未 ToolSearch 就 spawn 任何 agent
- spawn 后不发 `lead_ready`，假设 agent 会自动执行
- 未收到 `agent_ready` 就给该 agent 分配工作
- 对 fresh spawn 且刚回复"【agent_ready】已就绪"的 agent 发送"保持空闲 / 等待新 PR"
- 替未响应的 agent 脑补结论

**诊断**（如 agent 未发送报告）：
```bash
tmux capture-pane -t <pane-id> -p -S -1000 | grep -E "ToolSearch|SendMessage|InputValidationError"
```

其他常见陷阱详见 `references/debug-guide.md`。

---

## Review Quality Standards（强制，写回前自查）

> **针对 PR #737 暴露的 8 类审查质量问题。每条都有真实踩坑反例。任一条不满足必须先修正再写回 comment。**

### 1. 禁虚假精度评分

LLM 拟合不出小数点评分，强行打分就是幻觉。

- ❌ "代码质量评分：89.75 / 100 (A-)"
- ❌ "架构符合性：A (90)、错误处理：B+ (85)、测试覆盖：A (95)"
- ✅ "APPROVE（已解决 3 项技术债，遗留 2 项次要问题转 follow-up）"

### 2. 强制规则引用

凡是判定为"违规 / 技术债 / 应修复"的条目，必须**引用具体规则来源**。

- ❌ "异常类型不一致（ValueError 应改为 SystemError）"——没有规则依据
- ✅ "`ValueError` 不在 `CLAUDE.md` HARD RULE 13 规定的 `SystemError / UserError / BatchError` 体系内"

合法引用源：`CLAUDE.md` 第 N 条 / `.claude/rules/coding-standards.md § X` / `.claude/rules/python-standards.md` / `docs/standards/error-handling.md` 等。

### 3. 验证再断言（数字基于本 PR 实际 diff）

- ❌ 在不修改 PRService 的 PR 中报告 "PRService at 394/400 maintained"——本 PR 不改它
- ❌ "函数大小超标（68 行，接近 100 行上限）"——project 标准是 < 100 建议，68 行**未超标**
- ✅ "`get_numstat()` 函数体 65 行（含 docstring），Client/Utils 层建议上限 100，未超标"

### 4. 禁滑动靶点（论证只针对本 PR 改动）

- ❌ 本 PR 函数不直接调用 subprocess，却写"无 shell 注入风险：使用 subprocess.run 列表形式"——这是替既有代码做声明
- ✅ "本 PR 新增的 `get_numstat()` 不直接调用 subprocess，通过注入的 `run` callable 委托；底层 `_run` 安全性属于既有代码，不在本次审查范围"

### 5. 禁无关指标

不要把与本 PR 无关的项目级指标作为"verification result"列出。

- ❌ 本 PR 不改 PRService，却列 "PRService at 394/400 maintained" 作为验证结果
- ✅ 仅列**本 PR 改动文件**的真实数据（行数、覆盖率、增删比）

### 6. 强制识别真实重构机会

`code-analyst` 必须做**结构性扫描**，不能只跑样板检查。重点找：重复代码段、冗余防御（discriminated union 之后又做 isinstance）、已有规则在新代码中的违反点。

- ❌ 在 PR #737 中遗漏 BRANCH 与 PR 分支的 `merge_base + 三点 diff` 重复
- ✅ 明确指出"BRANCH 和 PR 两条分支共享同一 `merge_base + 三点 diff` 模式，可提取私有 helper 减少 6 行重复"

### 7. 测试评估看性质而非数量

- ❌ "9 个测试 → 测试覆盖 A (95)"
- ✅ "9 个 MagicMock 单元测试，覆盖 4 种 ChangeSource + 4 种错误分支，但缺乏与真实 GitClient.\_run 的集成契约测试"

必须区分：单元（mock） / 集成（真实依赖）、happy path / 错误分支。

### 8. comment 格式（写回前最后一道关）

**必须包含**：决策一行（APPROVE / NEEDS_CHANGES / REJECT） / 已解决技术债（带 diff 引用） / 遗留问题（每条带规则引用） / follow-up issue 链接 / 审查依据（引用了哪些规则文档）。

**禁止包含**：
- ❌ 百分制 / 字母评分（除非用户明确要求）
- ❌ "Phase 1 / Phase 2 / Phase 3" 内部流程标题作叙事结构（这是 skill 的执行结构，不是审查报告的叙事结构）
- ❌ 已解决与未解决问题混在一起

---

## Recovery

按 `references/recovery-playbook.md` 处理，不在主流程临场发明 workaround：

- TeamCreate 与 Agent spawn 状态不一致
- 已有 Team 但需确认是否可复用
- TeamDelete 后 UI 残留
- 部分审查 agent 超时 / 缺失
- 背景报告未送达
- teammate-message PR 编号路由错误（Claude Code 已知 bug #40166 / #39651）

执行过程看不到 / model 不对 / PR 编号错位 → `references/debug-guide.md`。

## File Map

- `SKILL.md`：生命周期、phase 契约、质量标准、硬边界。
- `references/execution-reference.md`：消息样例与等待策略。
- `references/recovery-playbook.md`：故障恢复路径。
- `references/debug-guide.md`：pane 可见性说明、agent 执行过程查看方法、model 参数核查、PR 编号路由诊断。
- `.claude/team-templates/pr-review-team.yaml`：团队配置真源。
- `.claude/agents/pr-*.md`：teammate 项目特定职责。
- `docs/references/team-guide.md`：Team 功能通用背景。

## Usage

```
/vibe-review-pr 604
```
