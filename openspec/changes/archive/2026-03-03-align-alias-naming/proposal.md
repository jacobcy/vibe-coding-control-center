## Why

当前 `config/aliases/` 下的命令命名风格不统一：Claude 系命令混用下划线（`c_safe`、`cc_cn`）与连写（`ccy`、`cwt`），前缀也不一致（`cc*` / `c_*` / `cwt`），OpenCode 同理（`oo*` vs `owt`）。这种不一致增加了记忆负担，与其他前缀族（`vt*`、`wt*`、`os*`）的命名规律形成割裂。

## What Changes

- **BREAKING** 重命名 `c_safe` → `ccs`（Claude Safe，统一 `cc*` 前缀，去掉下划线）
- **BREAKING** 重命名 `cwt` → `ccwt`（Claude in Worktree，统一 `cc*` 前缀）
- **BREAKING** 重命名 `cc_cn` → `cccn`（Claude China endpoint，去掉下划线）
- **BREAKING** 重命名 `cc_off` → `ccoff`（Claude Official endpoint，去掉下划线）
- **BREAKING** 重命名 `cc_endpoint` → `ccep`（Claude Endpoint show，缩短 + 去掉下划线）
- **BREAKING** 重命名 `owt` → `oowt`（OpenCode in Worktree，统一 `oo*` 前缀）
- 为每个旧命令保留 deprecated alias，执行时输出迁移提示（渐进式迁移）
- 更新 `docs/references/alias-helper.md` 中的命令名称（已部分完成）
- 更新 `config/aliases/vibe.sh` 中对 `vibe alias` 的输出描述

## Capabilities

### New Capabilities

- `alias-naming-convention`：定义完整的 alias 命名约定规则（前缀族 + 动作后缀 + 分隔符规范），作为后续 alias 扩展的标准参考
- `alias-deprecation-shim`：在旧名 alias 上添加 deprecation shim 函数（执行旧命令 → 打印警告 → 调用新命令），支持渐进式迁移

### Modified Capabilities

（无 — 现有 specs 不涉及 alias 命名层）

## Impact

- **直接修改文件**：
  - `config/aliases/claude.sh`（重命名 5 个 alias/函数 + 添加 deprecation shims）
  - `config/aliases/opencode.sh`（重命名 `owt` → `oowt` + 添加 deprecation shim）
  - `docs/references/alias-helper.md`（更新命令名称表格）
- **间接影响**：
  - 所有在 zshrc / dotfiles 中手写了旧命令的用户需要迁移（shim 提供缓冲期）
  - `vibe alias` 输出内容会同步更新（显示新名 + deprecated 标注）
- **不影响**：`vt*`、`wt*`、`os*`、`oo`、`ooa`、`ccy`、`ccp` 命名不变
