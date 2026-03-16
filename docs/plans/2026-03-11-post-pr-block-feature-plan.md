---
document_type: plan
title: post pr block feature
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/v2/git-workflow-standard.md
  - .agent/workflows/vibe-commit.md
  - skills/vibe-commit/SKILL.md
  - skills/vibe-integrate/SKILL.md
---

# Goal

当当前 flow 已进入 `open + had_pr` 阶段时，阻止其继续承载新的功能开发，并把用户引导到 follow-up / integrate / 新 flow 的正确路径。

# Non-Goals

- 不在本轮实现 had_pr flow 的完整 block/resume shell 能力
- 不改 PR 审查本身的 GitHub 事实

# Tech Stack

- Workflow docs
- Skill docs
- 轻量技能测试

# Step Tasks

1. 审计 `git-workflow-standard` 与 `vibe-commit` / `vibe-integrate` 的当前文案，找出 had_pr 后仍可继续开发的缺口。
2. 先补 skill / workflow 级 smoke 断言，固定“PR 已提交后不得继续新功能开发”的提示。
3. 修改 workflow 和 skill，把用户路由到：
   - follow-up on current PR
   - integrate current PR
   - create a new flow for the next target
4. 运行相关 skills 测试或文本检查。

# Files To Modify

- `.agent/workflows/vibe-commit.md`
- `skills/vibe-commit/SKILL.md`
- `skills/vibe-integrate/SKILL.md`
- `tests/skills/test_skills.bats`

# Test Command

```bash
bats tests/skills/test_skills.bats
```

# Expected Result

- 已发 PR 的 flow 不再被文案允许继续承载“下一个新目标”
- skill 路由建议与标准一致

# Change Summary

- Modified: 3-4 files
- Approximate lines: 15-40
