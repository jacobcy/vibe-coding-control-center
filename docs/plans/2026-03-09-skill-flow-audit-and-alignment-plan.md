# Skill Flow Audit And Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 审计并修正 `/vibe-new`、`/vibe-save`、`/vibe-continue` 及相邻流程类 skill/workflow，使其与当前 shell 能力、共享状态标准、flow 生命周期标准一致，并在新的 flow 中执行该修复。

**Architecture:** 先在新的 flow 中执行“审计收口 -> 文案/流程修正 -> 验证回归”三段式改造。只修 skill/workflow 文本契约与 handoff 规则，不在本轮扩展新的 shell 原子能力；若发现 skill 依赖了 shell 尚不存在的能力，统一降级为 `Capability Gap` 记录，而不是让 skill 继续越权描述。

**Tech Stack:** Zsh, Markdown skills/workflows, `bin/vibe`, `rg`, `git`, `bats`

---

## Goal

- 系统审计流程类入口：
  - `/vibe-new`
  - `/vibe-save`
  - `/vibe-continue`
  - `/vibe-commit`
  - `/vibe-integrate`
  - `/vibe-done`
- 对齐两层文档：
  - `skills/*/SKILL.md`
  - `.agent/workflows/*.md`
- 让 skill 对 shell 的调用只引用当前真实存在的命令与参数。
- 把 `.agent/context/task.md` 统一收敛为短期 handoff，不再被任何流程类 skill 描述成共享真源。
- 为后续执行保留清晰的 `Capability Gap` 清单，避免边修文案边偷偷扩 shell。

## Non-Goals

- 本轮不修改 `lib/*.sh`、`bin/vibe`、`tests/*.bats` 的业务实现。
- 本轮不新增新的顶层 shell 子命令。
- 本轮不重写 `vibe-orchestrator` 的 Gate 框架，只修其与 `/vibe-new` 相关的入口契约。
- 本轮不处理 `vibe-skills` 的全局偏好逻辑或第三方 skill 安装流程。
- 本轮不做跨项目文档大规模重构。

## Current Findings

### Finding 1: `flow new` 已切到新语义，但 `/vibe-new` 与 `vibe-orchestrator` 仍需审计是否完全跟上

- `.agent/workflows/vibe-new.md` 仍把“当前目录开新任务 / 新目录开新任务”的编排写得过重。
- `supervisor/vibe-orchestrator/SKILL.md` 仍直接规定 `vibe task add`、`vibe task update --bind-current`、`vibe flow new` 的具体时机，需要确认是否已完全跟上新的 flow/worktree 分离语义。
- 最新帮助输出确认：
  - `vibe flow new <name> [--agent <name>] [--branch <ref>] [--save-unstash]`
  - `vibe flow switch <name> [--branch <ref>] [--save-stash]` 仅作兼容入口
- 因此 `/vibe-new` 相关文案需要显式承认：
  - `flow new` 现在是在当前目录创建新的逻辑 flow / branch
  - 并行新目录隔离应写 `wtnew` / `vnew`
  - 不能在 skill 层假设 shell 会自动补 task / roadmap / priority 推断

### Finding 2: `vibe-save` / `vibe-continue` 的字段模型与当前标准有漂移

- `skills/vibe-save/SKILL.md`、`skills/vibe-continue/SKILL.md` 中列出的字段包含：
  - `assigned_worktree`
  - `worktree_name`
  - `current_task`
  - `dirty`
- 但 `docs/standards/registry-json-standard.md` 中的当前 task runtime 字段是：
  - `runtime_worktree_name`
  - `runtime_worktree_path`
  - `runtime_branch`
  - `runtime_agent`
- `docs/standards/command-standard.md` 也明确 `dirty` 属于查询期可显示字段，不应伪装成持久化真源字段。
- 因此 `save/continue` 需要改成：
  - 区分“共享真源字段”与“查询展示字段”
  - 不再把旧 schema 字段写成“真实字段名”
  - 对 `.vibe/*` 只保留缓存层表述，不把缓存字段混成共享 schema

### Finding 3: workflow 包装层与底层 skill 的职责边界不完全一致

- `.agent/workflows/vibe-save.md` 仍写成 skill 负责直接写 `.agent/context/memory.md` 等文件，缺少“共享状态写入必须通过 shell API”的强调。
- `.agent/workflows/vibe-done.md` 仍把 `vibe flow done` 和 `/vibe-done` 的职责描述得过近，容易让人误解成 shell 与 skill 可互相替代。
- `.agent/workflows/vibe-commit.md` 已切到新的 `flow new` 语义，但仍需要检查相邻 skill 是否同步到“当前目录串行 flow / 新目录并行 worktree”的边界。

