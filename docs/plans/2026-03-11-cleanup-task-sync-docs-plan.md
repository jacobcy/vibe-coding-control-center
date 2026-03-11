---
document_type: plan
title: cleanup task sync docs
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/command-standard.md
  - docs/standards/shell-skill-boundary-audit.md
  - skills/vibe-task/SKILL.md
---

# Goal

清理现行文档和 skill 文案中对已删除 `vibe task sync` 的过时表述，避免继续误导用户把 task 当作 GitHub 导入入口。

# Non-Goals

- 不为历史归档文档做大规模考古清理
- 不新增新的 task 导入命令

# Tech Stack

- Markdown docs
- `rg` 文本审计

# Step Tasks

1. 用 `rg` 圈定当前仍引用 `vibe task sync` 的现行文档和 skill。
2. 先确定哪些是现行真源，哪些只是 archive，不扩大修改范围。
3. 把现行文档中的旧表述统一改成 `vibe roadmap sync` 或 task audit 语义。
4. 用 `rg` 复查当前文档层已无过时入口。

# Files To Modify

- `docs/standards/command-standard.md`
- `docs/standards/shell-skill-boundary-audit.md`
- `skills/vibe-task/SKILL.md`

# Test Command

```bash
rg -n "vibe task sync|task sync" docs skills .agent -g '!docs/archive/**'
```

# Expected Result

- 现行文档不再把 `vibe task sync` 当现存能力
- task / roadmap 边界文案一致

# Change Summary

- Modified: 2-4 files
- Approximate lines: 10-35
