---
document_type: plan
title: roadmap sync auto check
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - lib/roadmap_query.sh
  - lib/roadmap_help.sh
  - tests/roadmap/test_roadmap_status_render.bats
---

# Goal

让 `vibe roadmap status` 在启动时主动检查 GitHub Projects 同步前置条件，并给出明确提示，而不是要求用户自己猜是否需要先 `roadmap sync`。

# Non-Goals

- 不在本轮实现完整 GitHub Projects 双向同步
- 不改 roadmap item 数据模型

# Tech Stack

- Zsh shell CLI
- Bats

# Step Tasks

1. 审计 `vibe roadmap status` 当前输出，找出能承载“需同步提醒”的位置。
2. 先补文本或 JSON 级测试，固定“检测到未同步时有提示”的行为。
3. 最小修改 `lib/roadmap_query.sh` / help 文案，增加自动检查与提示输出。
4. 运行 roadmap 相关测试回归。

# Files To Modify

- `lib/roadmap_query.sh`
- `lib/roadmap_help.sh`
- `tests/roadmap/test_roadmap_status_render.bats`

# Test Command

```bash
bats tests/roadmap/test_roadmap_status_render.bats
```

# Expected Result

- `vibe roadmap status` 能主动暴露“建议先 sync”的状态
- 用户无需先读文档才能知道下一步

# Change Summary

- Modified: 2-3 files
- Approximate lines: 15-45
