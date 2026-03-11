---
document_type: plan
title: roadmap projects sync
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - lib/roadmap.sh
  - lib/roadmap_write.sh
  - lib/roadmap_help.sh
  - docs/references/github_project.md
---

# Goal

为 `vibe roadmap sync` 落地 GitHub Projects item 同步能力，使 roadmap 层真正以 Project item mirror 为主语义。

# Non-Goals

- 不把 repo issue 直接偷换成本地 task
- 不在本轮重做整个 roadmap schema

# Tech Stack

- Zsh shell CLI
- GitHub CLI / API
- Bats contracts

# Step Tasks

1. 审计当前 `roadmap sync` 实现与 help，确认仍停留在 issue-first 兼容导入的缺口。
2. 先补 contract / shell 测试，固定 Projects-first 的输入输出行为。
3. 最小修改 roadmap sync 实现，接入 GitHub Projects item 同步。
4. 回归 roadmap contract 与 shared-state contract。

# Files To Modify

- `lib/roadmap.sh`
- `lib/roadmap_write.sh`
- `lib/roadmap_help.sh`
- `tests/contracts/test_roadmap_contract.bats`
- `tests/contracts/test_shared_state_contracts.bats`

# Test Command

```bash
bats tests/contracts/test_roadmap_contract.bats
bats tests/contracts/test_shared_state_contracts.bats
```

# Expected Result

- `vibe roadmap sync` 具备 GitHub Projects item mirror 同步能力
- help、contracts、shared state 输出语义一致

# Change Summary

- Modified: 4-5 files
- Approximate lines: 25-80
