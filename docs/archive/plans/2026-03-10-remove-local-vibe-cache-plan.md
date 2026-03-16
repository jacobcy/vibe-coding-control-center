---
title: "Remove Local .vibe Cache Implementation Plan"
date: "2026-03-10"
status: "draft"
author: "GPT-5.4"
related_docs:
  - docs/plans/2026-03-10-remove-local-vibe-cache-design.md
  - docs/standards/v2/shell-capability-design.md
  - docs/standards/git-workflow-standard.md
  - docs/standards/glossary.md
  - lib/task_write.sh
  - lib/task_query.sh
  - lib/task_actions.sh
  - lib/task.sh
  - skills/vibe-save/SKILL.md
  - skills/vibe-continue/SKILL.md
  - .agent/workflows/vibe-start.md
  - STRUCTURE.md
  - tests/test_task_ops.bats
---

# Remove Local .vibe Cache Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除 worktree 本地 `.vibe/` 运行时缓存，让 shell 仅依赖共享真源识别当前 task，同时保留 `~/.vibe/` 的全局语义，并同步修正文档、技能和测试。

**Architecture:** 先用测试固定“绑定 task 后不再生成 `.vibe/*`，查询当前 task 仅依赖共享真源”的目标行为，再删除本地缓存写入和读取分支，最后同步 skills、workflow、结构文档与审计结论，确保运行时、文档和边界叙述收敛成单一模型。

**Tech Stack:** Zsh CLI (`lib/task_write.sh`, `lib/task_query.sh`, `lib/task_actions.sh`, `lib/task.sh`), Markdown (`skills/`, `.agent/workflows/`, `STRUCTURE.md`, `docs/plans/`), Bats (`tests/test_task_ops.bats` 及相关 task/flow 测试)。

---

### Task 1: 固定删除本地缓存后的 shell 契约

**Files:**
- Modify: `tests/test_task_ops.bats`
- Inspect: `lib/task_query.sh`
- Inspect: `lib/task_actions.sh`
- Inspect: `lib/task_write.sh`

**Step 1: 写绑定当前 task 后不生成 `.vibe/current-task.json` 的失败测试**

覆盖：
- 执行 `vibe task update <task-id> --bind-current`
- 共享真源中的绑定关系正常更新
- 当前 worktree 下不存在 `.vibe/current-task.json`

**Step 2: 写当前 task 查询仅依赖共享真源的失败测试**

覆盖：
- 没有本地 `.vibe/`
- 仍能按当前 worktree 路径正确识别 `current_task`

**Step 3: 写无绑定 task 时的回归测试**

覆盖：
- 当前 worktree 未绑定 task
- 查询命令返回空或现有预期行为
- 不因缺少 `.vibe/` 报错

**Step 4: 运行 task 测试确认当前实现失败**

Run: `bats tests/test_task_ops.bats`

Expected:
- 新增的“无 `.vibe/` 仍能工作”用例失败
- 旧的“.vibe 文件存在”断言失败

### Task 2: 删除 `.vibe/*` 写入路径

**Files:**
- Modify: `lib/task_write.sh`
- Modify: `lib/task_actions.sh`

**Step 1: 删除 `_vibe_task_refresh_cache` helper**

要求：
- 移除 `.vibe/current-task.json`
- 移除 `.vibe/focus.md`
- 移除 `.vibe/session.json`
- 不保留空壳 helper

**Step 2: 移除 `--bind-current` 触发本地缓存刷新的调用**

要求：
- `vibe task update --bind-current` 仍更新共享真源
- 不再创建 `.vibe/` 目录

**Step 3: 运行 task 测试验证最小行为仍成立**

Run: `bats tests/test_task_ops.bats`

Expected:
- 与共享真源绑定相关的用例通过
- 不再有 `.vibe/*` 生成

### Task 3: 删除 `.vibe/current-task.json` 读取分支

**Files:**
- Modify: `lib/task_query.sh`
- Inspect: `lib/task.sh`

**Step 1: 移除当前 task 优先读取 `.vibe/current-task.json` 的逻辑**

要求：
- 直接用 `git rev-parse --show-toplevel` 或当前 worktree 路径
- 只从 `.git/vibe/worktrees.json` 解析 `current_task`

**Step 2: 校对 fallback 行为**

