---
name: vibe-orchestra
description: Use when the user wants heartbeat-style governance over the issue pool. inspect running issues, judge which issue is worth starting next, backfill assignee-triggered candidates, and propose non-state label or routing actions. Do not use for single-flow execution governance, coding, or implementation work.
---

# Vibe Orchestra

> 项目命令参考见 `skills/vibe-instruction/SKILL.md`

`vibe-orchestra` 负责 orchestra 心跳层的 **assignee issue pool** 治理。它关心的范围仅限于 assignee issue pool：现在有哪些 issue 正在运行、哪些已满足 assignee 触发条件但尚未进入调度，以及在人机协作环节接下来哪个 assignee issue 值得优先处理。它不负责单 flow 执行，也不负责 broader repo backlog 的 triage。

## 概念区别

- **governance**：无临时 worktree 的 scan agent，只观察和建议，不执行代码修改。
- **supervisor/apply**：有临时 worktree 的治理执行 agent，负责实际治理执行动作。
- **`@vibe/supervisor/governance/assignee-pool.md`（原 orchestra.md，使用 `vibe3 handoff show @vibe/supervisor/governance/assignee-pool.md` 命令读取）**：governance supervisor material，是 governance agent 的角色材料，不是 runtime orchestra 本体。
- **runtime orchestra / governance supervisor material / supervisor apply 是三个独立概念，不可混淆。**

优先级判断口径必须对齐 `@vibe/supervisor/governance/assignee-pool.md`（使用 `vibe3 handoff show @vibe/supervisor/governance/assignee-pool.md` 命令读取）。可以把 `vibe-orchestra` 视为自动治理 supervisor 在人机协作环节的落地判断器：它不发明另一套优先级规则，只读取当前现场并按 supervisor 已定义的排序模型，指导人类如何找到下一个需要处理的 issue。

术语、对象边界与触发分流以以下标准为准：

- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/v3/skill-standard.md`
- `docs/standards/v3/command-standard.md`
- `docs/standards/v3/python-capability-design.md`
- `docs/standards/v3/worktree-lifecycle-standard.md`
- `docs/standards/v3/skill-trigger-standard.md`

## Scope

`vibe-orchestra` 只回答两类问题，且均以 **assignee issue pool** 为前提：

- assignee issue pool 中现在有哪些 issue 正在运行
- 在当前现场下，assignee issue pool 中接下来哪个 issue 值得建议优先处理

这里的"建议 issue"只是参考，不是强制调度结果；最终仍需结合 flow / PR / 人类当前上下文判断。

补充说明：

- assignee 是启动事实源
- `state/*` label 只反映 flow 实际状态，不是主触发源
- 常驻 server 与定时巡检只是运行模式差异，不改变本 skill 的职责边界
- 自动 ready queue 的建议顺序按 `milestone -> roadmap/* -> priority/[0-9] -> issue number` 理解，仅作用于 assignee issue pool 内部
- 人机协作时，若某个 assignee issue 已被人类明确接手、已有活跃 PR、或当前上下文要求先收口 follow-up，可临时覆盖自动顺序，但必须说明理由
- **不处理 supervisor issue，也不对 broader repo backlog 做 triage**

## What It Reads

以下观察面均以 **assignee issue pool** 为范围：

- running issues（assignee issue pool 中正在运行的 issue）
- assignee issue pool 中尚未启动但可被考虑的候选 issues
- `uv run python src/vibe3/cli.py task status` 中 assignee issue 的 active / ready / blocked 现场与 ready queue rank
- 当前是否已有人工明确接手的 assignee issue / PR follow-up / review 收口上下文
- assignee 与 queue / flow 现场事实
- assignee issue pool 中 issue 的 state labels
- `@vibe/supervisor/governance/roadmap-intake.md` 中的 intake 标准（使用 `vibe3 handoff show @vibe/supervisor/governance/roadmap-intake.md` 命令读取）
- dependency 详细信息：issue body 中的 `blocked_by`、`Depends on #N`、`Blocked by #N` 引用
- active flow / live dispatch 状态（通过 `vibe3 task status` / `vibe3 flow show` 获取）
- orchestra heartbeat status 与相关文档
- `@vibe/supervisor/governance/assignee-pool.md` 中的 queue guidance 与治理边界（使用 `vibe3 handoff show @vibe/supervisor/governance/assignee-pool.md` 命令读取）

## Candidate Criteria

本章节提炼 governance material 中的检查项，供 skill 执行时快速判断候选边界。详细标准以 `@vibe/supervisor/governance/assignee-pool.md` 为准。

### 候选边界验证

**必须同时满足**以下条件（缺一不可）：

- Issue 是 open 状态
- Issue 有 assignee
- Assignee 在本机 Manager agents 列表中（通过 `vibe3 status` 获取）
- Issue 没有 `orchestra-governed` 标签
- Issue 没有 `roadmap-reviewed` 标签

详细依据：`@vibe/supervisor/governance/assignee-pool.md` §候选边界验证

### 依赖过滤

**排除条件**（满足任一即排除）：

- 被 `blocked_by` 标签标记的 issue
- Issue body 中包含未关闭依赖引用（如 "Depends on #123"，且 #123 为 open 状态）
- 已有活跃 flow / live dispatch
- 被硬规则阻塞（涉及 `.claude/` 或 `.codex/` 目录）
- 是简单测试任务（应路由到 supervisor/apply）

**依赖检查命令**：

```bash
# 检查 blocked_by 标签
gh issue view <number> --json labels | jq '.labels[] | select(.name == "blocked_by")'

# 检查 body 中的依赖引用
gh issue view <number> --json body | jq -r '.body' | grep -i "depends on\|blocked by\|依赖"

# 检查依赖 issue 状态
gh issue view <dependency-number> --json state,stateReason
```

详细依据：`@vibe/supervisor/governance/assignee-pool.md` §依赖过滤

### Intake 标准

参考 `@vibe/supervisor/governance/roadmap-intake.md`（使用 `vibe3 handoff show @vibe/supervisor/governance/roadmap-intake.md` 命令读取）：

**Level 0 检查**（必须通过）：
- 检查 `.claude/` / `.codex/` 目录（命中即阻塞）

**反模式评估**：
- 检查是否命中 >= 2 条反模式特征
- 如：涉及核心基础设施、需要大量人类对齐、边界不明确等

**Level 1-3 框架**：
- Level 1：边界明确（改动范围清晰）
- Level 2：验收清晰（有明确的验收标准）
- Level 3：依赖就绪（无阻塞依赖）

详细依据：`@vibe/supervisor/governance/roadmap-intake.md`

## What It Produces

- running issues summary
- backfill candidates summary
- next-issue recommendation
- ready queue ordering judgment
- 最小 non-state label actions 或 routing suggestions
- start / wait / defer recommendations with short reasons
- Intake actions（若执行了 intake 前置检查）

## Hard Boundary

- 不负责 task registry 或 task 数据质量审计
- 不负责 runtime 绑定修复
- 不负责 roadmap 规划或版本目标
- 不负责 GitHub issue intake、模板补全或查重
- 不负责单个 flow 的 plan / run / review
- 不负责决定单个 issue 一定要先 plan、run、review 还是直接人工操作
- 不负责把 `state/*` label 当作启动执行的主驱动
- 不负责写代码
- 不负责替代人类做最终业务优先级拍板；它只给出基于 supervisor 语义和当前现场的建议
- 不负责 orchestra service 运行健康监控（转给 `vibe-debug-serve`）

当请求跨出这些边界时，按 `docs/standards/v3/skill-trigger-standard.md` 分流，不在本 skill 中重写职责矩阵。

## Execution Pattern

0. **Intake 前置检查（可选）**：
   - 如果用户明确要求"检查新 issue 入池"，执行：
     ```bash
     vibe3 scan governance --role roadmap-intake
     ```
   - 参考 `@vibe/supervisor/governance/roadmap-intake.md`（使用 `vibe3 handoff show @vibe/supervisor/governance/roadmap-intake.md` 命令读取）了解 intake 标准
   - 检查 Level 0 阻塞（`.claude/` / `.codex/` 目录）
   - 检查反模式特征
   - 对适合纳入的 issue 使用 `vibe3 task intake <issue-number>` 分配 assignee

1. **候选边界验证（强制）**：
   - 先运行 `vibe3 status` 获取本机 Manager agents 列表
   - 只处理同时满足以下条件的 issue：
     - Issue 是 open 状态
     - Issue 有 assignee
     - Assignee 在本机 Manager agents 列表中
     - Issue 没有 `orchestra-governed` 标签
     - Issue 没有 `roadmap-reviewed` 标签
   - 不符合任一条件的 issue 跳过（在 stdout 记录原因），不写 comment、不改 label

2. 查看当前 assignee issue pool 中的 running issues 与 queue / flow 现场

3. 补捞 assignee issue pool 中已满足 assignee 条件但尚未进入调度的候选 issue
   **依赖过滤（在列出候选后执行）**：
   - 使用以下命令检查 `blocked_by` 标签：
     ```bash
     gh issue view <number> --json labels | jq '.labels[] | select(.name == "blocked_by")'
     ```
   - 检查 body 中的依赖引用：
     ```bash
     gh issue view <number> --json body | jq -r '.body' | grep -i "depends on\|blocked by\|依赖"
     ```
   - 若发现依赖引用，检查依赖 issue 状态：
     ```bash
     gh issue view <dependency-number> --json state,stateReason
     ```
   - 排除条件：
     - 被 `blocked_by` 标签标记的 issue
     - Issue body 中包含未关闭依赖引用（依赖 issue 为 open 状态）
     - 已有活跃 flow / live dispatch 的 issue
     - 被硬规则阻塞（涉及 `.claude/` 或 `.codex/` 目录）
     - 简单测试任务（应路由到 supervisor/apply）
   - 详细排除标准参考 `## Candidate Criteria` 章节

4. **简单测试任务路由**：对通过依赖过滤的候选，判断是否应路由到 supervisor/apply：
   - **判断标准**（必须同时满足）：
     - 只涉及测试文件修改（`tests/`、`test_*.py` 等）
     - 不涉及业务代码改动（`src/` 等）
     - 预估改动范围 ≤ 5 个文件、≤ 100 行
   - 若是简单测试任务：
     - 执行 `gh issue edit <issue-number> --add-label "supervisor" --add-label "state/handoff" --remove-label "state/ready"`
     - 写 `[governance decide][assignee-pool]` comment 说明路由原因
     - 打 `orchestra-governed` 标签
     - 跳过后续入池评估
   - 否则继续正常入池评估

5. 判断 assignee issue pool 中是否已经存在足够明确的执行现场

6. 参考 `@vibe/supervisor/governance/assignee-pool.md`（使用 `vibe3 handoff show @vibe/supervisor/governance/assignee-pool.md` 命令读取），按 `milestone -> roadmap/* -> priority/[0-9] -> issue number` 对 assignee issue pool 的自动 ready queue 做人机治理判断

7. 结合当前人工上下文，识别 assignee issue pool 中哪些 issue 虽然不在自动顺位最前，但更适合现在先处理

8. 如有必要，提出最小 non-state label 调整建议（仅作用于 assignee issue pool 内）

9. 在治理结论处停止

## Output Contract

输出至少包含：

- `Running issues`
- `Backfill candidates`
- `Next issue`
- `Why this one now`
- `Label actions`
- `Why`

如果当前没有合适的建议 issue，明确写无，并说明原因。

## Stop Point

完成治理建议后停止。
不要进入执行分配、实现方案、代码修改或单 flow 管理。
