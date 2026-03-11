---
document_type: plan
title: workflow skill phase1 execution
status: completed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/plans/2026-03-11-workflow-skill-refactor-plan.md
  - docs/plans/2026-03-11-workflow-skill-boundary-audit.md
  - .agent/workflows/vibe-new.md
  - .agent/workflows/vibe-start.md
  - .agent/workflows/vibe-commit.md
  - .agent/README.md
  - skills/vibe-new/SKILL.md
  - skills/vibe-start/SKILL.md
---

# Goal

完成 workflow/skill 分层重构的 Phase 1：

- 为 `vibe-new`、`vibe-start` 补齐独立 skill
- 将 `vibe-new`、`vibe-start`、`vibe-commit` workflow 压薄为“入口 + 委托 + 停点”
- 在 `.agent/README.md` 中明确 `workflow = vibe:*`、`skill = vibe-*`

# Non-Goals

- 不修改 shell 命令能力
- 不修改 task / roadmap / flow 对象模型
- 不统一重写全部 workflow
- 不处理 PR、commit 或运行时 registry 修复

# Tech Stack

- Markdown workflow files in `.agent/workflows/`
- Markdown skill files in `skills/*/SKILL.md`
- Project standards in `docs/standards/`

# Step Tasks

1. 新建 `skills/vibe-new/SKILL.md`
   - 承载 intake 来源判断、plan/task 绑定、flow 使用纪律、handoff 输出

2. 新建 `skills/vibe-start/SKILL.md`
   - 承载当前 flow task 选择、`auto` 顺序、spec 缺失回退、blocker / handoff 处理

3. 压薄 `.agent/workflows/vibe-new.md`
   - 仅保留规划入口、委托 `vibe-new`、完成后停在 `/vibe-start`

4. 压薄 `.agent/workflows/vibe-start.md`
   - 仅保留执行入口、委托 `vibe-start`、缺 spec / 缺 task 时回退到上游 workflow

5. 压薄 `.agent/workflows/vibe-commit.md`
   - 保留提交入口与委托，不重复 `skills/vibe-commit/SKILL.md` 逻辑

6. 更新 `.agent/README.md`
   - 明确 workflow/skill 边界
   - 明确命名空间
   - 去掉过时入口引用

# Files To Modify

- `.agent/workflows/vibe-new.md`
- `.agent/workflows/vibe-start.md`
- `.agent/workflows/vibe-commit.md`
- `.agent/README.md`
- `skills/vibe-new/SKILL.md`
- `skills/vibe-start/SKILL.md`

# Test Commands

```bash
sed -n '1,40p' .agent/workflows/vibe-new.md
sed -n '1,40p' .agent/workflows/vibe-start.md
sed -n '1,40p' .agent/workflows/vibe-commit.md
find skills -maxdepth 2 -name 'SKILL.md' | sort
rg -n 'vibe:new|vibe:start|vibe:commit|workflow 只编排|workflow 不承载|skill 层真源' \
  .agent/workflows/vibe-new.md \
  .agent/workflows/vibe-start.md \
  .agent/workflows/vibe-commit.md \
  .agent/README.md
git status --short -- \
  .agent/workflows/vibe-new.md \
  .agent/workflows/vibe-start.md \
  .agent/workflows/vibe-commit.md \
  .agent/README.md \
  skills/vibe-new/SKILL.md \
  skills/vibe-start/SKILL.md
```

# Expected Result

- `vibe-new` 和 `vibe-start` 有独立 skill 真源
- `vibe-new` / `vibe-start` / `vibe-commit` workflow 不再承载复杂业务逻辑
- `.agent/README.md` 能明确区分 workflow 与 skill 的职责及命名空间
- 变更范围仅限文档和 skill 文件

# Change Summary

- Added: 2 new skill files, 1 execution plan
- Modified: 4 existing workflow/readme files
- Approximate delta:
  - workflow files net reduced by about 180 lines
  - skill files added about 210 lines
  - README updated by about 50 lines
