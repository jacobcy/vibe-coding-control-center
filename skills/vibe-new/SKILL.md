---
name: vibe-new
description: Use when the user wants to create or intake the next delivery target from roadmap items, handoff blockers, or missing task specs, and needs plan/task binding without entering implementation.
---

# /vibe-new - 创建 Flow 与同步 Issue

## 核心职责

`vibe-new` 只负责创建逻辑 flow 并同步 issue，不进入执行，也不创建 task。

**核心职责**：

- 创建逻辑 flow（不创建物理 worktree）
- 没指定 issue → 通过 `/vibe-issue` 创建 issue
- 有 issue 且已有 `vibe-task` label 或在 GitHub Project 中 → `vibe roadmap sync` 同步到本地
- 不创建 task，不进入执行

## 停止点

完成后输出：

- ✅ flow 已创建
- ✅ issue 已同步
- **下一步**：使用 `/vibe-start` 开始执行

## 必读文档

- `docs/standards/v2/git-workflow-standard.md` (flow 生命周期)
- `.agent/context/task.md` (当前上下文)

相关文档：

- 术语：`docs/standards/glossary.md`
- 动作语义：`docs/standards/action-verbs.md`
- Skill 标准：`docs/standards/v2/skill-standard.md`

## 完整流程

```
/vibe-new <feature>
  ├─ Step 1: 读取当前上下文
  │   ├─ vibe flow show
  │   ├─ vibe roadmap status
  │   └─ 检查当前 flow、roadmap 窗口、handoff blocker
  │
  ├─ Step 2: 选择 intake 来源
  │   ├─ 当前 flow 需要切换到新 issue
  │   ├─ handoff blocker
  │   ├─ roadmap item / repo issue
  │   └─ 用户显式指定的目标
  │
  ├─ Step 3: 补齐上游规划对象
  │   ├─ 缺 issue → 调用 /vibe-issue
  │   ├─ 缺 roadmap item → vibe roadmap sync 或 vibe roadmap add
  │   └─ 缺 plan → 等待 /vibe-start 编写 plan
  │
  ├─ Step 4: 处理 flow 现场
  │   ├─ 创建逻辑 flow：vibe flow new <slug> --branch origin/main
  │   └─ 同步 issue：vibe roadmap sync
  │
  └─ Step 5: 写入 handoff 与停止
      ├─ 更新 .agent/context/task.md
      └─ 输出停止点信息，等待用户执行 /vibe-start
```

## 核心边界

- 允许：读取 handoff、检查 roadmap 窗口、确认主 issue、判断旧 flow 到新 flow 的转换方式、必要时创建新的逻辑 flow
- 不允许：修改业务代码、进入实现、创建或更新 task、伪造没有 plan 的 task、擅自新建或切换物理 worktree
- 若当前 flow 已有 PR，只允许为下一个目标准备新的逻辑 flow，不得继续在当前 flow 中开发新目标

## Workflow

### Step 1: 读取当前上下文

优先读取：

```bash
vibe flow show
vibe roadmap status
```

必要时补充：

```bash
vibe task list
vibe task show <task-id>
vibe roadmap list
```

检查点：

- 当前 flow 是否已有 `current_task`
- 当前 flow 是否已经 `open + had_pr`
- 当前 roadmap 窗口是否存在 `current` / `p0` item
- `.agent/context/task.md` 是否存在 handoff blocker 或待 intake 事项

### Step 2: 选择 intake 来源

按以下顺序选择目标来源：

1. 当前 flow 已绑定但需要切换到新的主 issue / 新的 flow 语义
2. `.agent/context/task.md` 中明确记录的 handoff blocker
3. 当前 roadmap 窗口内已存在但尚未进入新 flow 的 roadmap item / repo issue
4. 用户显式指定的目标

如果以上来源都不存在，停止并报告“当前没有可 intake 的目标”。

### Step 3: 补齐上游规划对象

规则固定如下：

- 缺少 `repo issue` 或 bug 边界不清时，先委托 `vibe-issue`
- 缺少 roadmap item 时：
  - 如果 issue 已有 `vibe-task` label 或已在 GitHub Project 中：直接运行 `vibe roadmap sync`（会自动 intake）
  - 如果 issue 没有 label 且不在 Project 中：先添加 label 或添加到 Project，然后 `vibe roadmap sync`
  - 如果还没有 GitHub issue：运行 `vibe roadmap add <title>` 创建 draft item
- 缺少 plan 时，等待 `/vibe-start` 编写 plan（vibe-new 不负责创建 plan）
- 只有进入 `/vibe-start` 后，才允许从 issue 落 task 作为 execution bridge 并写入 `spec_standard/spec_ref`

### Step 4: 处理 flow 现场

当主 issue 与 plan 已确定后，再决定是否需要新的逻辑 flow：

- 若当前目录还没有承载目标 flow，默认使用：

```bash
vibe flow new <slug> --branch origin/main
```

- 若只是把已有 task 绑定到当前目录承载的 flow，使用：
- 若当前目录只需要切到新的逻辑 flow，保持在 flow 层完成切换，不在这里绑定 task

- 未经人类明确授权，不得使用 `wtnew`、`vnew`、`git worktree add`

### Step 5: 写入 handoff 与停止点

完成后更新 `.agent/context/task.md`，至少记录：

```markdown
## Skill Handoff

- skill: vibe-new
- updated_at: <ISO-8601>
- target: <issue-or-roadmap-item>
- plan: <plan-path-or-none>
- task: none
- flow: <flow-or-none>
- next: /vibe-start

## Issues Found (可选)

- type: <flow|doc|command|other>
- severity: <low|medium|high>
- description: <问题描述>
- context: <发现场景>
- suggestion: <改进建议（可选）>
```

然后停止，不进入执行。

## Restrictions

- 不得在本 skill 内创建 task；从 issue 落 task 是 `/vibe-start` 的责任
- 不得把 handoff 直接当真源，必须先核查 shell 输出
- 不得把 `flow`、`task`、`roadmap item` 混成同一对象
- 不得在 skill 里把物理 worktree 当默认隔离手段
