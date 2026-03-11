---
document_type: plan
title: workflow namespace tail cleanup
status: completed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/agent-workflow-standard.md
  - .agent/workflows/vibe-continue.md
  - .agent/workflows/vibe-done.md
  - .agent/workflows/vibe-issue.md
  - .agent/workflows/vibe-save.md
  - .agent/workflows/vibe-new-flow.md
  - .agent/workflows/vibe-skills.md
---

# Goal

清理剩余 workflow 的命名空间和分类说明，使其符合 `agent workflow` 标准：

- 统一剩余 workflow 的 frontmatter `name` 到 `vibe:*`
- 为每个 workflow 明确标注：
  - `skill-backed workflow`
  - `alias workflow`
  - `standalone orchestration workflow`

# Non-Goals

- 不修改对应 skill 文件
- 不新增 shell 能力
- 不重写这些 workflow 的完整业务逻辑

# Files To Modify

- `.agent/workflows/vibe-continue.md`
- `.agent/workflows/vibe-done.md`
- `.agent/workflows/vibe-issue.md`
- `.agent/workflows/vibe-save.md`
- `.agent/workflows/vibe-new-flow.md`
- `.agent/workflows/vibe-skills.md`

# Test Commands

```bash
rg -n '^name: ' .agent/workflows/vibe-continue.md \
  .agent/workflows/vibe-done.md \
  .agent/workflows/vibe-issue.md \
  .agent/workflows/vibe-save.md \
  .agent/workflows/vibe-new-flow.md \
  .agent/workflows/vibe-skills.md

rg -n 'skill-backed workflow|alias workflow|standalone orchestration workflow' \
  .agent/workflows/vibe-continue.md \
  .agent/workflows/vibe-done.md \
  .agent/workflows/vibe-issue.md \
  .agent/workflows/vibe-save.md \
  .agent/workflows/vibe-new-flow.md \
  .agent/workflows/vibe-skills.md

git status --short -- \
  docs/plans/2026-03-11-workflow-namespace-tail-cleanup.md \
  .agent/workflows/vibe-continue.md \
  .agent/workflows/vibe-done.md \
  .agent/workflows/vibe-issue.md \
  .agent/workflows/vibe-save.md \
  .agent/workflows/vibe-new-flow.md \
  .agent/workflows/vibe-skills.md
```

# Expected Result

- 剩余核心 `vibe-*` workflow 命名空间统一
- 每个入口都能按 `agent-workflow-standard` 被明确归类
