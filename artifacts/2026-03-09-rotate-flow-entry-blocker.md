# Rotate Flow Entry Blocker

date: 2026-03-09
scope: flow-entry
status: resolved

## Goal

按用户要求使用 `scripts/rotate.sh`，把未提交的计划文件一并带入新的审计 flow。

## Reproduction

Current state before running:

- branch: `codex/skill-flow-audit-bootstrap`
- dirty file: `docs/plans/2026-03-09-skill-flow-audit-and-alignment-plan.md`

Command:

```bash
zsh scripts/rotate.sh task/skill-flow-audit-alignment
```

Observed result:

```text
scripts/rotate.sh:56: command not found: _flow_switch
```

## Root Cause

- `scripts/rotate.sh` 只 `source "$VIBE_LIB/flow.sh"`。
- `_flow_switch` 定义在 `lib/flow_runtime.sh`。
- 当时脚本入口没有成功拿到该函数定义，导致 rotate 路径不可执行。

## Impact

- 当时无法按用户指定的 rotate 路径把未提交计划文件一起带入新的 flow。
- 该阻塞已被新的正式 shell 入口替代。

## Resolution

- 正式入口已收敛为：`vibe flow new <name> --branch <ref> --save-unstash`
- `scripts/rotate.sh` 仅保留兼容包装角色，不再作为推荐主路径
