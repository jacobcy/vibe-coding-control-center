---
document_type: plan
title: workflow filename namespace rename
status: completed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/agent-workflow-standard.md
  - .agent/README.md
  - scripts/init.sh
  - tests/skills/test_skills.bats
---

# Goal

将 `.agent/workflows/` 下的 `vibe-*.md` 文件名统一重命名为 `vibe:*.md`，使文件名与 workflow frontmatter 命名空间一致。

# Non-Goals

- 不重命名 `opsx-*` workflow
- 不修改 skill 文件名
- 不批量修复历史 archive / plan 文档中的旧路径引用

# Files To Modify

- `.agent/README.md`
- `scripts/init.sh`
- `tests/skills/test_skills.bats`
- `.agent/workflows/vibe-new-feature.md`（仅修内部链接）
- `.agent/workflows/` 下全部 `vibe-*.md` 文件名

# Test Commands

```bash
find .agent/workflows -maxdepth 1 -type f | sort
rg -n 'workflows/vibe:|\\.agent/workflows/vibe:' .agent/README.md scripts/init.sh tests/skills/test_skills.bats .agent/workflows
rg -n 'workflows/vibe-|\\.agent/workflows/vibe-' .agent/README.md scripts/init.sh tests/skills/test_skills.bats .agent/workflows
git status --short -- .agent/README.md scripts/init.sh tests/skills/test_skills.bats .agent/workflows docs/plans/2026-03-11-workflow-filename-namespace-rename.md
```

# Expected Result

- `.agent/workflows/` 中所有 `vibe-*` 文件都改为 `vibe:*`
- 运行时引用面同步到新路径
- 历史文档暂不作为本轮阻塞项
