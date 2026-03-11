---
document_type: plan
title: sync semantics docs
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/standards/command-standard.md
  - docs/standards/glossary.md
  - skills/vibe-task/SKILL.md
  - skills/vibe-roadmap/SKILL.md
---

# Goal

同步语义文档澄清，明确 `roadmap sync`、`task audit`、OpenSpec 注册三条路径的边界，避免“同步”一词继续混装多层职责。

# Non-Goals

- 不修改 shell 命令行为
- 不新增新的同步命令

# Tech Stack

- Markdown docs
- Skill docs

# Step Tasks

1. 审计当前标准文档和 skill 中“sync”语义的冲突点。
2. 先确定真源文档，以标准文件为主、skill 只做引用和收口。
3. 修改现行文档，分别说明：
   - `roadmap sync` = 规划层镜像同步
   - `task audit` = execution record 审计 / 修复
   - OpenSpec 注册 = execution spec 来源桥接
4. 用 `rg` 做轻量 smoke check。

# Files To Modify

- `docs/standards/command-standard.md`
- `docs/standards/glossary.md`
- `skills/vibe-task/SKILL.md`
- `skills/vibe-roadmap/SKILL.md`

# Test Command

```bash
rg -n "roadmap sync|task audit|OpenSpec|execution spec" docs skills
```

# Expected Result

- 三类“同步/审计/注册”入口边界清楚
- skill 与 standards 不再混说一套

# Change Summary

- Modified: 3-4 files
- Approximate lines: 15-45
