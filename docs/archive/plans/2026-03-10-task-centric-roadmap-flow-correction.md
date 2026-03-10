# GitHub-First Semantics Correction Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 以 GitHub 官方语义为基线，纠正本项目对 `repo issue`、`GitHub Project item`、`milestone`、`roadmap item`、`task`、`flow`、`PR` 的用词和职责边界，并优先统一入口文件与标准文件。

**Architecture:** 本次纠偏不再以现有本地语义为中心，而是以 GitHub 标准对象为上位约束。项目内部语义只能是 GitHub 语义的子集或更严格约束：`repo issue` 是来源层对象，`roadmap item` 镜像 GitHub Project item，`feature/task/bug` 是 roadmap item 的 type，`milestone` 是版本/阶段窗口锚点，`flow` 与 `PR` 属于执行与交付层。

**Tech Stack:** Markdown standards/workflows/skills, Zsh shell help text, shared JSON schemas (`roadmap.json`, `registry.json`, `worktrees.json`)

---

## Goal

- 用 GitHub 标准语义重写项目心智模型。
- 优先修正入口文件和标准文件，避免继续向用户传播旧语义。
- 在此基础上再评估 shell/skill 能力缺口与数据同步方向。

## Non-Goals

- 本计划不直接实现 GitHub Projects API 新能力。
- 本计划不立即重构 shared-state schema。
- 本计划不在本轮引入 `epic` 作为标准核心概念。
- 本计划不处理与本次语义纠偏无关的 PR/CI 流程问题。

## Current Facts

1. 当前很多文档仍把 `roadmap item` 当作纯本地 feature 概念，而不是 GitHub Project item 镜像。
2. 当前 `roadmap sync (shell)` 实现仍是“从 GitHub repo issue 拉回本地并直接 materialize 成 roadmap item”，见 `lib/roadmap_write.sh`。
3. 当前项目还未把 `milestone` 作为版本/阶段窗口的标准锚点。
4. 当前入口文档中仍混有“`flow new <feature>` 像是在定义 feature”的旧语义。
5. 当前本地 `task registry` 更像执行镜像，但很多文案仍把它当成与 roadmap 并列的产品对象。
6. 现有参考文档 `docs/references/github_project.md` 已更新为 GitHub-first 语义，可作为本计划的外部对齐依据。

## Target Semantics

### GitHub Standard Baseline

- `repo issue`: GitHub 仓库 issue，来源层对象
- `GitHub Project item`: Project 中的工作项，可来自 issue / PR / draft issue
- `milestone`: 版本或阶段窗口标准对象
- `issue type`: `feature` / `task` / `bug`
- `PR`: 交付与审查单元

### Project Subset Rules

- `roadmap item` = mirrored GitHub Project item
- `feature` / `task` / `bug` = roadmap item 的 `type`
- `1 feature = 1 branch = 1 PR`
- 一个 `feature` 可以包含多个 `task`
- `flow` 只负责执行现场，不承担规划语义
- 本地 `task registry` 解释为 roadmap item 的执行镜像 / runtime record

## Priority Order

1. 入口文件
2. 标准文件
3. skills
4. shell 帮助与提示语
5. capability gap / backfill 计划

## Task 1: 先统一入口文件语义

**Files:**
- Modify: `.agent/workflows/vibe-new-feature.md`
- Modify: `.agent/workflows/vibe-new-flow.md`
- Modify: `.agent/workflows/vibe-issue.md`

**Step 1: 入口文件统一命名**

- 后续文案统一使用 `repo issue`
- 不再把 `issue` 模糊地写成本地任务
- 不再把 `flow new` 写成“定义 feature”

**Step 2: `/vibe-new-feature` 调整为调度入口**

- 明确它是调度入口，不是直接建 feature 真源
- 输出应引导到：
  - repo issue / project item / roadmap item
  - task 选择
  - flow bind

**Step 3: `/vibe-new-flow` 调整为执行入口**

- 明确它只负责：
  - 创建现场
  - 为 `flow bind <task-id>` 做准备