### Finding 4: handoff 规则已在 `commit / integrate / done` 基本成型，但未覆盖 `new / save / continue`

- `skills/vibe-commit/SKILL.md`、`skills/vibe-integrate/SKILL.md`、`skills/vibe-done/SKILL.md` 已统一把 `.agent/context/task.md` 定位为短期 handoff。
- `new / save / continue` 仍更多强调 context 文件本身内容，没有统一到“handoff 摘要 + capability gap + next”这类固定结构。
- 这会导致前半段流程与后半段流程的上下文格式割裂。

### Finding 5: 当前 shell 已提供更多原子能力，旧 skill 文案需要消化

- `bin/vibe task --help` 已确认 `task update` 支持：
  - `--issue`
  - `--roadmap-item`
  - `--pr`
  - `--branch`
  - `--bind-current`
  - `--unassign`
  - `--agent`
- 若现有 skill 仍把这些能力写成缺失，或继续建议人工绕过 shell，则属于过期文案。

## Task 1: 在新 flow 中准备执行现场

**Files:**
- Modify: `.agent/context/task.md`

**Step 1: 检查当前现场干净度**

Run:
```bash
git status --short
git branch --show-current
```

Expected:
- 工作区干净
- 明确当前是否处于 detached HEAD 或无活跃 branch

**Step 2: 新开执行 flow**

Run:
```bash
bin/vibe flow new skill-flow-audit-alignment --agent codex --branch origin/main --save-unstash
```

Expected:
- 在当前目录切到新的逻辑 flow / branch
- 若存在未提交内容，可随 `--save-unstash` 一并带入

**Step 3: 记录本轮执行目标**

在 `.agent/context/task.md` 写入：
- 当前 flow 名
- 本轮范围只含 skill/workflow 文案契约对齐
- 不修改 shell 实现

## Task 2: 审计 `/vibe-new` 入口链路

**Files:**
- Modify: `.agent/workflows/vibe-new.md`
- Modify: `supervisor/vibe-orchestrator/SKILL.md`

**Step 1: 对齐入口职责**

明确：
- `/vibe-new` 是 Discussion Mode 入口
- shell 只负责原子能力
- skill 不替 shell 发明隐式 workflow

**Step 2: 收紧 flow 文案**

至少修正：
- `flow new`、`wtnew` / `vnew` 的使用场景
- `task add/update` 与 `flow new/bind` 的前后顺序
- 任何不再准确的“自动创建/自动绑定/自动推断”描述

**Step 3: 验证关键引用**

Run:
```bash
rg -n "flow new|save-unstash|wtnew|vnew|bind-current|roadmap|自动|隐式|HARD STOP" \
  .agent/workflows/vibe-new.md \
  supervisor/vibe-orchestrator/SKILL.md
```

Expected:
- `/vibe-new` 和 orchestrator 对 shell 的描述不再互相冲突
- 保留 Gate 0-3 + HARD STOP 结构

## Task 3: 审计 `/vibe-save` 与 `/vibe-continue`