要求：
- 当前路径无法匹配 worktree 时，行为与现有错误路径一致或更明确
- 不引入新的隐式本地 fallback 文件

**Step 3: 运行 task 相关回归测试**

Run: `bats tests/test_task_ops.bats`

Expected:
- 当前 task 查询在无 `.vibe/` 条件下通过

### Task 4: 同步 save / continue / start 的语义文本

**Files:**
- Modify: `skills/vibe-save/SKILL.md`
- Modify: `skills/vibe-continue/SKILL.md`
- Modify: `.agent/workflows/vibe-start.md`

**Step 1: 从 `/vibe-save (skill)` 中移除 `.vibe/*` 读取入口**

要求：
- 强调 `task.md` 是 handoff
- 强调共享真源是唯一 task 绑定来源
- 不再提 `.vibe/current-task.json`、`.vibe/focus.md`、`.vibe/session.json`

**Step 2: 从 `/vibe-continue (skill)` 中移除 `.vibe/*` 恢复顺序**

要求：
- 恢复顺序改为共享真源优先，再读 `task.md`
- 不再把 pointer/cache 视作前置真源

**Step 3: 校对 `/vibe-start` 的执行前提**

要求：
- 不引入 `.vibe/*`
- 继续强调计划文件和共享 task 元数据

### Task 5: 修正文档中的双重 `.vibe` 语义

**Files:**
- Modify: `STRUCTURE.md`
- Modify: `docs/tasks/2026-03-10-continue-save-start-audit/findings-2026-03-10.md`
- Modify: `docs/tasks/2026-03-10-continue-save-start-audit/README.md`

**Step 1: 更新结构文档**

要求：
- 明确 `~/.vibe/` 继续保留
- 将 `<worktree>/.vibe/` 标记为历史方案或已淘汰方案
- 当前运行时真源只保留 `.git/vibe/`

**Step 2: 刷新审计结论**

要求：
- 将之前关于 `.vibe/*` 仍为恢复入口的 findings 标记为已收敛或待实现修正
- 保持审计文档与当前设计一致

### Task 6: 清理测试和帮助面中的遗留断言

**Files:**
- Modify: `tests/test_task_ops.bats`
- Search/Modify: task/flow 相关测试与文档中对 `.vibe/*` 的现行断言

**Step 1: 删除“必须存在 `.vibe/current-task.json`”类断言**

要求：
- 改成验证共享真源中的绑定关系
- 若仍需验证当前 task，可通过 shell 查询输出断言

**Step 2: 搜索并清理运行时文档中的现行描述**

重点检查：
- `skills/`
- `.agent/workflows/`
- `docs/standards/`
- 非 archive 的 `docs/tasks/` 与 `docs/plans/`

说明：
- archive 历史文档可保留，但应避免被当作当前真源引用

### Task 7: 汇总验证

**Files to inspect during execution:**
- `lib/task_write.sh`
- `lib/task_query.sh`
- `lib/task_actions.sh`
- `skills/vibe-save/SKILL.md`
- `skills/vibe-continue/SKILL.md`
- `.agent/workflows/vibe-start.md`
- `STRUCTURE.md`
- `tests/test_task_ops.bats`

**Step 1: 跑 task 相关测试**

Run: `bats tests/test_task_ops.bats`

Expected:
- task 绑定与查询相关用例全部通过
- 无 `.vibe/*` 依赖

**Step 2: 跑 shell 语法检查**

Run: `zsh -n lib/task.sh lib/task_write.sh lib/task_query.sh lib/task_actions.sh`

Expected:
- 无语法错误

**Step 3: 抽查帮助与文档一致性**

Run:

```bash
rg -n "\.vibe/current-task\.json|\.vibe/focus\.md|\.vibe/session\.json" skills .agent/workflows STRUCTURE.md docs/tasks docs/plans
```

Expected:
- 非 archive 范围内不再把 `<worktree>/.vibe/` 当作当前运行时真源

## Expected Result

- `<worktree>/.vibe/` 不再是当前系统的运行时缓存层。
- `~/.vibe/` 继续保留全局配置语义，不受本轮影响。
- shell 只通过共享真源识别当前目录承载的 flow 所对应 task。
- `task.md` 保持 handoff 角色，不承担 shell 查询入口。
- save / continue / start / STRUCTURE / 测试的叙述与实现重新一致。