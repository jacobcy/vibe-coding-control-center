---
document_type: plan
title: workflow vibe new feature thinning
status: completed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/agent-workflow-standard.md
  - .agent/workflows/vibe-new-feature.md
  - .agent/workflows/vibe-new.md
---

# Goal

将 `vibe-new-feature` 收敛为符合 `agent workflow` 标准的薄入口：

- 明确它是面向 `repo issue / roadmap item` 选择的规划入口
- 不再承载独立业务规则
- 不再残留 `wtnew / vnew` 物理 worktree 语义
- 将实际规划逻辑统一导向 `vibe:new`

# Non-Goals

- 不修改 `vibe-new` skill
- 不修改 shell 命令能力
- 不处理其他 workflow

# Files To Modify

- `.agent/workflows/vibe-new-feature.md`

# Test Commands

```bash
sed -n '1,120p' .agent/workflows/vibe-new-feature.md
rg -n 'wtnew|vnew|Shared Task Binding Rules|Exception Escalation Hook|name: \"vibe:new-feature\"|alias workflow|委托 `vibe:new`' \
  .agent/workflows/vibe-new-feature.md
git status --short -- \
  docs/plans/2026-03-11-workflow-vibe-new-feature-thinning.md \
  .agent/workflows/vibe-new-feature.md
```

# Expected Result

- `vibe-new-feature` 变成薄 workflow
- 文案明确它是 `vibe:new` 的 feature-oriented alias / orchestration 入口
- 不再出现 `wtnew / vnew`