**Files:**
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`
- Modify: `.agent/workflows/vibe-save.md`
- Modify: `.agent/workflows/vibe-continue.md`

**Step 1: 修正 schema 表述**

明确分开三类内容：
- 共享真源字段：只引用当前标准允许字段
- 查询展示字段：如 dirty/clean，只说明“由 shell 查询得到”
- 本地缓存字段：只描述 `.vibe/*` 的缓存用途，不冒充共享 schema

**Step 2: 收紧写入边界**

明确：
- skill 可以读取路径用于定位
- 共享状态写入必须走 `vibe task update` / `vibe flow ...`
- `.agent/context/task.md` 是本地 handoff，不是共享真源

**Step 3: 统一恢复/保存报告格式**

至少补齐：
- 当前操作者
- 当前 flow / task / next step
- capability gap（若命令不足）
- 下一步建议

**Step 4: 验证字段漂移已消除**

Run:
```bash
rg -n "assigned_worktree|current_task_id|version\\b|\\bdirty\\b|runtime_worktree_name|runtime_branch|runtime_agent|共享真源|handoff" \
  skills/vibe-save/SKILL.md \
  skills/vibe-continue/SKILL.md \
  .agent/workflows/vibe-save.md \
  .agent/workflows/vibe-continue.md
```

Expected:
- 不再把旧字段名标成“真实字段”
- 新 runtime 字段与缓存字段职责清晰

## Task 4: 审计 `commit / integrate / done` 的相邻流程一致性

**Files:**
- Modify: `.agent/workflows/vibe-commit.md`
- Modify: `.agent/workflows/vibe-done.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `skills/vibe-integrate/SKILL.md`
- Modify: `skills/vibe-done/SKILL.md`

**Step 1: 对齐 flow 生命周期用语**

明确：
- `commit` 只处理 `open + no_pr`
- `integrate` 只处理 `open + had_pr`
- `done` 只处理 merged 后收口

**Step 2: 对齐 `new` 主入口与 handoff 用法**

修正：
- 串行进入下一个交付目标时优先写 `new`
- `switch` 若仍被提及，只能作为兼容别名说明，不得作为主推荐路径
- handoff 结构统一引用 `.agent/context/task.md` 为短期记录

**Step 3: 验证收口语义**

Run:
```bash
rg -n "open \\+ no_pr|open \\+ had_pr|flow done|flow new|save-unstash|wtnew|vnew|handoff|共享真源" \
  .agent/workflows/vibe-commit.md \
  .agent/workflows/vibe-done.md \
  skills/vibe-commit/SKILL.md \
  skills/vibe-integrate/SKILL.md \
  skills/vibe-done/SKILL.md
```

Expected:
- 三段式 skill 与最新 flow lifecycle 标准一致

## Task 5: 汇总 Capability Gap 与标准引用缺口

**Files:**
- Modify: `docs/plans/2026-03-09-skill-flow-audit-and-alignment-plan.md`
- Modify: `.agent/context/task.md`

**Step 1: 记录本轮发现的 gap**

若执行中发现 skill 需要但 shell 没有的原子能力：
- 不在本轮私自实现
- 追加到计划末尾的 `Capability Gap` 小节

**Step 2: 记录标准引用缺口**

重点检查是否显式引用：
- `docs/standards/glossary.md`
- `docs/standards/action-verbs.md`
- `docs/standards/command-standard.md`
- `docs/standards/git-workflow-standard.md`
- `docs/standards/worktree-lifecycle-standard.md`

**Step 3: 更新 handoff**

把执行结果写回 `.agent/context/task.md`，至少包含：
- 已审计文件
- 已修正的漂移类型
- 尚未解决的 capability gap
- 下一步是否进入 review / commit

## Task 6: 验证回归

**Files:**
- Modify: `tests/test_vibe.bats` (only if current doc/help tests need extension)

**Step 1: 文本回归检查**

Run:
```bash
rg -n "vibe flow continue|assigned_worktree|current_task_id|只写 \\.git/vibe|直接修改 JSON|flow switch <name>|save-stash" \
  skills \
  .agent/workflows \
  supervisor
```

Expected:
- 不再出现已知错误命令或越权描述

**Step 2: 命令帮助校验**

Run:
```bash
bin/vibe flow --help
bin/vibe flow new --help
bin/vibe flow switch --help
bin/vibe task --help
```

Expected:
- 计划引用的命令与当前帮助输出一致

**Step 3: 差异与格式检查**

Run:
```bash
git diff --check
git diff --stat
```

Expected:
- 无空白错误
- 变更集中在 skill/workflow 文档层

## Test Command

```bash
rg -n "vibe flow continue|assigned_worktree|current_task_id|只写 \\.git/vibe|直接修改 JSON|flow switch <name>|save-stash" skills .agent/workflows supervisor
bin/vibe flow --help
bin/vibe flow new --help
bin/vibe flow switch --help
bin/vibe task --help
git diff --check
git diff --stat
```

## Expected Result

- `/vibe-new`、`/vibe-save`、`/vibe-continue` 的 skill/workflow 契约与当前 shell 能力一致。
- `commit / integrate / done` 与前半段流程的 handoff 结构一致。
- 不再把旧 schema 字段、缓存字段、查询字段混写成共享真源字段。
- 执行阶段将在当前目录的 `task/skill-flow-audit-alignment` flow 中推进，不再依赖新 worktree。
- 若仍存在 shell 能力缺口，会被明确记录为 `Capability Gap`，而不是继续隐式绕过。

## Change Summary

- Planned modified files: 10-12
- Planned added lines: ~220
- Planned removed lines: ~120
- Logical change count: 1

## Capability Gap Placeholder

- 当前结论：`none`
- 已确认无需新增 shell 原子能力即可完成本轮 skill/workflow 契约收敛。
- 本轮显式引用并已对齐的标准：
  - `docs/standards/glossary.md`
  - `docs/standards/action-verbs.md`
  - `docs/standards/command-standard.md`
  - `docs/standards/git-workflow-standard.md`
  - `docs/standards/worktree-lifecycle-standard.md`
