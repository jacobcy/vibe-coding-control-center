---
document_type: artifact
title: GitHub Project Bootstrap Artifacts
status: active
author: Codex GPT-5
created: 2026-03-10
last_updated: 2026-03-10
related_docs:
  - docs/plans/2026-03-10-github-project-bootstrap-sync-cutover-plan.md
---

# GitHub Project Bootstrap Artifacts

## Contents

- `report-*.json`: 每次 dry-run/apply 的审计与 proposal 输出
- `writeback-*.json`: apply 后待写回 GitHub Project custom fields 的扩展字段提案
- `snapshots/<timestamp>/`: apply 前保存的本地 `roadmap.json` 与 `registry.json`

## Restore

```bash
cp artifacts/github-project-bootstrap/snapshots/<timestamp>/roadmap.json .git/vibe/roadmap.json
cp artifacts/github-project-bootstrap/snapshots/<timestamp>/registry.json .git/vibe/registry.json
```

## Rerun Order

```bash
zsh scripts/github_project_field_map.sh --check
zsh scripts/github_project_bootstrap_sync.sh --dry-run
zsh scripts/github_project_bootstrap_sync.sh --apply
vibe check bootstrap --json
```
