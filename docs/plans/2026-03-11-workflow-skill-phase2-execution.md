---
document_type: plan
title: workflow skill phase2 execution
status: completed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/plans/2026-03-11-workflow-skill-refactor-plan.md
  - .agent/workflows/vibe-check.md
  - .agent/workflows/vibe-task.md
  - skills/vibe-check/SKILL.md
  - skills/vibe-task/SKILL.md
---

# Goal

完成 workflow/skill 分层重构的 Phase 2 周边入口清理：

- 将 `vibe-check` workflow 进一步压薄，只保留入口、委托、停点
- 将 `vibe-task` workflow 统一到 `vibe:*` 命名空间和同一薄模板

# Non-Goals

- 不修改 `skills/vibe-check/SKILL.md`
- 不修改 `skills/vibe-task/SKILL.md`
- 不扩展 shell 审计或修复能力
- 不处理其他 workflow

# Tech Stack

- Markdown workflow files in `.agent/workflows/`
- Markdown skill files in `skills/*/SKILL.md`

# Step Tasks

1. 压薄 `.agent/workflows/vibe-check.md`
   - 只保留 runtime 审计入口、委托 `vibe-check`、结果交付和边界

2. 压薄 `.agent/workflows/vibe-task.md`
   - 统一成 `vibe:task`
   - 只保留 task 总览 / registry 审计入口、委托 `vibe-task`、结果交付和边界

3. 验证 workflow/skill 关系
   - workflow 是否只保留入口与委托
   - skill 是否仍承载对象边界、shell 顺序和修复逻辑

# Files To Modify

- `.agent/workflows/vibe-check.md`
- `.agent/workflows/vibe-task.md`

# Test Commands

```bash
sed -n '1,80p' .agent/workflows/vibe-check.md
sed -n '1,80p' .agent/workflows/vibe-task.md
rg -n 'name: \"vibe:check\"|name: \"vibe:task\"|委托 `vibe-check`|委托 `vibe-task`|workflow 不承载' \
  .agent/workflows/vibe-check.md \
  .agent/workflows/vibe-task.md
git status --short -- \
  docs/plans/2026-03-11-workflow-skill-phase2-execution.md \
  .agent/workflows/vibe-check.md \
  .agent/workflows/vibe-task.md
```

# Expected Result

- `vibe-check` 与 `vibe-task` workflow 都统一到薄入口模板
- 命名空间收敛为 `vibe:check` 与 `vibe:task`
- 具体业务逻辑仍全部保留在 skill 文件中

# Change Summary

- Added: 1 execution plan
- Modified: 2 workflow files
- Approximate delta:
  - workflow files net reduced by about 20-40 lines