**Step 4: `/vibe-issue` 对齐 GitHub 入口**

- 明确 issue 是来源层
- `roadmap sync` 对齐 GitHub Project 同步，而不是“issue 原料 -> 本地 item”偷换

**Step 5: 验证**

Run:

```bash
rg -n "repo issue|GitHub Project item|milestone|flow bind <task-id>|1 feature = 1 branch = 1 PR" .agent/workflows
```

Expected:

- 三个入口文件均使用 GitHub-first 语义。

**Step 6: Commit**

```bash
git add .agent/workflows/vibe-new-feature.md .agent/workflows/vibe-new-flow.md .agent/workflows/vibe-issue.md
git commit -m "docs(workflows): align entrypoints with GitHub-first semantics"
```

## Task 2: 再统一标准文件

**Files:**
- Modify: `docs/standards/glossary.md`
- Modify: `docs/standards/command-standard.md`
- Modify: `docs/standards/data-model-standard.md`
- Modify: `docs/standards/roadmap-json-standard.md`
- Modify: `docs/standards/registry-json-standard.md`

**Step 1: 统一术语**

- `issue` 在项目语境下默认改称 `repo issue`
- `roadmap item` 改写为 GitHub Project item 镜像
- `feature/task/bug` 改写为 roadmap item type

**Step 2: 明确 milestone 地位**

- 把 milestone 写成版本/阶段窗口的标准锚点
- 对现有 `version_goal` 语义做兼容说明或迁移注记

**Step 3: 明确项目级特别约束**

- `1 feature = 1 branch = 1 PR`
- 一个 feature 可拆多个 task
- flow 只属于执行层

**Step 4: 重新解释本地 task**

- 不把本地 task 解释成另一套产品规划对象
- 统一解释为 execution record / runtime record

**Step 5: 验证**

Run:

```bash
rg -n "repo issue|GitHub Project item|roadmap item.*type|milestone|1 feature = 1 branch = 1 PR|execution record" docs/standards
```

Expected:

- 标准文件与参考文档口径一致。

**Step 6: Commit**

```bash
git add docs/standards/glossary.md docs/standards/command-standard.md docs/standards/data-model-standard.md docs/standards/roadmap-json-standard.md docs/standards/registry-json-standard.md
git commit -m "docs(standards): adopt GitHub-first project semantics"
```

## Task 3: 收敛 skills 语义

**Files:**
- Modify: `skills/vibe-roadmap/SKILL.md`
- Modify: `skills/vibe-task/SKILL.md`
- Optional Modify: `skills/vibe-save/SKILL.md`

**Step 1: `vibe-roadmap` 对齐 GitHub Projects**

- 明确其职责是维护 mirrored Project items
- 维护 `type`
- 维护 milestone / repo issue / roadmap item 关系

**Step 2: `vibe-task` 对齐执行镜像**

- 明确其处理的是 execution record
- roadmap item 的 `type=task` 与本地 task record 的关系要写清

**Step 3: 如有必要，补 `vibe-save` 边界**

- 避免 `/save` 继续暗示它在决定规划语义

**Step 4: 验证**

Run:

```bash
rg -n "repo issue|Project item|milestone|execution record|type=task" skills/vibe-roadmap/SKILL.md skills/vibe-task/SKILL.md skills/vibe-save/SKILL.md
```

Expected:

- skill 层与标准层一致，不再传播旧的内部自造语义。

**Step 5: Commit**

```bash
git add skills/vibe-roadmap/SKILL.md skills/vibe-task/SKILL.md skills/vibe-save/SKILL.md
git commit -m "docs(skills): align roadmap and task skills with GitHub semantics"
```

## Task 4: 收紧 shell 帮助与提示语

**Files:**
- Modify: `lib/roadmap_write.sh`
- Modify: `lib/flow.sh`
- Optional Modify: `lib/task_actions.sh`
- Optional Modify: `bin/vibe`

**Step 1: `roadmap sync` 帮助语收紧**

