---
name: "vibe:start"
description: (LEGACY) Legacy execution-entry workflow. Use vibe:continue instead.
category: Workflow
tags: [workflow, vibe, execution, legacy]
---

# vibe:start (LEGACY)

**Status**: DEPRECATED.

**Replacement**: 请改用 `/vibe-continue`。

## 定位

- `vibe:start` 是旧版 workflow 层执行入口，现已由 `vibe:continue` 替代。
- 它不再承担正式执行分发逻辑。

## Steps

1. 提示用户：`该入口已废弃。请使用 /vibe-continue 恢复执行或加载上下文。`
2. 委托 `vibe:continue` workflow 或直接建议用户调用 `/vibe-continue`。

## Boundary

- 本文件仅保留作兼容性参考。
- 正式逻辑请查阅 `.agent/workflows/vibe:continue.md`。