- 不再表述为“拉 issue 原料 -> 本地 feature”
- 改写为同步本地 roadmap item 与 GitHub Project item

**Step 2: `flow new` 提示语收紧**

- 删除/避免 `flow new <feature>` 的误导性暗示
- 强调“先有任务清单，再 bind task”

**Step 3: task 提示语补 execution record 语义**

- 如有必要，在 help / success message 中补“task 是执行镜像”的说明

**Step 4: 验证**

Run:

```bash
bin/vibe roadmap --help
bin/vibe task --help
bin/vibe flow new --help
rg -n "Project item|repo issue|execution record|bind <task-id>" lib/roadmap_write.sh lib/flow.sh lib/task_actions.sh bin/vibe
```

Expected:

- shell 帮助和提示语不再与标准语义冲突。

**Step 5: Commit**

```bash
git add lib/roadmap_write.sh lib/flow.sh lib/task_actions.sh bin/vibe
git commit -m "docs(shell): align help text with GitHub-first semantics"
```

## Task 5: 列出能力缺口与后续补图

**Files:**
- Modify: `docs/standards/shell-skill-boundary-audit.md`
- Optional Modify: `docs/plans/2026-03-10-task-centric-roadmap-flow-correction.md`

**Step 1: 记录新的 capability gap**

- 目前 `roadmap sync` 还没有真正对接 GitHub Projects item
- 目前 milestone 还未成为正式同步锚点
- 目前缺少从已有 PR / commits 回填 task 的能力
- 目前本地 task 与 GitHub `type=task` item 的桥接不完整

**Step 2: 列出后续拼图**

- roadmap item <-> GitHub Project item sync
- milestone 对齐
- 从已有 PR / commit 反向补 task
- task 回写 repo issue / project item

**Step 3: 验证**

Run:

```bash
rg -n "GitHub Project|milestone|PR / commit|backfill task|type=task" docs/standards/shell-skill-boundary-audit.md docs/plans/2026-03-10-task-centric-roadmap-flow-correction.md
```

Expected:

- 能力缺口被明确记录，且不与新标准语义冲突。

**Step 4: Commit**

```bash
git add docs/standards/shell-skill-boundary-audit.md docs/plans/2026-03-10-task-centric-roadmap-flow-correction.md
git commit -m "docs(plan): record GitHub-first capability gaps and backfill work"
```

## Test Commands

```bash
rg -n "repo issue|GitHub Project item|milestone|1 feature = 1 branch = 1 PR|execution record" docs/references docs/standards .agent/workflows skills lib
bin/vibe roadmap --help
bin/vibe task --help
bin/vibe flow new --help
bin/vibe check
```

## Expected Result

- 入口文件先统一为 GitHub-first 语义。
- 标准文件再统一为 GitHub-first 语义。
- skills 与 shell 帮助文案不再传播旧的内部自造概念。
- 项目语义与 GitHub 标准语义不冲突，只表现为更严格子集约束。
- 后续 GitHub Project / milestone / task backfill 的能力缺口被清楚列出。

## Files to Modify Summary

- `.agent/workflows/vibe-new-feature.md`
- `.agent/workflows/vibe-new-flow.md`
- `.agent/workflows/vibe-issue.md`
- `docs/standards/glossary.md`
- `docs/standards/command-standard.md`
- `docs/standards/data-model-standard.md`
- `docs/standards/roadmap-json-standard.md`
- `docs/standards/registry-json-standard.md`
- `skills/vibe-roadmap/SKILL.md`
- `skills/vibe-task/SKILL.md`
- `skills/vibe-save/SKILL.md`
- `lib/roadmap_write.sh`
- `lib/flow.sh`
- `lib/task_actions.sh`
- `bin/vibe`
- `docs/standards/shell-skill-boundary-audit.md`

## Estimated Change Summary

- Added: ~120-180 lines
- Modified: ~120-220 lines
- Removed: ~40-80 lines
- Priority: entrypoints first, standards second, then skills/shell/help, finally capability gap tracking
